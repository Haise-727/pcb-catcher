"""FastAPI application — routes, MJPEG stream, and the inspection trigger.

Binds to 127.0.0.1 only. An MSME's design files are its customer's confidential
IP, so nothing may cross the host boundary (NFR-011). That is asserted by test
in tests/test_api.py rather than left to code review, because it is a
one-character change away from being wrong.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Generator

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import bench, capture, config, db, demo, export, inspector, logging_setup, retention
from .pipeline import bom, placement

# Demo mode swaps where pixels come from and nothing else -- every stage
# downstream runs its production path. Opt-in via GERBEREYE_DEMO so a station
# can never silently serve fake frames when a real camera fails.
DEMO_MODE = demo.demo_enabled()
camera = demo.DemoCamera() if DEMO_MODE else capture.Camera()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Open the camera on startup, release it on shutdown.

    The camera is a process-wide singleton because there is one physical
    station, one operator and one board at a time.
    """
    config.ensure_dirs()
    logging_setup.setup()
    camera.open()

    # Cheap when there is nothing to do, and it means a station left running
    # for months does not depend on anyone remembering to reclaim space.
    if config.RETENTION.sweep_on_startup:
        conn = db.connect()
        try:
            retention.sweep(conn, config.RETENTION.days)
        finally:
            conn.close()

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


class BomUpload(BaseModel):
    board_type_id: int
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
    payload: dict[str, Any] = {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "camera": {
            "connected": state.connected,
            "settings_locked": state.settings_locked,
            "degraded_reason": state.degraded_reason,
        },
    }
    if DEMO_MODE:
        profile = camera.bench.profile
        payload["demo"] = {
            "board_index": camera.board_index,
            "board_name": camera.board_name,
            "board_description": camera.board_description,
            "boards": demo.board_catalog(),
            "bench_profile": profile.name,
            "bench_expectation": profile.expectation,
            "bench_profiles": bench.profile_catalog(),
        }
    return payload


