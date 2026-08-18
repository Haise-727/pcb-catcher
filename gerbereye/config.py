"""Application configuration.

Two tiers, per architecture.md §6:
  - Application config (paths, camera index, port) lives here, read at startup.
  - Classification *thresholds* belong per-board-type in the database, not here.

The threshold defaults below are seed values written into a board type's
`thresholds` row when it is created. Once a board type exists, its stored row is
authoritative — editing this file will not change an existing board (ADR-004).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Repository root, resolved from this file so the app works regardless of the
# working directory it was launched from.
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("GERBEREYE_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "gerbereye.db"
GOLDEN_DIR = DATA_DIR / "golden"
IMAGE_DIR = DATA_DIR / "images"


@dataclass(frozen=True)
class ServerConfig:
    # Loopback only. An MSME's design files are its customer's confidential IP,
    # so the process must never be reachable from the factory LAN (NFR-011).
    # Binding 0.0.0.0 here would break the strongest security claim the project
    # makes, so this value is asserted by test rather than left to review.
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass(frozen=True)
class CameraConfig:
    index: int = int(os.environ.get("GERBEREYE_CAMERA_INDEX", "0"))
    width: int = 1920
    height: int = 1080
    fps: int = 30

    # Auto exposure/focus/white-balance silently destroy frame comparability
    # between the golden capture and the live frame, which is the fastest route
    # to a false call on every board. Capture locks these at startup (FR-006).
    lock_settings: bool = True

    # Manual values applied once the auto modes are disabled. These are driver
    # dependent; a webcam that refuses them reports a degraded capture state
    # rather than silently falling back to auto.
    manual_exposure: float = -6.0
    manual_focus: float = 0.0
    manual_wb_kelvin: float = 4600.0


@dataclass(frozen=True)
class ThresholdDefaults:
    """Seed values for a new board type's `thresholds` row.

    These are inferred starting points refined against measured results, not
    IPC-A-610 citations — do not present them as standards-derived.
    """

    # Per-pixel intensity delta above which a pixel counts as "changed".
    diff_intensity: int = 40

    # Contour area (px^2) below which a changed region is treated as noise.
    # Sized for a 1080p frame of a ~100mm board; retune per board type.
    min_region_area: int = 120

    # Gaussian blur kernel applied before differencing, to stop single-pixel
    # sensor noise from generating regions. Must be odd.
    blur_kernel: int = 5

    # ROI = footprint extent x this scale (BR-03).
    roi_scale: float = 1.20


SERVER = ServerConfig()
CAMERA = CameraConfig()
THRESHOLDS = ThresholdDefaults()


def ensure_dirs() -> None:
    """Create the local data directories. Safe to call repeatedly."""
    for directory in (DATA_DIR, GOLDEN_DIR, IMAGE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
