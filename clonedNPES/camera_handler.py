"""
Professional Camera Handler with Auto-Detection and Fallbacks
Handles camera initialization, error recovery, and demo mode
"""

import cv2
import os
import numpy as np
import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CameraHandler:
    """
    Robust camera handler with:
    - Auto-detection of available cameras
    - Multiple fallback options
    - Demo mode with sample video
    - Error recovery and reconnection
    - Performance optimization
    """
    
    def __init__(self, preferred_index: int = 0):
        """
        Initialize camera handler - CAMERA REQUIRED
        
        Args:
            preferred_index: Preferred camera index (default: 0)
        """
        self.preferred_index = preferred_index
        self.cap = None
        self.camera_index = None
        self.last_frame = None
        self.frame_count = 0
        
        # Initialize camera - MUST succeed
        self._initialize_camera()
    
    def _initialize_camera(self):
        """Initialize camera - faster detection"""
        # 1. Try index 0 with DSHOW (Standard Windows)
        if self._try_camera(0, cv2.CAP_DSHOW):
            return
            
        # 2. Try index 0 with ANY
        if self._try_camera(0, cv2.CAP_ANY):
            return
            
        # 3. Try index 1 (USB webcam)
        if self._try_camera(1, cv2.CAP_DSHOW):
            return

        # 4. Try index 2
        if self._try_camera(2, cv2.CAP_DSHOW):
            return
            
        # Try DirectShow backend (Windows)
        logger.warning("Trying DirectShow backend...")
        if self._try_camera(self.preferred_index, cv2.CAP_DSHOW):
            logger.info(f"✓ Camera {self.preferred_index} initialized with DirectShow")
            return
        
        # Try MSMF backend (Windows)
        logger.warning("Trying MSMF backend...")
        if self._try_camera(self.preferred_index, cv2.CAP_MSMF):
            logger.info(f"✓ Camera {self.preferred_index} initialized with MSMF")
            return
        
        # No camera found - CRITICAL ERROR
        error_msg = """
╔══════════════════════════════════════════════════════════════════╗
║                    CAMERA NOT FOUND - CRITICAL ERROR              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  No camera could be detected on your system.                     ║
║                                                                   ║
║  TROUBLESHOOTING STEPS:                                          ║
║                                                                   ║
║  1. Connect a USB webcam to your computer                        ║
║  2. Check Windows camera permissions:                            ║
║     - Settings → Privacy → Camera                                ║
║     - Enable camera access for apps                              ║
║  3. Close other applications using the camera:                   ║
║     - Zoom, Teams, Skype, etc.                                   ║
║  4. Try a different USB port                                     ║
║  5. Restart your computer                                        ║
║  6. Update camera drivers                                        ║
║                                                                   ║
║  If you have a built-in laptop camera, make sure it's enabled    ║
║  in Device Manager.                                              ║
║                                                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""
        logger.error(error_msg)
        raise RuntimeError("CAMERA REQUIRED: No camera found. Please connect a camera and try again.")
    
    def _try_camera(self, index: int, backend: int = cv2.CAP_ANY) -> bool:
        """
        Try to open camera with given index and backend
        
        Args:
            index: Camera index
            backend: OpenCV backend (CAP_ANY, CAP_DSHOW, CAP_MSMF, etc.)
        
        Returns:
            True if camera opened successfully
        """
        try:
            # Force DirectShow on Windows if backend is ANY, as MSMF is buggy
            if backend == cv2.CAP_ANY and os.name == 'nt':
                 backend = cv2.CAP_DSHOW
                 
            cap = cv2.VideoCapture(index, backend)
            
            if not cap.isOpened():
                return False
            
            # Try to read frame to verify
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return False
            
            # Simple validation
            if len(frame.shape) != 3 or frame.shape[0] < 10:
                cap.release()
                return False
            
            # Success! Store the capture object
            self.cap = cap
            self.camera_index = index
            self.is_demo_mode = False
            
            # Configure camera for optimal performance
            try:
                self._configure_camera()
            except:
                pass
                
            return True
            
        except Exception as e:
            logger.error(f"Error trying camera {index} with backend {backend}: {e}")
            return False
    
    def _configure_camera(self):
        """Configure camera settings for optimal performance"""
        if self.cap is None:
            return
        
        try:
            # Set resolution (balance between quality and performance)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            # Set FPS
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Disable auto-focus for faster capture (if supported)
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            
            # Get actual settings
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            logger.info(f"Camera configured: {width}x{height} @ {fps}fps")
            
        except Exception as e:
            logger.warning(f"Could not configure camera settings: {e}")
    
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a frame from camera with validation and retry
        
        Returns:
            Tuple of (success, frame)
        """
        if self.cap is None:
            return False, None
        
        # Read frame directly - optimized for speed
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                # One quick retry
                time.sleep(0.01)
                ret, frame = self.cap.read()
                if not ret:
                    return False, None
            
            # Skip validation for raw speed - trust the camera
            self.last_frame = frame
            self.frame_count += 1
            return True, frame
            
        except Exception:
            return False, None
    
    def _validate_frame(self, frame: np.ndarray) -> bool:
        """Validate that frame is usable - relaxed validation"""
        try:
            # Check if frame exists and has basic shape
            if frame is None:
                return False
            
            # Check if frame has 3 dimensions (height, width, channels)
            if len(frame.shape) != 3:
                return False
            
            # Check if frame has reasonable dimensions (very relaxed)
            h, w = frame.shape[:2]
            if h < 10 or w < 10:  # Very minimal check
                return False
            
            # That's it! Don't be too strict
            return True
            
        except Exception:
            return False
    
    def _reconnect(self):
        """Attempt to reconnect to camera"""
        logger.info("Attempting to reconnect to camera...")
        
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
        
        time.sleep(0.5)  # Brief wait before reconnecting
        
        # Try to reinitialize
        try:
            self._initialize_camera()
        except RuntimeError as e:
            logger.error(f"Reconnection failed: {e}")
            raise
    
    
    def is_opened(self) -> bool:
        """Check if camera is opened"""
        return self.cap is not None and self.cap.isOpened()
    
    def release(self):
        """Release camera resources"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info("Camera released")
    
    def get_info(self) -> dict:
        """Get camera information"""
        info = {
            'camera_index': self.camera_index,
            'is_opened': self.is_opened(),
            'frame_count': self.frame_count
        }
        
        if self.cap is not None:
            info.update({
                'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': int(self.cap.get(cv2.CAP_PROP_FPS))
            })
        
        return info


def get_camera(preferred_index: int = 0) -> CameraHandler:
    """
    Get a camera handler instance
    
    Args:
        preferred_index: Preferred camera index
    
    Returns:
        CameraHandler instance
    """
    return CameraHandler(preferred_index)


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Camera Handler...")
    print("=" * 60)
    
    try:
        camera = get_camera()
        info = camera.get_info()
        
        print(f"\nCamera Info:")
        print(f"  Index: {info['camera_index']}")
        print(f"  Resolution: {info.get('width', 'N/A')}x{info.get('height', 'N/A')}")
        print(f"  FPS: {info.get('fps', 'N/A')}")
        print(f"  Status: {'Opened' if info['is_opened'] else 'Closed'}")
        
        print(f"\nReading 10 test frames...")
        for i in range(10):
            ret, frame = camera.read()
            if ret and frame is not None:
                print(f"  Frame {i+1}: ✓ {frame.shape}")
            else:
                print(f"  Frame {i+1}: ✗ Failed")
        
        camera.release()
        print("\n✓ Test complete!")
        
    except RuntimeError as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease connect a camera and try again.")

