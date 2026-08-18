"""Pipeline tests — differencing, verdict, placement parsing, registration.

These run entirely on synthetic frames, so they pass with no camera and no
physical board attached. That matters during the build: the pipeline stays
verifiable while the hardware is still being assembled.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from gerbereye.pipeline import differencing, placement, registration, verdict


def make_board(components=((100, 100), (200, 100), (300, 100), (400, 200))):
    """Synthetic board: dark substrate with bright rectangular 'components'."""
    board = np.full((480, 640, 3), 30, np.uint8)
    for x, y in components:
        cv2.rectangle(board, (x, y), (x + 40, y + 25), (200, 200, 200), -1)
    return board


def remove_component(board, x, y):
    """Erase one component, simulating a missing part."""
    out = board.copy()
    cv2.rectangle(out, (x, y), (x + 40, y + 25), (30, 30, 30), -1)
    return out


# --------------------------------------------------------------------------
# Differencing
# --------------------------------------------------------------------------

def test_identical_frames_report_no_defects():
    board = make_board()
    result = differencing.diff_against_golden(board.copy(), board, align=False)
    assert result.defect_count == 0
    assert verdict.derive_verdict(result.regions) is verdict.BoardVerdict.PASS


def test_missing_component_is_detected_at_its_location():
    board = make_board()
    live = remove_component(board, 200, 100)
    result = differencing.diff_against_golden(live, board, align=False)

    assert result.defect_count == 1
    x, y, w, h = result.regions[0].bbox
    # The flagged region must actually cover the erased component, not merely
    # exist somewhere -- a detector that fires in the wrong place is worse than
    # one that does not fire at all.
    assert x <= 200 <= x + w
    assert y <= 100 <= y + h


def test_sensor_noise_does_not_produce_false_calls():
    """The adoption metric is the false-call rate, so noise robustness is the
    single most important property of this stage (NFR-005)."""
    board = make_board()
    rng = np.random.default_rng(seed=42)
    noisy = np.clip(
        board.astype(np.int16) + rng.normal(0, 4, board.shape), 0, 255
    ).astype(np.uint8)

    result = differencing.diff_against_golden(noisy, board, align=False)
    assert result.defect_count == 0


def test_multiple_defects_are_reported_largest_first():
    board = make_board()
    live = remove_component(remove_component(board, 200, 100), 300, 100)
    result = differencing.diff_against_golden(live, board, align=False)

    assert result.defect_count == 2
    areas = [r.area_px for r in result.regions]
    assert areas == sorted(areas, reverse=True)


def test_mismatched_golden_resolution_is_handled():
    """A golden captured at a different resolution should still be usable."""
    board = make_board()
    small_golden = cv2.resize(board, (320, 240))
    result = differencing.diff_against_golden(board, small_golden, align=False)
    assert isinstance(result, differencing.DiffResult)


# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------

def test_verdict_passes_on_empty_regions():
    assert verdict.derive_verdict([]) is verdict.BoardVerdict.PASS


def test_verdict_fails_on_any_region():
    region = differencing.DiffRegion(bbox=(0, 0, 10, 10), area_px=100)
    assert verdict.derive_verdict([region]) is verdict.BoardVerdict.FAIL


def test_summary_lists_named_designators():
    regions = [
        differencing.DiffRegion(bbox=(0, 0, 10, 10), area_px=100, ref_des="C14"),
        differencing.DiffRegion(bbox=(50, 50, 10, 10), area_px=90),
    ]
    summary = verdict.summarise(regions)
    assert summary["verdict"] == "fail"
    assert summary["region_count"] == 2
    assert summary["named_count"] == 1
    assert summary["designators"] == ["C14"]


# --------------------------------------------------------------------------
# Pick-and-place parsing
# --------------------------------------------------------------------------

def test_parses_kicad_style_export():
    text = (
        "Ref,Val,Package,PosX,PosY,Rot,Side\n"
        "C14,100nF,C_0805,12.7,20.3,90,top\n"
        "R1,10k,R_0603,15.0,20.3,0,top\n"
    )
    components = placement.parse_placement_text(text)
    assert [c.ref_des for c in components] == ["C14", "R1"]
    assert components[0].x_mm == pytest.approx(12.7)
    assert components[0].rotation_deg == pytest.approx(90.0)


def test_parses_jlcpcb_style_quoted_export_with_unit_suffix():
    text = (
        '"Designator","Mid X","Mid Y","Layer","Rotation"\n'
        '"C1","5.08mm","10.16mm","top","270"\n'
        '"D2","20.00mm","11.00mm","bottom","90"\n'
    )
    components = placement.parse_placement_text(text)
    assert components[0].x_mm == pytest.approx(5.08)
    assert components[1].side == "bottom"


def test_inch_coordinates_convert_to_millimetres():
    text = "Designator,X (inch),Y (inch)\nR5,0.5,1.0\n"
    components = placement.parse_placement_text(text)
    assert components[0].x_mm == pytest.approx(12.7)
    assert components[0].y_mm == pytest.approx(25.4)


def test_duplicate_designators_are_rejected():
    """BR-01 makes refdes the key. A duplicate means the file is wrong, and
    keeping the first would inspect the wrong coordinate for every later row."""
    text = "Designator,X,Y\nR1,50,50\nR1,60,60\n"
    with pytest.raises(placement.PlacementParseError, match="duplicate"):
        placement.parse_placement_text(text)


def test_missing_required_columns_names_what_is_missing():
    with pytest.raises(placement.PlacementParseError, match="could not find"):
        placement.parse_placement_text("Foo,Bar\n1,2\n")


def test_empty_file_is_rejected():
    with pytest.raises(placement.PlacementParseError):
        placement.parse_placement_text("")


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

MARKER_POSITIONS_MM = {0: (0.0, 0.0), 1: (60.0, 0.0), 2: (60.0, 40.0), 3: (0.0, 40.0)}


def make_marker_frame():
    """Render the four jig markers into a blank frame at known pixel spots."""
    dictionary = cv2.aruco.getPredefinedDictionary(registration.ARUCO_DICT)
    frame = np.full((600, 800, 3), 255, np.uint8)
    for marker_id, (cx, cy) in {0: (100, 100), 1: (700, 100), 2: (700, 500), 3: (100, 500)}.items():
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 80)
        frame[cy - 40 : cy + 40, cx - 40 : cx + 40] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return frame


def test_detects_all_four_markers():
    detected = registration.detect_markers(make_marker_frame())
    assert sorted(detected) == [0, 1, 2, 3]


def test_homography_from_four_markers_is_registered():
    detected = registration.detect_markers(make_marker_frame())
    result = registration.compute_homography(MARKER_POSITIONS_MM, detected)
    assert result.state is registration.RegistrationState.REGISTERED
    assert result.residual_px < registration.RESIDUAL_REGISTERED_MAX
    assert result.ok


def test_fewer_than_four_markers_fails_without_a_transform():
    detected = registration.detect_markers(make_marker_frame())
    partial = {k: detected[k] for k in (0, 1)}
    result = registration.compute_homography(MARKER_POSITIONS_MM, partial)
    assert result.state is registration.RegistrationState.FAILED
    assert result.homography is None
    assert not result.ok


def test_component_projects_to_expected_pixel_location():
    detected = registration.detect_markers(make_marker_frame())
    result = registration.compute_homography(MARKER_POSITIONS_MM, detected)

    # A component at the centre of the 60x40mm marker rectangle must land at
    # the centre of the 800x600 frame's marker rectangle, i.e. (400, 300).
    boxes = registration.project_components(
        result.homography, [{"ref_des": "C14", "x_mm": 30.0, "y_mm": 20.0}]
    )
    x, y, w, h = boxes["C14"]
    assert x + w / 2 == pytest.approx(400, abs=5)
    assert y + h / 2 == pytest.approx(300, abs=5)


def test_region_naming_attributes_only_overlapping_regions():
    detected = registration.detect_markers(make_marker_frame())
    result = registration.compute_homography(MARKER_POSITIONS_MM, detected)
    boxes = registration.project_components(
        result.homography, [{"ref_des": "C14", "x_mm": 30.0, "y_mm": 20.0}]
    )

    on_component = differencing.DiffRegion(bbox=(395, 295, 10, 10), area_px=100)
    off_component = differencing.DiffRegion(bbox=(20, 20, 8, 8), area_px=64)
    named = registration.name_regions([on_component, off_component], boxes)

    assert named[0].ref_des == "C14"
    # An unexplained change is still shown to the operator, just unnamed.
    assert named[1].ref_des is None
