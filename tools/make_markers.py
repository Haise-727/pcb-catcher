"""Generate the printable ArUco marker sheet for the jig — issue #5.

    python tools/make_markers.py

Writes tools/markers/aruco_jig_sheet.png. Print it at 100% scale (no "fit to
page" — that changes the physical size and invalidates the measurements), then
tape the four markers around the board position on the jig.

Why printed markers and not the board's own copper fiducials: copper fiducials
are small, low-contrast and easily confused with vias and test points. Printed
ArUco markers give the same four point correspondences with a far more
forgiving detector, and they work on boards that carry no fiducials at all
(the RSK-03 fallback).

After taping them down, measure the centre-to-centre distances and update
DEFAULT_MARKER_POSITIONS_MM in gerbereye/inspector.py. The homography maps
design millimetres onto pixels, so those numbers must match reality.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step: put the repo root on the
# path so `import gerbereye` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from gerbereye.pipeline.registration import ARUCO_DICT

OUTPUT_DIR = Path(__file__).parent / "markers"

# Printed size per marker. 25mm is large enough to detect reliably at 1080p
# from typical jig height, small enough to sit outside the board outline.
MARKER_MM = 25
DPI = 300
MARKER_PX = int(MARKER_MM / 25.4 * DPI)

# Quiet zone. ArUco detection needs white space around the pattern; without it
# the detector misses markers that are otherwise perfectly in focus.
QUIET_PX = MARKER_PX // 4


def render_marker(marker_id: int) -> np.ndarray:
    """One marker with its quiet zone and a printed id label."""
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER_PX)

    canvas = np.full(
        (MARKER_PX + QUIET_PX * 2, MARKER_PX + QUIET_PX * 2), 255, dtype=np.uint8
    )
    canvas[QUIET_PX : QUIET_PX + MARKER_PX, QUIET_PX : QUIET_PX + MARKER_PX] = marker

    cv2.putText(
        canvas, f"ID {marker_id}", (QUIET_PX, canvas.shape[0] - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA,
    )
    return canvas


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tiles = [render_marker(i) for i in range(4)]
    tile_h, tile_w = tiles[0].shape
    gap = QUIET_PX

    # 2x2 layout, matching the corner order the inspector expects:
    #   0 = bottom-left origin, 1 = bottom-right, 2 = top-right, 3 = top-left.
    sheet = np.full((tile_h * 2 + gap, tile_w * 2 + gap), 255, dtype=np.uint8)
    positions = {
        3: (0, 0),
        2: (0, tile_w + gap),
        0: (tile_h + gap, 0),
        1: (tile_h + gap, tile_w + gap),
    }
    for marker_id, (top, left) in positions.items():
        sheet[top : top + tile_h, left : left + tile_w] = tiles[marker_id]

    out = OUTPUT_DIR / "aruco_jig_sheet.png"
    cv2.imwrite(str(out), sheet)

    for marker_id, tile in enumerate(tiles):
        cv2.imwrite(str(OUTPUT_DIR / f"aruco_{marker_id}.png"), tile)

    print(f"Wrote {out}")
    print(f"  marker size   {MARKER_MM}mm at {DPI} DPI")
    print("  layout        ID3 top-left, ID2 top-right, ID0 bottom-left, ID1 bottom-right")
    print("\nNext:")
    print("  1. Print at 100% scale — do NOT use 'fit to page'.")
    print("  2. Tape the markers around the board position on the jig.")
    print("  3. Measure centre-to-centre distances in mm.")
    print("  4. Update DEFAULT_MARKER_POSITIONS_MM in gerbereye/inspector.py.")
    print("  5. Verify with: python tools/detect_markers.py")


if __name__ == "__main__":
    main()
