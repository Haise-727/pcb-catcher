"""Reliability and degraded-mode tests — NFR-009, NFR-010, NFR-012.

These cover what happens when things go wrong, which is most of what an
inspection station actually has to survive on a shop floor: the camera gets
unplugged, the process is killed mid-shift, a customer's file is malformed, the
golden reference is deleted from under it.

The standard applied throughout is: **fail visibly, never silently**. A station
that reports a fault is recoverable. A station that quietly reports PASS
because it could not actually inspect anything is dangerous — it tells an
operator a board is good when nothing was checked.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from gerbereye import config, db, inspector
from gerbereye.capture import Camera, CaptureState


@pytest.fixture()
def temp_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "reliability.db")
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")
    return tmp_path


@pytest.fixture()
def conn(temp_env):
    connection = db.connect()
    yield connection
    connection.close()


@pytest.fixture()
def client(conn):
    from gerbereye import api

    with TestClient(api.app) as test_client:
        yield test_client


def make_board(with_defect: bool = False):
    import cv2

    board = np.full((240, 400, 3), 40, np.uint8)
    for x in (80, 160, 240):
        cv2.rectangle(board, (x, 100), (x + 30, 118), (200, 205, 210), -1)
    if with_defect:
        cv2.rectangle(board, (160, 100), (190, 118), (40, 40, 40), -1)
    return board


# --------------------------------------------------------------------------
# NFR-009 — recoverability
# --------------------------------------------------------------------------

def test_records_survive_the_process_that_wrote_them(temp_env):
    """RPO is one inspection: anything committed must outlive the process."""
    conn = db.connect()
    board_type_id = db.get_or_create_board_type(conn, "durable")
    db.record_inspection(conn, board_type_id, "fail", "cad", [
        {"bbox": [1, 2, 3, 4], "area_px": 500, "ref_des": "C14",
         "defect_class": "absent", "confidence": 0.9, "detail": "gone"},
    ])
    conn.close()

    reopened = db.connect()
    try:
        records = db.list_inspections(reopened)
        assert len(records) == 1
        regions = db.list_regions(reopened, records[0]["id"])
        assert regions[0]["ref_des"] == "C14"
        assert regions[0]["defect_class"] == "absent"
    finally:
        reopened.close()


def test_database_survives_an_abrupt_process_kill(tmp_path):
    """Kill mid-run rather than closing cleanly, and check the file is intact.

    WAL mode is what makes this safe; a regression to the default journal would
    show up here as a corrupted or truncated database.
    """
    db_path = tmp_path / "killed.db"
    # Paths must be Path objects, not strings -- config.ensure_dirs() calls
    # .mkdir() on them.
    script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(Path.cwd())!r})
from gerbereye import config, db
config.DATA_DIR = Path({str(tmp_path)!r})
config.DB_PATH = Path({str(db_path)!r})
config.GOLDEN_DIR = Path({str(tmp_path / 'g')!r})
config.IMAGE_DIR = Path({str(tmp_path / 'i')!r})
conn = db.connect()
bt = db.get_or_create_board_type(conn, 'killed')
for i in range(20):
    db.record_inspection(conn, bt, 'pass', 'cad', [])
print('WROTE', flush=True)
import os
os._exit(9)   # no cleanup, no flush, no atexit
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert "WROTE" in result.stdout

    # Reopen independently and confirm every committed row is readable.
    reopened = sqlite3.connect(db_path)
    reopened.row_factory = sqlite3.Row
    try:
        count = reopened.execute("SELECT COUNT(*) AS n FROM inspection").fetchone()["n"]
        assert count == 20
        assert reopened.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reopened.close()


# --------------------------------------------------------------------------
# NFR-010 — degraded modes, one per dependency
# --------------------------------------------------------------------------

def test_inspection_without_a_camera_reports_a_fault_not_a_pass(conn):
    """The dangerous failure mode.

    A station that returns PASS because it could not capture anything tells an
    operator the board is good when nothing was inspected. It must refuse.
    """
    board_type_id = db.get_or_create_board_type(conn, "nocam")
    inspector.capture_golden(conn, Camera(), board_type_id, frame=make_board())

    class DeadCamera:
        state = CaptureState(connected=False, degraded_reason="unplugged")

        def read(self):
            return None

    with pytest.raises(inspector.InspectionError, match="no frame"):
        inspector.run_inspection(conn, DeadCamera(), board_type_id)


def test_inspection_without_a_golden_reference_is_refused(conn):
    """Nothing to compare against is a station fault, not a good board."""
    board_type_id = db.get_or_create_board_type(conn, "nogolden")
    with pytest.raises(inspector.InspectionError, match="golden reference"):
        inspector.run_inspection(conn, Camera(), board_type_id, frame=make_board())


def test_deleted_golden_file_is_reported_clearly(conn, temp_env):
    """Retention or a manual cleanup can remove the file while the row remains."""
    board_type_id = db.get_or_create_board_type(conn, "missing-golden")
    result = inspector.capture_golden(conn, Camera(), board_type_id, frame=make_board())
    Path(result["image_path"]).unlink()

    with pytest.raises(inspector.InspectionError, match="unreadable"):
        inspector.run_inspection(conn, Camera(), board_type_id, frame=make_board())


def test_registration_failure_degrades_to_unnamed_regions(conn):
    """Losing the markers costs the names, not the inspection.

    Reporting anonymous regions is far more useful to an operator than refusing
    to inspect, so this must degrade rather than abort.
    """
    board_type_id = db.get_or_create_board_type(conn, "noreg")
    inspector.capture_golden(conn, Camera(), board_type_id, frame=make_board())
    # A component map exists, so the CAD path is attempted -- but the frames
    # carry no ArUco markers, so registration cannot succeed.
    db.replace_components(conn, board_type_id, [
        {"ref_des": "C1", "x_mm": 10.0, "y_mm": 10.0, "footprint": "C_0805"},
    ])

    outcome = inspector.run_inspection(
        conn, Camera(), board_type_id, frame=make_board(with_defect=True)
    )

    assert outcome.verdict == "fail"
    assert outcome.regions, "differencing should still produce regions"
    assert outcome.path_used == "differencing"
    assert all(r["ref_des"] is None for r in outcome.regions)
    assert "unavailable" in (outcome.message or "")


def test_api_reports_camera_state_rather_than_hiding_it(client):
    body = client.get("/api/health").json()
    assert "camera" in body
    assert "connected" in body["camera"]


def test_trigger_without_golden_returns_503_not_200(client):
    """A station fault is a 503. Returning 200 with an empty result would read
    as a clean board."""
    board_type_id = client.post("/api/board-types", json={"name": "x"}).json()["board_type_id"]
    response = client.post("/api/trigger", params={"board_type_id": board_type_id})
    assert response.status_code == 503


# --------------------------------------------------------------------------
# Malformed input — expected control flow, not crashes
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "content",
    [
        "",                                   # empty
        "Designator,X,Y\n",                   # header only
        "Foo,Bar\n1,2\n",                     # wrong columns
        "Designator,X,Y\nR1,notanumber,10\n", # unparseable coordinate
        "\x00\x01\x02binary garbage",         # not a CSV at all
    ],
)
def test_malformed_placement_files_return_400(client, content):
    """Customer files are routinely malformed. Each must produce an actionable
    message, never a 500."""
    board_type_id = client.post("/api/board-types", json={"name": "bad"}).json()["board_type_id"]
    response = client.post(
        "/api/board-types/placement",
        json={"board_type_id": board_type_id, "content": content},
    )
    assert response.status_code == 400
    assert response.json()["detail"]


@pytest.mark.parametrize("content", ["", "Part,Qty\nfoo,1\n", "\x00garbage"])
def test_malformed_bom_files_return_400(client, content):
    board_type_id = client.post("/api/board-types", json={"name": "badbom"}).json()["board_type_id"]
    response = client.post(
        "/api/board-types/bom", json={"board_type_id": board_type_id, "content": content}
    )
    assert response.status_code == 400


def test_unknown_inspection_returns_404(client):
    assert client.get("/api/inspections/99999").status_code == 404


def test_override_of_unknown_region_returns_404(client):
    response = client.post(
        "/api/override", json={"region_verdict_id": 99999, "revised_verdict": "false_call"}
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# First-run state (OQ-10)
# --------------------------------------------------------------------------

def test_empty_station_serves_every_endpoint_without_error(client):
    """A fresh install has no board types, no inspections and no images. None
    of that is an error state, and the UI must be able to render it."""
    assert client.get("/api/board-types").json() == []
    assert client.get("/api/inspections").json() == []
    assert client.get("/api/trends").json()["designators"] == []
    assert client.get("/api/storage").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"
