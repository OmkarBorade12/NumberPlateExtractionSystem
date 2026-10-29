"""Unit tests for database_utils (SQLite persistence layer)."""
import database_utils
from database_utils import init_db, save_detection_to_db, get_recent_detections


def test_init_db_creates_tables(isolated_storage):
    conn = database_utils.get_db_connection()
    tables = {r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert 'detections' in tables
    assert 'vehicle_registry' in tables


def test_save_and_fetch_detection(isolated_storage):
    detection_id = save_detection_to_db('MH12AB1234', 0.92, 'snapshots/x.jpg', user='omkar')
    assert detection_id is not None
    rows = get_recent_detections()
    assert len(rows) == 1
    assert rows[0]['plate_text'] == 'MH12AB1234'
    assert rows[0]['confidence'] == 0.92
    assert rows[0]['user'] == 'omkar'


def test_save_detection_defaults_to_system_user(isolated_storage, monkeypatch):
    monkeypatch.delenv('DETECTOR_USER', raising=False)
    save_detection_to_db('AB12CD3456', 0.8, 'snapshots/y.jpg')
    rows = get_recent_detections()
    assert rows[0]['user'] == 'System'


def test_save_detection_respects_env_user(isolated_storage, monkeypatch):
    monkeypatch.setenv('DETECTOR_USER', 'envuser')
    save_detection_to_db('AB12CD3456', 0.8, 'snapshots/y.jpg')
    rows = get_recent_detections()
    assert rows[0]['user'] == 'envuser'


def test_recent_limit(isolated_storage):
    for i in range(15):
        save_detection_to_db(f'PLATE{i:02d}', 0.9, '')
    assert len(get_recent_detections(limit=10)) == 10


def test_recent_order_newest_first(isolated_storage):
    save_detection_to_db('FIRST', 0.9, '')
    save_detection_to_db('SECOND', 0.9, '')
    rows = get_recent_detections()
    assert rows[0]['plate_text'] == 'SECOND'


def test_save_failure_returns_none(isolated_storage, monkeypatch):
    monkeypatch.setattr(database_utils, 'get_db_connection',
                        lambda: (_ for _ in ()).throw(RuntimeError('db down')))
    assert save_detection_to_db('X1', 0.9, '') is None
