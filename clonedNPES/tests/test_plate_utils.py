"""Unit tests for plate_utils: normalization, validation, CSV persistence, cache init."""
import csv
import os

import numpy as np
import pytest

import plate_utils
from plate_utils import (
    normalize_plate,
    is_valid_plate,
    save_plate_to_csv,
    initialize_plate_cache,
    get_top_n,
    get_last_seen_iso,
)


# ---------------------------------------------------------------- normalize_plate
@pytest.mark.parametrize('raw,expected', [
    ('mh12ab1234', 'MH12AB1234'),          # uppercase + strip
    ('  MH 12 AB 1234  ', 'MH 12 AB 1234'),
    ('MO1I2', 'M0112'),                    # O->0, I->1
    ('a b\t c', 'A B C'),                  # collapse whitespace
])
def test_normalize_plate_basic(raw, expected):
    assert normalize_plate(raw) == expected


@pytest.mark.parametrize('placeholder', ['PLATE', 'NO OCR', 'UNKNOWN'])
def test_normalize_plate_preserves_placeholders(placeholder):
    assert normalize_plate(placeholder.lower()) == placeholder.upper()


# ---------------------------------------------------------------- is_valid_plate
@pytest.mark.parametrize('plate,expected', [
    ('MH12AB1234', True),
    ('AB1234', True),
    ('PLATE', True),          # placeholder allowed for manual review
    ('NO OCR', True),
    ('UNKNOWN', True),
    ('ABC', False),           # too short
    ('', False),
    ('ABCD', False),          # no digits
    ('12', False),            # too short
])
def test_is_valid_plate(plate, expected):
    assert is_valid_plate(plate) is expected


# ---------------------------------------------------------------- save_plate_to_csv
def test_save_skips_low_confidence(isolated_storage):
    save_plate_to_csv('MH12AB1234', confidence=0.3)
    assert not os.path.exists(plate_utils.filename)


def test_save_skips_invalid_plate(isolated_storage):
    save_plate_to_csv('AB', confidence=0.9)
    assert not os.path.exists(plate_utils.filename)


def test_save_skips_non_numeric_confidence(isolated_storage):
    save_plate_to_csv('MH12AB1234', confidence='not-a-number')
    assert not os.path.exists(plate_utils.filename)


def test_save_accepts_confidence_list_and_np_scalar(isolated_storage):
    save_plate_to_csv('MH12AB1234', confidence=[0.9, 0.8])
    save_plate_to_csv('XY34CD5678', confidence=np.float64(0.95))
    with open(plate_utils.filename, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    assert len(rows) == 3  # header + 2 rows
    assert rows[0] == ['Plate Text', 'Date', 'Time', 'Image Path', 'User']


def test_save_writes_row_and_updates_counts(isolated_storage):
    save_plate_to_csv('MH12AB1234', confidence=0.9)
    with open(plate_utils.filename, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]['Plate Text'] == 'MH12AB1234'
    assert plate_utils.existing_plates['MH12AB1234'] == 1
    assert 'MH12AB1234' in plate_utils.last_seen


def test_save_records_user_from_env(isolated_storage, monkeypatch):
    monkeypatch.setenv('DETECTOR_USER', 'omkar')
    save_plate_to_csv('MH12AB1234', confidence=0.9)
    with open(plate_utils.filename, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert rows[0]['User'] == 'omkar'


def test_save_writes_snapshot_image(isolated_storage):
    import cv2
    img = np.zeros((60, 200, 3), dtype=np.uint8)
    save_plate_to_csv('MH12AB1234', confidence=0.9, plate_img=img)
    files = os.listdir(isolated_storage / 'snapshots')
    assert len(files) == 1
    assert files[0].startswith('MH12AB1234_')


def test_dedupe_window_blocks_rapid_repeat(isolated_storage, monkeypatch):
    monkeypatch.setattr(plate_utils, 'DEDUPE_SECONDS', 60)
    save_plate_to_csv('MH12AB1234', confidence=0.9)
    save_plate_to_csv('MH12AB1234', confidence=0.9)
    with open(plate_utils.filename, newline='', encoding='utf-8') as f:
        assert len(list(csv.DictReader(f))) == 1


def test_repeat_after_dedupe_window_is_saved(isolated_storage, monkeypatch):
    import datetime
    monkeypatch.setattr(plate_utils, 'DEDUPE_SECONDS', 5)
    save_plate_to_csv('MH12AB1234', confidence=0.9)
    plate_utils.last_seen['MH12AB1234'] -= datetime.timedelta(seconds=10)
    save_plate_to_csv('MH12AB1234', confidence=0.9)
    with open(plate_utils.filename, newline='', encoding='utf-8') as f:
        assert len(list(csv.DictReader(f))) == 2


# ---------------------------------------------------------------- initialize_plate_cache
def test_initialize_cache_counts_rows(isolated_storage):
    with open(plate_utils.filename, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Plate Text', 'Date', 'Time', 'Image Path', 'User'])
        w.writerow(['MH12AB1234', '2026-01-01', '10:00:00', '', ''])
        w.writerow(['MH12AB1234', '2026-01-01', '11:00:00', '', ''])
        w.writerow(['XY34CD5678', '2026-01-01', '12:00:00', '', ''])
    initialize_plate_cache()
    assert plate_utils.existing_plates == {'MH12AB1234': 2, 'XY34CD5678': 1}
    assert plate_utils.last_seen['MH12AB1234'].strftime('%H:%M:%S') == '11:00:00'


def test_initialize_cache_backfills_user_column(isolated_storage):
    with open(plate_utils.filename, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Plate Text', 'Date', 'Time', 'Image Path'])
        w.writerow(['MH12AB1234', '2026-01-01', '10:00:00', 'snap.jpg'])
    initialize_plate_cache()
    with open(plate_utils.filename, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    assert 'User' in header
    assert all(len(r) == len(header) for r in rows)


def test_initialize_cache_missing_file(isolated_storage):
    initialize_plate_cache()
    assert plate_utils.existing_plates == {}


# ---------------------------------------------------------------- accessors
def test_get_top_n_sorted(isolated_storage):
    plate_utils.existing_plates = {'A1': 2, 'B2': 5, 'C3': 1}
    assert get_top_n(2) == [('B2', 5), ('A1', 2)]


def test_get_last_seen_iso_format(isolated_storage):
    import datetime
    plate_utils.last_seen = {'A1': datetime.datetime(2026, 1, 2, 3, 4, 5)}
    assert get_last_seen_iso() == {'A1': '2026-01-02 03:04:05'}
