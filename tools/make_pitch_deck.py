"""Generate the VITISH 2026 idea PPT from the official template.

    .venv/bin/python tools/make_pitch_deck.py

Fills `docs/presentation/VITISH'26_IdeaTemplate.pptx` with the GerberEye idea
and writes `docs/presentation/GerberEye_VITISH2026_Idea.pptx`.

Written as a script rather than hand-edited slides so the deck can be
regenerated after any number change -- the figures here are pulled from the
same places the docs quote, and a deck edited by hand drifts from them within a
day.

Template rules it obeys (from the instructions slide, which it deletes):
  - maximum seven slides including the title page
  - points, diagrams and tables rather than paragraphs
  - the section headings are the template's and are not reworded
  - export to PDF before uploading to the portal
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "presentation" / "VITISH'26_IdeaTemplate.pptx"
OUTPUT = ROOT / "docs" / "presentation" / "GerberEye_VITISH2026_Idea.pptx"

# -- palette ----------------------------------------------------------------
# Blue is the template's own accent (0070C0); everything else is chosen to sit
# beside it without competing with the ministry logos along the top.
NAVY = RGBColor(0x1F, 0x38, 0x64)
BLUE = RGBColor(0x00, 0x70, 0xC0)
PALE = RGBColor(0xDE, 0xEB, 0xF7)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
PALE_GREEN = RGBColor(0xE6, 0xF2, 0xE7)
RED = RGBColor(0xC0, 0x00, 0x00)
PALE_RED = RGBColor(0xFB, 0xE9, 0xE9)
AMBER = RGBColor(0xBF, 0x8F, 0x00)
GREY = RGBColor(0x59, 0x59, 0x59)
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BORDER = RGBColor(0xBF, 0xBF, 0xBF)

BODY_FONT = "Calibri"
TITLE_FONT = "Times New Roman"

# Logos occupy y 0.19-1.03in across the full width, so content starts below.
TITLE_Y, TITLE_H = 1.06, 0.56
BODY_TOP, BODY_BOTTOM = 1.72, 6.98
LEFT, RIGHT = 0.42, 12.91
FULL_W = RIGHT - LEFT


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def drop(shape) -> None:
    shape._element.getparent().remove(shape._element)


def find(slide, name: str):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    return None


def clear_guidance(slide, *names: str) -> None:
    """Remove the template's 'describe your idea here' prompt boxes."""
    for name in names:
        shape = find(slide, name)
        if shape is not None:
            drop(shape)


def set_title(slide, text: str) -> None:
    """Retitle in place, normalised to one position across the deck."""
    for shape in slide.shapes:
        if shape.is_placeholder and shape.name.startswith("Title"):
            shape.left, shape.top = Inches(LEFT), Inches(TITLE_Y)
            shape.width, shape.height = Inches(FULL_W), Inches(TITLE_H)
            frame = shape.text_frame
            frame.word_wrap = True
            frame.clear()
            para = frame.paragraphs[0]
            para.alignment = PP_ALIGN.LEFT
            run = para.add_run()
            run.text = text
            run.font.size = Pt(25)
            run.font.bold = True
            run.font.name = TITLE_FONT
            run.font.color.rgb = NAVY
            return


