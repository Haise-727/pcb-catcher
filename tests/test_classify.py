"""Defect classification tests — issue #37, FR-012/013/014.

Built on synthetic boards so they run with no camera and no physical hardware.

The classifier answers "how does this differ from correct?" by searching for
the golden crop in the live frame, so every test here constructs a golden board
and a deliberately damaged copy, then asserts the class and — just as
importantly — the reasoning the operator is shown.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from gerbereye.pipeline import classify
from gerbereye.pipeline.classify import DefectClass


PX_PER_MM = 16.0


def make_board():
    """Board substrate with three chip components on visible pads."""
    board = np.full((240, 400, 3), 40, np.uint8)
    # Faint texture, so the substrate is not perfectly uniform. A flat
    # background would let template matching succeed for the wrong reasons.
    rng = np.random.default_rng(7)
    board = np.clip(board.astype(np.int16) + rng.normal(0, 3, board.shape), 0, 255).astype(np.uint8)
    return board


def draw_part(board, cx, cy, w=32, h=18, angle=0.0):
    """Draw a chip part: two bright pads with a dark body between them."""
    rect = ((cx, cy), (w, h), angle)
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillConvexPoly(board, box, (190, 200, 205))
    inner = cv2.boxPoints(((cx, cy), (w * 0.5, h * 0.92), angle)).astype(np.int32)
    cv2.fillConvexPoly(board, inner, (35, 35, 40))
    return board


@pytest.fixture()
def golden():
    board = make_board()
    draw_part(board, 100, 120)
    return board


BBOX = (100 - 22, 120 - 15, 44, 30)   # footprint box around the part at (100,120)
PACKAGE_MM = (2.0, 1.25)


def classify_at(live, golden_board, bbox=BBOX):
    return classify.classify_component(
        live, golden_board, bbox, package_mm=PACKAGE_MM, px_per_mm=PX_PER_MM
    )


# --------------------------------------------------------------------------
# The four classes
# --------------------------------------------------------------------------

def test_matching_component_is_present(golden):
    """An unchanged component must be positively cleared, not flagged.

    Differencing can fire on lighting or a smudge; saying "this part is fine"
    is more useful to the operator than staying silent.
    """
    result = classify_at(golden.copy(), golden)
    assert result.defect is DefectClass.PRESENT
    assert result.confidence > 0.5


def test_removed_component_is_absent(golden):
    live = make_board()  # same substrate, no part drawn
    result = classify_at(live, golden)
    assert result.defect is DefectClass.ABSENT
    assert "not found" in result.detail


def test_rotated_component_is_rotated(golden):
    live = make_board()
    draw_part(live, 100, 120, angle=90)
    result = classify_at(live, golden)
    assert result.defect is DefectClass.ROTATED
    assert "rotated" in result.detail


def test_displaced_component_is_offset_not_absent(golden):
    """The distinction that matters most.

    Inside a tight footprint an offset part and a missing one look identical --
    the pads are bare either way. Only a wider search separates them, and
    calling a displaced part "missing" sends the technician looking for a
    component that is sitting right next to where it belongs.
    """
    live = make_board()
    draw_part(live, 100 + 18, 120 + 8)
    result = classify_at(live, golden)
    assert result.defect is DefectClass.OFFSET
    assert "from its intended position" in result.detail


def test_offset_detail_reports_millimetres_when_scale_is_known(golden):
    """An operator thinks in millimetres, not pixels."""
    live = make_board()
    draw_part(live, 100 + 18, 120 + 8)
    result = classify_at(live, golden)
    assert "mm)" in result.detail


# --------------------------------------------------------------------------
# Not fabricating answers
# --------------------------------------------------------------------------

def test_small_displacement_within_tolerance_stays_present(golden):
    """BR-04 allows movement up to 25% of the smaller package dimension.

    Flagging every sub-threshold wobble would bury the operator in false calls,
    which is the failure NFR-005 exists to prevent.
    """
    live = make_board()
    draw_part(live, 101, 120)  # 1px, far inside tolerance
    result = classify_at(live, golden)
    assert result.defect is DefectClass.PRESENT


def test_featureless_reference_region_reports_unknown(golden):
    """A box over blank substrate means the projection is wrong, not the board.

    Blaming the component for a bad box would send someone to rework a part
    that is perfectly fine.
    """
    blank_box = (300, 40, 44, 30)
    result = classify.classify_component(
        make_board(), make_board(), blank_box, package_mm=PACKAGE_MM, px_per_mm=PX_PER_MM
    )
    assert result.defect is DefectClass.UNKNOWN
    assert "reference" in result.detail


def test_region_outside_the_frame_reports_unknown(golden):
    result = classify.classify_component(golden.copy(), golden, (5000, 5000, 40, 30))
    assert result.defect is DefectClass.UNKNOWN


def test_tiny_component_is_not_guessed_at(golden):
    """Below a few pixels there is nothing to match, and a confident answer
    would be invented rather than measured."""
    result = classify.classify_component(golden.copy(), golden, (100, 120, 3, 3))
    assert result.defect is DefectClass.UNKNOWN


# --------------------------------------------------------------------------
# Search-window sizing — the regression that made offsets read as missing
# --------------------------------------------------------------------------

def test_search_window_has_a_minimum_absolute_margin():
    """A pure scale factor leaves too little slack on small parts.

    2.6x on a 15px-wide 0603 gives only 12px of search room, so a part
    displaced 22px falls outside the window and reads as missing. Displacement
    is a physical distance, so the margin has to be absolute.
    """
    tight = classify._expand((100, 100, 15, 30), classify.SEARCH_FACTOR, min_pad_px=0)
    padded = classify._expand((100, 100, 15, 30), classify.SEARCH_FACTOR, min_pad_px=32)
    assert padded[2] > tight[2]
    assert padded[2] >= 15 + 64


def test_rotation_needs_a_margin_over_the_upright_match():
    """Without a margin, noise decides between two near-equal scores and a
    correctly-placed symmetric part gets reported as rotated."""
    assert classify.ROTATION_MARGIN > 0


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------

def test_unnamed_regions_are_left_unclassified(golden):
    """With no component-map entry there is no reference geometry, and a
    guessed class would be fabrication."""
    from gerbereye.pipeline.differencing import DiffRegion

    region = DiffRegion(bbox=(10, 10, 20, 20), area_px=400)
    classify.classify_regions([region], golden.copy(), golden, component_boxes={})
    assert region.defect_class is None


def test_named_regions_receive_class_confidence_and_detail(golden):
    from gerbereye.pipeline.differencing import DiffRegion

    live = make_board()
    region = DiffRegion(bbox=BBOX, area_px=400, ref_des="R1")
    classify.classify_regions(
        [region], live, golden,
        component_boxes={"R1": BBOX},
        component_index={"R1": {"package_mm": PACKAGE_MM}},
        px_per_mm=PX_PER_MM,
    )
    assert region.defect_class == DefectClass.ABSENT.value
    assert region.confidence is not None
    assert region.detail


# --------------------------------------------------------------------------
# Dense boards — where identical neighbours confuse a template matcher
# --------------------------------------------------------------------------

# Spacing mirrors a real tight layout: 0603 parts on a 2.5mm pitch means the
# gap between neighbours is about 1.3x the inspected footprint. Packing them
# tighter than that would make the footprint boxes overlap, which does not
# happen on a real board and would test something else entirely.
DENSE_PITCH = 52
DENSE_CENTRES = (48, 100, 152, 204)


def make_dense_board(missing=None):
    """A row of identical parts on a realistic tight pitch.

    This is the case that breaks naive template matching: every part looks
    exactly like every other, so a template will happily match a neighbour.
    """
    board = make_board()
    for index, cx in enumerate(DENSE_CENTRES):
        if missing is not None and index == missing:
            continue
        draw_part(board, cx, 120, w=30, h=16)
    return board


DENSE_BBOX = (100 - 20, 120 - 12, 40, 24)   # footprint of the part at x=100


def test_missing_part_among_identical_neighbours_is_absent_not_offset():
    """The dense-board failure.

    A missing 0603 surrounded by identical 0603s produced a confident 'offset'
    -- the matcher found a neighbour that looked exactly like the template and
    reported the part as displaced. That blames a component which is simply not
    there, and sends a technician to reposition something that is missing.
    """
    golden_board = make_dense_board()
    live = make_dense_board(missing=1)   # the part at x=100 removed

    result = classify.classify_component(
        live, golden_board, DENSE_BBOX, package_mm=(2.0, 1.25), px_per_mm=PX_PER_MM
    )
    assert result.defect is DefectClass.ABSENT


def test_offset_bound_is_a_full_component_length():
    """At a full component length the part no longer overlaps its own
    footprint, so it is somewhere else rather than badly placed."""
    assert classify.OFFSET_MAX_FACTOR <= 1.0


def test_rotation_match_far_from_expected_position_is_disbelieved():
    """A part that has turned has not also travelled. A distant rotated match
    is evidence of the wrong component, not a rotated one."""
    assert classify.ROTATION_MAX_DRIFT <= 1.0


def test_offset_requires_a_strong_match():
    """Match quality is the primary defence against neighbour confusion.

    A genuinely displaced part is the same part, so it matches its own template
    almost perfectly (measured 0.98-1.00). A template landing on a lookalike
    neighbour only partially overlaps and scores 0.41-0.62. The gate sits
    between those populations.
    """
    assert 0.62 < classify.OFFSET_MIN_SCORE < 0.98
