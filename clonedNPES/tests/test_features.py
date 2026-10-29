"""Integration tests for the newer API features: stats, health, pagination,
plate deletion, vehicle registry, and filtered exports."""
import csv
import json

import pytest

import webapp
import plate_utils
from database_utils import save_detection_to_db
from conftest import login, register


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Plate Text', 'Date', 'Time', 'Image Path', 'User'])
        w.writerows(rows)


# ---------------------------------------------------------------- /api/health
def test_health_reports_ok(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['MH12AB1234', '2026-01-01', '11:00:00', '', 'omkar'],
               ['XY34CD5678', '2026-01-02', '09:00:00', '', 'omkar']])
    data = client.get('/api/health').get_json()
    assert data['status'] == 'ok'
    assert data['detection_running'] is False
    assert data['total_detections'] == 3
    assert data['unique_plates'] == 2
    assert 'time' in data


def test_health_survives_broken_detection_module(client, isolated_storage, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'web_detection', None)
    data = client.get('/api/health').get_json()
    assert data['status'] == 'ok'
    assert data['detection_running'] is False


# ---------------------------------------------------------------- pagination
@pytest.fixture
def many_rows(client, isolated_storage):
    register(client, 'omkar', 'secret123')
    write_csv(isolated_storage / 'detected_plates.csv',
              [[f'P{i:05d}', '2026-01-01', f'{i // 60:02d}:{i % 60:02d}:00', '', 'omkar']
               for i in range(25)])
    return client


def test_plates_returns_all_by_default(many_rows):
    data = many_rows.get('/api/plates').get_json()
    assert len(data) == 25
    assert many_rows.get('/api/plates').headers['X-Total-Count'] == '25'


def test_plates_limit_and_offset(many_rows):
    rv = many_rows.get('/api/plates?limit=10&offset=5')
    assert len(rv.get_json()) == 10
    assert rv.headers['X-Total-Count'] == '25'
    rv2 = many_rows.get('/api/plates?limit=10&offset=20')
    assert len(rv2.get_json()) == 5  # clamped to remaining rows


def test_plates_pagination_survives_bad_values(many_rows):
    rv = many_rows.get('/api/plates?limit=abc&offset=xyz')
    assert rv.status_code == 200
    assert len(rv.get_json()) == 25  # falls back to unpaginated


def test_plates_limit_zero_returns_all(many_rows):
    assert len(many_rows.get('/api/plates?limit=0').get_json()) == 25


def test_plates_pagination_combines_with_filters(many_rows):
    data = many_rows.get('/api/plates?plate=P00000&limit=5').get_json()
    assert len(data) == 1


# ---------------------------------------------------------------- delete plate
def test_delete_plate_unauthorized(client, isolated_storage):
    assert client.delete('/api/plates/MH12AB1234').status_code == 401