@app.post("/api/demo/board")
def select_demo_board(index: int) -> dict[str, Any]:
    """Choose which bundled board sits 'under the camera'.

    Stands in for physically swapping boards, so the demo can show a clean
    pass and each defect class without touching hardware.
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=409, detail="not running in demo mode")
    try:
        camera.select_board(index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "board_index": camera.board_index,
        "board_name": camera.board_name,
        "board_description": camera.board_description,
    }


@app.post("/api/demo/next-board")
def next_demo_board() -> dict[str, Any]:
    if not DEMO_MODE:
        raise HTTPException(status_code=409, detail="not running in demo mode")
    camera.next_board()
    return {
        "board_index": camera.board_index,
        "board_name": camera.board_name,
        "board_description": camera.board_description,
    }


@app.post("/api/bench/profile")
def select_bench_profile(name: str) -> dict[str, Any]:
    """Change simulated bench conditions (virtual jig / ring light / sensor).

    Stands in for hardware we cannot currently build: it lets the frame
    stability gate (#3), the degraded-capture state (#35) and the
    illumination-drives-false-calls claim (RSK-02) be demonstrated rather than
    asserted. Demo mode only -- the real camera path has real conditions.
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=409, detail="not running in demo mode")
    try:
        camera.select_bench_profile(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile = camera.bench.profile
    return {
        "bench_profile": profile.name,
        "label": profile.label,
        "description": profile.description,
        "expectation": profile.expectation,
        "settings_locked": profile.settings_locked,
        "degraded_reason": profile.degraded_reason,
        "simulated": True,
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
def camera_stability(samples: int = 100) -> dict[str, Any]:
    """Frame-stability bench check (AC-006.2, issue #3).

    Mean deviation must sit below 2 grey levels before threshold tuning is
    meaningful. Exposed as an endpoint so it can be run from the UI on the
    shop floor rather than only from a developer's terminal.
    """
    stats: dict[str, Any] = dict(capture.measure_frame_stability(camera, samples=samples))
    # In demo mode this measures the virtual bench, not a camera. Flagging it
    # in the payload is the difference between demonstrating that the gate
    # works and quoting a fabricated AC-006.2 result.
    stats["simulated"] = DEMO_MODE
    if DEMO_MODE:
        stats["bench_profile"] = camera.bench.profile.name
    return stats


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
        db.replace_components(
            conn, payload.board_type_id, [c.as_dict() for c in components]
        )
        excluded = sorted(c.ref_des for c in components if c.dnp)
        return {
            "board_type_id": payload.board_type_id,
            "component_count": len(components) - len(excluded),
            # Surfaced so the technician notices at setup if the file knocks
            # out more of the board than expected (AC-002.2).
            "dnp_excluded": len(excluded),
            "dnp_designators": excluded,
        }
    except placement.PlacementParseError as exc:
        # A malformed customer file is expected control flow, not a server
        # fault -- 400 with the specific reason, so the operator can fix it.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/board-types/bom")
def upload_bom(payload: BomUpload) -> dict[str, Any]:
    """Ingest a BOM to exclude do-not-populate designators (FR-002).

    The BOM is authoritative over any DNP hint in the pick-and-place file,
    because it is the document a human curates.
    """
    conn = get_conn()
    try:
        entries = bom.parse_bom_text(payload.content)
        excluded = bom.dnp_designators(entries)
        matched = db.set_dnp(conn, payload.board_type_id, excluded)
        return {
            "board_type_id": payload.board_type_id,
            "bom_entries": len(entries),
            "dnp_in_bom": len(excluded),
            "dnp_applied": matched,
            "dnp_designators": sorted(excluded),
            "inspectable_components": len(db.list_components(conn, payload.board_type_id)),
        }
    except bom.BomParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/board-types/{board_type_id}/components")
def list_components(board_type_id: int, include_dnp: bool = True) -> dict[str, Any]:
    """Component map for a board type, DNP entries flagged.

    Defaults to including DNP so the setup screen can show what was excluded;
    the inspection path never uses this endpoint.
    """
    conn = get_conn()
    try:
        components = db.list_components(conn, board_type_id, include_dnp=include_dnp)
        return {
            "board_type_id": board_type_id,
            "components": components,
            "dnp_count": db.count_dnp(conn, board_type_id),
        }
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


@app.get("/api/inspections/{inspection_id}/regions/{region_id}.jpg")
def region_crop(inspection_id: int, region_id: int, zoom: int = 4, context: int = 12):
    """Crop of one defect region from the stored inspection frame.

    Lets the operator confirm a call without leaning over the board. The crop
    is padded with surrounding context, because a tightly-cropped component is
    almost unreadable out of position -- you need the neighbours to orient.
    """
    conn = get_conn()
    try:
        record = db.get_inspection(conn, inspection_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such inspection")
        if not record.get("frame_path"):
            raise HTTPException(status_code=404, detail="no frame stored for this inspection")

        region = next((r for r in record["regions"] if r["id"] == region_id), None)
        if region is None:
            raise HTTPException(status_code=404, detail="no such region")

        frame = cv2.imread(record["frame_path"])
        if frame is None:
            raise HTTPException(status_code=410, detail="frame file is no longer available")

        x, y, w, h = region["bbox"]
        height, width = frame.shape[:2]
        x0 = max(x - context, 0)
        y0 = max(y - context, 0)
        x1 = min(x + w + context, width)
        y1 = min(y + h + context, height)
        crop = frame[y0:y1, x0:x1]
        if crop.size == 0:
            raise HTTPException(status_code=404, detail="region lies outside the frame")

        # Outline the region within the crop so it is obvious which part of the
        # context is the actual finding.
        annotated = crop.copy()
        cv2.rectangle(
            annotated, (x - x0, y - y0), (x - x0 + w, y - y0 + h), (77, 72, 229), 1
        )

        zoom = max(1, min(zoom, 12))
        enlarged = cv2.resize(
            annotated, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST
        )
        return StreamingResponse(
            iter([capture.encode_jpeg(enlarged, quality=90)]), media_type="image/jpeg"
        )
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


@app.get("/api/trends")
def defect_trends(
    board_type_id: int | None = None, days: int | None = None, limit: int = 25
) -> dict[str, Any]:
    """Recurring defects by designator (FR-023).

    Turns the station from a detector into something that improves the line: a
    single missing C14 is a rework job, C14 missing on 40% of boards is a
    feeder problem.
    """
    conn = get_conn()
    try:
        since = None
        if days:
            since = (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).isoformat()
        return db.defect_trends(conn, board_type_id=board_type_id, since=since, limit=limit)
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Retention
# --------------------------------------------------------------------------

@app.get("/api/storage")
def storage_usage() -> dict[str, Any]:
    """Image footprint and the retention window in force."""
    conn = get_conn()
    try:
        return {
            "retention_days": config.RETENTION.days,
            **retention.usage(conn),
            "records": retention.verdict_row_count(conn),
        }
    finally:
        conn.close()


@app.post("/api/storage/sweep")
def run_sweep(retention_days: int | None = None) -> dict[str, Any]:
    """Delete inspection images past the retention window.

    Images only. Inspection and verdict rows are never removed -- they are the
    audit trail, and the response reports their counts so a caller can confirm
    nothing was lost.
    """
    conn = get_conn()
    try:
        before = retention.verdict_row_count(conn)
        result = retention.sweep(conn, retention_days or config.RETENTION.days)
        return {
            **result.as_dict(),
            "records_before": before,
            "records_after": retention.verdict_row_count(conn),
        }
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
