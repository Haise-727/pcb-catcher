"""Image retention sweep.

FR-024, NFR-002. Every inspection writes a frame to disk and nothing removed
them, so storage grew without bound. At 100+ boards a shift that fills a shop
laptop in weeks, and an inspection station that stops working because its disk
is full is a worse failure than one that keeps no images at all.

## The rule that must not be broken

The sweep deletes **image files** and nulls the path columns pointing at them.
It never deletes an `inspection`, `region_verdict` or `override` row.

Those rows are the audit trail (NFR-012), and they are what lets an MSME answer
"what did you inspect?" months later. Deleting them to reclaim space would turn
a traceability record into a database that merely happens to contain some
history — which is exactly the capability the product is sold on.

So the record survives forever; only the pixels expire. A months-old inspection
still reports what was found, when, by whom, and which components were
involved. It just cannot show you the photograph any more.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import logging_setup

# Default window. Long enough that a QA supervisor reviewing last month's
# escapes still has the images, short enough to bound disk use.
DEFAULT_RETENTION_DAYS = 30


@dataclass
class SweepResult:
    files_deleted: int = 0
    bytes_reclaimed: int = 0
    rows_updated: int = 0
    missing_files: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "files_deleted": self.files_deleted,
            "bytes_reclaimed": self.bytes_reclaimed,
            "rows_updated": self.rows_updated,
            "missing_files": self.missing_files,
            "errors": self.errors,
        }


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _delete_file(path_str: str, result: SweepResult) -> bool:
    """Remove one image. Returns True when the row should be nulled.

    A file that is already gone still counts as handled -- the point of the
    sweep is that no row keeps pointing at an image the station cannot produce,
    and a manually deleted file leaves exactly that dangling reference.
    """
    path = Path(path_str)
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        result.missing_files += 1
        return True
    except OSError as exc:
        result.errors.append(f"{path}: {exc}")
        return False

    try:
        path.unlink()
    except OSError as exc:
        # A permissions problem should not abort the whole sweep, and it must
        # not null the row either -- the file is still there.
        result.errors.append(f"{path}: {exc}")
        return False

    result.files_deleted += 1
    result.bytes_reclaimed += size
    return True


def sweep(
    conn: sqlite3.Connection, retention_days: int = DEFAULT_RETENTION_DAYS
) -> SweepResult:
    """Delete inspection images older than the retention window.

    Golden references are deliberately exempt: a board type's reference is not
    inspection history, it is configuration, and deleting it would break every
    future inspection of that board type.
    """
    result = SweepResult()
    cutoff = _cutoff(retention_days)

    rows = conn.execute(
        "SELECT id, frame_path FROM inspection"
        " WHERE frame_path IS NOT NULL AND started_at < ?",
        (cutoff,),
    ).fetchall()

    for row in rows:
        if _delete_file(row["frame_path"], result):
            # Null the path rather than the row. The inspection, its verdict
            # and every region it found remain queryable and exportable.
            conn.execute(
                "UPDATE inspection SET frame_path = NULL WHERE id = ?", (row["id"],)
            )
            result.rows_updated += 1

    conn.commit()

    logging_setup.log_event(
        "retention_sweep",
        retention_days=retention_days,
        **result.as_dict(),
    )
    return result


def usage(conn: sqlite3.Connection) -> dict:
    """Current image footprint, for deciding whether a sweep is due."""
    rows = conn.execute(
        "SELECT frame_path FROM inspection WHERE frame_path IS NOT NULL"
    ).fetchall()

    total_bytes = 0
    present = 0
    for row in rows:
        try:
            total_bytes += Path(row["frame_path"]).stat().st_size
            present += 1
        except OSError:
            # Counted via `dangling` rather than raising: a missing file is a
            # normal state after a manual cleanup.
            continue

    return {
        "inspections_with_images": len(rows),
        "images_present": present,
        "dangling_references": len(rows) - present,
        "bytes": total_bytes,
        "megabytes": round(total_bytes / (1024 * 1024), 2),
    }


def verdict_row_count(conn: sqlite3.Connection) -> dict:
    """Counts of the rows the sweep must never touch.

    Used by the test that asserts retention is non-destructive, and useful as a
    sanity check after a sweep on a real station.
    """
    return {
        "inspections": conn.execute("SELECT COUNT(*) AS n FROM inspection").fetchone()["n"],
        "region_verdicts": conn.execute("SELECT COUNT(*) AS n FROM region_verdict").fetchone()["n"],
        "overrides": conn.execute("SELECT COUNT(*) AS n FROM override").fetchone()["n"],
    }
