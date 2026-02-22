"""
Web-Based ANPR Detection Engine
Runs detection in background and streams video to browser
"""

import cv2
import threading
import time
import logging
import numpy as np
from datetime import datetime
from camera_handler import CameraHandler
from plate_utils import save_plate_to_csv, normalize_plate, is_valid_plate

# CRITIAL: Disable experimental Paddle features globally BEFORE any import
import os
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_mkldnn"] = "0"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"

# Shim for langchain.docstore if missing (PaddleOCR 3.x dependency)
import sys
import types

# MOCK Langchain components to avoid heavy/broken imports
print("[DEBUG] Shim: Mocking langchain components...")

# 1. Mock langchain package
if 'langchain' not in sys.modules:
    sys.modules['langchain'] = types.ModuleType('langchain')

# 2. Mock langchain.docstore.document.Document
if 'langchain.docstore' not in sys.modules:
    docstore = types.ModuleType('langchain.docstore')
    sys.modules['langchain.docstore'] = docstore
    
    # Mock Document class
    class Document:
        def __init__(self, page_content, metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}
    
    # PaddleOCR usually looks for langchain.docstore.document.Document
    document_mod = types.ModuleType('langchain.docstore.document')
    document_mod.Document = Document
    sys.modules['langchain.docstore.document'] = document_mod
    docstore.document = document_mod
    print("[DEBUG] Shim: Mocked langchain.docstore.document.Document")

# 3. Mock langchain.text_splitter
if 'langchain.text_splitter' not in sys.modules:
    text_splitter_mod = types.ModuleType('langchain.text_splitter')
    sys.modules['langchain.text_splitter'] = text_splitter_mod
    
    class TextSplitter:
        def __init__(self, *args, **kwargs): pass
        def split_text(self, text): return [text]
        
    class CharacterTextSplitter(TextSplitter): pass
    class RecursiveCharacterTextSplitter(TextSplitter): pass
    
    text_splitter_mod.TextSplitter = TextSplitter
    text_splitter_mod.CharacterTextSplitter = CharacterTextSplitter
    text_splitter_mod.RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter
    
    print("[DEBUG] Shim: Mocked langchain.text_splitter")

logger = logging.getLogger(__name__)


