"""
ANPR Pro - Configuration File
Customize system behavior without editing source code
"""

# ===================================
# Camera Settings
# ===================================

# Camera source (0 for USB webcam, RTSP URL for IP camera, or video file path)
CAMERA_SOURCE = 0

# Frame resolution for processing (lower = less RAM, higher = better accuracy)
FRAME_WIDTH = 640
FRAME_HEIGHT = 640

# Camera capture resolution (before downscaling)
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# ===================================
# Detection Settings
# ===================================

# YOLO model path
YOLO_MODEL = 'yolo11n.pt'  # Options: yolo11n.pt, yolo11s.pt, yolo11m.pt

# Detection confidence threshold (0.0 to 1.0)
DETECTION_CONFIDENCE = 0.25

# IoU threshold for NMS
DETECTION_IOU = 0.45

# Tracker type
TRACKER = 'botsort.yaml'  # Options: botsort.yaml, bytetrack.yaml

# ===================================
# OCR Settings
# ===================================

# PaddleOCR language
OCR_LANGUAGE = 'en'

# Use GPU for OCR (requires CUDA)
OCR_USE_GPU = False

# OCR confidence threshold
OCR_CONFIDENCE = 0.6

# OCR detection thresholds
OCR_DET_DB_THRESH = 0.3
OCR_DET_DB_BOX_THRESH = 0.5

# OCR batch size
OCR_BATCH_SIZE = 6

# ===================================
# Plate Validation
# ===================================

# Plate format regex pattern
# Indian format: MH12 AB 1234
PLATE_PATTERN = r'^[A-Z]{2,3}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4}$'

# US format example: ABC-1234
# PLATE_PATTERN = r'^[A-Z]{3}-\d{4}$'

# European format example: AB-123-CD
# PLATE_PATTERN = r'^[A-Z]{2}-\d{3}-[A-Z]{2}$'

# Character normalization rules
NORMALIZE_O_TO_0 = True  # Convert O to 0
NORMALIZE_I_TO_1 = True  # Convert I to 1

# ===================================
# Deduplication Settings
# ===================================

# Seconds before re-processing the same plate
DEDUPE_SECONDS = 40

# Seconds before re-processing the same tracked vehicle
TRACK_TIMEOUT = 5

# ===================================
# Performance Settings
# ===================================

# Queue sizes (lower = less RAM, higher = smoother processing)
FRAME_QUEUE_SIZE = 10
DETECTION_QUEUE_SIZE = 20

# Number of processing threads
NUM_CAPTURE_THREADS = 1
NUM_DETECTION_THREADS = 1
NUM_OCR_THREADS = 1

# ===================================
# Storage Settings
# ===================================

# CSV file for detections
CSV_FILE = 'detected_plates.csv'

# Snapshot directory
SNAPSHOT_DIR = 'snapshots'

# Log file
LOG_FILE = 'detector.log'

# Save snapshots
SAVE_SNAPSHOTS = True

# Snapshot image quality (1-100, higher = better quality, larger file)
SNAPSHOT_QUALITY = 85

# ===================================
# Web Application Settings
# ===================================

# Flask host and port
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 5000

# Debug mode (set to False in production)
WEBAPP_DEBUG = True

# Session secret key (change this in production!)
WEBAPP_SECRET = 'dev-secret-change-me-in-production'

# API key for endpoint protection (optional)
# Set this to enable API key authentication
WEBAPP_API_KEY = None  # Example: 'your-secret-api-key-here'

# Auto-refresh interval (seconds)
AUTO_REFRESH_INTERVAL = 5

# Items per page in dashboard
ITEMS_PER_PAGE = 12

# ===================================
# Logging Settings
# ===================================

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = 'INFO'

# Log format
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Log to file
LOG_TO_FILE = True

# Log to console
LOG_TO_CONSOLE = True

# Max log file size (bytes)
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB

# Number of log backup files
LOG_BACKUP_COUNT = 5

# ===================================
# Advanced Settings
# ===================================

# Enable performance monitoring
ENABLE_PERFORMANCE_MONITORING = True

# Display live video feed
DISPLAY_VIDEO = True

# Video window name
VIDEO_WINDOW_NAME = "ANPR System - Professional Grade"

# Performance overlay height (pixels)
PERFORMANCE_OVERLAY_HEIGHT = 120

# ===================================
# Export Settings
# ===================================

# Default export format
DEFAULT_EXPORT_FORMAT = 'xlsx'  # Options: csv, xlsx

# Excel sheet name
EXCEL_SHEET_NAME = 'Detections'

# ===================================
# Notification Settings (Future)
# ===================================

# Enable email notifications
ENABLE_EMAIL_NOTIFICATIONS = False

# Email settings
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USERNAME = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'
EMAIL_FROM = 'ANPR Pro <noreply@anprpro.com>'
EMAIL_TO = ['admin@example.com']

# Enable SMS notifications
ENABLE_SMS_NOTIFICATIONS = False

# SMS settings (Twilio example)
SMS_ACCOUNT_SID = 'your-account-sid'
SMS_AUTH_TOKEN = 'your-auth-token'
SMS_FROM_NUMBER = '+1234567890'
SMS_TO_NUMBERS = ['+1234567890']

# ===================================
# Database Settings (Future)
# ===================================

# Database type
DATABASE_TYPE = 'csv'  # Options: csv, sqlite, postgresql, mysql

# SQLite settings
SQLITE_DB_PATH = 'anpr.db'

# PostgreSQL settings
POSTGRES_HOST = 'localhost'
POSTGRES_PORT = 5432
POSTGRES_DB = 'anpr'
POSTGRES_USER = 'anpr_user'
POSTGRES_PASSWORD = 'your-password'

# MySQL settings
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_DB = 'anpr'
MYSQL_USER = 'anpr_user'
MYSQL_PASSWORD = 'your-password'
