"""Shared pytest fixtures for the ANPR test suite."""
import os
import sys
import types

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import plate_utils  # noqa: E402


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Point every module-level file path at a temp directory and reset global state."""
    snapshots = tmp_path / 'snapshots'
    snapshots.mkdir()

    monkeypatch.setattr(plate_utils, 'filename', str(tmp_path / 'detected_plates.csv'))
    monkeypatch.setattr(plate_utils, 'snapshot_dir', str(snapshots))
    monkeypatch.setattr(plate_utils, 'existing_plates', {})
    monkeypatch.setattr(plate_utils, 'last_seen', {})

    import database_utils
    monkeypatch.setattr(database_utils, 'DB_FILE', str(tmp_path / 'test_anpr.db'))
    database_utils.init_db()

    import webapp
    monkeypatch.setattr(webapp, 'CSV_FILE', str(tmp_path / 'detected_plates.csv'))
    monkeypatch.setattr(webapp, 'USERS_FILE', str(tmp_path / 'users.json'))
    monkeypatch.setattr(webapp, 'SNAPSHOT_DIR', str(snapshots))
    monkeypatch.setattr(webapp, 'LOG_FILE', str(tmp_path / 'detector.log'))
    return tmp_path


@pytest.fixture
def client(isolated_storage, monkeypatch):
    """Flask test client with a fresh temp-backed app (no API key unless a test sets one)."""
    import webapp
    monkeypatch.setattr(webapp, 'API_KEY', None)
    webapp.app.config['TESTING'] = True
    with webapp.app.test_client() as c:
        yield c


@pytest.fixture
def fake_web_detection(monkeypatch):
    """Inject a stub web_detection module so /api/start|stop|status never touch real models."""
    stub = types.ModuleType('web_detection')

    state = {'running': False, 'started': 0, 'stopped': 0, 'stats': {'fps': 30.0, 'detections': 2}}

    def start_detection():
        state['started'] += 1
        state['running'] = True
        return True

    def stop_detection():
        state['stopped'] += 1
        state['running'] = False
        return True

    def is_detection_running():
        return state['running']

    def get_detection_stats():
        return dict(state['stats'])

    stub.start_detection = start_detection
    stub.stop_detection = stop_detection
    stub.is_detection_running = is_detection_running
    stub.get_detection_stats = get_detection_stats
    stub.state = state
    monkeypatch.setitem(sys.modules, 'web_detection', stub)
    return stub


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def register(client, username, password):
    return client.post('/register',
                       data={'username': username, 'password': password, 'password2': password},
                       follow_redirects=True)
