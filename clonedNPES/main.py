"""
Enhanced Main Script with Robust Camera Handling
Supports both legacy and professional engines
"""

import cv2
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to use professional engine first
try:
    from anpr_engine import ANPREngine
    from camera_handler import CameraHandler
    USE_PROFESSIONAL = True
    logger.info("✓ Professional ANPR Engine available")
except ImportError as e:
    USE_PROFESSIONAL = False
    logger.warning(f"Professional engine not available: {e}")
    logger.info("Using legacy engine...")


if USE_PROFESSIONAL:
    # ===================================
    # Professional Engine (Recommended)
    # ===================================
    
    def main():
        """Run professional ANPR engine"""
        logger.info("=" * 70)
        logger.info("  ANPR PRO - Professional License Plate Recognition System")
        logger.info("  Optimized for 8GB RAM | YOLOv11-Nano + PaddleOCR")
        logger.info("=" * 70)
        logger.info("")
        
        # Test camera first
        logger.info("Testing camera availability...")
        try:
            camera = CameraHandler(preferred_index=0)
            cam_info = camera.get_info()
            
            logger.info(f"Camera Status:")
            logger.info(f"  Index: {cam_info['camera_index']}")
            logger.info(f"  Resolution: {cam_info.get('width', 'N/A')}x{cam_info.get('height', 'N/A')}")
            logger.info(f"  FPS: {cam_info.get('fps', 'N/A')}")
            logger.info("")
            
            camera.release()
            
        except RuntimeError as e:
            logger.error(f"Camera initialization failed: {e}")
            logger.error("Please connect a camera and try again.")
            return
        
        # Initialize and start engine
        logger.info("Initializing ANPR engine...")
        engine = ANPREngine(camera_source=0, frame_width=640, frame_height=640)
        
        try:
            logger.info("Starting detection... (Press 'Q' to quit)")
            logger.info("")
            engine.start()
        except KeyboardInterrupt:
            logger.info("\nKeyboard interrupt received")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            engine.stop()
            logger.info("ANPR Engine shutdown complete")
    
    if __name__ == "__main__":
        main()

else:
    # ===================================
    # Legacy Engine (Fallback)
    # ===================================
    
    from datetime import datetime
    import easyocr
    from ultralytics import YOLO
    from plate_utils import save_plate_to_csv, normalize_plate, is_valid_plate
    
    # Try to import camera handler
    try:
        from camera_handler import CameraHandler
        USE_CAMERA_HANDLER = True
    except ImportError:
        USE_CAMERA_HANDLER = False
        logger.warning("Camera handler not available, using basic cv2.VideoCapture")
    
    logger.info("=" * 70)
    logger.info("  ANPR - Legacy License Plate Recognition System")
    logger.info("=" * 70)
    logger.info("")
    
    # Initialize models
    logger.info("Loading YOLO model...")
    model = YOLO('yolov8n.pt')
    
    logger.info("Loading EasyOCR...")
    reader = easyocr.Reader(['en'])
    
    # Initialize camera
    if USE_CAMERA_HANDLER:
        logger.info("Initializing camera with robust handler...")
        try:
            camera = CameraHandler(preferred_index=0)
            cam_info = camera.get_info()
            # Default to not demo mode if key missing
            is_demo = cam_info.get('is_demo_mode', False)
            
            logger.info(f"Camera: {'DEMO MODE' if is_demo else 'LIVE'}")
            
            if is_demo:
                logger.warning("⚠ Running in DEMO MODE - No camera detected")
        except RuntimeError as e:
            logger.error(f"Camera init failed: {e}")
            USE_CAMERA_HANDLER = False
            camera = None

    if not USE_CAMERA_HANDLER:
        logger.info("Initializing camera...")
        camera = None
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("✗ Failed to open camera!")
            sys.exit(1)
        logger.info("✓ Camera opened")
    
    logger.info("Starting detection... (Press 'Q' to quit)")
    logger.info("")
    
    # Main detection loop
    frame_count = 0
    
    while True:
        # Read frame
        if USE_CAMERA_HANDLER:
            ret, frame = camera.read()
        else:
            ret, frame = cap.read()
        
        if not ret:
            logger.warning("Failed to read frame")
            break
        
        frame_count += 1
        
        # Run YOLO detection
        results = model(frame, verbose=False)
        boxes = results[0].boxes.xyxy.cpu().numpy()
        
        # Process detections
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            plate_img = frame[y1:y2, x1:x2]
            
            # Run OCR
            text_results = reader.readtext(plate_img)
            
            for (bbox, txt, prob) in text_results:
                try:
                    save_plate_to_csv(txt, prob, plate_img=plate_img)
                    logger.info(f"✓ Detected: {txt} (Confidence: {prob:.2f})")
                except Exception:
                    pass
                
                # Draw on frame
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, txt, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
        
        # Fallback: OCR on full frame if no detections
        if len(boxes) == 0 and frame_count % 30 == 0:  # Every 30 frames
            try:
                texts = reader.readtext(frame)
                for (bbox, txt, prob) in texts:
                    if prob < 0.4:
                        continue
                    normalized = normalize_plate(txt)
                    if is_valid_plate(normalized):
                        try:
                            x_coords = [int(p[0]) for p in bbox]
                            y_coords = [int(p[1]) for p in bbox]
                            x_min = max(0, min(x_coords))
                            x_max = min(frame.shape[1], max(x_coords))
                            y_min = max(0, min(y_coords))
                            y_max = min(frame.shape[0], max(y_coords))
                            crop = frame[y_min:y_max, x_min:x_max]
                        except Exception:
                            crop = frame.copy()
                        save_plate_to_csv(normalized, prob, plate_img=crop)
            except Exception:
                pass
        
        # Display frame
        cv2.imshow("ANPR - Number Plate Detection", frame)
        
        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup
    if USE_CAMERA_HANDLER:
        camera.release()
    else:
        cap.release()
    
    cv2.destroyAllWindows()
    logger.info("Detection stopped")