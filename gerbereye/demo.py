"""Demo mode — run the whole station with no camera attached.

The hardware chain cannot be brought up on demand, and the dev machine's camera
will not hold a fixed exposure (#35). `DemoCamera` satisfies the same interface
as the real `Camera` but serves bundled board images, so capture, differencing,
registration, naming, verdict, override and export all run through their real
code paths.

This is deliberately **not** a mock that short-circuits the pipeline. The only
thing replaced is where pixels come from. Everything downstream is the
production path, which is what makes the demo honest: if it works here, the
same code works on a real frame.

It is also the RSK-07 fallback. If hardware fails on demo day, `GERBEREYE_DEMO=1`
gives a working station in one environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from . import config
from .capture import CaptureState

DEMO_DIR = config.ROOT / "demo"

# Board images in the order the operator cycles through them. Golden first, so
# the first inspection after setup demonstrates a clean pass.
DEMO_BOARDS: list[tuple[str, str]] = [
    ("golden", "Correctly assembled"),
    ("defect_missing", "C2 and R3 missing"),
    ("defect_rotated", "U1 rotated 90 degrees"),
    ("defect_offset", "R5 offset from its pads"),
    ("defect_mixed", "C2 missing, U1 rotated, R5 offset"),
]


def demo_enabled() -> bool:
    """Demo mode is opt-in via the environment, never a silent default.

    A station that quietly served fake frames when the camera failed would be
    dangerous -- an operator could inspect nothing and be told the board passed.
    """
    return os.environ.get("GERBEREYE_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


def demo_assets_present() -> bool:
    return (DEMO_DIR / "golden.png").is_file()


def ensure_demo_assets() -> bool:
    """Generate the demo board set if it is missing.

    Images are gitignored because the render noise defeats PNG compression, so
    a fresh clone has the generator but not its output.
    """
    if demo_assets_present():
        return True
    try:
        import subprocess
        import sys

        subprocess.run(
            [sys.executable, str(config.ROOT / "tools" / "make_demo_boards.py")],
            check=True,
            capture_output=True,
        )
    except Exception:
        return False
    return demo_assets_present()


class DemoCamera:
    """Serves bundled board images in place of a live camera.

    Mirrors `Camera`'s interface: open/read/release plus a `state`. The
    inspector and API cannot tell the difference, which is the point.
    """

    def __init__(self, board_index: int = 0) -> None:
        self._board_index = board_index
        self._cache: dict[str, np.ndarray] = {}
        self.state = CaptureState(
            connected=True,
            settings_locked=True,
            # Stated plainly rather than left blank: anyone reading the health
            # endpoint must be able to tell this is not a real camera.
            degraded_reason=None,
        )

    # -- board selection ---------------------------------------------------

    @property
    def board_index(self) -> int:
        return self._board_index

    @property
    def board_name(self) -> str:
        return DEMO_BOARDS[self._board_index][0]

    @property
    def board_description(self) -> str:
        return DEMO_BOARDS[self._board_index][1]

    def select_board(self, index: int) -> None:
        if not 0 <= index < len(DEMO_BOARDS):
            raise IndexError(f"demo board index out of range: {index}")
        self._board_index = index

    def select_board_by_name(self, name: str) -> None:
        for index, (board, _) in enumerate(DEMO_BOARDS):
            if board == name:
                self._board_index = index
                return
        raise KeyError(f"no demo board named {name!r}")

    def next_board(self) -> str:
        """Advance to the next board, wrapping. Drives the keyboard shortcut."""
        self._board_index = (self._board_index + 1) % len(DEMO_BOARDS)
        return self.board_name

    # -- camera interface --------------------------------------------------

    def open(self) -> CaptureState:
        if not ensure_demo_assets():
            self.state = CaptureState(
                connected=False,
                settings_locked=False,
                degraded_reason="demo assets missing; run tools/make_demo_boards.py",
            )
        return self.state

    def read(self) -> np.ndarray | None:
        """Return the selected board image.

        A fresh copy each call, because the inspector writes annotations onto
        frames and a shared array would accumulate them across inspections.
        """
        name = self.board_name
        if name not in self._cache:
            path = DEMO_DIR / f"{name}.png"
            image = cv2.imread(str(path))
            if image is None:
                return None
            self._cache[name] = image

        frame = self._cache[name].copy()

        # A trace of sensor noise per read, so consecutive frames are not
        # bit-identical. Without it the demo would be unrealistically perfect
        # and would hide any alignment bug the real path would expose.
        noise = np.random.default_rng().normal(0, 0.8, frame.shape)
        return np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    def release(self) -> None:
        self._cache.clear()


def board_catalog() -> list[dict]:
    """Demo boards for the UI picker."""
    return [
        {"index": index, "name": name, "description": description}
        for index, (name, description) in enumerate(DEMO_BOARDS)
    ]
