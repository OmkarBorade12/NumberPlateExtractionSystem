"""Unit tests for camera_handler with a mocked OpenCV capture backend."""
import numpy as np
import pytest

import camera_handler
from camera_handler import CameraHandler


class FakeCapture:
    """Stands in for cv2.VideoCapture."""
    instances = []

    def __init__(self, index, backend):
        self.index = index
        self.backend = backend
        self.opened = True
        self.released = False
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.read_calls = 0
        FakeCapture.instances.append(self)

    def isOpened(self):
        return self.opened and not self.released

    def read(self):
        self.read_calls += 1
        if not self.opened or self.released:
            return False, None
        return True, self.frame.copy()

    def get(self, prop):
        return {1: 1280.0, 3: 1280.0, 4: 720.0, 5: 30.0, 47: 0.0}.get(int(prop), 0.0)

    def set(self, prop, value):
        return True

    def release(self):
        self.released = True


@pytest.fixture
def fake_cv(monkeypatch):
    FakeCapture.instances = []
    monkeypatch.setattr(camera_handler.cv2, 'VideoCapture', FakeCapture)
    return FakeCapture


def test_camera_initializes_with_first_backend(fake_cv):
    cam = CameraHandler(preferred_index=0)
    assert cam.camera_index == 0
    assert cam.is_opened()
    assert cam.cap.backend == camera_handler.cv2.CAP_DSHOW


def test_camera_falls_back_to_next_index(fake_cv, monkeypatch):
    # first two attempts (index 0) fail to open
    original_init = FakeCapture.__init__

    def flaky_init(self, index, backend):
        original_init(self, index, backend)
        if index == 0:
            self.opened = False

    monkeypatch.setattr(FakeCapture, '__init__', flaky_init)
    cam = CameraHandler(preferred_index=0)
    assert cam.camera_index == 1


def test_camera_raises_when_none_available(fake_cv, monkeypatch):
    monkeypatch.setattr(FakeCapture, 'isOpened', lambda self: False)
    with pytest.raises(RuntimeError, match='CAMERA REQUIRED'):
        CameraHandler(preferred_index=0)


def test_camera_rejects_backend_that_cannot_read(fake_cv, monkeypatch):
    original_read = FakeCapture.read

    def dead_read(self):
        self.opened = False
        return False, None

    monkeypatch.setattr(FakeCapture, 'read', dead_read)
    with pytest.raises(RuntimeError):
        CameraHandler(preferred_index=0)


def test_read_returns_frames(fake_cv):
    cam = CameraHandler(preferred_index=0)
    ret, frame = cam.read()
    assert ret is True
    assert frame.shape == (480, 640, 3)
    assert cam.frame_count == 1


def test_read_survives_single_failure(fake_cv):
    cam = CameraHandler(preferred_index=0)
    calls = {'n': 0}

    def flaky_read():
        calls['n'] += 1
        if calls['n'] == 1:
            return False, None
        return True, np.zeros((10, 10, 3), dtype=np.uint8)

    cam.cap.read = flaky_read
    ret, frame = cam.read()
    assert ret is True
    assert frame is not None
    assert calls['n'] == 2  # one failure + the internal retry


def test_read_fails_when_cap_none():
    cam = CameraHandler.__new__(CameraHandler)
    cam.cap = None
    ret, frame = cam.read()
    assert ret is False
    assert frame is None


def test_release(fake_cv):
    cam = CameraHandler(preferred_index=0)
    cam.release()
    assert cam.cap is None
    assert not cam.is_opened()


def test_get_info(fake_cv):
    cam = CameraHandler(preferred_index=0)
    info = cam.get_info()
    assert info['camera_index'] == 0
    assert info['is_opened'] is True
    assert info['width'] == 1280
    assert info['height'] == 720
    assert info['fps'] == 30
