"""CSV export tests — the target for issue #16 (@YUVARAJ-R-ai).

These tests are written and currently failing by design. Implement
gerbereye/export.py:build_inspection_csv() until they pass; the API route is
already wired, so nothing else needs touching.

Run just this file with:
    .venv/bin/pytest tests/test_export.py -v
"""

from __future__ import annotations

import csv
import io

import pytest

from gerbereye import config, db
from gerbereye.export import CSV_COLUMNS, build_inspection_csv


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    """A database holding one failed inspection with two regions, one
    overridden, plus one clean inspection that flagged nothing."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "export.db")
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")

    conn = db.connect()
    board_type_id = db.get_or_create_board_type(conn, "export-board")

    failed = db.record_inspection(
        conn, board_type_id, "fail", "cad",
        [
            {"bbox": [10, 20, 30, 40], "area_px": 1200, "ref_des": "C14"},
            {"bbox": [50, 60, 20, 20], "area_px": 400, "ref_des": None},
        ],
    )
    first_region = db.list_regions(conn, failed)[0]["id"]
    db.add_override(conn, first_region, "false_call")

    db.record_inspection(conn, board_type_id, "pass", "differencing", [])

    yield conn
    conn.close()


def read_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def test_header_matches_declared_columns(seeded_db):
    rows = read_csv(build_inspection_csv(seeded_db))
    assert rows[0] == CSV_COLUMNS


def test_one_row_per_region(seeded_db):
    rows = read_csv(build_inspection_csv(seeded_db))
    body = rows[1:]
    # Two regions from the failed inspection, plus one placeholder row for the
    # clean inspection.
    assert len(body) == 3


def test_clean_inspection_still_appears(seeded_db):
    """A board that passed is a result worth recording. Dropping it would make
    the export look like the board was never inspected."""
    rows = read_csv(build_inspection_csv(seeded_db))
    verdict_column = CSV_COLUMNS.index("board_verdict")
    assert any(row[verdict_column] == "pass" for row in rows[1:])


def test_bbox_is_flattened_into_four_columns(seeded_db):
    rows = read_csv(build_inspection_csv(seeded_db))
    header = rows[0]
    for row in rows[1:]:
        record = dict(zip(header, row))
        if record["ref_des"] == "C14":
            assert record["bbox_x"] == "10"
            assert record["bbox_y"] == "20"
            assert record["bbox_w"] == "30"
            assert record["bbox_h"] == "40"
            return
    pytest.fail("no row found for C14")


def test_overridden_region_reports_yes_and_its_revised_verdict(seeded_db):
    rows = read_csv(build_inspection_csv(seeded_db))
    header = rows[0]
    records = [dict(zip(header, row)) for row in rows[1:]]

    overridden = [r for r in records if r["overridden"] == "yes"]
    assert len(overridden) == 1
    assert overridden[0]["region_verdict"] == "false_call"


def test_designator_is_present_for_named_regions(seeded_db):
    rows = read_csv(build_inspection_csv(seeded_db))
    header = rows[0]
    designators = {dict(zip(header, row))["ref_des"] for row in rows[1:]}
    assert "C14" in designators
