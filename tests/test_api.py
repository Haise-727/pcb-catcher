"""API tests, including the security assertion that NFR-011 depends on.

Uses FastAPI's TestClient, so these run in-process with no camera attached.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient

from gerbereye import config, db, inspector
from gerbereye.capture import Camera


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point the app at a throwaway database and image tree."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")
    conn = db.connect()
    yield conn
    conn.close()


@pytest.fixture()
def client(temp_db):
    from gerbereye import api

    with TestClient(api.app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# The security assertion
# --------------------------------------------------------------------------

def test_server_config_binds_loopback_only():
    """NFR-011 is one character away from being wrong.

    An MSME's design files are its customer's confidential IP. Binding
    0.0.0.0 would expose them to the factory LAN and break the strongest
    security claim the project makes, so the bind address is asserted here
    rather than left to code review.
    """
    assert config.SERVER.host == "127.0.0.1"
    assert config.SERVER.host != "0.0.0.0"


def test_no_cloud_client_dependencies_are_declared():
    """CON-01: no cloud service may sit between placing a board and a result."""
    requirements = (config.ROOT / "requirements.txt").read_text().lower()
    for forbidden in ("boto3", "google-cloud", "azure-", "requests-aws", "openai"):
        assert forbidden not in requirements


# --------------------------------------------------------------------------
# Board types and ingestion
# --------------------------------------------------------------------------

def test_health_reports_camera_state(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "camera" in response.json()


def test_create_and_list_board_type(client):
    created = client.post("/api/board-types", json={"name": "demo-board"})
    assert created.status_code == 200
    board_type_id = created.json()["board_type_id"]

    listed = client.get("/api/board-types").json()
    assert any(b["id"] == board_type_id for b in listed)


def test_placement_upload_populates_component_map(client):
    board_type_id = client.post("/api/board-types", json={"name": "pnp"}).json()["board_type_id"]
    payload = {
        "board_type_id": board_type_id,
        "content": "Designator,X,Y,Rotation\nC1,10.0,10.0,0\nR2,20.0,10.0,90\n",
    }
    response = client.post("/api/board-types/placement", json=payload)
    assert response.status_code == 200
    assert response.json()["component_count"] == 2


def test_malformed_placement_returns_400_not_500(client):
    """A malformed customer file is expected control flow, not a server fault.
    The operator needs a specific reason they can act on."""
    board_type_id = client.post("/api/board-types", json={"name": "bad"}).json()["board_type_id"]
    response = client.post(
        "/api/board-types/placement",
        json={"board_type_id": board_type_id, "content": "Foo,Bar\n1,2\n"},
    )
    assert response.status_code == 400
    assert "could not find" in response.json()["detail"]


def test_trigger_without_golden_reference_returns_503(client):
    """Inspecting before a reference exists is a station fault, not a bad board."""
    board_type_id = client.post("/api/board-types", json={"name": "nogolden"}).json()["board_type_id"]
    response = client.post("/api/trigger", params={"board_type_id": board_type_id})
    assert response.status_code == 503
    assert "golden reference" in response.json()["detail"]


def test_thresholds_are_retunable_without_restart(client):
    """NFR-013 / ADR-004: thresholds are per-board-type config, not constants."""
    board_type_id = client.post("/api/board-types", json={"name": "tunable"}).json()["board_type_id"]
    response = client.patch(
        "/api/board-types/thresholds",
        json={"board_type_id": board_type_id, "diff_intensity": 55},
    )
    assert response.status_code == 200
    assert response.json()["diff_intensity"] == 55


# --------------------------------------------------------------------------
# Full inspection loop, driven with synthetic frames
# --------------------------------------------------------------------------

def make_board(with_defect: bool = False):
    import cv2

    board = np.full((480, 640, 3), 30, np.uint8)
    for x, y in ((100, 100), (200, 100), (300, 100)):
        cv2.rectangle(board, (x, y), (x + 40, y + 25), (200, 200, 200), -1)
    if with_defect:
        cv2.rectangle(board, (200, 100), (240, 125), (30, 30, 30), -1)
    return board


def test_full_inspection_loop_pass_then_fail_then_override(temp_db):
    """End-to-end: golden capture, clean pass, defective fail, override.

    Runs the same inspector path a live trigger uses, with frames supplied
    directly so it needs no camera.
    """
    conn = temp_db
    camera = Camera()
    board_type_id = db.get_or_create_board_type(conn, "loop-test")

    golden = make_board()
    inspector.capture_golden(conn, camera, board_type_id, frame=golden)

    clean = inspector.run_inspection(conn, camera, board_type_id, frame=make_board())
    assert clean.verdict == "pass"
    assert clean.regions == []

    defective = inspector.run_inspection(
        conn, camera, board_type_id, frame=make_board(with_defect=True)
    )
    assert defective.verdict == "fail"
    assert len(defective.regions) == 1

    # Override the flagged region, then confirm the correction is visible and
    # the original row was appended to rather than edited.
    region_id = defective.regions[0]["id"]
    db.add_override(conn, region_id, "false_call")

    reread = db.get_inspection(conn, defective.inspection_id)
    assert reread["regions"][0]["verdict"] == "false_call"
    assert reread["regions"][0]["overridden"] is True


def test_override_is_append_only(temp_db):
    """A correction must never mutate the original verdict row (NFR-012)."""
    conn = temp_db
    board_type_id = db.get_or_create_board_type(conn, "append-only")
    inspection_id = db.record_inspection(
        conn, board_type_id, "fail", "differencing",
        [{"bbox": [1, 2, 3, 4], "area_px": 500}],
    )
    region_id = db.list_regions(conn, inspection_id)[0]["id"]

    db.add_override(conn, region_id, "false_call")
    db.add_override(conn, region_id, "defect")

    # Both corrections are retained; the latest wins on read.
    overrides = conn.execute(
        "SELECT COUNT(*) AS n FROM override WHERE region_verdict_id = ?", (region_id,)
    ).fetchone()["n"]
    assert overrides == 2
    assert db.list_regions(conn, inspection_id)[0]["verdict"] == "defect"


def test_inspection_records_survive_reconnect(temp_db):
    """Records must outlive the process that wrote them (NFR-009)."""
    conn = temp_db
    board_type_id = db.get_or_create_board_type(conn, "durable")
    db.record_inspection(conn, board_type_id, "pass", "differencing", [])
    conn.close()

    reopened = db.connect()
    try:
        assert len(db.list_inspections(reopened)) == 1
    finally:
        reopened.close()
