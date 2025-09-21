import csv
import os
import re
from datetime import datetime

filename = 'detected_plates.csv'
snapshot_dir = 'snapshots'
os.makedirs(snapshot_dir, exist_ok=True)

existing_plates = {}
# no last_saved_plate blocking so every detection is stored as its own row
last_seen = {}
# make dedupe window configurable via environment variable
import os
DEDUPE_SECONDS = int(os.environ.get('WEBAPP_DEDUPE_SECONDS', '40'))

def normalize_plate(text):
    text = text.upper().strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('O', '0').replace('I', '1')
    return text

def is_valid_plate(text):
    pattern = r'^[A-Z]{2,3}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4}$'
    return re.match(pattern, text) is not None

def initialize_plate_cache():
    global existing_plates
    if not os.path.exists(filename):
        existing_plates = {}
        return
    # ensure CSV has a User column; backfill existing rows with empty User if missing
    try:
        with open(filename, newline='', encoding='utf-8') as f:
            sample = f.read()
        if 'User' not in sample and 'user' not in sample:
            # rewrite CSV with an added User column (empty for existing rows)
            rows = []
            with open(filename, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for r in reader:
                    rows.append(r)
            if rows:
                header = rows[0]
                # append User to header and empty value to each row
                new_rows = []
                new_header = header + ['User']
                new_rows.append(new_header)
                for r in rows[1:]:
                    new_rows.append(r + [''])
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(new_rows)
    except Exception:
        # if normalization fails, proceed; initialize_plate_cache will still try to read rows
        pass
    # Recompute counts by counting rows across CSV and initialize last_seen times
    counts = {}
    seen = {}
    with open(filename, newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if not row:
                continue
            plate = (row.get('Plate Text') or row.get('plate') or row.get('plate text') or row.get('Plate') or '')
            plate = plate.strip().upper() if plate else ''
            if not plate:
                continue
            # increment count per detection row
            counts[plate] = counts.get(plate, 0) + 1
            # parse date/time from row to compute last seen
            date = (row.get('Date') or row.get('date') or '').strip()
            time = (row.get('Time') or row.get('time') or '').strip()
            # read user if present
            user = (row.get('User') or row.get('user') or '').strip()
            if date and time:
                try:
                    dt = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M:%S')
                    # keep the latest datetime per plate
                    if plate not in seen or dt > seen[plate]:
                        seen[plate] = dt
                except Exception:
                    pass
    existing_plates = counts
    # initialize last_seen dict
    for p, dt in seen.items():
        last_seen[p] = dt


def get_last_seen_iso():
    """Return a mapping plate -> last seen as ISO string (or empty)."""
    out = {}
    for p, dt in last_seen.items():
        try:
            out[p] = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            out[p] = ''
    return out


def get_top_n(n=5):
    """Return list of (plate, count) sorted by count desc."""
    items = sorted(existing_plates.items(), key=lambda x: x[1], reverse=True)
    return items[:n]

def save_plate_to_csv(plate_text, confidence=1.0, threshold=0.6, plate_img=None):
    global existing_plates, last_saved_plate

    try:
        if isinstance(confidence, (list, tuple)):
            confidence = confidence[0]
        if hasattr(confidence, 'item'):
            confidence = confidence.item()
        confidence = float(confidence)
    except Exception:
        return

    if confidence < threshold:
        return

    plate_text = normalize_plate(plate_text)
    if not is_valid_plate(plate_text):
        return

    # dedupe: skip saving if we've seen the same plate within DEDUPE_SECONDS
    prev_dt = last_seen.get(plate_text)
    now = datetime.now()
    if prev_dt and (now - prev_dt).total_seconds() < DEDUPE_SECONDS:
        return

    # store every valid detection as a separate row (one detection -> one CSV row)

    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    # record last seen time for this plate
    last_seen[plate_text] = now

    # update in-memory count
    count = existing_plates.get(plate_text, 0) + 1
    existing_plates[plate_text] = count

    image_filename = f"{plate_text.replace(' ', '_')}_{date_str}_{time_str.replace(':', '-')}.jpg"
    image_path = os.path.join(snapshot_dir, image_filename)
    if plate_img is not None:
        import cv2
        cv2.imwrite(image_path, plate_img)

    # determine user for this detection: prefer environment variable set by the webapp when starting the detector
    username = os.environ.get('DETECTOR_USER', '')

    file_exists = os.path.isfile(filename)
    # ensure CSV has header with User column before writing
    if not file_exists:
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            fieldnames = ['Plate Text', 'Date', 'Time', 'Image Path', 'User']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
    # append a new row for this detection including the user who started the detector
    try:
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            fieldnames = ['Plate Text', 'Date', 'Time', 'Image Path', 'User']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writerow({'Plate Text': plate_text, 'Date': date_str, 'Time': time_str, 'Image Path': image_path, 'User': username})
    except Exception:
        # fallback: append CSV row using writer directly
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([plate_text, date_str, time_str, image_path, username])