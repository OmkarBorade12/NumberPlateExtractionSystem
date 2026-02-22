"""
Professional ANPR Engine - Optimized for 8GB RAM
Uses YOLOv11-Nano + PaddleOCR + Multi-threading + BoT-SORT Tracking
"""

import cv2
import os
import threading
import queue
import time
from datetime import datetime
from collections import defaultdict
import numpy as np
from ultralytics import YOLO

# Shim for langchain.docstore if missing (PaddleOCR 3.x dependency)
import sys
import types
try:
    import langchain.docstore
except ImportError:
    try:
        import langchain_community.docstore as docstore
        if 'langchain' not in sys.modules:
            sys.modules['langchain'] = types.ModuleType('langchain')
        sys.modules['langchain.docstore'] = docstore
    except ImportError:
        pass
try:
    import langchain.text_splitter
except ImportError:
    try:
        import langchain_text_splitters as ts
        if 'langchain' not in sys.modules:
            sys.modules['langchain'] = types.ModuleType('langchain')
        sys.modules['langchain.text_splitter'] = ts
    except ImportError:
        pass

from paddleocr import PaddleOCR
from plate_utils import save_plate_to_csv, normalize_plate, is_valid_plate
from camera_handler import CameraHandler
import psutil
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('detector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ANPREngine:
    """
    High-performance ANPR Engine with:
    - YOLOv11-Nano for detection
    - PaddleOCR for text extraction
    - Multi-threading for parallel processing
    - BoT-SORT tracking for deduplication
    - Memory-optimized frame processing
    """
    
    def __init__(self, camera_source=0, frame_width=640, frame_height=640):
        """
        Initialize ANPR Engine
        
        Args:
            camera_source: Camera index or RTSP URL
            frame_width: Target frame width for processing (default 640)
            frame_height: Target frame height for processing (default 640)
        """
        self.camera_source = camera_source
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Performance metrics
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.processing_times = []
        
        # Threading components
        self.frame_queue = queue.Queue(maxsize=10)
        self.detection_queue = queue.Queue(maxsize=20)
        self.running = False
        
        # Tracking dictionary to avoid duplicate OCR
        self.tracked_plates = {}  # track_id -> (plate_text, last_seen_time)
        self.track_timeout = 5  # seconds before re-processing same vehicle
        
        # Initialize models
        logger.info("Initializing YOLOv11-Nano model...")
        self.detector = self._load_yolo_model()
        
        logger.info("Initializing PaddleOCR (lightweight)...")
        try:
            self.ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang='en',
                use_gpu=False,  # Set to True if GPU available
                show_log=False,
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                rec_batch_num=6
            )
        except Exception:
            try:
                # Fallback for 3.x
                self.ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                # We can either raise or set to None; but Professional Engine needs it
                raise e
        
        logger.info("ANPR Engine initialized successfully")
        self._log_system_resources()
    
    def _load_yolo_model(self):
        """Load YOLO model with support for custom trained models"""
        # Priority order: Custom trained > YOLOv11n > YOLOv8n
        model_paths = [
            'models/anpr_custom_best.pt',  # Custom trained model
            'yolo11n.pt',                   # YOLOv11-Nano
            'yolov8n.pt'                    # YOLOv8-Nano (fallback)
        ]
        
        for model_path in model_paths:
            if os.path.exists(model_path):
                logger.info(f"Loading YOLO model: {model_path}")
                try:
                    model = YOLO(model_path)
                    logger.info(f"✓ Successfully loaded: {model_path}")
                    return model
                except Exception as e:
                    logger.warning(f"Failed to load {model_path}: {e}")
                    continue
        
        # If no local model found, download YOLOv11n
        logger.info("No local model found. Downloading YOLOv11-Nano...")
        model = YOLO('yolo11n.pt')  # Auto-download
        logger.info("✓ YOLOv11-Nano downloaded and loaded")
        return model
    
    def _log_system_resources(self):
        """Log current system resource usage"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        logger.info(f"System Resources:")
        logger.info(f"  RAM: {memory.percent}% used ({memory.used / (1024**3):.2f}GB / {memory.total / (1024**3):.2f}GB)")
        logger.info(f"  CPU: {cpu_percent}%")
    
    def start(self):
        """Start the ANPR engine with multi-threading"""
        self.running = True
        
        # Thread 1: Capture frames from camera
        capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
        capture_thread.start()
        
        # Thread 2: Detect plates using YOLO
        detection_thread = threading.Thread(target=self._detect_plates, daemon=True)
        detection_thread.start()
        
        # Thread 3: Extract text using OCR
        ocr_thread = threading.Thread(target=self._extract_text, daemon=True)
        ocr_thread.start()
        
        # Main thread: Display results and monitor performance
        self._display_loop()
    
    def stop(self):
        """Stop the ANPR engine"""
        self.running = False
        logger.info("ANPR Engine stopped")
    
    def _capture_frames(self):
        """Thread 1: Capture and preprocess frames"""
        # Use robust camera handler - CAMERA REQUIRED
        camera = CameraHandler(
            preferred_index=self.camera_source if isinstance(self.camera_source, int) else 0
        )
        
        # Get camera info
        cam_info = camera.get_info()
        logger.info(f"Camera initialized:")
        logger.info(f"  Index: {cam_info['camera_index']}")
        logger.info(f"  Resolution: {cam_info.get('width', 'N/A')}x{cam_info.get('height', 'N/A')}")
        logger.info(f"  FPS: {cam_info.get('fps', 'N/A')}")
        
        frame_skip = 0
        max_skip = 2  # Process every 3rd frame to reduce load
        
        while self.running:
            ret, frame = camera.read()
            
            if not ret or frame is None:
                logger.warning("Failed to read frame, retrying...")
                time.sleep(0.1)
                continue
            
            # Skip frames to reduce processing load (optional)
            frame_skip += 1
            if frame_skip % max_skip != 0:
                continue
            
            # Downscale frame to save memory (critical for 8GB RAM)
            try:
                frame_resized = cv2.resize(frame, (self.frame_width, self.frame_height))
            except Exception as e:
                logger.error(f"Error resizing frame: {e}")
                continue
            
            # Add to queue (non-blocking)
            try:
                self.frame_queue.put((frame, frame_resized), block=False)
            except queue.Full:
                pass  # Skip frame if queue is full
            
            self.frame_count += 1
        
        camera.release()
        logger.info("Camera released")
    
    def _detect_plates(self):
        """Thread 2: Detect license plates using YOLOv11 with BoT-SORT tracking"""
        while self.running:
            try:
                # Get frame from queue
                frame_original, frame_resized = self.frame_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            start_time = time.time()
            
            # Run YOLOv11 detection with tracking
            results = self.detector.track(
                frame_resized,
                persist=True,
                tracker="botsort.yaml",  # BoT-SORT tracker
                conf=0.25,
                iou=0.45,
                verbose=False
            )
            
            # Process detections
            if results and len(results) > 0:
                boxes = results[0].boxes
                
                if boxes is not None and len(boxes) > 0:
                    for box in boxes:
                        # Get bounding box coordinates
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        conf = float(box.conf[0])
                        
                        # Get track ID if available
                        track_id = int(box.id[0]) if box.id is not None else None
                        
                        # Skip if we've recently processed this track
                        if track_id is not None:
                            if track_id in self.tracked_plates:
                                last_seen = self.tracked_plates[track_id][1]
                                if time.time() - last_seen < self.track_timeout:
                                    continue  # Skip this detection
                        
                        # Crop plate region from original frame
                        # Scale coordinates back to original frame size
                        scale_x = frame_original.shape[1] / self.frame_width
                        scale_y = frame_original.shape[0] / self.frame_height
                        
                        x1_orig = int(x1 * scale_x)
                        y1_orig = int(y1 * scale_y)
                        x2_orig = int(x2 * scale_x)
                        y2_orig = int(y2 * scale_y)
                        
                        plate_crop = frame_original[y1_orig:y2_orig, x1_orig:x2_orig]
                        
                        # Add to OCR queue
                        try:
                            self.detection_queue.put({
                                'crop': plate_crop,
                                'bbox': (x1, y1, x2, y2),
                                'conf': conf,
                                'track_id': track_id,
                                'frame': frame_resized.copy()
                            }, block=False)
                        except queue.Full:
                            pass
            
            # Track processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)
    
    def _extract_text(self):
        """Thread 3: Extract text using PaddleOCR"""
        while self.running:
            try:
                detection = self.detection_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            plate_crop = detection['crop']
            track_id = detection['track_id']
            
            # Skip if crop is too small
            if plate_crop.shape[0] < 20 or plate_crop.shape[1] < 40:
                continue
            
            try:
                # Run PaddleOCR with robust call
                try:
                    result = self.ocr_engine.ocr(plate_crop, cls=True)
                except TypeError:
                    result = self.ocr_engine.ocr(plate_crop)
                
                if result and len(result) > 0 and result[0]:
                    for line in result[0]:
                        text = line[1][0]
                        confidence = line[1][1]
                        
                        # Normalize and validate
                        normalized_text = normalize_plate(text)
                        
                        if is_valid_plate(normalized_text) and confidence > 0.6:
                            # Save to database
                            save_plate_to_csv(
                                normalized_text,
                                confidence,
                                plate_img=plate_crop
                            )
                            
                            # Update tracking
                            if track_id is not None:
                                self.tracked_plates[track_id] = (normalized_text, time.time())
                            
                            logger.info(f"✓ Detected: {normalized_text} (Confidence: {confidence:.2f})")
                            break
            
            except Exception as e:
                logger.error(f"OCR error: {e}")
    
    def _display_loop(self):
        """Main thread: Display results and performance metrics"""
        cv2.namedWindow("ANPR System - Professional Grade", cv2.WINDOW_NORMAL)
        
        while self.running:
            try:
                # Get latest frame
                frame_original, frame_resized = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Calculate FPS
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                self.fps = self.frame_count / elapsed
            
            # Get system stats
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0)
            
            # Create display frame
            display_frame = frame_original.copy()
            
            # Draw performance overlay
            overlay_height = 120
            overlay = np.zeros((overlay_height, display_frame.shape[1], 3), dtype=np.uint8)
            overlay[:] = (20, 20, 20)  # Dark background
            
            # Add text
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(overlay, f"FPS: {self.fps:.1f}", (10, 25), font, 0.6, (0, 255, 0), 2)
            cv2.putText(overlay, f"RAM: {memory.percent:.1f}% ({memory.used / (1024**3):.1f}GB)", (10, 50), font, 0.6, (0, 255, 255), 2)
            cv2.putText(overlay, f"CPU: {cpu_percent:.1f}%", (10, 75), font, 0.6, (255, 165, 0), 2)
            cv2.putText(overlay, f"Tracked Vehicles: {len(self.tracked_plates)}", (10, 100), font, 0.6, (255, 255, 255), 2)
            
            # Average processing time
            if self.processing_times:
                avg_time = sum(self.processing_times) / len(self.processing_times)
                cv2.putText(overlay, f"Avg Process Time: {avg_time*1000:.1f}ms", (400, 25), font, 0.6, (147, 112, 219), 2)
            
            # Combine overlay with frame
            display_frame = np.vstack([overlay, display_frame])
            
            # Show frame
            cv2.imshow("ANPR System - Professional Grade", display_frame)
            
            # Check for quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.stop()
                break
        
        cv2.destroyAllWindows()


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Professional ANPR System - Optimized for 8GB RAM")
    logger.info("YOLOv11-Nano + PaddleOCR + Multi-threading + BoT-SORT")
    logger.info("=" * 60)
    
    # Initialize engine
    engine = ANPREngine(camera_source=0)
    
    try:
        # Start processing
        engine.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        engine.stop()
        logger.info("ANPR Engine shutdown complete")


if __name__ == "__main__":
    main()
