"""Prepare a ready-to-demo station in one command.

    python tools/seed_demo.py

Generates the demo boards if missing, then creates a board type with its golden
reference, component map and BOM already loaded — so the app opens straight
onto a station that can inspect immediately, with no setup clicking.

That matters for two reasons: a jury demo should not begin with five minutes of
configuration, and the RSK-07 fallback needs to be one command, not a
remembered sequence.

Safe to re-run: it resets the demo board type each time rather than
accumulating duplicates.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from gerbereye import config, db, demo, inspector
from gerbereye.pipeline import bom, footprints, placement

BOARD_TYPE_NAME = "Demo Board (60x40mm)"


def main() -> int:
    print("Preparing demo station\n")

    if not demo.ensure_demo_assets():
        print("FAIL  could not generate demo assets")
        print("      run: python tools/make_demo_boards.py")
        return 1
    print(f"  assets      {demo.DEMO_DIR}")

    config.ensure_dirs()
    conn = db.connect()
    try:
        # Reset rather than append, so re-running does not leave stale board
        # types cluttering the operator's picker.
        existing = conn.execute(
            "SELECT id FROM board_type WHERE name = ?", (BOARD_TYPE_NAME,)
        ).fetchone()
        if existing:
            board_type_id = int(existing["id"])
            conn.execute("DELETE FROM component WHERE board_type_id = ?", (board_type_id,))
            conn.execute("DELETE FROM golden_reference WHERE board_type_id = ?", (board_type_id,))
            conn.commit()
            print(f"  board type  reusing #{board_type_id}")
        else:
            board_type_id = db.create_board_type(conn, BOARD_TYPE_NAME)
            print(f"  board type  created #{board_type_id}")

        # Component map from the pick-and-place file.
        components = placement.parse_placement_file(demo.DEMO_DIR / "placement.csv")
        db.replace_components(conn, board_type_id, [c.as_dict() for c in components])
        print(f"  placement   {len(components)} components")

        # BOM marks C7 do-not-populate. Without this the demo would report C7
        # as a defect on every board, which is exactly the failure FR-002
        # exists to prevent.
        entries = bom.parse_bom_text((demo.DEMO_DIR / "bom.csv").read_text())
        excluded = bom.dnp_designators(entries)
        applied = db.set_dnp(conn, board_type_id, excluded)
        print(f"  bom         {len(entries)} entries, {applied} marked do-not-populate")

        inspectable = db.list_components(conn, board_type_id)
        coverage = footprints.summarise_coverage(inspectable)
        print(
            f"  footprints  {coverage['matched']}/{coverage['total']} matched"
            + (f", unmatched: {', '.join(coverage['unmatched_designators'])}"
               if coverage["unmatched"] else "")
        )

        # Golden reference, captured from the correctly-assembled render via
        # the same code path a real capture uses.
        golden = cv2.imread(str(demo.DEMO_DIR / "golden.png"))
        if golden is None:
            print("FAIL  could not read demo/golden.png")
            return 1
        camera = demo.DemoCamera()
        result = inspector.capture_golden(conn, camera, board_type_id, frame=golden)
        print(f"  golden      {Path(result['image_path']).name}")

        # Prove the station works before claiming it is ready. A seed script
        # that reports success without verifying is worth nothing at 3am.
        print("\nVerifying:")
        failures = 0
        for index, (name, description) in enumerate(demo.DEMO_BOARDS):
            frame = cv2.imread(str(demo.DEMO_DIR / f"{name}.png"))
            outcome = inspector.run_inspection(
                conn, camera, board_type_id, frame=frame, persist=False
            )
            named = sorted({r["ref_des"] for r in outcome.regions if r.get("ref_des")})
            expected_pass = name == "golden"
            ok = (outcome.verdict == "pass") == expected_pass
            failures += 0 if ok else 1
            flag = "ok " if ok else "BAD"
            detail = ", ".join(named) if named else "-"
            print(f"  {flag} {name:16} {outcome.verdict:4}  {len(outcome.regions)} regions  {detail}")

        if failures:
            print(f"\nFAIL  {failures} board(s) gave an unexpected verdict")
            return 1

        print(f"\nReady. Board type #{board_type_id} — {BOARD_TYPE_NAME}")
        print("\nStart the station in demo mode:")
        print("  GERBEREYE_DEMO=1 .venv/bin/python run.py")
        print("  cd web && npm run dev          # separate terminal")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
