"""Retention sweep tests — issue #34, FR-024, NFR-002, NFR-012.

The central assertion is that the sweep is **non-destructive to records**. It
reclaims image files; it must never remove an inspection, a region verdict or
an override. Those rows are what let an MSME answer "what did you inspect?"
months later, and deleting them to save disk would turn a traceability record
into a database that merely happens to contain history.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gerbereye import config, db, retention


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "retention.db")
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")
    connection = db.connect()
    yield connection
    connection.close()


# Filenames must be unique per call. Deriving them from age_days alone made two
# same-age inspections share one file, so deleting it emptied both.
_counter = itertools.count()


def add_inspection(conn, tmp_path, *, age_days: int, with_image: bool = True) -> tuple[int, Path | None]:
    """Insert an inspection dated `age_days` ago, with a real file on disk."""
    board_type_id = db.get_or_create_board_type(conn, "sweep-board")
    image_path = None
    if with_image:
        image_dir = tmp_path / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"frame_{age_days}_{next(_counter)}.jpg"
        image_path.write_bytes(b"x" * 2048)

    started = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    cursor = conn.execute(
        "INSERT INTO inspection (board_type_id, started_at, verdict, path_used, frame_path)"
        " VALUES (?, ?, 'fail', 'cad', ?)",
        (board_type_id, started, str(image_path) if image_path else None),
    )
    inspection_id = int(cursor.lastrowid)
    conn.execute(
        "INSERT INTO region_verdict (inspection_id, bbox_json, ref_des, area_px)"
        " VALUES (?, '[1,2,3,4]', 'C14', 500)",
        (inspection_id,),
    )
    conn.commit()
    return inspection_id, image_path


# --------------------------------------------------------------------------
# The rule that must not break
# --------------------------------------------------------------------------

def test_sweep_never_deletes_inspection_or_verdict_rows(conn, tmp_path):
    """NFR-012. The record outlives the pixels."""
    for age in (60, 45, 1):
        add_inspection(conn, tmp_path, age_days=age)

    before = retention.verdict_row_count(conn)
    retention.sweep(conn, retention_days=30)
    after = retention.verdict_row_count(conn)

    assert after == before
    assert after["inspections"] == 3
    assert after["region_verdicts"] == 3


def test_old_images_are_deleted_and_their_paths_nulled(conn, tmp_path):
    old_id, old_path = add_inspection(conn, tmp_path, age_days=60)

    result = retention.sweep(conn, retention_days=30)

    assert result.files_deleted == 1
    assert result.bytes_reclaimed == 2048
    assert not old_path.exists()
    # Nulled so nothing keeps pointing at an image the station cannot produce.
    row = conn.execute("SELECT frame_path FROM inspection WHERE id = ?", (old_id,)).fetchone()
    assert row["frame_path"] is None


def test_recent_images_are_kept(conn, tmp_path):
    recent_id, recent_path = add_inspection(conn, tmp_path, age_days=2)

    retention.sweep(conn, retention_days=30)

    assert recent_path.exists()
    row = conn.execute("SELECT frame_path FROM inspection WHERE id = ?", (recent_id,)).fetchone()
    assert row["frame_path"] == str(recent_path)


def test_swept_inspection_is_still_fully_queryable(conn, tmp_path):
    """The point of keeping the row: the finding survives without the photo."""
    old_id, _ = add_inspection(conn, tmp_path, age_days=90)
    retention.sweep(conn, retention_days=30)

    record = db.get_inspection(conn, old_id)
    assert record is not None
    assert record["verdict"] == "fail"
    assert record["regions"][0]["ref_des"] == "C14"
    assert record["frame_path"] is None


def test_overrides_survive_a_sweep(conn, tmp_path):
    old_id, _ = add_inspection(conn, tmp_path, age_days=90)
    region_id = db.list_regions(conn, old_id)[0]["id"]
    db.add_override(conn, region_id, "false_call")

    retention.sweep(conn, retention_days=30)

    assert retention.verdict_row_count(conn)["overrides"] == 1
    assert db.list_regions(conn, old_id)[0]["verdict"] == "false_call"


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------

def test_already_missing_file_still_clears_the_dangling_reference(conn, tmp_path):
    """A manually deleted image leaves a row pointing at nothing. The sweep
    should tidy that rather than leaving a reference the station cannot honour."""
    old_id, old_path = add_inspection(conn, tmp_path, age_days=60)
    old_path.unlink()

    result = retention.sweep(conn, retention_days=30)

    assert result.missing_files == 1
    assert result.files_deleted == 0
    row = conn.execute("SELECT frame_path FROM inspection WHERE id = ?", (old_id,)).fetchone()
    assert row["frame_path"] is None


def test_sweep_on_empty_database_is_a_no_op(conn):
    result = retention.sweep(conn, retention_days=30)
    assert result.files_deleted == 0
    assert result.errors == []


def test_golden_references_are_never_swept(conn, tmp_path):
    """A golden reference is configuration, not history. Deleting it would
    break every future inspection of that board type."""
    board_type_id = db.get_or_create_board_type(conn, "golden-board")
    golden_dir = tmp_path / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)
    golden_path = golden_dir / "ref.png"
    golden_path.write_bytes(b"golden")

    conn.execute(
        "INSERT INTO golden_reference (board_type_id, image_path, captured_at)"
        " VALUES (?, ?, ?)",
        (board_type_id, str(golden_path),
         (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()),
    )
    conn.commit()

    retention.sweep(conn, retention_days=30)

    assert golden_path.exists()
    assert db.latest_golden_reference(conn, board_type_id) is not None


def test_usage_reports_footprint_and_dangling_references(conn, tmp_path):
    add_inspection(conn, tmp_path, age_days=1)
    _id, missing = add_inspection(conn, tmp_path, age_days=1)
    missing.unlink()

    stats = retention.usage(conn)
    assert stats["inspections_with_images"] == 2
    assert stats["images_present"] == 1
    assert stats["dangling_references"] == 1
    assert stats["bytes"] == 2048
