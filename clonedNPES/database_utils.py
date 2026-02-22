
import sqlite3
import os
from datetime import datetime
import logging

# Database configuration
DB_FILE = 'anpr.db'

def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Detections table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_text TEXT NOT NULL,
        confidence REAL,
        image_path TEXT,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        vehicle_type TEXT,
        user TEXT,
        camera_id TEXT,
        is_synced INTEGER DEFAULT 0
    )
    ''')
    
    # Create Vehicle Registry table (simulated RTO database)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vehicle_registry (
        plate_text TEXT PRIMARY KEY,
        owner_name TEXT,
        vehicle_model TEXT,
        registration_date TEXT,
        status TEXT DEFAULT 'Active'
    )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

def save_detection_to_db(plate_text, confidence, image_path, user=None, camera_id=None):
    """Save a new detection to the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user = user or os.environ.get('DETECTOR_USER', 'System')
        
        cursor.execute('''
        INSERT INTO detections (plate_text, confidence, image_path, user, camera_id)
        VALUES (?, ?, ?, ?, ?)
        ''', (plate_text, confidence, image_path, user, camera_id))
        
        detection_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return detection_id
    except Exception as e:
        logging.error(f"Failed to save detection to DB: {e}")
        return None

def get_recent_detections(limit=10):
    """Get recent detections"""
    conn = get_db_connection()
    
    try:
        detections = conn.execute(
            'SELECT * FROM detections ORDER BY captured_at DESC LIMIT ?',
            (limit,)
        ).fetchall()
        
        # Convert to list of dicts
        return [dict(row) for row in detections]
    finally:
        conn.close()

# Initialize DB on import if not exists
if not os.path.exists(DB_FILE):
    init_db()
