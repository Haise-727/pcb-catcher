"""SQLite persistence layer.

Physical realisation of system-model.md §1, cut to the tables the 8-hour MVP
actually needs.

Two structural rules carried over from the full design:

  1. Verdict tables are append-only. This module exposes no UPDATE or DELETE for
     `inspection`, `region_verdict` or `override`. A correction is a new
     `override` row, never a mutation of the original. That is what makes the
     audit trail real rather than a policy statement.

  2. Images live on the filesystem with paths held here. Storing multi-megabyte
     blobs inline would blow the memory ceiling on read.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import config

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS board_type (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

-- Per-board-type tuning. Kept out of code so a threshold change needs no
-- rebuild (NFR-013, ADR-004).
CREATE TABLE IF NOT EXISTS thresholds (
    board_type_id   INTEGER PRIMARY KEY REFERENCES board_type(id),
    diff_intensity  INTEGER NOT NULL,
    min_region_area INTEGER NOT NULL,
    blur_kernel     INTEGER NOT NULL,
    roi_scale       REAL    NOT NULL
);

-- Appended, never overwritten: golden boards get damaged or superseded, and
-- the history of what was used as reference is part of the audit trail.
CREATE TABLE IF NOT EXISTS golden_reference (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    board_type_id INTEGER NOT NULL REFERENCES board_type(id),
    image_path    TEXT NOT NULL,
    captured_at   TEXT NOT NULL
);

-- Component map from the pick-and-place file. Composite key enforces BR-01
-- (refdes unique within a board type) at the schema level, so a duplicate in a
-- customer file surfaces as a constraint violation rather than app logic.
CREATE TABLE IF NOT EXISTS component (
    board_type_id INTEGER NOT NULL REFERENCES board_type(id),
    ref_des       TEXT    NOT NULL,
    x_mm          REAL    NOT NULL,
    y_mm          REAL    NOT NULL,
    rotation_deg  REAL    NOT NULL,
    side          TEXT    NOT NULL,
    footprint     TEXT,
    PRIMARY KEY (board_type_id, ref_des)
);

CREATE TABLE IF NOT EXISTS inspection (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    board_type_id INTEGER NOT NULL REFERENCES board_type(id),
    started_at    TEXT    NOT NULL,
    verdict       TEXT    NOT NULL,
    path_used     TEXT    NOT NULL,
    frame_path    TEXT
);

CREATE TABLE IF NOT EXISTS region_verdict (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES inspection(id),
    bbox_json     TEXT    NOT NULL,
    ref_des       TEXT,
    area_px       INTEGER NOT NULL
);

-- A correction is a new row here. The original region_verdict is never edited.
CREATE TABLE IF NOT EXISTS override (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    region_verdict_id INTEGER NOT NULL REFERENCES region_verdict(id),
    original_verdict  TEXT NOT NULL,
    revised_verdict   TEXT NOT NULL,
    created_at        TEXT NOT NULL
);
"""


def utc_now() -> str:
    """Timestamps are stored UTC ISO-8601 so exports collate correctly."""
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    """Open the local database, creating it and its schema on first use."""
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL lets the UI read while an inspection is being written.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------
# Board types
# --------------------------------------------------------------------------

def create_board_type(conn: sqlite3.Connection, name: str) -> int:
    """Create a board type seeded with the default thresholds."""
    cur = conn.execute(
        "INSERT INTO board_type (name, created_at) VALUES (?, ?)",
        (name, utc_now()),
    )
    board_type_id = int(cur.lastrowid)
    t = config.THRESHOLDS
    conn.execute(
        "INSERT INTO thresholds (board_type_id, diff_intensity, min_region_area,"
        " blur_kernel, roi_scale) VALUES (?, ?, ?, ?, ?)",
        (board_type_id, t.diff_intensity, t.min_region_area, t.blur_kernel, t.roi_scale),
    )
    conn.commit()
    return board_type_id


