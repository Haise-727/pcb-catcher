"""Do-not-populate exclusion tests — issue #31, FR-002.

The headline assertion is AC-002.1: a DNP designator emits no result of any
kind. Everything else here exists to stop that guarantee being eroded by a
parsing edge case.

A DNP designator sits empty on every board of its type. If it is ever inspected
it produces the same false call on every single inspection, forever, which is
the fastest way to make an operator stop trusting the station.
"""

from __future__ import annotations

import numpy as np
import pytest

from gerbereye import config, db
from gerbereye.pipeline import bom, placement, registration


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "dnp.db")
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "images")
    connection = db.connect()
    yield connection
    connection.close()


# --------------------------------------------------------------------------
# The requirement
# --------------------------------------------------------------------------

def test_dnp_designator_is_never_returned_for_inspection(conn):
    """AC-002.1 — a DNP designator emits no result of any kind."""
    board_type_id = db.get_or_create_board_type(conn, "dnp-board")
    db.replace_components(conn, board_type_id, [
        {"ref_des": "C1", "x_mm": 10.0, "y_mm": 10.0},
        {"ref_des": "C7", "x_mm": 20.0, "y_mm": 10.0, "dnp": True},
        {"ref_des": "R1", "x_mm": 30.0, "y_mm": 10.0},
    ])

    inspected = {c["ref_des"] for c in db.list_components(conn, board_type_id)}
    assert inspected == {"C1", "R1"}
    assert "C7" not in inspected


def test_dnp_component_can_never_be_named_on_a_defect_region(conn):
    """The exclusion must hold at the point it actually matters.

    Even if a region appears exactly where the DNP part would be, no box exists
    for it, so no defect can carry its designator.
    """
    board_type_id = db.get_or_create_board_type(conn, "naming")
    db.replace_components(conn, board_type_id, [
        {"ref_des": "C1", "x_mm": 10.0, "y_mm": 10.0},
        {"ref_des": "C7", "x_mm": 30.0, "y_mm": 20.0, "dnp": True},
    ])

    components = db.list_components(conn, board_type_id)
    identity = np.eye(3, dtype=np.float32)
    boxes = registration.project_components(identity, components)

    assert "C1" in boxes
    assert "C7" not in boxes


def test_excluded_count_is_reported_at_setup(conn):
    """AC-002.2 — a silent exclusion is nearly as bad as none at all.

    The technician has to notice if a BOM knocks out more of the board than
    expected.
    """
    board_type_id = db.get_or_create_board_type(conn, "counted")
    db.replace_components(conn, board_type_id, [
        {"ref_des": "C1", "x_mm": 1.0, "y_mm": 1.0},
        {"ref_des": "C7", "x_mm": 2.0, "y_mm": 1.0, "dnp": True},
        {"ref_des": "C8", "x_mm": 3.0, "y_mm": 1.0, "dnp": True},
    ])

    assert db.count_dnp(conn, board_type_id) == 2
    listed = db.list_board_types(conn)[0]
    assert listed["component_count"] == 1   # inspectable only
    assert listed["dnp_count"] == 2


def test_dnp_entries_are_still_retrievable_for_display(conn):
    """Excluded from inspection, not erased -- setup still needs to show them."""
    board_type_id = db.get_or_create_board_type(conn, "display")
    db.replace_components(conn, board_type_id, [
        {"ref_des": "C1", "x_mm": 1.0, "y_mm": 1.0},
        {"ref_des": "C7", "x_mm": 2.0, "y_mm": 1.0, "dnp": True},
    ])

    everything = db.list_components(conn, board_type_id, include_dnp=True)
    assert {c["ref_des"] for c in everything} == {"C1", "C7"}
    assert next(c for c in everything if c["ref_des"] == "C7")["dnp"] == 1


# --------------------------------------------------------------------------
# BOM parsing
# --------------------------------------------------------------------------

def test_bom_dedicated_dnp_column():
    entries = bom.parse_bom_text(
        "Designator,Value,DNP\nC1,100nF,\nC7,100nF,DNP\nR1,10k,\n"
    )
    assert bom.dnp_designators(entries) == {"C7"}


def test_bom_populate_column_has_inverted_polarity():
    """A 'Populate' column means the opposite of a 'DNP' column.

    Reading one as the other would exclude every fitted component on the board.
    """
    entries = bom.parse_bom_text(
        "Designator,Value,Populate\nC1,100nF,Yes\nC7,100nF,No\n"
    )
    assert bom.dnp_designators(entries) == {"C7"}


