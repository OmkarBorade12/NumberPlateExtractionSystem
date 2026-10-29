"""Unit tests for the web detection engine with mocked YOLO and OCR models."""
import os
import sys
import time
import types

import numpy as np
import pytest

import plate_utils
import web_detection
from web_detection import WebANPREngine, parse_ocr_result


# ---------------------------------------------------------------- OCR result parsing
def test_parse_ocr_format_a_picks_best_confidence():
    # det+rec format: [[ [box, [text, score]], ... ]]
    results = [[
        [[[0, 0], [1, 1]], ['BAD', 0.4]],
        [[[0, 0], [2, 2]], ['MH12AB1234', 0.95]],
    ]]
    assert parse_ocr_result(results) == ('MH12AB1234', 0.95)


def test_parse_ocr_format_b_single_tuple():
    assert parse_ocr_result([[('MH12AB1234', 0.9)]]) == ('MH12AB1234', 0.9)


def test_parse_ocr_format_c_list_of_tuples():
    results = [[('AB12CD3456', 0.88), ('JUNK', 0.2)]]
    assert parse_ocr_result(results) == ('AB12CD3456', 0.88)


def test_parse_ocr_empty_and_malformed():
    assert parse_ocr_result(None) == (None, 0.0)
    assert parse_ocr_result([]) == (None, 0.0)
    assert parse_ocr_result([[]]) == (None, 0.0)
    assert parse_ocr_result([[['just-a-string']]]) == (None, 0.0)
    assert parse_ocr_result('not-a-list') == (None, 0.0)


# ---------------------------------------------------------------- engine lifecycle
@pytest.fixture
def engine():
    return WebANPREngine()


def test_engine_initial_state(engine):
    assert engine.running is False
    assert engine.use_yolo is False
    assert engine.use_ocr is False
    assert engine.get_frame() is None
    assert engine.get_stats() == {'fps': 0, 'detections': 0, 'last_plate': None}


def test_start_stop_lifecycle(engine, monkeypatch):
    monkeypatch.setattr(engine, '_initialize_resources', lambda: True)
    assert engine.start() is True
    assert engine.is_running()
    assert engine.detection_thread is not None
    assert engine.start() is True  # idempotent while running
    assert engine.stop() is True
    assert not engine.is_running()


def test_stop_when_not_running(engine):
    assert engine.stop() is False


def test_start_with_no_camera_runs_demo_mode(engine, monkeypatch):
    # Simulate a machine with no camera: CameraHandler raises
    def no_camera(preferred_index=0):
        raise RuntimeError('CAMERA REQUIRED')

    monkeypatch.setattr(web_detection, 'CameraHandler', no_camera)
    monkeypatch.setattr(engine, '_initialize_resources', lambda: True)
    engine.camera = None
    engine.start()
    try:
        time.sleep(0.5)
        # demo mode should still produce frames via the placeholder generator
        frame = engine.get_frame()
        assert frame is not None
        assert frame.shape == (480, 640, 3)
    finally:
        engine.stop()


# ---------------------------------------------------------------- detection pipeline
class FakeYOLOBoxes:
    def __init__(self, boxes):
        self._boxes = np.array(boxes, dtype=float)

    @property
    def xyxy(self):
        class Cpu:
            def __init__(self, arr):
                self.arr = arr

            def cpu(self):
                return self

            def numpy(self):
                return self.arr
        return Cpu(self._boxes)


class FakeYOLOResult:
    def __init__(self, boxes):
        self.boxes = FakeYOLOBoxes(boxes)


class FakeYOLO:
    def __init__(self, boxes):
        self._boxes = boxes
        self.calls = 0

    def __call__(self, frame, verbose=False):
        self.calls += 1
        return [FakeYOLOResult(self._boxes)]


class FakeOCR:
    def __init__(self, results, conf=0.9):
        self._results = results
        self._conf = conf
        self.calls = 0

    def ocr(self, img, cls=False):
        self.calls += 1
        return self._results


@pytest.fixture
def frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_detect_plate_saves_valid_result(engine, frame, isolated_storage):
    engine.yolo_model = FakeYOLO([[100, 100, 300, 180]])
    engine.ocr_reader = FakeOCR([[[[[0, 0], [1, 1]], ['mh12ab1234', 0.9]]]])
    engine.use_yolo = True
    engine.use_ocr = True

    result = engine._detect_plate(frame)

    assert result is not None
    assert result['text'] == 'MH12AB1234'  # normalized
    assert result['confidence'] == 0.9
    assert result['bbox'] == (100, 100, 300, 180)
    # row persisted
    assert plate_utils.existing_plates.get('MH12AB1234') == 1


def test_detect_plate_no_boxes_returns_none(engine, frame):
    engine.yolo_model = FakeYOLO([])
    engine.ocr_reader = FakeOCR([])
    engine.use_yolo = True
    engine.use_ocr = True
    assert engine._detect_plate(frame) is None
    assert engine.ocr_reader.calls == 0  # OCR skipped when nothing detected


def test_detect_plate_low_confidence_not_saved(engine, frame, isolated_storage):
    engine.yolo_model = FakeYOLO([[100, 100, 300, 180]])
    engine.ocr_reader = FakeOCR([[[[[0, 0], [1, 1]], ['MH12AB1234', 0.2]]]])
    engine.use_yolo = True
    engine.use_ocr = True
    result = engine._detect_plate(frame)
    assert result is not None
    assert plate_utils.existing_plates == {}


def test_detect_plate_placeholder_text_saved_for_review(engine, frame, isolated_storage):
    # OCR loaded but produced nothing -> raw "Plate" placeholder with low threshold
    engine.yolo_model = FakeYOLO([[100, 100, 300, 180]])
    engine.ocr_reader = FakeOCR([[]])
    engine.use_yolo = True
    engine.use_ocr = True
    result = engine._detect_plate(frame)
    assert result['text'] == 'Plate'
    assert plate_utils.existing_plates.get('PLATE') == 1


def test_detect_plate_scales_bbox_to_full_frame(engine, isolated_storage):
    big = np.zeros((1080, 1920, 3), dtype=np.uint8)
    engine.yolo_model = FakeYOLO([[50, 50, 150, 100]])  # in 640x480 space
    engine.ocr_reader = FakeOCR([[[[[0, 0], [1, 1]], ['MH12AB1234', 0.9]]]])
    engine.use_yolo = True
    engine.use_ocr = True
    result = engine._detect_plate(big)
    assert result['bbox'] == (150, 112, 450, 225)


def test_detect_plate_without_ocr_records_no_ocr(engine, frame, isolated_storage, monkeypatch):
    # make `from paddleocr import PaddleOCR` fail without importing the real library
    monkeypatch.setitem(sys.modules, 'paddleocr', types.ModuleType('paddleocr'))
    engine.yolo_model = FakeYOLO([[100, 100, 300, 180]])
    engine.use_yolo = True
    engine.use_ocr = False
    result = engine._detect_plate(frame)
    assert result['text'] in ('No OCR', 'Plate')
    assert plate_utils.existing_plates  # placeholder row saved for manual review


def test_draw_detection_and_overlay(engine, frame):
    detection = {'text': 'MH12AB1234', 'confidence': 0.9, 'bbox': (50, 50, 250, 120)}
    out = engine._draw_detection(frame, detection)
    assert out.shape == frame.shape
    out = engine._add_overlay(out)
    assert out.shape == frame.shape


def test_draw_detection_none_passthrough(engine, frame):
    assert engine._draw_detection(frame, None) is frame


def test_stats_update(engine):
    engine.stats['detections'] += 5
    assert engine.get_stats()['detections'] == 5
