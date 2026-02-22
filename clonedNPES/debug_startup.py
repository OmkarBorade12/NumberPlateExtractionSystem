
import sys
import os
import traceback

print("Testing web_detection import...")
try:
    import web_detection
    print("web_detection imported")
except Exception:
    print("Failed to import web_detection:")
    traceback.print_exc()

print("\nTesting Engine Creation...")
try:
    engine = web_detection.WebANPREngine()
    print("Engine created successfully")
    print("Running _initialize_resources()...")
    engine._initialize_resources()
    print("Resources initialized.")
except Exception:
    print("Failed to init resources:")
    traceback.print_exc()
