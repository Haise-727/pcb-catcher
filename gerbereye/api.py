"""FastAPI application — routes, MJPEG stream, and the inspection trigger.

Binds to 127.0.0.1 only. An MSME's design files are its customer's confidential
IP, so nothing may cross the host boundary (NFR-011). That is asserted by test
in tests/test_api.py rather than left to code review, because it is a
one-character change away from being wrong.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Generator

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import capture, config, db, export, inspector
from .pipeline import placement

camera = capture.Camera()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Open the camera on startup, release it on shutdown.

    The camera is a process-wide singleton because there is one physical
    station, one operator and one board at a time.
    """
    config.ensure_dirs()
    camera.open()
    yield
    camera.release()


app = FastAPI(
    title="GerberEye",
    description="Low-cost CAD-referenced optical inspection for PCB assembly",
    version="0.1.0",
    lifespan=lifespan,
)

# The Vite dev server runs on a different port during development. Both origins
# are loopback -- this widens the browser's same-origin policy, not the network
# bind, so NFR-011 is unaffected.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    """One connection per request.

    SQLite connections are not shareable across threads, and FastAPI serves
    requests from a thread pool.
    """
    return db.connect()


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------

class BoardTypeCreate(BaseModel):
    name: str


class PlacementUpload(BaseModel):
    board_type_id: int
    # Raw file content rather than a multipart upload: it keeps the operator UI
    # to a single fetch and avoids a file-picker dependency in the MVP.
    content: str


class OverrideRequest(BaseModel):
    region_verdict_id: int
    revised_verdict: str = "false_call"


class ThresholdUpdate(BaseModel):
    board_type_id: int
    diff_intensity: int | None = None
    min_region_area: int | None = None
    blur_kernel: int | None = None
    roi_scale: float | None = None


# --------------------------------------------------------------------------
# Health and capture state
# --------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    state = camera.state
    return {
        "status": "ok",
        "camera": {
            "connected": state.connected,
            "settings_locked": state.settings_locked,
            "degraded_reason": state.degraded_reason,
        },
    }


@app.post("/api/camera/reopen")
def reopen_camera() -> dict[str, Any]:
    """Recover after the camera was unplugged, without restarting the app."""
    state = camera.open()
    return {
        "connected": state.connected,
        "settings_locked": state.settings_locked,
        "degraded_reason": state.degraded_reason,
    }


@app.get("/api/camera/stability")
def camera_stability(samples: int = 100) -> dict[str, float]:
    """Frame-stability bench check (AC-006.2, issue #3).

    Mean deviation must sit below 2 grey levels before threshold tuning is
    meaningful. Exposed as an endpoint so it can be run from the UI on the
    shop floor rather than only from a developer's terminal.
    """
    return capture.measure_frame_stability(camera, samples=samples)


# --------------------------------------------------------------------------
# MJPEG stream
# --------------------------------------------------------------------------

def _mjpeg_frames() -> Generator[bytes, None, None]:
    """Yield multipart JPEG chunks for an <img> tag.

    MJPEG over an <img> src is the cheapest possible live view: no WebRTC, no
    per-frame marshalling into JavaScript, and it degrades gracefully when the
    camera disappears.
    """
    placeholder_interval = 1.0 / 5
    while True:
        frame = camera.read()
        if frame is None:
            # Emit a visible "no camera" card rather than stalling the stream,
            # so the operator sees the fault instead of a frozen last frame.
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                frame, "NO CAMERA", (150, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (60, 60, 220), 3,
            )
            time.sleep(placeholder_interval)

        jpeg = capture.encode_jpeg(frame)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"


@app.get("/stream.mjpg")
def stream() -> StreamingResponse:
    return StreamingResponse(
        _mjpeg_frames(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/frame.jpg")
def single_frame():
    """One still frame. Used by the UI to size its overlay canvas correctly."""
    frame = camera.read()
    if frame is None:
        raise HTTPException(status_code=503, detail="no frame available")
    return StreamingResponse(iter([capture.encode_jpeg(frame)]), media_type="image/jpeg")


# --------------------------------------------------------------------------
# Board types
# --------------------------------------------------------------------------

@app.get("/api/board-types")
def list_board_types() -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        return db.list_board_types(conn)
    finally:
        conn.close()


@app.post("/api/board-types")
def create_board_type(payload: BoardTypeCreate) -> dict[str, Any]:
    conn = get_conn()
    try:
        board_type_id = db.get_or_create_board_type(conn, payload.name)
        return {"board_type_id": board_type_id, "name": payload.name}
    finally:
        conn.close()


@app.post("/api/board-types/golden")
def capture_golden(board_type_id: int) -> dict[str, Any]:
    conn = get_conn()
    try:
        return inspector.capture_golden(conn, camera, board_type_id)
    except inspector.InspectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/board-types/placement")
def upload_placement(payload: PlacementUpload) -> dict[str, Any]:
    """Ingest a pick-and-place file to enable the CAD naming path."""
    conn = get_conn()
    try:
        components = placement.parse_placement_text(payload.content)
        count = db.replace_components(
            conn, payload.board_type_id, [c.as_dict() for c in components]
        )
        return {"board_type_id": payload.board_type_id, "component_count": count}
    except placement.PlacementParseError as exc:
        # A malformed customer file is expected control flow, not a server
        # fault -- 400 with the specific reason, so the operator can fix it.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/board-types/{board_type_id}/thresholds")
def get_thresholds(board_type_id: int) -> dict[str, Any]:
    conn = get_conn()
    try:
        return db.get_thresholds(conn, board_type_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


@app.patch("/api/board-types/thresholds")
def patch_thresholds(payload: ThresholdUpdate) -> dict[str, Any]:
    """Retune a board type without a rebuild (NFR-013, ADR-004)."""
    conn = get_conn()
    try:
        db.update_thresholds(
            conn,
            payload.board_type_id,
            diff_intensity=payload.diff_intensity,
            min_region_area=payload.min_region_area,
            blur_kernel=payload.blur_kernel,
            roi_scale=payload.roi_scale,
        )
        return db.get_thresholds(conn, payload.board_type_id)
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Inspection
# --------------------------------------------------------------------------

@app.post("/api/trigger")
def trigger(board_type_id: int) -> dict[str, Any]:
    """Inspect the board currently under the camera."""
    conn = get_conn()
    try:
        outcome = inspector.run_inspection(conn, camera, board_type_id)
        return outcome.as_dict()
    except inspector.InspectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/inspections")
def list_inspections(limit: int = 50) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        return db.list_inspections(conn, limit=limit)
    finally:
        conn.close()


@app.get("/api/inspections/{inspection_id}")
def get_inspection(inspection_id: int) -> dict[str, Any]:
    conn = get_conn()
    try:
        record = db.get_inspection(conn, inspection_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such inspection")
        return record
    finally:
        conn.close()


@app.post("/api/override")
def override(payload: OverrideRequest) -> dict[str, Any]:
    """Mark a flagged region a false call.

    Appends a correction; the original verdict row is never edited. One
    interaction by design -- an operator who has to fill in a form to dismiss a
    false call stops dismissing them and starts ignoring the station.
    """
    conn = get_conn()
    try:
        override_id = db.add_override(conn, payload.region_verdict_id, payload.revised_verdict)
        return {"override_id": override_id, "region_verdict_id": payload.region_verdict_id}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

@app.get("/api/export.csv")
def export_csv(limit: int = 500):
    """Download inspection records as CSV (FR-022).

    Implementation lives in gerbereye/export.py — issue #16.
    """
    conn = get_conn()
    try:
        body = export.build_inspection_csv(conn, limit=limit)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    finally:
        conn.close()
    return StreamingResponse(
        iter([body]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gerbereye_inspections.csv"},
    )
