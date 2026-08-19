"""CSV export of inspection records (FR-022).

OWNER: @YUVARAJ-R-ai — issue #16.

This module is deliberately the only file that task needs to touch. The route in
api.py already calls build_inspection_csv() and is finished, and
tests/test_export.py already asserts the expected behaviour. Implement the
function below until those tests pass and the feature is complete — no edits
anywhere else.

Why it matters for the pitch: "every board that passes through the station gets
a machine-generated record" is the traceability claim that lets an MSME bid on
work requiring an inspection trail. Today their answer to "what did you check?"
is a signature on a sheet.

Useful helpers already available:
    db.list_inspections(conn, limit=...)  -> newest-first inspection rows
    db.list_regions(conn, inspection_id)  -> regions with effective verdict

Column order must stay additive-only. An existing consumer's parser breaks if
columns are reordered or removed, so any new field goes on the end.
"""

from __future__ import annotations

import csv
import io
import sqlite3

from . import db

CSV_COLUMNS = [
    "inspection_id",
    "board_type",
    "inspected_at_utc",
    "board_verdict",
    "path_used",
    "region_id",
    "ref_des",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "area_px",
    "region_verdict",
    "overridden",
]


def build_inspection_csv(conn: sqlite3.Connection, limit: int = 500) -> str:
    """Render inspection records as CSV text, one row per inspected region.

    Required behaviour (asserted in tests/test_export.py):
      - First line is CSV_COLUMNS, in that order.
      - One row per region, carrying its parent inspection's fields alongside.
      - An inspection that flagged nothing still contributes exactly one row,
        with the region columns left empty. A clean board is a result worth
        recording, and dropping it would make the export look like the board
        was never inspected at all.
      - `overridden` is the string "yes" or "no", not a bool.
      - bbox is flattened from [x, y, w, h] into four separate columns.

    Args:
        conn: open database connection.
        limit: how many recent inspections to include, newest first.

    Returns:
        CSV text including the header row.
    """
    buffer = io.StringIO()
    # QUOTE_MINIMAL and \r\n keep the file readable by Excel, which is what an
    # MSME will actually open it in.
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)

    for inspection in db.list_inspections(conn, limit=limit):
        shared = [
            inspection["id"],
            inspection["board_type_name"],
            inspection["started_at"],
            inspection["verdict"],
            inspection["path_used"],
        ]

        regions = db.list_regions(conn, inspection["id"])
        if not regions:
            # A clean board still gets a row. Dropping it would make the export
            # look like the board was never inspected at all, which is the
            # opposite of the traceability claim this file exists to support.
            writer.writerow(shared + [""] * (len(CSV_COLUMNS) - len(shared)))
            continue

        for region in regions:
            x, y, w, h = region["bbox"]
            writer.writerow(
                shared
                + [
                    region["id"],
                    region["ref_des"] or "",
                    x,
                    y,
                    w,
                    h,
                    region["area_px"],
                    region["verdict"],
                    "yes" if region["overridden"] else "no",
                ]
            )

    return buffer.getvalue()
