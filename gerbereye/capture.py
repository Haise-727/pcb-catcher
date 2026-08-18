"""Camera capture with locked settings.

FR-006. The single most important thing this module does is disable the
camera's automatic exposure, focus and white balance. Auto modes re-expose
between the golden capture and the live frame, which shifts every pixel and
manufactures defect regions on a perfectly good board. Illumination stability
dominates the false-call rate more than any algorithm choice downstream
(RSK-02), so a camera that refuses manual control reports a degraded state
rather than quietly carrying on.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import config


@dataclass
class CaptureState:
    """What the capture subsystem currently is, for the operator UI."""

    connected: bool = False
    settings_locked: bool = False
    # Set when the driver refused manual control. Inspections taken in this
    # state are still useful, but they are marked degraded rather than
    # presented as trustworthy (FR-006 A1).
    degraded_reason: str | None = None


class Camera:
    """Single-camera wrapper.

    Holds one cv2.VideoCapture behind a lock. The MJPEG stream and the
    inspection trigger both read frames, and OpenCV capture objects are not
    thread-safe, so every read goes through the same mutex.
    """

    def __init__(self, cam_config=config.CAMERA) -> None:
        self._config = cam_config
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self.state = CaptureState()

    def open(self) -> CaptureState:
        """Open the camera and lock its settings. Safe to call repeatedly."""
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return self.state

            cap = cv2.VideoCapture(self._config.index)
            if not cap.isOpened():
                cap.release()
                self._cap = None
                self.state = CaptureState(
                    connected=False,
                    settings_locked=False,
                    degraded_reason=f"no camera at index {self._config.index}",
                )
                return self.state

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
            cap.set(cv2.CAP_PROP_FPS, self._config.fps)

            self._cap = cap
            locked, reason = self._lock_settings(cap) if self._config.lock_settings else (False, "locking disabled")
            self.state = CaptureState(
                connected=True, settings_locked=locked, degraded_reason=reason
            )
            return self.state

    def _lock_settings(self, cap: cv2.VideoCapture) -> tuple[bool, str | None]:
        """Switch exposure, focus and white balance to manual.

        Returns (locked, reason_if_not). Driver support varies widely across
        USB webcams, so each property is set independently and a partial
        failure degrades rather than aborts -- a board inspected under
        semi-locked settings is still better than no inspection at all.
        """
        failures: list[str] = []

        # 0.25 is the V4L2 magic value for "manual exposure" on most UVC
        # webcams; 0.75 means auto. There is no portable constant for this.
        if not cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25):
            failures.append("auto-exposure")
        if not cap.set(cv2.CAP_PROP_EXPOSURE, self._config.manual_exposure):
            failures.append("exposure")
        if not cap.set(cv2.CAP_PROP_AUTOFOCUS, 0):
            failures.append("autofocus")
        if not cap.set(cv2.CAP_PROP_FOCUS, self._config.manual_focus):
            failures.append("focus")
        if not cap.set(cv2.CAP_PROP_AUTO_WB, 0):
            failures.append("auto-white-balance")
        if not cap.set(cv2.CAP_PROP_WB_TEMPERATURE, self._config.manual_wb_kelvin):
            failures.append("white-balance")

        if failures:
            return False, "driver refused manual control of: " + ", ".join(failures)
        return True, None

    def read(self) -> np.ndarray | None:
        """Grab one frame as BGR, or None if the camera is unavailable."""
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ok, frame = self._cap.read()
            if not ok:
                # A read failure on an open handle usually means the cable was
                # pulled. Reflect that so the UI can say so (NFR-010).
                self.state = CaptureState(
                    connected=False, settings_locked=False, degraded_reason="camera disconnected"
                )
                return None
            return frame

    def release(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self.state = CaptureState()


def save_frame(frame: np.ndarray, path: Path) -> Path:
    """Write a frame to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    return path


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buffer.tobytes()


def measure_frame_stability(camera: Camera, samples: int = 100) -> dict[str, float]:
    """Capture N static frames and report how much the image drifts.

    This is the gate for AC-006.2 and the bench check in issue #3: mean
    per-pixel variation must sit below 2 levels on an 8-bit scale before any
    threshold tuning is worth doing. Tuning a threshold against unstable frames
    produces a number that stops being true the moment the light changes.

    Returns mean/max absolute deviation from the mean frame, in grey levels.
    """
    frames: list[np.ndarray] = []
    for _ in range(samples):
        frame = camera.read()
        if frame is None:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32))

    if len(frames) < 2:
        return {"samples": float(len(frames)), "mean_deviation": float("nan"), "max_deviation": float("nan")}

    stack = np.stack(frames, axis=0)
    mean_frame = stack.mean(axis=0)
    deviation = np.abs(stack - mean_frame)
    return {
        "samples": float(len(frames)),
        "mean_deviation": float(deviation.mean()),
        "max_deviation": float(deviation.max()),
    }