def test_bom_grouped_designators_are_expanded():
    """BOM rows routinely cover several parts sharing a value."""
    entries = bom.parse_bom_text(
        "Designator,Value,DNP\n\"C1,C2,C5\",100nF,DNP\nR1,10k,\n"
    )
    assert bom.dnp_designators(entries) == {"C1", "C2", "C5"}


def test_bom_free_text_dnp_marker_in_any_cell():
    entries = bom.parse_bom_text("Designator,Value\nC1,100nF\nC7,DNP\n")
    assert bom.dnp_designators(entries) == {"C7"}


def test_bom_without_designator_column_is_rejected():
    with pytest.raises(bom.BomParseError, match="designator column"):
        bom.parse_bom_text("Part,Qty\nfoo,1\n")


def test_bom_applies_only_to_components_that_exist(conn):
    """A BOM naming parts absent from the placement file must not invent rows."""
    board_type_id = db.get_or_create_board_type(conn, "partial")
    db.replace_components(conn, board_type_id, [
        {"ref_des": "C1", "x_mm": 1.0, "y_mm": 1.0},
        {"ref_des": "C7", "x_mm": 2.0, "y_mm": 1.0},
    ])

    entries = bom.parse_bom_text("Designator,DNP\nC7,DNP\nC99,DNP\n")
    matched = db.set_dnp(conn, board_type_id, bom.dnp_designators(entries))

    assert matched == 1
    assert {c["ref_des"] for c in db.list_components(conn, board_type_id)} == {"C1"}


# --------------------------------------------------------------------------
# Placement-file DNP hints
# --------------------------------------------------------------------------

def test_placement_dnp_column_marks_component():
    components = placement.parse_placement_text(
        "Designator,X,Y,DNP\nC1,10,10,\nC7,20,20,DNP\n"
    )
    assert {c.ref_des for c in components if c.dnp} == {"C7"}


def test_placement_dnp_column_no_means_fitted():
    """In a column headed DNP, 'no' means NOT do-not-populate.

    Reading it the other way round would silently exclude the whole board --
    the exact failure this test exists to prevent regressing.
    """
    components = placement.parse_placement_text(
        "Designator,X,Y,DNP\nC1,10,10,no\nR1,20,20,yes\n"
    )
    assert [c.dnp for c in components] == [False, True]


def test_placement_populate_column_is_inverted():
    components = placement.parse_placement_text(
        "Designator,X,Y,Populate\nC1,10,10,yes\nC7,20,20,no\n"
    )
    assert {c.ref_des for c in components if c.dnp} == {"C7"}


def test_placement_without_dnp_column_marks_nothing():
    """The common case: no populate information available, inspect everything."""
    components = placement.parse_placement_text(
        "Designator,X,Y\nC1,10,10\nC7,20,20\n"
    )
    assert not any(c.dnp for c in components)


# --------------------------------------------------------------------------
# Migration
# --------------------------------------------------------------------------

def test_legacy_database_gains_dnp_column(tmp_path, monkeypatch):
    """A database written before the column existed must upgrade in place,
    with its existing rows intact (NFR-012)."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        "CREATE TABLE board_type (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);"
        "CREATE TABLE component (board_type_id INTEGER NOT NULL, ref_des TEXT NOT NULL,"
        " x_mm REAL NOT NULL, y_mm REAL NOT NULL, rotation_deg REAL NOT NULL,"
        " side TEXT NOT NULL, footprint TEXT, PRIMARY KEY (board_type_id, ref_des));"
        "INSERT INTO board_type VALUES (1,'legacy','2026-01-01');"
        "INSERT INTO component VALUES (1,'R1',1,2,0,'top','R_0603');"
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "GOLDEN_DIR", tmp_path / "g")
    monkeypatch.setattr(config, "IMAGE_DIR", tmp_path / "i")

    upgraded = db.connect()
    try:
        columns = {r["name"] for r in upgraded.execute("PRAGMA table_info(component)")}
        assert "dnp" in columns
        rows = db.list_components(upgraded, 1)
        assert [r["ref_des"] for r in rows] == ["R1"]
        assert rows[0]["dnp"] == 0
    finally:
        upgraded.close()
