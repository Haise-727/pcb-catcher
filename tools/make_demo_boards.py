"""Generate the bundled demo board set.

    python tools/make_demo_boards.py

Writes to `demo/` a synthetic but realistic PCB:

    golden.png            correctly assembled — the reference
    defect_missing.png    two components removed
    defect_rotated.png    an IC rotated 90 degrees
    defect_offset.png     a part shifted off its pads
    defect_mixed.png      one of each, for the headline demo
    placement.csv         pick-and-place for the same board
    bom.csv               BOM marking C7 do-not-populate

Why this exists: the hardware chain cannot be brought up on demand, and the
camera on the dev machine will not hold a fixed exposure (#35). A bundled board
set lets the entire pipeline run end to end with no camera attached — it is the
demo, the RSK-07 fallback, and the seeded-defect corpus that #37 needs, all at
once.

The rendering is deliberately plain: flat colours, hard edges, even lighting.
It is not pretending to be a photograph. What it does reproduce faithfully is
the *geometry* — real millimetre coordinates, a real design-to-pixel scale, and
ArUco markers at measured positions — so registration and naming exercise the
same code paths a real board would.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from a clone with no install step.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import csv
import math

import cv2
import numpy as np

from gerbereye.pipeline.registration import ARUCO_DICT

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "demo"

# --- Physical layout -------------------------------------------------------
# Board and marker geometry in millimetres. These are the numbers that must
# agree with DEFAULT_MARKER_POSITIONS_MM for the CAD path to register.
BOARD_W_MM, BOARD_H_MM = 60.0, 40.0
MARKER_MM = 6.0
PX_PER_MM = 16          # 960x640 board area
MARGIN_PX = 96          # must exceed half a marker tile (see draw_markers)

# Marker centres in design mm, matching gerbereye.inspector.
MARKERS_MM = {0: (0.0, 0.0), 1: (60.0, 0.0), 2: (60.0, 40.0), 3: (0.0, 40.0)}

# --- Colours (BGR) ---------------------------------------------------------
SOLDERMASK = (52, 92, 36)
SILKSCREEN = (222, 228, 226)
PAD = (168, 186, 196)
BODY_PASSIVE = (46, 46, 52)
BODY_IC = (34, 34, 38)
BODY_ELEC = (108, 74, 42)
PIN = (196, 208, 214)

# --- The board's components ------------------------------------------------
# (refdes, x_mm, y_mm, rotation_deg, package, w_mm, h_mm, polarised)
COMPONENTS = [
    ("R1",  10.0, 32.0,   0, "R_0805", 2.0, 1.2, False),
    ("R2",  16.0, 32.0,   0, "R_0805", 2.0, 1.2, False),
    ("R3",  22.0, 32.0,   0, "R_0805", 2.0, 1.2, False),
    ("R4",  28.0, 32.0,   0, "R_0805", 2.0, 1.2, False),
    ("R5",  10.0, 27.0,  90, "R_0603", 1.6, 0.8, False),
    ("R6",  16.0, 27.0,  90, "R_0603", 1.6, 0.8, False),
    ("C1",  34.0, 32.0,   0, "C_0805", 2.0, 1.2, False),
    ("C2",  40.0, 32.0,   0, "C_0805", 2.0, 1.2, False),
    ("C3",  46.0, 32.0,   0, "C_0805", 2.0, 1.2, False),
    ("C4",  22.0, 27.0,  90, "C_0603", 1.6, 0.8, False),
    ("C5",  28.0, 27.0,  90, "C_0603", 1.6, 0.8, False),
    ("C6",  50.0, 22.0,   0, "CP_Elec", 4.0, 4.0, True),
    # C7 is deliberately absent from every render: the BOM marks it
    # do-not-populate, so a correct system must never report it (FR-002).
    ("C7",  50.0, 10.0,   0, "C_0805", 2.0, 1.2, False),
    ("U1",  20.0, 16.0,   0, "SOIC-8", 6.0, 5.0, True),
    ("U2",  38.0, 16.0,   0, "SOIC-14", 9.0, 6.0, True),
    ("D1",   8.0, 20.0,   0, "SOD-123", 2.8, 1.6, True),
    ("D2",   8.0, 14.0,   0, "SOD-123", 2.8, 1.6, True),
    ("J1",   8.0,  6.0,   0, "Conn_2P", 6.0, 4.0, False),
    ("Q1",  30.0,  8.0,   0, "SOT-23", 3.0, 2.4, True),
    ("Q2",  38.0,  8.0,   0, "SOT-23", 3.0, 2.4, True),
]

# Designators the BOM marks do-not-populate.
DNP = {"C7"}


def mm_to_px(x_mm: float, y_mm: float) -> tuple[int, int]:
    """Design mm -> image pixels.

    Y is flipped: design coordinates run bottom-left origin upward (BR-02),
    image rows run top-down.
    """
    x = MARGIN_PX + x_mm * PX_PER_MM
    y = MARGIN_PX + (BOARD_H_MM - y_mm) * PX_PER_MM
    return int(round(x)), int(round(y))


def canvas_size() -> tuple[int, int]:
    return (
        int(BOARD_W_MM * PX_PER_MM) + MARGIN_PX * 2,
        int(BOARD_H_MM * PX_PER_MM) + MARGIN_PX * 2,
    )


def draw_rotated_rect(img, cx, cy, w_px, h_px, angle_deg, colour):
    """Filled rectangle rotated about its centre."""
    rect = ((cx, cy), (w_px, h_px), angle_deg)
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillConvexPoly(img, box, colour, lineType=cv2.LINE_AA)
    return box


def draw_component(img, spec, *, offset_mm=(0.0, 0.0), extra_rotation=0.0, skip=False):
    """Render one component, optionally displaced or rotated to seed a defect."""
    ref_des, x_mm, y_mm, rot, package, w_mm, h_mm, polarised = spec
    if skip:
        return

    cx, cy = mm_to_px(x_mm + offset_mm[0], y_mm + offset_mm[1])
    angle = rot + extra_rotation
    w_px, h_px = w_mm * PX_PER_MM, h_mm * PX_PER_MM

    if package.startswith(("R_", "C_")) and not package.startswith("CP"):
        # Chip passive: two pads with a dark body bridging them.
        pad_w = w_px * 0.32
        for sign in (-1, 1):
            dx = sign * (w_px / 2 - pad_w / 2)
            px = cx + dx * math.cos(math.radians(angle))
            py = cy - dx * math.sin(math.radians(angle))
            draw_rotated_rect(img, px, py, pad_w, h_px * 1.15, angle, PAD)
        draw_rotated_rect(img, cx, cy, w_px * 0.5, h_px, angle, BODY_PASSIVE)

    elif package.startswith("SOIC") or package.startswith("Conn"):
        pins = 8 if package == "SOIC-8" else (14 if package == "SOIC-14" else 4)
        per_side = max(pins // 2, 2)
        for sign in (-1, 1):
            for i in range(per_side):
                t = (i + 0.5) / per_side - 0.5
                lx, ly = t * w_px, sign * (h_px / 2)
                rx = cx + lx * math.cos(math.radians(angle)) - ly * math.sin(math.radians(angle))
                ry = cy - (lx * math.sin(math.radians(angle)) + ly * math.cos(math.radians(angle)))
                draw_rotated_rect(img, rx, ry, w_px / per_side * 0.45, h_px * 0.28, angle, PIN)
        body = BODY_IC if package.startswith("SOIC") else (60, 60, 66)
        draw_rotated_rect(img, cx, cy, w_px * 0.86, h_px * 0.82, angle, body)
        if polarised:
            # Pin-1 dot: the visual cue a polarity check would key on.
            ox, oy = -w_px * 0.32, -h_px * 0.24
            dx = cx + ox * math.cos(math.radians(angle)) - oy * math.sin(math.radians(angle))
            dy = cy - (ox * math.sin(math.radians(angle)) + oy * math.cos(math.radians(angle)))
            cv2.circle(img, (int(dx), int(dy)), max(int(h_px * 0.09), 2), SILKSCREEN, -1, cv2.LINE_AA)

    elif package.startswith("CP_Elec"):
        radius = int(w_px / 2)
        cv2.circle(img, (int(cx), int(cy)), radius, BODY_ELEC, -1, cv2.LINE_AA)
        cv2.circle(img, (int(cx), int(cy)), radius, (140, 100, 60), 2, cv2.LINE_AA)
        # Polarity stripe.
        cv2.ellipse(img, (int(cx), int(cy)), (radius, radius), angle, 120, 240, SILKSCREEN, -1)

    elif package.startswith("SOT"):
        for sign, count in ((-1, 2), (1, 1)):
            for i in range(count):
                t = (i + 0.5) / count - 0.5
                lx, ly = t * w_px * 0.8, sign * (h_px / 2)
                rx = cx + lx * math.cos(math.radians(angle)) - ly * math.sin(math.radians(angle))
                ry = cy - (lx * math.sin(math.radians(angle)) + ly * math.cos(math.radians(angle)))
                draw_rotated_rect(img, rx, ry, w_px * 0.22, h_px * 0.3, angle, PIN)
        draw_rotated_rect(img, cx, cy, w_px * 0.75, h_px * 0.7, angle, BODY_IC)

    else:  # SOD-123 diode
        draw_rotated_rect(img, cx, cy, w_px, h_px, angle, BODY_PASSIVE)
        ox = -w_px * 0.3
        sx = cx + ox * math.cos(math.radians(angle))
        sy = cy - ox * math.sin(math.radians(angle))
        draw_rotated_rect(img, sx, sy, w_px * 0.14, h_px, angle, SILKSCREEN)


def draw_markers(img):
    """Place the four ArUco markers at their design-mm positions."""
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    size_px = int(MARKER_MM * PX_PER_MM)
    for marker_id, (mx, my) in MARKERS_MM.items():
        cx, cy = mm_to_px(mx, my)
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, size_px)
        marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        # Quiet zone: the detector needs white space around the pattern.
        pad = size_px // 4
        tile = np.full((size_px + pad * 2, size_px + pad * 2, 3), 255, np.uint8)
        tile[pad:pad + size_px, pad:pad + size_px] = marker_bgr
        h, w = tile.shape[:2]
        y0, x0 = cy - h // 2, cx - w // 2
        y1, x1 = y0 + h, x0 + w
        if y0 < 0 or x0 < 0 or y1 > img.shape[0] or x1 > img.shape[1]:
            continue
        img[y0:y1, x0:x1] = tile


def render_board(defects: dict | None = None) -> np.ndarray:
    """Render the board. `defects` maps refdes -> how it is wrong."""
    defects = defects or {}
    width, height = canvas_size()
    img = np.full((height, width, 3), 24, np.uint8)

    # Board substrate.
    tl, br = mm_to_px(0, BOARD_H_MM), mm_to_px(BOARD_W_MM, 0)
    cv2.rectangle(img, tl, br, SOLDERMASK, -1)
    cv2.rectangle(img, tl, br, (30, 60, 22), 3)

    # Silkscreen designator labels, drawn under the parts like a real board.
    for spec in COMPONENTS:
        ref_des = spec[0]
        if ref_des in DNP:
            continue
        lx, ly = mm_to_px(spec[1], spec[2])
        cv2.putText(img, ref_des, (lx - 14, ly - int(spec[6] * PX_PER_MM / 2) - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150, 170, 155), 1, cv2.LINE_AA)

    for spec in COMPONENTS:
        ref_des = spec[0]
        # C7 is do-not-populate: never drawn on any board, correct or not.
        if ref_des in DNP:
            continue
        defect = defects.get(ref_des)
        if defect == "missing":
            draw_component(img, spec, skip=True)
        elif defect == "rotated":
            draw_component(img, spec, extra_rotation=90)
        elif defect == "offset":
            draw_component(img, spec, offset_mm=(1.4, 0.9))
        else:
            draw_component(img, spec)

    draw_markers(img)

    # Very light noise so the frames are not bit-identical, which would be
    # unrealistically clean and would hide alignment bugs.
    noise = np.random.default_rng(0).normal(0, 1.4, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def write_placement(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Rotation", "Layer", "Footprint"])
        for ref_des, x_mm, y_mm, rot, package, *_ in COMPONENTS:
            writer.writerow([ref_des, f"{x_mm:.2f}mm", f"{y_mm:.2f}mm", rot, "top", package])


def write_bom(path: Path) -> None:
    """BOM marking C7 do-not-populate, so the #31 exclusion is demonstrable."""
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Designator", "Value", "Footprint", "DNP"])
        for ref_des, _x, _y, _r, package, *_ in COMPONENTS:
            value = {"R": "10k", "C": "100nF", "U": "IC", "D": "1N4148", "J": "HDR", "Q": "MMBT3904"}.get(ref_des[0], "")
            writer.writerow([ref_des, value, package, "DNP" if ref_des in DNP else ""])


DEFECT_SETS = {
    "golden": {},
    "defect_missing": {"C2": "missing", "R3": "missing"},
    "defect_rotated": {"U1": "rotated"},
    "defect_offset": {"R5": "offset"},
    "defect_mixed": {"C2": "missing", "U1": "rotated", "R5": "offset"},
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, defects in DEFECT_SETS.items():
        image = render_board(defects)
        cv2.imwrite(str(OUTPUT_DIR / f"{name}.png"), image)
        described = ", ".join(f"{k}={v}" for k, v in defects.items()) or "correctly assembled"
        print(f"  {name}.png  ({described})")

    write_placement(OUTPUT_DIR / "placement.csv")
    write_bom(OUTPUT_DIR / "bom.csv")
    print(f"  placement.csv  ({len(COMPONENTS)} components)")
    print(f"  bom.csv        ({len(DNP)} marked DNP)")

    width, height = canvas_size()
    print(f"\nBoard {BOARD_W_MM}x{BOARD_H_MM}mm rendered at {width}x{height}px "
          f"({PX_PER_MM} px/mm)")
    print(f"Wrote to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