def get_or_create_board_type(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM board_type WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return int(row["id"])
    return create_board_type(conn, name)


def list_board_types(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT b.id, b.name, b.created_at,"
        "       (SELECT COUNT(*) FROM component c WHERE c.board_type_id = b.id) AS component_count,"
        "       (SELECT COUNT(*) FROM golden_reference g WHERE g.board_type_id = b.id) AS golden_count"
        " FROM board_type b ORDER BY b.id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_thresholds(conn: sqlite3.Connection, board_type_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM thresholds WHERE board_type_id = ?", (board_type_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"no thresholds row for board type {board_type_id}")
    return dict(row)


def update_thresholds(conn: sqlite3.Connection, board_type_id: int, **fields: Any) -> None:
    """Tuning knob for FR/NFR threshold work. Thresholds are config, not verdicts,
    so unlike the verdict tables they are legitimately mutable."""
    allowed = {"diff_intensity", "min_region_area", "blur_kernel", "roi_scale"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE thresholds SET {assignments} WHERE board_type_id = ?",
        (*updates.values(), board_type_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Golden references
# --------------------------------------------------------------------------

def add_golden_reference(conn: sqlite3.Connection, board_type_id: int, image_path: Path) -> int:
    cur = conn.execute(
        "INSERT INTO golden_reference (board_type_id, image_path, captured_at)"
        " VALUES (?, ?, ?)",
        (board_type_id, str(image_path), utc_now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def latest_golden_reference(conn: sqlite3.Connection, board_type_id: int) -> dict[str, Any] | None:
    """Supersession is by recency — the newest row wins, older ones are kept."""
    row = conn.execute(
        "SELECT * FROM golden_reference WHERE board_type_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (board_type_id,),
    ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------
# Components (pick-and-place map)
# --------------------------------------------------------------------------

def replace_components(
    conn: sqlite3.Connection, board_type_id: int, components: Iterable[dict[str, Any]]
) -> int:
    """Write the component map for a board type, replacing any previous map.

    Components are design data, not verdicts, so re-ingesting a corrected
    pick-and-place file legitimately replaces them.
    """
    conn.execute("DELETE FROM component WHERE board_type_id = ?", (board_type_id,))
    rows = [
        (
            board_type_id,
            c["ref_des"],
            c["x_mm"],
            c["y_mm"],
            c.get("rotation_deg", 0.0),
            c.get("side", "top"),
            c.get("footprint"),
        )
        for c in components
    ]
    conn.executemany(
        "INSERT INTO component (board_type_id, ref_des, x_mm, y_mm, rotation_deg,"
        " side, footprint) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def list_components(conn: sqlite3.Connection, board_type_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT ref_des, x_mm, y_mm, rotation_deg, side, footprint"
        " FROM component WHERE board_type_id = ? ORDER BY ref_des",
        (board_type_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Inspections — append-only from here down
# --------------------------------------------------------------------------

def record_inspection(
    conn: sqlite3.Connection,
    board_type_id: int,
    verdict: str,
    path_used: str,
    regions: Iterable[dict[str, Any]],
    frame_path: Path | None = None,
) -> int:
    """Persist one inspection and its regions as a single transaction.

    The inspection row is only visible once its regions are committed alongside
    it, so a crash mid-write cannot leave a verdict with no supporting detail.
    """
    cur = conn.execute(
        "INSERT INTO inspection (board_type_id, started_at, verdict, path_used, frame_path)"
        " VALUES (?, ?, ?, ?, ?)",
        (board_type_id, utc_now(), verdict, path_used, str(frame_path) if frame_path else None),
    )
    inspection_id = int(cur.lastrowid)
    conn.executemany(
        "INSERT INTO region_verdict (inspection_id, bbox_json, ref_des, area_px)"
        " VALUES (?, ?, ?, ?)",
        [
            (inspection_id, json.dumps(r["bbox"]), r.get("ref_des"), int(r["area_px"]))
            for r in regions
        ],
    )
    conn.commit()
    return inspection_id


def get_inspection(conn: sqlite3.Connection, inspection_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM inspection WHERE id = ?", (inspection_id,)).fetchone()
    if row is None:
        return None
    inspection = dict(row)
    inspection["regions"] = list_regions(conn, inspection_id)
    return inspection


def list_regions(conn: sqlite3.Connection, inspection_id: int) -> list[dict[str, Any]]:
    """Regions with their effective verdict.

    The effective verdict is the most recent override if one exists, otherwise
    the original. Resolving it in the query keeps the original row untouched
    while still letting callers read current state in one hop.
    """
    rows = conn.execute(
        "SELECT r.id, r.bbox_json, r.ref_des, r.area_px,"
        "       (SELECT o.revised_verdict FROM override o"
        "         WHERE o.region_verdict_id = r.id ORDER BY o.id DESC LIMIT 1) AS revised"
        " FROM region_verdict r WHERE r.inspection_id = ? ORDER BY r.id",
        (inspection_id,),
    ).fetchall()
    regions = []
    for r in rows:
        regions.append(
            {
                "id": r["id"],
                "bbox": json.loads(r["bbox_json"]),
                "ref_des": r["ref_des"],
                "area_px": r["area_px"],
                "verdict": r["revised"] or "defect",
                "overridden": r["revised"] is not None,
            }
        )
    return regions


def list_inspections(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.id, i.board_type_id, b.name AS board_type_name, i.started_at,"
        "       i.verdict, i.path_used,"
        "       (SELECT COUNT(*) FROM region_verdict r WHERE r.inspection_id = i.id) AS region_count"
        " FROM inspection i JOIN board_type b ON b.id = i.board_type_id"
        " ORDER BY i.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_override(
    conn: sqlite3.Connection, region_verdict_id: int, revised_verdict: str
) -> int:
    """Append a correction. The original region_verdict row is left untouched."""
    row = conn.execute(
        "SELECT id FROM region_verdict WHERE id = ?", (region_verdict_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"no region verdict {region_verdict_id}")
    cur = conn.execute(
        "INSERT INTO override (region_verdict_id, original_verdict, revised_verdict, created_at)"
        " VALUES (?, ?, ?, ?)",
        (region_verdict_id, "defect", revised_verdict, utc_now()),
    )
    conn.commit()
    return int(cur.lastrowid)
