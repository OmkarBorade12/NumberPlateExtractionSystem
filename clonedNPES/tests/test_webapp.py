"""Integration tests for the Flask webapp: auth, pages, and all API endpoints."""
import csv
import io
import json
import os

import numpy as np
import pytest

import plate_utils
import webapp
from conftest import login, register


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Plate Text', 'Date', 'Time', 'Image Path', 'User'])
        w.writerows(rows)


# ---------------------------------------------------------------- routing / auth
def test_root_redirects_to_pro(client):
    rv = client.get('/')
    assert rv.status_code == 302
    assert rv.headers['Location'].endswith('/pro')


def test_pro_requires_login(client):
    rv = client.get('/pro')
    assert rv.status_code == 302
    assert rv.headers['Location'].endswith('/login')


def test_classic_requires_login(client):
    rv = client.get('/classic')
    assert rv.status_code == 302


def test_login_page_renders(client):
    assert client.get('/login').status_code == 200


def test_register_page_renders(client):
    assert client.get('/register').status_code == 200


def test_register_login_logout_flow(client, isolated_storage):
    rv = register(client, 'omkar', 'secret123')
    assert rv.status_code == 200
    assert os.path.exists(isolated_storage / 'users.json')
    users = json.loads((isolated_storage / 'users.json').read_text(encoding='utf-8'))
    assert 'omkar' in users
    # hashed, not plaintext
    assert users['omkar'] != 'secret123'

    client.get('/logout')
    assert client.get('/pro').status_code == 302

    rv = login(client, 'omkar', 'secret123')
    assert rv.status_code == 200
    assert client.get('/pro').status_code == 200


def test_register_rejects_duplicate_username(client, isolated_storage):
    register(client, 'omkar', 'secret123')
    client.get('/logout')
    rv = client.post('/register', data={'username': 'omkar', 'password': 'other123',
                                        'password2': 'other123'})
    assert rv.status_code == 302  # redirected back with flash


def test_register_rejects_password_mismatch(client):
    rv = client.post('/register', data={'username': 'a', 'password': 'secret123',
                                        'password2': 'different'})
    assert rv.status_code == 302
    assert client.get('/pro').status_code == 302  # must not be logged in


def test_register_rejects_short_password(client):
    rv = client.post('/register', data={'username': 'a', 'password': 'abc',
                                        'password2': 'abc'})
    assert rv.status_code == 302


def test_register_rejects_missing_fields(client):
    rv = client.post('/register', data={'username': '', 'password': '', 'password2': ''})
    assert rv.status_code == 302


def test_login_wrong_password(client, isolated_storage):
    register(client, 'omkar', 'secret123')
    client.get('/logout')
    rv = login(client, 'omkar', 'wrongpass')
    assert rv.status_code == 200
    # session must not be set -> /pro still redirects
    assert client.get('/pro').status_code == 302


def test_login_missing_fields(client):
    rv = client.post('/login', data={'username': '', 'password': ''})
    assert rv.status_code == 302


def test_logout(client, isolated_storage):
    register(client, 'omkar', 'secret123')
    rv = client.get('/logout', follow_redirects=True)
    assert rv.status_code == 200
    assert client.get('/pro').status_code == 302


# ---------------------------------------------------------------- /api/plates
def test_api_plates_empty_when_logged_out(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', 'x.jpg', 'omkar']])
    rv = client.get('/api/plates')
    assert rv.status_code == 200
    assert rv.get_json() == []


def test_api_plates_scoped_to_logged_in_user(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', 'x.jpg', 'omkar'],
               ['XY34CD5678', '2026-01-01', '11:00:00', 'y.jpg', 'someoneelse']])
    register(client, 'omkar', 'secret123')
    data = client.get('/api/plates').get_json()
    assert len(data) == 1
    assert data[0]['plate'] == 'MH12AB1234'