def test_delete_plate_removes_csv_and_db_rows(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['MH12AB1234', '2026-01-01', '11:00:00', '', 'omkar'],
               ['XY34CD5678', '2026-01-01', '12:00:00', '', 'omkar']])
    save_detection_to_db('MH12AB1234', 0.9, '', user='omkar')
    save_detection_to_db('XY34CD5678', 0.9, '', user='omkar')
    register(client, 'omkar', 'secret123')

    rv = client.delete('/api/plates/mh12ab1234')  # case-insensitive target
    assert rv.status_code == 200
    assert rv.get_json() == {'status': 'deleted', 'removed': 2}

    with open(isolated_storage / 'detected_plates.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert [r['Plate Text'] for r in rows] == ['XY34CD5678']

    remaining = [r['plate_text'] for r in client.get('/api/db/test').get_json()]
    assert remaining == ['XY34CD5678']


def test_delete_plate_missing_returns_404(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.delete('/api/plates/ZZZZ9999')
    assert rv.status_code == 404
    assert rv.get_json()['status'] == 'not_found'


def test_delete_last_plate_leaves_header_only_csv(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.delete('/api/plates/MH12AB1234')
    assert rv.status_code == 200
    with open(isolated_storage / 'detected_plates.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    assert rows == [['Plate Text', 'Date', 'Time', 'Image Path', 'User']]


# ---------------------------------------------------------------- /api/stats
def test_stats_day_hour_aggregation(client, isolated_storage):
    write_csv(isolated_storage / 'detected_plates.csv',
              [['AAAA1111', '2026-01-01', '10:15:00', '', 'omkar'],
               ['AAAA1111', '2026-01-01', '10:45:00', '', 'omkar'],
               ['BBBB2222', '2026-01-01', '11:05:00', '', 'omkar'],
               ['CCCC3333', '2026-01-02', '23:59:00', '', 'omkar']])
    # 'top' comes from the in-memory cache that production loads at startup
    plate_utils.initialize_plate_cache()
    register(client, 'omkar', 'secret123')
    data = client.get('/api/stats').get_json()
    assert data['total'] == 4
    assert data['unique'] == 3
    assert data['per_day'] == {'2026-01-01': 3, '2026-01-02': 1}
    assert data['per_hour'] == {'10': 2, '11': 1, '23': 1}
    assert data['top'][0] == ['AAAA1111', 2]


def test_stats_empty(client, isolated_storage):
    register(client, 'omkar', 'secret123')
    data = client.get('/api/stats').get_json()
    assert data['total'] == 0
    assert data['per_day'] == {}


# ---------------------------------------------------------------- vehicle registry
def test_vehicle_lookup_not_found(client):
    rv = client.get('/api/vehicle/MH12AB1234')
    assert rv.status_code == 404
    assert rv.get_json()['status'] == 'not_found'


def test_vehicle_register_and_lookup(client):
    register(client, 'omkar', 'secret123')
    rv = client.post('/api/vehicle/MH 12 AB 1234', data={
        'owner_name': 'Omkar', 'vehicle_model': 'Honda City',
        'registration_date': '2024-05-01'})
    assert rv.status_code == 200
    assert rv.get_json()['owner_name'] == 'Omkar'
    # lookup normalizes spaces and casing
    rv = client.get('/api/vehicle/mh12ab1234')
    data = rv.get_json()
    assert rv.status_code == 200
    assert data['plate_text'] == 'MH12AB1234'
    assert data['vehicle_model'] == 'Honda City'
    assert data['status'] == 'Active'


def test_vehicle_update_overwrites(client):
    register(client, 'omkar', 'secret123')
    client.post('/api/vehicle/AB12CD3456', data={'owner_name': 'First'})
    rv = client.post('/api/vehicle/AB12CD3456', data={
        'owner_name': 'Second', 'vehicle_model': 'Swift'})
    data = rv.get_json()
    assert data['owner_name'] == 'Second'
    assert data['vehicle_model'] == 'Swift'
    # no duplicate rows
    vehicles = client.get('/api/vehicles').get_json()
    assert len(vehicles) == 1


def test_vehicle_register_requires_owner(client):
    register(client, 'omkar', 'secret123')
    rv = client.post('/api/vehicle/AB12CD3456', data={'vehicle_model': 'X'})
    assert rv.status_code == 400


def test_vehicle_register_requires_session_without_api_key(client):
    rv = client.post('/api/vehicle/AB12CD3456', data={'owner_name': 'A'})
    assert rv.status_code == 401


def test_vehicle_list(client):
    register(client, 'omkar', 'secret123')
    client.post('/api/vehicle/AB12CD3456', data={'owner_name': 'A'})
    client.post('/api/vehicle/MH12AB1234', data={'owner_name': 'B'})
    vehicles = client.get('/api/vehicles').get_json()
    assert [v['plate_text'] for v in vehicles] == ['AB12CD3456', 'MH12AB1234']


def test_vehicle_post_requires_auth_when_api_key_set(client, monkeypatch):
    import webapp
    monkeypatch.setattr(webapp, 'API_KEY', 'tok123')
    rv = client.post('/api/vehicle/AB12CD3456', data={'owner_name': 'A'})
    assert rv.status_code == 401
    rv = client.post('/api/vehicle/AB12CD3456', data={'owner_name': 'A'},
                     headers={'X-API-KEY': 'tok123'})
    assert rv.status_code == 200


# ---------------------------------------------------------------- filtered export
def test_export_csv_with_plate_filter(client, isolated_storage, monkeypatch):
    monkeypatch.chdir(isolated_storage)
    monkeypatch.setattr(webapp, 'CSV_FILE', 'detected_plates.csv')
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['XY34CD5678', '2026-01-01', '11:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.get('/api/export?plate=1234')
    assert rv.status_code == 200
    assert b'MH12AB1234' in rv.data
    assert b'XY34CD5678' not in rv.data


def test_export_csv_with_date_filter(client, isolated_storage, monkeypatch):
    monkeypatch.chdir(isolated_storage)
    monkeypatch.setattr(webapp, 'CSV_FILE', 'detected_plates.csv')
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['MH12AB1234', '2026-02-02', '10:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.get('/api/export?date=2026-02-02')
    body = rv.data.decode('utf-8')
    assert '2026-02-02' in body and '2026-01-01' not in body


def test_export_xlsx_with_plate_filter(client, isolated_storage, monkeypatch):
    import io as _io
    import pandas as pd
    monkeypatch.chdir(isolated_storage)
    monkeypatch.setattr(webapp, 'CSV_FILE', 'detected_plates.csv')
    write_csv(isolated_storage / 'detected_plates.csv',
              [['MH12AB1234', '2026-01-01', '10:00:00', '', 'omkar'],
               ['XY34CD5678', '2026-01-01', '11:00:00', '', 'omkar']])
    register(client, 'omkar', 'secret123')
    rv = client.get('/api/export?plate=1234&format=xlsx')
    assert rv.status_code == 200
    df = pd.read_excel(_io.BytesIO(rv.data))
    assert list(df['Plate Text']) == ['MH12AB1234']
