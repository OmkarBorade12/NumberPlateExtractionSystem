"""End-to-end test: boots the real Flask server as a subprocess on port 5001
and exercises register -> login -> start detection -> status -> summary -> stop.

Runs from a temp working directory so real user data is never touched.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 5001
BASE = f'http://127.0.0.1:{PORT}'


def _port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0


class Http:
    """Tiny cookie-aware HTTP helper over urllib."""

    def __init__(self):
        self.cookies = {}

    def request(self, path, data=None, headers=None, method=None):
        headers = dict(headers or {})
        if self.cookies:
            headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        body = urllib.parse.urlencode(data).encode() if data else None
        if body is not None:
            headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        req = urllib.request.Request(f'{BASE}{path}', data=body, headers=headers,
                                     method=method or ('POST' if body else 'GET'))
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req, timeout=15)
        except urllib.error.HTTPError as e:
            resp = e
        self._store_cookies(resp.headers.get_all('Set-Cookie') or [])
        return resp.status, resp.read()

    def _store_cookies(self, set_cookie_headers):
        for header in set_cookie_headers:
            parts = header.split(';')[0].split('=', 1)
            if len(parts) == 2:
                self.cookies[parts[0].strip()] = parts[1].strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('e2e')
    # stage local model files so the engine never triggers a download
    os.makedirs(os.path.join(str(tmp), 'models'), exist_ok=True)
    for src_rel, dst_rel in (('models/anpr_custom_best.pt', 'models/anpr_custom_best.pt'),
                             ('yolov8n.pt', 'yolov8n.pt')):
        src = os.path.join(PROJECT_DIR, src_rel)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(str(tmp), dst_rel))
    env = dict(os.environ)
    env.update({
        'PYTHONIOENCODING': 'utf-8',
        'WEBAPP_DEDUPE_SECONDS': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    # disable the debug reloader so we manage exactly one process
    proc = subprocess.Popen(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0, r"%s"); import webapp; '
         'webapp.app.run(host="127.0.0.1", port=%d, debug=False, use_reloader=False)' % (
             PROJECT_DIR.replace('\\', '\\\\'), PORT)],
        cwd=str(tmp), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            if _port_open(PORT):
                break
            if proc.poll() is not None:
                out = proc.stdout.read().decode('utf-8', errors='replace')
                raise RuntimeError(f'server exited early:\n{out}')
            time.sleep(0.5)
        else:
            raise RuntimeError('server did not become ready in time')
        yield str(tmp)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_full_user_and_detection_workflow(server):
    http = Http()

    # 1. unauthenticated: / redirects to /pro, /pro redirects to /login
    status, _ = http.request('/')
    assert status == 302
    status, _ = http.request('/pro')
    assert status == 302

    # 2. login page renders
    status, body = http.request('/login')
    assert status == 200 and b'login' in body.lower()

    # 3. register a fresh user and land on the dashboard
    status, _ = http.request('/register', data={
        'username': 'e2euser', 'password': 'e2epass123', 'password2': 'e2epass123'})
    assert status == 302
    status, body = http.request('/pro')
    assert status == 200

    # 4. control endpoints require the session we just earned
    status, body = http.request('/api/start', data=b'', method='POST')
    assert status == 200
    assert b'started' in body

    # 5. status flips to running (engine may still be loading models in background)
    deadline = time.time() + 20
    running = False
    while time.time() < deadline:
        status, body = http.request('/api/status')
        assert status == 200
        if b'true' in body.lower():
            running = True
            break
        time.sleep(0.5)
    assert running, f'status never became running: {body!r}'

    # 6. summary + plates endpoints respond with valid JSON
    status, body = http.request('/api/summary')
    assert status == 200
    assert b'total' in body
    status, body = http.request('/api/plates')
    assert status == 200

    # 7. duplicate start is handled gracefully
    status, body = http.request('/api/start', data=b'', method='POST')
    assert status == 200
    assert b'already_running' in body

    # 8. stop detection
    status, body = http.request('/api/stop', data=b'', method='POST')
    assert status == 200
    assert b'stopped' in body

    # 9. logs endpoint responds
    status, body = http.request('/api/logs')
    assert status == 200

    # 10. health endpoint reports system state
    status, body = http.request('/api/health')
    assert status == 200
    assert b'"ok"' in body
    assert b'detection_running' in body

    # 11. stats endpoint aggregates
    status, body = http.request('/api/stats')
    assert status == 200
    assert b'per_day' in body and b'per_hour' in body

    # 12. pagination: limit/offset respected, total count header present
    status, body = http.request('/api/plates?limit=2&offset=0')
    assert status == 200

    # 13. vehicle registry: register then look up
    status, body = http.request('/api/vehicle/E2E01AB1234', data={
        'owner_name': 'E2E Owner', 'vehicle_model': 'Test Model'})
    assert status == 200
    assert b'E2E Owner' in body
    status, body = http.request('/api/vehicle/e2e01ab1234')
    assert status == 200
    assert b'Test Model' in body
    status, body = http.request('/api/vehicles')
    assert status == 200
    assert b'E2E01AB1234' in body

    # 14. unknown vehicle returns 404
    status, body = http.request('/api/vehicle/ZZZ00XX9999')
    assert status == 404

    # 15. logout kills the session
    status, _ = http.request('/logout')
    assert status == 302
    status, _ = http.request('/pro')
    assert status == 302

    # 16. after logout, delete endpoint is refused
    status, body = http.request('/api/plates/E2E01AB1234', method='DELETE')
    assert status == 401


def test_delete_plate_flow(server):
    """Seed a CSV in the server's working directory, then delete a plate over HTTP."""
    import csv as csv_mod

    http = Http()
    status, _ = http.request('/login', data={'username': 'e2euser', 'password': 'e2epass123'})
    assert status == 302

    csv_path = os.path.join(server, 'detected_plates.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv_mod.writer(f)
        w.writerow(['Plate Text', 'Date', 'Time', 'Image Path', 'User'])
        w.writerow(['DEL01AB1234', '2026-01-01', '10:00:00', '', 'e2euser'])
        w.writerow(['DEL01AB1234', '2026-01-01', '11:00:00', '', 'e2euser'])
        w.writerow(['KEEP02CD5678', '2026-01-01', '12:00:00', '', 'e2euser'])

    # delete one plate
    status, body = http.request('/api/plates/del01ab1234', method='DELETE')
    assert status == 200
    assert b'"removed": 2' in body or b'"removed":2' in body

    # verify over HTTP: only the kept plate remains, stats reflect the change
    status, body = http.request('/api/plates')
    assert status == 200
    assert b'KEEP02CD5678' in body
    assert b'DEL01AB1234' not in body
    status, body = http.request('/api/stats')
    assert status == 200
    assert b'"total": 1' in body or b'"total":1' in body

    # deleting an unknown plate returns 404
    status, body = http.request('/api/plates/DEL01AB1234', method='DELETE')
    assert status == 404


def test_wrong_password_rejected(server):
    http = Http()
    status, _ = http.request('/login', data={'username': 'e2euser', 'password': 'nope'})
    assert status == 302
    status, _ = http.request('/pro')
    assert status == 302  # still locked out