class WebANPREngine:
    """
    Web-based ANPR engine that runs in background
    and provides video streaming capability
    """
    
    def __init__(self):
        self.camera = None
        self.running = False
        self.detection_thread = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.stats = {
            'fps': 0,
            'detections': 0,
            'last_plate': None
        }
        
        # Try to import detection models
        self.use_yolo = False
        self.use_ocr = False
        self.yolo_model = None
        self.ocr_reader = None
        self.resources_initialized = False
        self.resources_initialized = False
    
    def start(self):
        """Start the detection engine immediately (initialization happens in thread)"""
        if self.running:
            logger.warning("Engine already running")
            return True # Consider it started
        
        logger.info("Request to start Web ANPR Engine received...")
        
        # Reset stats
        self.stats['detections'] = 0
        self.stats['fps'] = 0
        
        # Start detection thread immediately
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        logger.info("✓ Detection thread launched")
        return True
    
    def _initialize_resources(self):
        """Called inside the thread to initialize camera and models"""
        if self.resources_initialized:
            return True
            
        # 1. Initialize camera
        try:
            if self.camera is None:
                logger.info("Initializing camera in background...")
                self.camera = CameraHandler(preferred_index=0)
                logger.info("✓ Camera initialized")
        except Exception as e:
            logger.warning(f"Camera init failed: {e}. Using demo mode.")
            self.camera = None

        # 2. YOLO check and load
        if not self.use_yolo:
            logger.info("Loading YOLO in background...")
            try:
                try:
                    from ultralytics import YOLO
                except ModuleNotFoundError:
                    # Retry import
                    import importlib
                    ultralytics = importlib.import_module("ultralytics")
                    YOLO = ultralytics.YOLO
                    
                import os
                
                # Priority order: Custom trained > YOLOv11n > YOLOv8n
                model_paths = [
                    'models/anpr_custom_best.pt',
                    'yolo11n.pt',
                    'yolov8n.pt'
                ]
                
                model_loaded = False
                for model_path in model_paths:
                    if os.path.exists(model_path):
                        try:
                            self.yolo_model = YOLO(model_path)
                            self.use_yolo = True
                            logger.info(f"✓ YOLO model loaded: {model_path}")
                            model_loaded = True
                            break
                        except Exception as e:
                            logger.warning(f"Failed to load {model_path}: {e}")
                
                if not model_loaded:
                    # Fallback to downloading YOLOv11n
                    logger.info("Downloading default YOLOv11-Nano model...")
                    self.yolo_model = YOLO('yolo11n.pt')
                    self.use_yolo = True
                    logger.info("✓ YOLOv11-Nano loaded")
                    
            except Exception as e:
                logger.error(f"Failed to load YOLO: {e}")
                
        # 3. PaddleOCR Load
        if not self.use_ocr:
            logger.info("Loading PaddleOCR in background...")
            
            try:
                from paddleocr import PaddleOCR
                
                # Use robust settings (det=True is safer for imperfect crops)
                # But keep MKL-DNN disabled to prevent crashes
                self.ocr_reader = PaddleOCR(
                    use_angle_cls=False,
                    lang='en',
                    use_gpu=False,
                    show_log=False,
                    enable_mkldnn=False,
                    ocr_version='PP-OCRv4'
                )
                
                self.use_ocr = True
                logger.info("✓ PaddleOCR loaded (Robust Mode)")
            except Exception as e:
                logger.warning(f"PaddleOCR init failed: {e}")
                
                # Fallback purely for recognition if detection model fails
                try:
                    self.ocr_reader = PaddleOCR(use_angle_cls=False, lang='en', enable_mkldnn=False, det=False)
                    self.use_ocr = True
                    logger.info("✓ PaddleOCR loaded (Rec Only Fallback)")
                except:
                    pass
                logger.info("✓ PaddleOCR loaded (MKLDNN Disabled)")
            except Exception as e:
                logger.warning(f"PaddleOCR not available: {e}")
        
        self.resources_initialized = True
        return True
    
    def stop(self):
        """Stop the detection engine"""
        if not self.running:
            return False
        
        logger.info("Stopping Web ANPR Engine...")
        self.running = False
        
        if self.detection_thread:
            self.detection_thread.join(timeout=2)
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        logger.info("✓ Web ANPR Engine stopped")
        return True
    
    def _detection_loop(self):
        """Main detection loop"""
        # Initialize resources first
        self._initialize_resources()
        
        frame_count = 0
        start_time = time.time()
        last_detection_time = 0
        detection_cooldown = 0.5  # seconds between detections (reduced for better responsiveness)
        
        while self.running:
            try:
                # Read frame
                if self.camera:
                    ret, frame = self.camera.read()
                else:
                    # Retry camera initialization occasionally
                    if frame_count % 100 == 0:
                        try:
                            self.camera = CameraHandler(preferred_index=0)
                        except: pass
                        
                    # Virtual demo/placeholder feed
                    ret = True
                    # Create a simple pulsing/animated placeholder so it doesn't look static
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    pulse = int(127 + 127 * np.sin(time.time() * 2))
                    frame[:] = (pulse // 4, pulse // 4, pulse // 4)
                    cv2.putText(frame, "Initializing Camera...", (180, 240), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                    time.sleep(0.03) # Limit demo FPS
                
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue
                
                frame_count += 1
                
                # Calculate FPS every 10 frames for faster updates
                if frame_count % 10 == 0:
                    elapsed = time.time() - start_time
                    self.stats['fps'] = 10 / elapsed if elapsed > 0 else 0
                    start_time = time.time()
                
                # Run detection (force detection if resources ready)
                current_time = time.time()
                
                if (current_time - last_detection_time > detection_cooldown):
                    
                    # Run on a copy to avoid threading issues with display
                    detect_frame = frame.copy()
                    
                    # Try detection if YOLO is loaded
                    if self.use_yolo:
                        detected_plate = self._detect_plate(detect_frame)
                        
                        if detected_plate:
                            self.stats['detections'] += 1
                            self.stats['last_plate'] = detected_plate
                            last_detection_time = current_time
                # Draw last known detection if recent (< 2s ago)
                if self.stats['last_plate'] and (current_time - last_detection_time < 2.0):
                     frame = self._draw_detection(frame, self.stats['last_plate'])
                
                # Add overlay
                frame = self._add_overlay(frame)
                
                # Store latest frame
                with self.frame_lock:
                    self.latest_frame = frame.copy()
                
                # Minimal sleep to prevent 100% CPU usage but keep high FPS
                time.sleep(0.001)
                
            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(0.1)
    
    def _detect_plate(self, frame):
        """Detect and recognize license plate"""
        try:
            # Resize for faster processing
            small_frame = cv2.resize(frame, (640, 480))
            
            # Run YOLO detection
            results = self.yolo_model(small_frame, verbose=False)
            boxes = results[0].boxes.xyxy.cpu().numpy()
            
            if len(boxes) == 0:
                return None
            
            # Get first detection
            box = boxes[0]
            x1, y1, x2, y2 = map(int, box)
            
            # Scale back to original frame
            scale_x = frame.shape[1] / 640
            scale_y = frame.shape[0] / 480
            
            x1 = int(x1 * scale_x)
            y1 = int(y1 * scale_y)
            x2 = int(x2 * scale_x)
            y2 = int(y2 * scale_y)
            
            # Crop plate
            plate_img = frame[y1:y2, x1:x2]
            
            if plate_img.size == 0:
                return None
            
            # --- OCR Preprocessing ---
            # PaddleOCR handles preprocessing internally, but resizing helps small plates
            h, w = plate_img.shape[:2]
            if h < 32: # Minimum height recommendation
                scale = 32 / h
                plate_img = cv2.resize(plate_img, (int(w * scale), 32), interpolation=cv2.INTER_CUBIC)
            
            # Use the original color image for OCR, not grayscale
            ocr_img = plate_img
            
            # --- Robust OCR Handling ---
            text = "Plate"
            confidence = 0.5
            
            if self.use_ocr:
                try:
                    # 1. Try standard OCR (Rec+Det or just Rec depending on init)
                    try:
                        ocr_results = self.ocr_reader.ocr(ocr_img, cls=False)
                    except:
                        # Retry with list input if single image fails
                        ocr_results = self.ocr_reader.ocr([ocr_img], cls=False)
                    
                    # 2. Parse results
                    detected_text = None
                    detected_conf = 0.0
                    
                    if ocr_results and isinstance(ocr_results, list):
                        # Handle different return formats
                        res = ocr_results[0]
                        if res:
                            # Format A: [[[[box], [text, score]...]]] (Standard)
                            if isinstance(res, list) and len(res) > 0 and isinstance(res[0], (list, tuple)) and len(res[0]) == 2 and isinstance(res[0][1], (list, tuple)):
                                # Find best confidence
                                best = max(res, key=lambda x: x[1][1])
                                detected_text = best[1][0]
                                detected_conf = best[1][1]
                                
                            # Format B: [('text', 0.9)] (Rec Only)
                            elif isinstance(res, (list, tuple)) and len(res) == 2 and isinstance(res[0], str):
                                detected_text = res[0]
                                detected_conf = res[1]
                                
                            # Format C: [[('text', 0.9)]] (Rec Only list)
                            elif isinstance(res, list) and len(res) > 0 and isinstance(res[0], (list, tuple)) and isinstance(res[0][0], str):
                                detected_text = res[0][0]
                                detected_conf = res[0][1]

                    if detected_text:
                        text = detected_text
                        confidence = detected_conf
                    else:
                        logger.debug("OCR returned empty result")

                    logger.debug(f"OCR Raw: {text} ({confidence:.2f})")
                except Exception as e:
                    logger.warning(f"OCR parse failed: {e}")
            else:
                # If use_ocr is False, try to re-init it ONCE (lazy retry)
                try:
                    logger.info("Retrying PaddleOCR init...")
                    from paddleocr import PaddleOCR
                    self.ocr_reader = PaddleOCR(use_angle_cls=False, lang='en', enable_mkldnn=False)
                    self.use_ocr = True
                except:
                   text = "No OCR"
            
            # Return raw result if OCR disabled or failed
            if text == "Plate" or text == "No OCR":
                 # Save unrecognized plate for manual review
                 save_plate_to_csv(text.upper(), confidence, threshold=0.1, plate_img=plate_img)
                 
                 return {
                     'text': text,
                     'confidence': confidence,
                     'bbox': (x1, y1, x2, y2)
                 }
            
            # Normalize and validate (only if we have text)
            
            # Normalize and validate
            normalized = normalize_plate(text)
            
            # Save to CSV/DB if it's reasonably confident or at least better than generic "Plate"
            if (is_valid_plate(normalized) and confidence > 0.45) or (text != "Plate" and confidence > 0.5):
                save_plate_to_csv(normalized, confidence, plate_img=plate_img)
            
            return {
                'text': normalized,
                'confidence': confidence,
                'bbox': (x1, y1, x2, y2)
            }
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            # Fallback return for error during processing but after detection
            try:
                if 'x1' in locals():
                    return {'text': 'ERROR', 'confidence': 0, 'bbox': (x1, y1, x2, y2)}
            except: pass
        
        return None
    
    def _draw_detection(self, frame, detection):
        """Draw detection on frame"""
        if not detection:
            return frame
        
        x1, y1, x2, y2 = detection['bbox']
        text = detection['text']
        conf = detection['confidence']
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
        
        # Draw label background
        label = f"{text} ({conf:.2f})"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2
        
        (label_w, label_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        cv2.rectangle(frame, (x1, y1 - label_h - 10), (x1 + label_w, y1), (0, 255, 0), -1)
        
        # Draw text
        cv2.putText(frame, label, (x1, y1 - 5), font, font_scale, (0, 0, 0), thickness)
        
        return frame
    
    def _add_overlay(self, frame):
        """Add information overlay to frame"""
        overlay = frame.copy()
        
        # Semi-transparent background
        cv2.rectangle(overlay, (10, 10), (350, 100), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
        
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Title
        cv2.putText(frame, "ANPR - LIVE CAMERA", (20, 35), font, 0.6, (0, 255, 255), 2)
        
        # FPS
        cv2.putText(frame, f"FPS: {self.stats['fps']:.1f}", (20, 60), font, 0.5, (0, 255, 0), 1)
        
        # Detections
        cv2.putText(frame, f"Detections: {self.stats['detections']}", (20, 80), font, 0.5, (255, 255, 255), 1)
        
        # Last plate
        if self.stats['last_plate']:
            last_plate = self.stats['last_plate']['text']
            cv2.putText(frame, f"Last: {last_plate}", (180, 60), font, 0.5, (255, 255, 0), 1)
        
        return frame
    
    def get_frame(self):
        """Get latest frame for streaming"""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None
    
    def get_stats(self):
        """Get current statistics"""
        return self.stats.copy()
    
    def is_running(self):
        """Check if engine is running"""
        return self.running


# Global engine instance
_engine = None


def get_engine():
    """Get or create engine instance"""
    global _engine
    if _engine is None:
        try:
            _engine = WebANPREngine()
        except Exception as e:
            logger.error(f"Failed to create WebANPREngine: {e}")
            return None
    return _engine

def start_detection():
    """Start detection"""
    engine = get_engine()
    if engine is None:
        return False
    return engine.start()


def stop_detection():
    """Stop detection"""
    engine = get_engine()
    if engine is None:
        return False
    return engine.stop()


def is_detection_running():
    """Check if detection is running"""
    engine = get_engine()
    if engine is None:
        return False
    return engine.is_running()


def get_video_frame():
    """Get current video frame"""
    engine = get_engine()
    if engine is None:
        return None
    return engine.get_frame()


def get_detection_stats():
    """Get detection statistics"""
    engine = get_engine()
    if engine is None:
        return {}
    return engine.get_stats()