def test_api_plates_plate_and_date_filters(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['MH12AB9999', '2026-01-02', '11:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    data = client.get('/api/plates?plate=1234').get_json()
    assert len(data) == 1 and data[0]['plate'] == 'MH12AB1234'
    data = client.get('/api/plates?date=2026-01-02').get_json()
    assert len(data) == 1 and data[0]['plate'] == 'MH12AB9999'


def test_api_plates_newest_first(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['AAAA1111', '2026-01-01', '10:00:00', '', 'omkar'],
               ['BBBB2222', '2026-01-01', '11:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    data = client.get('/api/plates').get_json()
    assert data[0]['plate'] == 'BBBB2222'


# ---------------------------------------------------------------- /api/latest + /api/summary
def test_api_latest_default_and_limit(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [[f'P{i:05d}', '2026-01-01', f'10:{i:02d}:00', '', 'omkar'] for i in range(15)])
    register(client, 'omkar', 'secret123')
    assert len(client.get('/api/latest').get_json()) == 10
    assert len(client.get('/api/latest?n=3').get_json()) == 3


def test_api_latest_survives_bad_n(client, isolated_storage):
    """Regression: non-numeric n used to raise a 500."""
    write_csv(isolated_storage / 'detected_plates.csv',
              [['AAAA1111', '2026-01-01', '10:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.get('/api/latest?n=abc')
    assert rv.status_code == 200
    assert len(rv.get_json()) == 1


def test_api_summary(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['MH12AB1234', '2026-01-01', '11:00:00', '', 'omkar'],
               ['XY34CD5678', '2026-01-01', '12:00:00', '', 'omkar']])
    # production loads counts into memory at startup (webapp.__main__)
    plate_utils.initialize_plate_cache()
    register(client, 'omkar', 'secret123')
    data = client.get('/api/summary').get_json()
    assert data['total'] == 3
    assert data['unique'] == 2
    assert list(data['top'][0]) == ['MH12AB1234', 2]


# ---------------------------------------------------------------- control + status APIs
def test_api_start_unauthorized(client):
    rv = client.post('/api/start')
    assert rv.status_code == 401
    assert rv.get_json()['status'] == 'unauthorized'


def test_api_stop_unauthorized(client):
    assert client.post('/api/stop').status_code == 401


def test_api_export_unauthorized(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    assert client.get('/api/export').status_code == 401


def test_api_start_authenticated(client, fake_web_detection):
    register(client, 'omkar', 'secret123')
    rv = client.post('/api/start')
    assert rv.status_code == 200
    assert rv.get_json()['status'] == 'started'
    assert fake_web_detection.state['started'] == 1


def test_api_start_already_running(client, fake_web_detection):
    register(client, 'omkar', 'secret123')
    client.post('/api/start')
    assert client.post('/api/start').get_json()['status'] == 'already_running'


def test_api_stop_when_not_running(client, fake_web_detection):
    register(client, 'omkar', 'secret123')
    assert client.post('/api/stop').get_json()['status'] == 'not_running'


def test_api_stop_running(client, fake_web_detection):
    register(client, 'omkar', 'secret123')
    client.post('/api/start')
    assert client.post('/api/stop').get_json()['status'] == 'stopped'
    assert fake_web_detection.state['stopped'] == 1


def test_api_start_sets_detector_user_env(client, fake_web_detection, monkeypatch):
    register(client, 'omkar', 'secret123')
    monkeypatch.delenv('DETECTOR_USER', raising=False)
    client.post('/api/start')
    assert os.environ.get('DETECTOR_USER') == 'omkar'


def test_api_status(client, fake_web_detection):
    assert client.get('/api/status').get_json() == {'running': False, 'stats': {}}
    fake_web_detection.state['running'] = True
    data = client.get('/api/status').get_json()
    assert data['running'] is True
    assert data['stats']['fps'] == 30.0


def test_api_status_when_detection_module_broken(client, monkeypatch):
    # simulate import failure of web_detection
    import sys
    monkeypatch.delitem(sys.modules, 'web_detection', raising=False)
    monkeypatch.setitem(sys.modules, 'web_detection', None)  # import raises ImportError
    assert client.get('/api/status').get_json() == {'running': False, 'stats': {}}


# ---------------------------------------------------------------- db, logs, snapshots, export
def test_api_db_test_roundtrip(client, isolated_storage):
    from database_utils import save_detection_to_db
    save_detection_to_db('MH12AB1234', 0.9, 'x.jpg', user='omkar')
    data = client.get('/api/db/test').get_json()
    assert isinstance(data, list) and data[0]['plate_text'] == 'MH12AB1234'


def test_api_logs_empty(client):
    assert client.get('/api/logs').get_json() == {'lines': []}


def test_api_logs_returns_tail(client, isolated_storage):
    log = isolated_storage / 'detector.log'
    log.write_text('\n'.join(f'line{i}' for i in range(300)), encoding='utf-8')
    lines = client.get('/api/logs').get_json()['lines']
    assert len(lines) == 200
    assert lines[-1] == 'line299'


def test_snapshot_serving(client, isolated_storage):
    snap = isolated_storage / 'snapshots' / 'test.jpg'
    snap.write_bytes(b'\xff\xd8fakejpg')
    assert client.get('/snapshots/test.jpg').status_code == 200
    assert client.get('/snapshots/missing.jpg').status_code == 404


def test_api_export_csv(client, isolated_storage, monkeypatch):
    # the CSV export resolves the file relative to cwd, matching production layout
    monkeypatch.chdir(isolated_storage)
    monkeypatch.setattr(webapp, 'CSV_FILE', 'detected_plates.csv')
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.get('/api/export')
    assert rv.status_code == 200
    assert 'detected_plates.csv' in rv.headers.get('Content-Disposition', '')
    assert b'MH12AB1234' in rv.data


def test_api_export_xlsx(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.get('/api/export?format=xlsx')
    assert rv.status_code == 200
    # xlsx files start with the PK zip magic
    assert rv.data[:2] == b'PK'


def test_api_export_no_file(client):
    register(client, 'omkar', 'secret123')
    assert client.get('/api/export').status_code == 404


def test_api_key_token_auth(client, isolated_storage, monkeypatch):
    """With WEBAPP_API_KEY set, control endpoints accept the header and reject others."""
    monkeypatch.setattr(webapp, 'API_KEY', 'tok123')
    monkeypatch.chdir(isolated_storage)
    monkeypatch.setattr(webapp, 'CSV_FILE', 'detected_plates.csv')
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    assert client.get('/api/export').status_code == 401
    assert client.get('/api/export', headers={'X-API-KEY': 'wrong'}).status_code == 401
    assert client.get('/api/export', headers={'X-API-KEY': 'tok123'}).status_code == 200
    # and pages no longer demand a session when the API key is configured
    assert client.get('/pro').status_code == 200


def test_api_plates_with_api_key_sees_all_rows(client, isolated_storage, monkeypatch):
    monkeypatch.setattr(webapp, 'API_KEY', 'tok123')
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    data = client.get('/api/plates').get_json()
    assert len(data) == 1


# ---------------------------------------------------------------- misc helpers
def test_create_placeholder_frame():
    frame = webapp.create_placeholder_frame()
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8


def test_video_feed_streams_multipart(client):
    """The stream must yield JPEG multipart chunks (regression: missing time import)."""
    with client.get('/api/video_feed') as rv:
        assert rv.status_code == 200
        assert 'multipart/x-mixed-replace' in rv.content_type
        chunk = next(rv.response)  # pull exactly one frame, then close the generator
        assert chunk.startswith(b'--frame')
        assert b'\xff\xd8' in chunk  # JPEG SOI marker


def test_users_file_corrupt_returns_empty(client, isolated_storage):
    (isolated_storage / 'users.json').write_text('{broken json', encoding='utf-8')
    assert webapp.load_users() == {}