def rule(slide, y: float) -> None:
    """Thin accent rule under the title, tying the page to the template blue."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LEFT), Inches(y),
                                 Inches(FULL_W), Inches(0.035))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE
    bar.line.fill.background()
    bar.shadow.inherit = False


def panel(slide, x, y, w, h, fill=WHITE, line=BORDER, radius=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    if radius:
        shape.adjustments[0] = 0.06
    shape.text_frame.word_wrap = True
    return shape


def header(slide, x, y, w, text, colour=BLUE, size=12):
    """A section cap: coloured bar with white text."""
    bar = panel(slide, x, y, w, 0.30, fill=colour, line=None)
    frame = bar.text_frame
    frame.margin_left, frame.margin_right = Inches(0.09), Inches(0.05)
    frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = frame.paragraphs[0]
    para.alignment = PP_ALIGN.LEFT
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.name = BODY_FONT
    run.font.color.rgb = WHITE
    return bar


def bullets(slide, x, y, w, h, items, size=11.5, colour=RGBColor(0x26, 0x26, 0x26)):
    """items: list of (text, level, bold) or plain strings.

    Segments wrapped in ** ** inside a string are emitted bold, so a line can
    carry emphasis without needing to be split by the caller.
    """
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(0.04)
    frame.margin_top = frame.margin_bottom = 0

    for index, item in enumerate(items):
        text, level, bold = (item if isinstance(item, tuple) else (item, 0, False))
        para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        para.space_after = Pt(3)
        para.space_before = Pt(0)
        para.line_spacing = 0.95
        prefix = "" if level == 0 else "    "
        marker = "▸  " if level == 0 else "–  "
        if text.startswith("!"):          # a lead line, no bullet marker
            text, marker = text[1:], ""

        # The marker is its own run. Folding it into the first text chunk lost
        # it whenever a line opened with bold, because that chunk is empty.
        if prefix or marker:
            lead = para.add_run()
            lead.text = prefix + marker
            lead.font.size = Pt(size)
            lead.font.name = BODY_FONT
            lead.font.color.rgb = colour

        for chunk_index, chunk in enumerate(text.split("**")):
            if not chunk:
                continue
            run = para.add_run()
            run.text = chunk
            run.font.size = Pt(size)
            run.font.name = BODY_FONT
            run.font.bold = bold or bool(chunk_index % 2)
            run.font.color.rgb = colour
    return box


def table(slide, x, y, w, headers, rows, col_ratios=None,
          head_fill=NAVY, size=10, head_size=10, row_h=0.26, head_h=0.28,
          cell_colours=None):
    """A styled table. cell_colours: {(row, col): RGBColor} for text accents."""
    shape = slide.shapes.add_table(len(rows) + 1, len(headers),
                                   Inches(x), Inches(y), Inches(w),
                                   Inches(head_h + row_h * len(rows)))
    tbl = shape.table
    tbl.first_row = True
    tbl.horz_banding = False

    if col_ratios:
        total = sum(col_ratios)
        for index, ratio in enumerate(col_ratios):
            tbl.columns[index].width = Emu(int(Inches(w) * ratio / total))

    tbl.rows[0].height = Inches(head_h)
    for index in range(1, len(rows) + 1):
        tbl.rows[index].height = Inches(row_h)

    def write(cell, text, bold, colour, fill, align, font_size):
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill
        cell.margin_left = cell.margin_right = Inches(0.06)
        cell.margin_top = cell.margin_bottom = Inches(0.02)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame = cell.text_frame
        frame.word_wrap = True
        frame.clear()
        para = frame.paragraphs[0]
        para.alignment = align
        for chunk_index, chunk in enumerate(str(text).split("**")):
            if not chunk:
                continue
            run = para.add_run()
            run.text = chunk
            run.font.size = Pt(font_size)
            run.font.name = BODY_FONT
            run.font.bold = bold or bool(chunk_index % 2)
            run.font.color.rgb = colour

    for col, text in enumerate(headers):
        write(tbl.cell(0, col), text, True, WHITE, head_fill,
              PP_ALIGN.LEFT, head_size)

    for row_index, row in enumerate(rows, start=1):
        fill = WHITE if row_index % 2 else LIGHT
        for col, text in enumerate(row):
            colour = (cell_colours or {}).get((row_index - 1, col),
                                              RGBColor(0x26, 0x26, 0x26))
            write(tbl.cell(row_index, col), text, False, colour, fill,
                  PP_ALIGN.LEFT, size)
    return shape


def flow(slide, x, y, w, steps, h=0.62, gap=0.10, fill=PALE, edge=BLUE,
         text_colour=NAVY, size=9.5, caption_size=8):
    """A left-to-right pipeline of chevrons.

    steps: list of (label, sublabel). Chevrons rather than boxes-and-arrows
    because the direction reads at a glance from the back of a room.
    """
    count = len(steps)
    step_w = (w - gap * (count - 1)) / count
    for index, (label, sub) in enumerate(steps):
        left = x + index * (step_w + gap)
        shape = slide.shapes.add_shape(
            MSO_SHAPE.CHEVRON if index else MSO_SHAPE.PENTAGON,
            Inches(left), Inches(y), Inches(step_w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
        shape.line.color.rgb = edge
        shape.line.width = Pt(0.75)
        shape.shadow.inherit = False
        shape.adjustments[0] = 0.22

        frame = shape.text_frame
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = Inches(0.03)
        frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER
        para.line_spacing = 0.9
        run = para.add_run()
        run.text = label
        run.font.size = Pt(size)
        run.font.bold = True
        run.font.name = BODY_FONT
        run.font.color.rgb = text_colour
        if sub:
            sub_para = frame.add_paragraph()
            sub_para.alignment = PP_ALIGN.CENTER
            sub_para.line_spacing = 0.9
            sub_run = sub_para.add_run()
            sub_run.text = sub
            sub_run.font.size = Pt(caption_size)
            sub_run.font.name = BODY_FONT
            sub_run.font.color.rgb = GREY


def callout(slide, x, y, w, h, text, fill=PALE_GREEN, edge=GREEN,
            colour=RGBColor(0x1B, 0x4D, 0x1E), size=11.5, align=PP_ALIGN.LEFT):
    box = panel(slide, x, y, w, h, fill=fill, line=edge)
    frame = box.text_frame
    frame.margin_left = frame.margin_right = Inches(0.12)
    frame.margin_top = frame.margin_bottom = Inches(0.06)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = frame.paragraphs[0]
    para.alignment = align
    para.line_spacing = 0.95
    for index, chunk in enumerate(text.split("**")):
        if not chunk:
            continue
        run = para.add_run()
        run.text = chunk
        run.font.size = Pt(size)
        run.font.name = BODY_FONT
        run.font.bold = bool(index % 2)
        run.font.color.rgb = colour
    return box


# ---------------------------------------------------------------------------
# slides
# ---------------------------------------------------------------------------

def slide1_title(slide) -> None:
    box = find(slide, "TextBox 9")
    frame = box.text_frame
    frame.word_wrap = True
    frame.clear()
    box.left, box.top = Inches(0.42), Inches(2.70)
    box.width, box.height = Inches(6.30), Inches(2.60)

    lines = [
        ("Problem Statement ID", "VITISH-82"),
        ("Problem Statement Title", "Low-cost Optical Inspection for PCB Assembly"),
        ("Theme", "Smart Automation / Manufacturing"),
        ("PS Category", "Hardware"),
        ("Idea Title", "GerberEye — CAD-Referenced Optical Inspection"),
        ("Team Name", "<team name>"),
        ("Team ID", "<team id>"),
    ]
    for index, (label, value) in enumerate(lines):
        para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        para.space_after = Pt(7)
        para.line_spacing = 0.95
        key = para.add_run()
        key.text = f"{label}:  "
        key.font.size = Pt(13)
        key.font.bold = True
        key.font.name = BODY_FONT
        key.font.color.rgb = NAVY
        val = para.add_run()
        val.text = value
        val.font.size = Pt(13)
        val.font.name = BODY_FONT
        val.font.color.rgb = RGBColor(0x26, 0x26, 0x26)

    # The template's subtitle placeholder sits underneath its own title box,
    # so it is moved clear rather than left to collide.
    subtitle = find(slide, "Subtitle 3")
    if subtitle is not None:
        subtitle.left, subtitle.top = Inches(0.42), Inches(2.16)
        subtitle.width, subtitle.height = Inches(6.30), Inches(0.42)
        frame = subtitle.text_frame
        frame.word_wrap = True
        frame.clear()
        para = frame.paragraphs[0]
        para.alignment = PP_ALIGN.LEFT
        run = para.add_run()
        run.text = "The design file already knows what should be on the board."
        run.font.size = Pt(14)
        run.font.italic = True
        run.font.bold = False
        run.font.name = TITLE_FONT
        run.font.color.rgb = BLUE

    # Credibility strip: three numbers a juror can check in the repository.
    chip_w, chip_gap = 1.98, 0.18
    for index, (value, label, colour) in enumerate([
            ("154", "unit tests passing", GREEN),
            ("29/29", "integration checks", BLUE),
            ("0", "network calls made", NAVY)]):
        x = 0.42 + index * (chip_w + chip_gap)
        chip = panel(slide, x, 5.42, chip_w, 0.72, fill=WHITE, line=colour)
        frame = chip.text_frame
        frame.margin_left = frame.margin_right = Inches(0.06)
        frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER
        para.line_spacing = 0.92
        big = para.add_run()
        big.text = value
        big.font.size, big.font.bold = Pt(19), True
        big.font.name, big.font.color.rgb = BODY_FONT, colour
        sub = frame.add_paragraph()
        sub.alignment = PP_ALIGN.CENTER
        sub_run = sub.add_run()
        sub_run.text = label
        sub_run.font.size = Pt(9)
        sub_run.font.name = BODY_FONT
        sub_run.font.color.rgb = GREY

    callout(slide, 0.42, 6.28, 6.30, 0.72,
            "Commercial AOI: **₹15–50 lakh**.   This: **under ₹10,000**, "
            "on the laptop the shop already owns.",
            fill=PALE, edge=BLUE, colour=NAVY, size=12)


def slide2_solution(slide) -> None:
    clear_guidance(slide, "TextBox 8")
    set_title(slide, "IDEA TITLE — GerberEye: CAD-Referenced PCB Inspection")
    rule(slide, 1.66)

    col_w, gap = 6.10, 0.23
    right_x = LEFT + col_w + gap

    # -- the problem --------------------------------------------------------
    header(slide, LEFT, 1.82, col_w, "THE PROBLEM", RED)
    bullets(slide, LEFT, 2.20, col_w, 1.55, [
        "An MSME inspects assembled PCBs **by eye**, under a magnifier lamp",
        "~**200 reference designators** cross-checked against a printed drawing",
        "Accuracy falls with **fatigue and board density**; nothing is recorded",
        "Automating it costs **₹15–50 lakh** — more than the shop earns in a year",
    ])

    # -- the insight --------------------------------------------------------
    header(slide, right_x, 1.82, col_w, "THE INSIGHT", GREEN)
    bullets(slide, right_x, 2.20, col_w, 1.55, [
        "The shop **already owns the design files** — it cannot manufacture without them",
        "The **pick-and-place file** states what sits at every coordinate",
        "So: **the design file is the label**",
        "**No training data. No annotation. No dataset needed.**",
    ])

    # -- pipeline -----------------------------------------------------------
    header(slide, LEFT, 3.86, FULL_W, "HOW IT WORKS", BLUE)
    flow(slide, LEFT, 4.24, FULL_W, [
        ("Design files", "Gerber · P&P · BOM"),
        ("Register", "CAD → camera"),
        ("Extract ROI", "per component"),
        ("Classify", "absent/rotated/offset"),
        ("Verdict", "pass / fail"),
        ("Record", "CSV · trends"),
    ], h=0.72)

    # -- uniqueness ---------------------------------------------------------
    header(slide, LEFT, 5.20, FULL_W, "INNOVATION & UNIQUENESS", NAVY)
    table(slide, LEFT, 5.58, FULL_W,
          ["", "Conventional approach", "GerberEye"],
          [["Reference", "Operator memory / printed drawing", "**The CAD file itself**"],
           ["Training data", "Thousands of labelled defect images", "**None — the P&P file is the label**"],
           ["Output", "\"This board looks wrong\"", "**\"U1 rotated 90°, C2 missing\"**"],
           ["Cost / connectivity", "₹15–50 lakh, vendor-tied", "**< ₹10,000, fully offline**"]],
          col_ratios=[0.17, 0.40, 0.43], row_h=0.245, size=10.5)


def slide3_technical(slide) -> None:
    clear_guidance(slide, "TextBox 8")
    set_title(slide, "TECHNICAL APPROACH")
    rule(slide, 1.66)

    header(slide, LEFT, 1.80, FULL_W, "INSPECTION PIPELINE  —  CPU only, no GPU, ~100 ms per board", BLUE)
    flow(slide, LEFT, 2.18, FULL_W, [
        ("Capture", "locked exposure"),
        ("Detect markers", "ArUco / fiducial"),
        ("Homography", "mm → pixels"),
        ("Project parts", "footprint extents"),
        ("Template match", "~2 ms/part"),
        ("Verdict", "IPC-A-610 classes"),
        ("Persist", "append-only"),
    ], h=0.68)

    col_w, gap = 6.10, 0.23
    right_x = LEFT + col_w + gap

    header(slide, LEFT, 3.10, col_w, "TWO-PATH ARCHITECTURE (ADR-002)", NAVY)
    table(slide, LEFT, 3.48, col_w,
          ["Path", "Needs", "Gives"],
          [["A — Golden differencing", "One known-good board", "Regions that differ"],
           ["B — CAD registration", "Gerber + pick-and-place", "**Defects named by designator**"]],
          col_ratios=[0.30, 0.32, 0.38], row_h=0.40, size=10)
    bullets(slide, LEFT, 4.52, col_w, 0.55, [
        "!Path A works with **zero design files**, so the demo cannot be blocked "
        "by a missing CAD↔board pair. Path B is the differentiator.",
    ], size=10, colour=GREY)

    header(slide, right_x, 3.10, col_w, "TECHNOLOGY STACK — permissive licences only", NAVY)
    table(slide, right_x, 3.48, col_w,
          ["Layer", "Choice", "Licence"],
          [["Computer vision", "OpenCV", "Apache-2.0"],
           ["CAD parsing", "pygerber", "MIT"],
           ["Backend", "Python · FastAPI · SQLite", "MIT"],
           ["Operator UI", "React + Vite", "MIT"],
           ["Compute", "Laptop CPU / Raspberry Pi", "—"]],
          col_ratios=[0.30, 0.45, 0.25], row_h=0.235, size=10)

    callout(slide, LEFT, 5.30, FULL_W, 0.62,
            "**Why not YOLO / deep learning?**   The latency budget allows ~6 ms per component on a CPU "
            "with no GPU — and Ultralytics is AGPL-3.0, so an MSME deploying it would inherit a copyleft "
            "obligation. Every dependency here is MIT, Apache-2.0 or BSD.",
            fill=PALE, edge=BLUE, colour=NAVY, size=10.5)

    callout(slide, LEFT, 6.04, FULL_W, 0.62,
            "**The hard part is registration, not comparison.**   CAD is in millimetres about a board datum; "
            "the camera sees pixels at unknown scale and perspective. Solving that homography is what makes "
            "\"is C2 present?\" answerable — and it needs Gerber knowledge **and** computer vision.",
            fill=PALE_GREEN, edge=GREEN, size=10.5)


def slide4_feasibility(slide) -> None:
    clear_guidance(slide, "TextBox 8")
    set_title(slide, "SOLUTION FEASIBILITY & VIABILITY")
    rule(slide, 1.66)

    col_w, gap = 6.10, 0.23
    right_x = LEFT + col_w + gap

    header(slide, LEFT, 1.80, col_w, "ALREADY BUILT AND VERIFIED", GREEN)
    table(slide, LEFT, 2.18, col_w,
          ["Capability", "Evidence"],
          [["Full pipeline, end to end", "**154 unit tests, 0 failing**"],
           ["Frontend ↔ backend wiring", "**29 / 29 integration checks**"],
           ["Defect naming + classification", "absent / rotated / offset + measurement"],
           ["Audit trail", "append-only records, CSV export"],
           ["Runs with no camera at all", "demo mode + simulated bench"]],
          col_ratios=[0.52, 0.48], row_h=0.245, size=10, head_fill=GREEN)

    header(slide, right_x, 1.80, col_w, "INDICATIVE BILL OF MATERIALS", NAVY)
    table(slide, right_x, 2.18, col_w,
          ["Item", "Cost"],
          [["USB webcam, 1080p", "₹1,200"],
           ["LED ring light + diffuser", "₹900"],
           ["Fixed jig, mount, enclosure", "₹1,600"],
           ["Raspberry Pi (optional edge node)", "₹4,800"],
           ["Laptop", "already owned"],
           ["**Total**", "**< ₹10,000**"]],
          col_ratios=[0.72, 0.28], row_h=0.20, size=10)

    header(slide, LEFT, 3.86, FULL_W, "RISKS AND HOW EACH IS CONTAINED", RED)
    table(slide, LEFT, 4.24, FULL_W,
          ["Risk", "Why it matters", "Containment"],
          [["Illumination instability", "**Dominant term** in the false-call rate — larger than any algorithm change",
            "Stability gate refuses to trust thresholds above 2 grey levels; degraded state shown, not hidden"],
           ["Camera refuses exposure lock", "Breaks golden-board comparison between captures",
            "Detected and reported; enclosure controls ambient light; reproduced in simulation for testing"],
           ["No matched CAD ↔ board pair yet", "Path B cannot be demonstrated on that board",
            "Two-path design — Path A needs no design files at all"],
           ["Hardware failure on demo day", "Loses the live demonstration",
            "Demo mode is a complete working station with no camera attached"]],
          col_ratios=[0.22, 0.36, 0.42], row_h=0.44, size=9.5, head_fill=RED)

    callout(slide, LEFT, 6.24, FULL_W, 0.60,
            "**Stated honestly:** recall and false-call rate are **not yet measured** — that needs seeded "
            "defects on real boards. We offer falsifiability instead: hand us a board, pull a component, "
            "and we will re-run it in front of you.",
            fill=RGBColor(0xFF, 0xF6, 0xE0), edge=AMBER,
            colour=RGBColor(0x6B, 0x4E, 0x00), size=10.5)


def slide5_impact(slide) -> None:
    clear_guidance(slide, "TextBox 8")
    set_title(slide, "REAL WORLD IMPACTS, BENEFITS & RELEVANCE")
    rule(slide, 1.66)

    header(slide, LEFT, 1.80, FULL_W, "WHAT CHANGES ON THE SHOP FLOOR", BLUE)
    table(slide, LEFT, 2.18, FULL_W,
          ["", "Today", "With GerberEye"],
          [["Method", "Eye + magnifier + printed assembly drawing", "**Camera + the shop's own design files**"],
           ["Time per board", "2–5 minutes of concentrated attention", "**Seconds, unattended**"],
           ["What the operator is told", "\"Something looks wrong here\"", "**\"U1 rotated 90°. C2 missing. R5 off its pads by 1.6 mm\"**"],
           ["Record of inspection", "A signature on a sheet", "**Machine-generated record, exportable as CSV**"],
           ["Cost to automate", "₹15–50 lakh", "**Under ₹10,000**"]],
          col_ratios=[0.17, 0.36, 0.47], row_h=0.30, size=10.5)

    col_w = (FULL_W - 0.46) / 3
    x2 = LEFT + col_w + 0.23
    x3 = x2 + col_w + 0.23

    header(slide, LEFT, 4.10, col_w, "ECONOMIC", GREEN)
    bullets(slide, LEFT, 4.48, col_w, 1.90, [
        "Defects caught **in-house**, not at the customer's incoming inspection",
        "An inspection trail lets an MSME **bid for contracts** that require one",
        "Recurring-defect trends turn detection into **process improvement** — a feeder fault, not a rework job",
    ], size=10.5)

    header(slide, x2, 4.10, col_w, "SOCIAL", BLUE)
    bullets(slide, x2, 4.48, col_w, 1.90, [
        "**The operator is always the authority** — one-click override, no form to fill",
        "Augments the inspector rather than replacing them; **no de-skilling**",
        "Removes the fatigue-driven error that eye inspection makes inevitable",
    ], size=10.5)

    header(slide, x3, 4.10, col_w, "STRATEGIC", NAVY)
    bullets(slide, x3, 4.48, col_w, 1.90, [
        "**Frugal Industry 4.0** for MSMEs — aligned with SAMARTH Udyog Bharat 4.0",
        "**Zero network egress** — customer design IP never leaves the machine",
        "Built to **IPC-A-610** defect taxonomy; **IPC-2591 (CFX)** ready for MES integration",
    ], size=10.5)

    callout(slide, LEFT, 6.20, FULL_W, 0.66,
            "**CAD software checks whether the design is correct. GerberEye checks whether the board in "
            "your hand matches it.**   Design defects happen once; assembly defects happen on every unit, "
            "on every shift.",
            fill=PALE, edge=BLUE, colour=NAVY, size=11.5, align=PP_ALIGN.CENTER)


def slide6_team(slide) -> None:
    clear_guidance(slide, "TextBox 8")
    set_title(slide, "TEAM CAPABILITY")
    rule(slide, 1.66)

    col_w, gap = 6.10, 0.23
    right_x = LEFT + col_w + gap

    header(slide, LEFT, 1.80, col_w, "TEAM AND ROLES  —  5 CSE + 1 ECE", NAVY)
    table(slide, LEFT, 2.18, col_w,
          ["Stream", "Ownership"],
          [["Capture & golden reference", "ECE — jig, lighting, camera settings"],
           ["Differencing engine (Path A)", "CSE — computer vision"],
           ["CAD registration (Path B)", "CSE — Gerber / pick-and-place, homography"],
           ["Backend & data", "CSE — FastAPI, SQLite, records"],
           ["Operator UI", "CSE — React, overlay, override"],
           ["Demo, risk & pitch", "Team lead"]],
          col_ratios=[0.44, 0.56], row_h=0.235, size=10)

    header(slide, right_x, 1.80, col_w, "PROOF OF WORK — this repository", GREEN)
    table(slide, right_x, 2.18, col_w,
          ["Artefact", "Scale"],
          [["Requirements engineering", "27 functional, 13 non-functional, 16 stakeholder"],
           ["Architecture", "6 ADRs, C4 model, ATAM-lite evaluation"],
           ["Implementation", "~7,800 lines; 154 tests; 29 integration checks"],
           ["Traceability", "Every requirement traced both directions, orphan-checked"],
           ["Working prototype", "Runs end to end today, with no hardware"]],
          col_ratios=[0.38, 0.62], row_h=0.28, size=10, head_fill=GREEN)

    header(slide, LEFT, 4.08, FULL_W, "WHY THIS DOMAIN — AND WHAT WE FOUND IN OUR OWN SYSTEM", BLUE)
    callout(slide, LEFT, 4.46, FULL_W, 1.15,
            "We benchmarked against a **221-component 0603 board** rather than our own demo board. "
            "**Two of five seeded defects were missed — both of them 'missing components'**, the class that "
            "should be easiest. A removed 0603 changes ~100 px² of contour area; the default noise floor was "
            "120 px², so the region was discarded and **the board reported PASS**.\n"
            "That is an escape, not a false call — the dangerous direction. The station now computes the "
            "smallest component's expected change from its footprint and **warns when the threshold would hide it**.",
            fill=PALE, edge=BLUE, colour=NAVY, size=11)

    callout(slide, LEFT, 5.78, FULL_W, 0.66,
            "**Finding a silent recall failure in your own system, and building the guard that surfaces it, "
            "is the capability we would most like to be judged on.**",
            fill=PALE_GREEN, edge=GREEN, size=11.5, align=PP_ALIGN.CENTER)


def slide7_research(slide) -> None:
    clear_guidance(slide, "TextBox 8")
    set_title(slide, "RESEARCH AND REFERENCES")
    rule(slide, 1.66)

    header(slide, LEFT, 1.80, FULL_W, "STANDARDS AND SPECIFICATIONS", NAVY)
    table(slide, LEFT, 2.18, FULL_W,
          ["Reference", "What it gives the project"],
          [["**IPC-A-610** — Acceptability of Electronic Assemblies",
            "The defect taxonomy: absent, misaligned, rotated, polarity-reversed, tombstoned"],
           ["**IPC-2591 (CFX)** — Connected Factory Exchange",
            "The MES integration path — how an inspection station reports to a factory line"],
           ["**Gerber RS-274X / X2** (Ucamco specification)",
            "Board geometry; X2 attributes carry component and net metadata"],
           ["**Pick-and-place / centroid file** (CAD output)",
            "Reference designator, X, Y, rotation, side — **the ground truth used as the label**"]],
          col_ratios=[0.38, 0.62], row_h=0.36, size=10)

    col_w, gap = 6.10, 0.23
    right_x = LEFT + col_w + gap

    header(slide, LEFT, 4.02, col_w, "LIBRARIES AND TECHNIQUES", BLUE)
    bullets(slide, LEFT, 4.40, col_w, 2.10, [
        "**OpenCV** — ArUco marker detection, homography (RANSAC), ECC alignment, template matching",
        "**pygerber** — Gerber rendering to raster for CAD-to-camera reference",
        "**Golden-board differencing** — the classical AOI baseline, used as the no-design-files path",
        "Surveyed **PatchCore / anomalib** few-shot anomaly detection — deferred: CPU latency budget",
    ], size=10.5)

    header(slide, right_x, 4.02, col_w, "FINDINGS THAT SHAPED THE DESIGN", GREEN)
    bullets(slide, right_x, 4.40, col_w, 2.10, [
        "Public PCB datasets (DeepPCB, HRIPCB) are **bare-board trace defects** — the wrong problem entirely",
        "**No usable public dataset of PCB assembly defects exists** → so the design file must be the label",
        "GitHub survey: **no prior art** for projecting Gerber/pick-and-place onto a live camera frame",
        "Commercial AOI is vendor-locked and cloud-tied — **offline operation is a requirement, not a feature**",
    ], size=10.5)

    callout(slide, LEFT, 6.24, FULL_W, 0.60,
            "**Working prototype, requirements set and architecture decision records:**   "
            "github.com/Haise-727/pcb-catcher",
            fill=PALE, edge=BLUE, colour=NAVY, size=11.5, align=PP_ALIGN.CENTER)


# ---------------------------------------------------------------------------

def delete_slide(prs, index: int) -> None:
    slides = prs.slides._sldIdLst
    slide_id = list(slides)[index]
    prs.part.drop_rel(slide_id.rId)
    slides.remove(slide_id)


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"template not found: {TEMPLATE}")
        return 1

    prs = Presentation(str(TEMPLATE))
    builders = [slide1_title, slide2_solution, slide3_technical,
                slide4_feasibility, slide5_impact, slide6_team, slide7_research]
    for build, slide in zip(builders, prs.slides):
        build(slide)

    # The template's own instructions say to remove this before uploading.
    delete_slide(prs, 7)

    prs.save(str(OUTPUT))
    print(f"wrote {OUTPUT.relative_to(ROOT)}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
    print("Export to PDF before uploading to the portal:")
    print(f"  libreoffice --headless --convert-to pdf --outdir {OUTPUT.parent} '{OUTPUT}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
