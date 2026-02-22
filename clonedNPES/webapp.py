from flask import Flask, render_template, jsonify, send_from_directory, request, send_file, session, redirect, url_for, flash, Response
import csv
import os
import subprocess
import signal
import sys
from threading import Lock
from flask import abort
from plate_utils import initialize_plate_cache
from plate_utils import get_last_seen_iso, get_top_n
try:
    from database_utils import get_recent_detections, get_db_connection
    params_db_available = True
except ImportError:
    params_db_available = False
import io
import pandas as pd
import json
import cv2
import logging
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# simple token auth: only enable when WEBAPP_API_KEY is set in the environment
API_KEY = os.environ.get('WEBAPP_API_KEY')

if API_KEY:
    print('WEBAPP_API_KEY is set: control endpoints require this token in X-API-KEY header')
else:
    print('WEBAPP_API_KEY not set: control endpoints are NOT protected (no token required).')

app = Flask(__name__, static_folder='static', template_folder='templates')
# Session secret
app.secret_key = os.environ.get('WEBAPP_SECRET', 'dev-secret-change-me')

USERS_FILE = 'users.json'


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)


def create_user(username, password):
    users = load_users()
    if username in users:
        return False
    users[username] = generate_password_hash(password)
    save_users(users)
    return True


def verify_user(username, password):
    users = load_users()
    ph = users.get(username)
    if not ph:
        return False
    return check_password_hash(ph, password)


def _check_token_or_session():
    token = request.headers.get('X-API-KEY', '')
    if API_KEY:
        return token == API_KEY
    # if no API key configured, allow authenticated session
    if session.get('user'):
        return True
    return False

CSV_FILE = 'detected_plates.csv'
SNAPSHOT_DIR = 'snapshots'

# Simple process management for detection script
proc = None
proc_lock = Lock()
LOG_FILE = 'detector.log'


def read_csv_rows():
    if not os.path.exists(CSV_FILE):
        return []
    rows_out = []
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            # normalize keys and values
            plate = (row.get('Plate Text') or row.get('plate') or row.get('plate text') or '').strip()
            if not plate:
                continue
            date = (row.get('Date') or row.get('date') or '').strip()
            time = (row.get('Time') or row.get('time') or '').strip()
            image = (row.get('Image Path') or row.get('image') or row.get('image_path') or '').strip()
            image_basename = os.path.basename(image) if image else ''
            user = (row.get('User') or row.get('user') or '').strip()
            rows_out.append({'plate': plate.upper(), 'date': date, 'time': time, 'image': image_basename, 'user': user})
    # return rows newest-first so the UI shows the latest detection at the top
    try:
        return rows_out[::-1]
    except Exception:
        return rows_out


def proc_running():
    global proc
    return proc is not None and proc.poll() is None


@app.route('/')
def index():
    # Redirect to professional UI by default
    return redirect(url_for('index_pro'))


@app.route('/classic')
def index_classic():
    # Classic UI (legacy)
    if not API_KEY:
        if not session.get('user'):
            return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/pro')
