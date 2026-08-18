"""Render a Gerber layer to PNG and report its coordinate extents — issue #10.

    python tools/render_gerber.py path/to/board.gbr [-o out.png]

Two purposes:

  1. Confirm pygerber parses the board's design files at all, before the CAD
     path depends on them.
  2. Print the coordinate extents in millimetres, so the board's origin and
     orientation can be checked against BR-02 (origin lower-left, X right,
     Y up). A pick-and-place file whose origin disagrees with the Gerber
     places every projected component box in the wrong spot, and that is far
     easier to catch here than by squinting at a misaligned overlay.

The rendered image is not used by the inspection path -- registration works
from ArUco markers and pick-and-place coordinates. This is a verification
tool, not a pipeline stage.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step: put the repo root on the
# path so `import gerbereye` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gerber", type=Path, help="Gerber file (.gbr, .gtl, .gto ...)")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output PNG")
    parser.add_argument("--dpmm", type=int, default=40, help="render resolution, dots per mm")
    args = parser.parse_args()

    if not args.gerber.is_file():
        print(f"FAIL  no such file: {args.gerber}")
        return 2

    try:
        from pygerber.gerberx3.api.v2 import GerberFile
    except ImportError:
        print("FAIL  pygerber not installed. Run: .venv/bin/pip install -r requirements.txt")
        return 2

    output = args.output or args.gerber.with_suffix(".png")

    try:
        parsed = GerberFile.from_file(str(args.gerber)).parse()
    except Exception as exc:
        # Malformed customer files are expected, not exceptional -- name the
        # file and the reason so it can be fixed rather than guessed at.
        print(f"FAIL  could not parse {args.gerber.name}: {exc}")
        return 1

    try:
        image = parsed.render_raster(str(output), dpmm=args.dpmm)
    except Exception as exc:
        print(f"FAIL  parsed but could not render: {exc}")
        return 1

    print(f"PASS  rendered {args.gerber.name} -> {output}")

    # Extents tell you whether the origin convention matches BR-02. A board
    # whose X or Y minimum is strongly negative is using a different origin
    # than the pick-and-place file probably assumes.
    info = getattr(image, "image_info", None)
    if info is not None:
        print("\n  coordinate extents (mm)")
        print(f"    X  {info.min_x_mm:8.3f} .. {info.max_x_mm:8.3f}   width  {info.width_mm:7.3f}")
        print(f"    Y  {info.min_y_mm:8.3f} .. {info.max_y_mm:8.3f}   height {info.height_mm:7.3f}")
        if info.min_x_mm < -0.01 or info.min_y_mm < -0.01:
            print("\n  NOTE  origin is not at the lower-left corner of the board.")
            print("        Check the pick-and-place file uses the same origin (BR-02),")
            print("        otherwise every projected component box will be offset.")

    print("\nOpen the PNG and confirm the orientation matches the physical board")
    print("as the camera sees it. If it is mirrored, the bottom layer was rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
