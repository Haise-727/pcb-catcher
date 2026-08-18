"""Inspection orchestrator.

Owns the sequence a single inspection runs through, and decides which of the
two paths applies. Precedence is FR-015 AC-015.4: where a component map exists
the CAD path runs and adds designator names; otherwise the differencing path
runs alone and regions stay anonymous.

Both paths produce the same region shape and converge on the same verdict
stage, so the caller never branches on which one ran.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from . import config, db
from .capture import Camera, save_frame
from .pipeline import differencing, registration, verdict

# Marker positions on the jig, in design millimetres. Measured once when the
# jig is built (issue #5) and constant thereafter. Overridden per board type
# once more than one jig exists.
DEFAULT_MARKER_POSITIONS_MM: dict[int, tuple[float, float]] = {
    0: (0.0, 0.0),
    1: (60.0, 0.0),
    2: (60.0, 40.0),
    3: (0.0, 40.0),
}


@dataclass
class InspectionOutcome:
    verdict: str
    path_used: str
    regions: list[dict[str, Any]] = field(default_factory=list)
    inspection_id: int | None = None
    registration_state: str | None = None
    registration_residual_px: float | None = None
    degraded: bool = False
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "inspection_id": self.inspection_id,
            "verdict": self.verdict,
            "path_used": self.path_used,
            "regions": self.regions,
            "registration_state": self.registration_state,
            "registration_residual_px": self.registration_residual_px,
            "degraded": self.degraded,
            "message": self.message,
        }


class InspectionError(RuntimeError):
    """Raised when an inspection cannot run at all.

    Distinct from a failed *board*: this means the station could not perform
    the check, which the operator must fix before the result means anything.
    """


def run_inspection(
    conn: sqlite3.Connection,
    camera: Camera,
    board_type_id: int,
    frame: np.ndarray | None = None,
    persist: bool = True,
) -> InspectionOutcome:
    """Capture, compare, name, judge and record one board.

    Args:
        frame: use this frame instead of reading the camera. Lets tests and the
            seeded-defect corpus run the exact same path as a live inspection.
        persist: write the result to the database.
    """
    golden_row = db.latest_golden_reference(conn, board_type_id)
    if golden_row is None:
        raise InspectionError(
            "no golden reference captured for this board type -- capture one first"
        )

    golden = cv2.imread(golden_row["image_path"])
    if golden is None:
        raise InspectionError(f"golden reference unreadable: {golden_row['image_path']}")

    if frame is None:
        frame = camera.read()
    if frame is None:
        raise InspectionError("no frame available from camera")

    thresholds = db.get_thresholds(conn, board_type_id)

    # --- Path A: differencing. Always runs; it is what produces the regions.
    diff = differencing.diff_against_golden(
        live=frame,
        golden=golden,
        diff_intensity=thresholds["diff_intensity"],
        min_region_area=thresholds["min_region_area"],
        blur_kernel=thresholds["blur_kernel"],
    )
    regions = diff.regions
    path_used = "differencing"
    registration_state = None
    residual = None
    degraded = False
    message = None

    # --- Path B: CAD naming. Only when a component map exists for this board.
    components = db.list_components(conn, board_type_id)
    if components:
        detected = registration.detect_markers(frame)
        result = registration.compute_homography(DEFAULT_MARKER_POSITIONS_MM, detected)
        registration_state = result.state.value
        residual = result.residual_px

        if result.ok:
            boxes = registration.project_components(
                result.homography, components, roi_scale=thresholds["roi_scale"]
            )
            regions = registration.name_regions(regions, boxes)
            path_used = "cad"
            degraded = result.state is registration.RegistrationState.DEGRADED
            if degraded:
                message = f"registration degraded ({residual:.1f}px) -- names may be approximate"
        else:
            # Registration failing does not invalidate the differencing result,
            # it only costs the names. Reporting anonymous regions is far more
            # useful than refusing to inspect.
            message = f"CAD naming unavailable: {result.message}. Regions are unnamed."

    board_verdict = verdict.derive_verdict(regions)
    region_dicts = [r.as_dict() for r in regions]

    inspection_id = None
    if persist:
        frame_path = config.IMAGE_DIR / f"inspection_{db.utc_now().replace(':', '-')}.jpg"
        save_frame(frame, frame_path)
        inspection_id = db.record_inspection(
            conn,
            board_type_id=board_type_id,
            verdict=board_verdict.value,
            path_used=path_used,
            regions=region_dicts,
            frame_path=frame_path,
        )
        # Re-read so the caller gets the database ids the UI needs to send an
        # override back against.
        region_dicts = db.list_regions(conn, inspection_id)

    return InspectionOutcome(
        verdict=board_verdict.value,
        path_used=path_used,
        regions=region_dicts,
        inspection_id=inspection_id,
        registration_state=registration_state,
        registration_residual_px=residual,
        degraded=degraded,
        message=message,
    )


def capture_golden(
    conn: sqlite3.Connection, camera: Camera, board_type_id: int, frame: np.ndarray | None = None
) -> dict[str, Any]:
    """Store a new golden reference for a board type.

    Appended, never overwritten -- golden boards get damaged or superseded, and
    which reference produced a given verdict is part of the audit trail.
    """
    if frame is None:
        frame = camera.read()
    if frame is None:
        raise InspectionError("no frame available from camera")

    path = config.GOLDEN_DIR / f"board_{board_type_id}_{db.utc_now().replace(':', '-')}.png"
    save_frame(frame, path)
    golden_id = db.add_golden_reference(conn, board_type_id, path)
    return {"golden_reference_id": golden_id, "image_path": str(path)}
