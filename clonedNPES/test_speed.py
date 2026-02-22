
print("Startup...")
import cv2
print("cv2 OK")
import numpy
print("numpy OK")
try:
    import web_detection
    print("web_detection OK")
except Exception as e:
    print(f"web_detection failed: {e}")
