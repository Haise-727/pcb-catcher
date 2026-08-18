"""Defect trend aggregation tests — issue #40, FR-023.

The load-bearing behaviour is that overridden regions are excluded. An operator
dismissing a call is saying the board was fine, so counting it would let a
noisy threshold masquerade as a process fault — and this view exists precisely
to decide where to spend engineering effort.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from gerbereye import config, db


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "trends.db")
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")
    connection = db.connect()
    yield connection
    connection.close()


def record(conn, board_type_id, regions, *, age_days: int = 0):
    """Insert one inspection, optionally backdated."""
    inspection_id = db.record_inspection(
        conn, board_type_id, "fail" if regions else "pass", "cad", regions
    )
    if age_days:
        started = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
        conn.execute(
            "UPDATE inspection SET started_at = ? WHERE id = ?", (started, inspection_id)
        )
        conn.commit()
    return inspection_id


def region(ref_des, defect_class="absent"):
    return {
        "bbox": [10, 10, 20, 20],
        "area_px": 400,
        "ref_des": ref_des,
        "defect_class": defect_class,
        "confidence": 0.9,
        "detail": "test",
    }


def test_designators_are_ranked_worst_first(conn):
    board_type_id = db.get_or_create_board_type(conn, "ranked")
    for _ in range(5):
        record(conn, board_type_id, [region("C14")])
    for _ in range(2):
        record(conn, board_type_id, [region("R7")])

    trends = db.defect_trends(conn, board_type_id)
    assert [d["ref_des"] for d in trends["designators"]] == ["C14", "R7"]
    assert trends["designators"][0]["occurrences"] == 5


def test_rate_is_relative_to_total_inspections(conn):
    """A count means nothing without the denominator: 12 failures out of 15
    boards is a crisis, out of 1500 it is noise."""
    board_type_id = db.get_or_create_board_type(conn, "rated")
    for _ in range(2):
        record(conn, board_type_id, [region("C14")])
    for _ in range(8):
        record(conn, board_type_id, [])

    trends = db.defect_trends(conn, board_type_id)
    assert trends["inspections"] == 10
    assert trends["designators"][0]["rate"] == pytest.approx(0.2)


def test_overridden_regions_are_excluded(conn):
    """An operator dismissing a call is saying the board was fine. Counting it
    would let a noisy threshold look like a process fault."""
    board_type_id = db.get_or_create_board_type(conn, "overridden")
    inspection_id = record(conn, board_type_id, [region("C14")])
    record(conn, board_type_id, [region("C14")])

    before = db.defect_trends(conn, board_type_id)
    assert before["designators"][0]["occurrences"] == 2

    region_id = db.list_regions(conn, inspection_id)[0]["id"]
    db.add_override(conn, region_id, "false_call")

    after = db.defect_trends(conn, board_type_id)
    assert after["designators"][0]["occurrences"] == 1


def test_counts_are_split_by_defect_class(conn):
    """Which failure mode dominates decides what to fix: absent points at the
    feeder, rotated at placement, offset at the stencil."""
    board_type_id = db.get_or_create_board_type(conn, "classes")
    record(conn, board_type_id, [region("U1", "absent")])
    record(conn, board_type_id, [region("U1", "rotated")])
    record(conn, board_type_id, [region("U1", "rotated")])
    record(conn, board_type_id, [region("U1", "offset")])

    entry = db.defect_trends(conn, board_type_id)["designators"][0]
    assert entry["absent"] == 1
    assert entry["rotated"] == 2
    assert entry["offset"] == 1


def test_unnamed_regions_are_not_aggregated(conn):
    """Without a designator there is nothing to attribute a trend to."""
    board_type_id = db.get_or_create_board_type(conn, "unnamed")
    record(conn, board_type_id, [{"bbox": [1, 2, 3, 4], "area_px": 100}])

    trends = db.defect_trends(conn, board_type_id)
    assert trends["designators"] == []
    assert trends["inspections"] == 1


def test_date_window_filters_older_inspections(conn):
    board_type_id = db.get_or_create_board_type(conn, "windowed")
    record(conn, board_type_id, [region("C14")], age_days=90)
    record(conn, board_type_id, [region("C14")])

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    trends = db.defect_trends(conn, board_type_id, since=since)

    assert trends["inspections"] == 1
    assert trends["designators"][0]["occurrences"] == 1


def test_board_types_are_kept_separate(conn):
    """Two board types share a designator namespace; C14 on one says nothing
    about C14 on the other."""
    first = db.get_or_create_board_type(conn, "board-a")
    second = db.get_or_create_board_type(conn, "board-b")
    record(conn, first, [region("C14")])
    record(conn, second, [region("C14")])
    record(conn, second, [region("C14")])

    assert db.defect_trends(conn, first)["designators"][0]["occurrences"] == 1
    assert db.defect_trends(conn, second)["designators"][0]["occurrences"] == 2


def test_empty_database_returns_an_empty_report(conn):
    trends = db.defect_trends(conn, board_type_id=None)
    assert trends["designators"] == []
    assert trends["inspections"] == 0