def index_pro():
    # Professional UI (new)
    if not API_KEY:
        if not session.get('user'):
            return redirect(url_for('login'))
    return render_template('index_pro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if not username or not password:
        flash('Missing username or password')
        return redirect(url_for('login'))
    if verify_user(username, password):
        session['user'] = username
        flash('Logged in')
        return redirect(url_for('index'))
    else:
        flash('Invalid credentials')
        return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    password2 = request.form.get('password2', '')
    if not username or not password:
        flash('Missing username or password')
        return redirect(url_for('register'))
    if password != password2:
        flash('Passwords do not match')
        return redirect(url_for('register'))
    if len(password) < 6:
        flash('Password must be at least 6 characters')
        return redirect(url_for('register'))
    ok = create_user(username, password)
    if not ok:
        flash('Username already exists')
        return redirect(url_for('register'))
    session['user'] = username
    flash('Registered and logged in')
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out')
    return redirect(url_for('index'))


@app.route('/api/plates')
def api_plates():
    plate_q = request.args.get('plate', '').strip().upper()
    date_q = request.args.get('date', '').strip()
    rows = read_csv_rows()
    # if no API key configured, restrict results to the logged-in user
    if not API_KEY:
        user = session.get('user')
        if user:
            rows = [r for r in rows if (r.get('user') or r.get('User') or '').strip() == user]
        else:
            # not logged in - return empty
            rows = []
    if plate_q:
        rows = [r for r in rows if plate_q in r['plate']]
    if date_q:
        rows = [r for r in rows if date_q in r['date']]
    return jsonify(rows)


@app.route('/api/db/test')
def api_db_test():
    if not params_db_available:
        return jsonify({'error': 'Database module not loaded'})
    try:
        conn = get_db_connection()
        rows = conn.execute('SELECT * FROM detections ORDER BY id DESC LIMIT 20').fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/status')
def api_status():
    try:
        from web_detection import is_detection_running, get_detection_stats
        running = is_detection_running()
        stats = get_detection_stats() if running else {}
        return jsonify({
            'running': running,
            'stats': stats
        })
    except:
        return jsonify({'running': False, 'stats': {}})


@app.route('/api/latest')
def api_latest():
    rows = read_csv_rows()
    # return the most recent N rows
    n = int(request.args.get('n', '10'))
    # read_csv_rows now returns newest-first, so take the first n rows
    return jsonify(rows[:n])


@app.route('/api/summary')
def api_summary():
    rows = read_csv_rows()
    total = len(rows)
    unique = len(set(r['plate'] for r in rows))
    last_seen_map = get_last_seen_iso()
    top = get_top_n(10)
    return jsonify({'total': total, 'unique': unique, 'last_seen': last_seen_map, 'top': top})


@app.route('/snapshots/<path:filename>')
def snapshot_file(filename):
    return send_from_directory(SNAPSHOT_DIR, filename)


@app.route('/api/start', methods=['POST'])
def api_start():
    # auth: accept API key or logged-in session when API key not set
    if not _check_token_or_session():
        return jsonify({'status': 'unauthorized'}), 401
    
    try:
        from web_detection import start_detection, is_detection_running
        
        if is_detection_running():
            return jsonify({'status': 'already_running'})
        
        # Set user in environment for detection
        if session.get('user'):
            os.environ['DETECTOR_USER'] = session.get('user')
        
        success = start_detection()
        
        if success:
            logger.info("✓ Detection started successfully")
            return jsonify({'status': 'started'})
        else:
            logger.error("✗ Failed to start detection")
            return jsonify({'status': 'failed', 'error': 'Could not start detection'}), 500
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error starting detection: {error_details}")
        return jsonify({'status': 'error', 'error': str(e), 'details': error_details}), 500


@app.route('/api/stop', methods=['POST'])
def api_stop():
    # auth: accept API key or logged-in session when API key not set
    if not _check_token_or_session():
        return jsonify({'status': 'unauthorized'}), 401
    
    try:
        from web_detection import stop_detection, is_detection_running
        
        if not is_detection_running():
            return jsonify({'status': 'not_running'})
        
        success = stop_detection()
        
        if success:
            logger.info("✓ Detection stopped")
            return jsonify({'status': 'stopped'})
        else:
            return jsonify({'status': 'failed'}), 500
            
    except Exception as e:
        logger.error(f"Error stopping detection: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/video_feed')
def video_feed():
    """Video streaming route for live camera feed"""
    def generate():
        try:
            from web_detection import get_video_frame
            
            while True:
                frame = get_video_frame()
                
                if frame is None:
                    # Send a placeholder frame
                    frame = create_placeholder_frame()
                
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                if not ret:
                    time.sleep(0.01)
                    continue
                
                frame_bytes = buffer.tobytes()
                
                # Yield frame in multipart format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                # Limit streaming FPS to save bandwidth/CPU
                time.sleep(0.03)
                
        except GeneratorExit:
            pass
        except Exception as e:
            logger.error(f"Video feed error: {e}")
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def create_placeholder_frame():
    """Create a placeholder frame when no video available"""
    import numpy as np
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (30, 30, 30)
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, "Starting camera...", (180, 240), 
                font, 1.0, (255, 255, 255), 2)
    
    return frame


@app.route('/api/logs')
def api_logs():
    # returns last 200 lines of the detector log
    if not os.path.exists(LOG_FILE):
        return jsonify({'lines': []})
    try:
        with open(LOG_FILE, 'rb') as f:
            data = f.read()
        text = data.decode('utf-8', errors='replace')
        lines = text.splitlines()
        return jsonify({'lines': lines[-200:]})
    except Exception:
        return jsonify({'lines': ['error reading log file']}), 500


@app.route('/api/export')
def api_export():
    # auth: allow export when API key provided or user logged in (if no API_KEY configured)
    if not _check_token_or_session():
        return jsonify({'status': 'unauthorized'}), 401
    if not os.path.exists(CSV_FILE):
        return jsonify({'status': 'no_file'}), 404
    # also support xlsx export via ?format=xlsx
    fmt = request.args.get('format', '').lower()
    if fmt == 'xlsx':
        try:
            df = pd.read_csv(CSV_FILE)
            bio = io.BytesIO()
            with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Detections')
            bio.seek(0)
            return send_file(bio, as_attachment=True, download_name='detected_plates.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception:
            return jsonify({'status': 'error_creating_xlsx'}), 500
    return send_from_directory(os.getcwd(), CSV_FILE, as_attachment=True)


if __name__ == '__main__':
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    # initialize plate cache from existing CSV so counts are correct
    try:
        initialize_plate_cache()
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5000, debug=True)

