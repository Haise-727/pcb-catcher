"""Footprint dimension and region-attribution tests — issue #36.

Before real footprint extents existed, every component got the same 3mm box.
That is larger than an 0402 and much smaller than a SOIC-14, so a defect at the
edge of a large IC fell outside its own box and came back unnamed. Region
naming is the entire value of the CAD path, so these tests pin the sizes and
the attribution rule that make it work.
"""

from __future__ import annotations

import numpy as np
import pytest

from gerbereye.pipeline import footprints, registration
from gerbereye.pipeline.differencing import DiffRegion


# --------------------------------------------------------------------------
# Dimension lookup
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "footprint,expected",
    [
        ("R_0805", (2.0, 1.25)),
        ("C_0603", (1.6, 0.8)),
        ("0402", (1.0, 0.5)),
        ("R_2512", (6.3, 3.2)),
        ("SOT-23", (2.9, 2.4)),
        ("SOD-123", (2.8, 1.8)),
    ],
)
def test_known_packages_resolve_to_real_dimensions(footprint, expected):
    dims, matched = footprints.lookup(footprint)
    assert matched
    assert dims == expected


def test_pin_count_drives_dual_row_package_length():
    """A SOIC-14 is longer than a SOIC-8; a fixed table would miss that."""
    (soic8_len, soic8_w), _ = footprints.lookup("SOIC-8")
    (soic14_len, soic14_w), _ = footprints.lookup("SOIC-14")
    assert soic14_len > soic8_len
    assert soic8_w == soic14_w  # body width is constant across the family


def test_quad_package_is_square_and_scales_with_pins():
    (small, _), _ = footprints.lookup("TQFP-32")
    (large, _), _ = footprints.lookup("TQFP-100")
    assert large > small
    dims, _ = footprints.lookup("TQFP-64")
    assert dims[0] == dims[1]


def test_unknown_footprint_falls_back_and_reports_it():
    """An unmatched package must be visible, not silently mis-sized."""
    dims, matched = footprints.lookup("SomeVendorSpecificThing")
    assert dims == footprints.NOMINAL_MM
    assert matched is False


def test_missing_footprint_is_handled():
    dims, matched = footprints.lookup(None)
    assert dims == footprints.NOMINAL_MM
    assert matched is False


def test_rotated_component_swaps_its_extents():
    """A part rotated 90 degrees occupies its width along X."""
    flat = footprints.extent_for({"footprint": "SOIC-8", "rotation_deg": 0})
    turned = footprints.extent_for({"footprint": "SOIC-8", "rotation_deg": 90})
    assert flat == (turned[1], turned[0])


def test_diagonal_rotation_uses_bounding_square():
    """Over-covering slightly is safer than cropping the component."""
    extent = footprints.extent_for({"footprint": "SOIC-14", "rotation_deg": 45})
    assert extent[0] == extent[1]
    assert extent[0] == pytest.approx(max(footprints.lookup("SOIC-14")[0]))


def test_coverage_summary_lists_unmatched_designators():
    components = [
        {"ref_des": "R1", "footprint": "R_0805"},
        {"ref_des": "U9", "footprint": "MysteryPackage"},
    ]
    summary = footprints.summarise_coverage(components)
    assert summary["total"] == 2
    assert summary["matched"] == 1
    assert summary["unmatched_designators"] == ["U9"]


# --------------------------------------------------------------------------
# Projection uses those dimensions
# --------------------------------------------------------------------------

def test_projected_box_scales_with_package_size():
    """A SOIC-14 must project to a visibly larger box than an 0402."""
    identity = np.eye(3, dtype=np.float32)
    boxes = registration.project_components(
        identity,
        [
            {"ref_des": "R1", "x_mm": 10.0, "y_mm": 10.0, "footprint": "R_0402"},
            {"ref_des": "U1", "x_mm": 30.0, "y_mm": 10.0, "footprint": "SOIC-14"},
        ],
    )
    assert boxes["U1"][2] > boxes["R1"][2] * 4


# --------------------------------------------------------------------------
# Attribution rule
# --------------------------------------------------------------------------

def test_region_is_attributed_by_overlap_not_centre():
    """The offset case, which centre-testing gets wrong.

    An offset component produces a region spanning its intended and actual
    positions, so the region centre can sit outside the footprint while the
    region clearly belongs to that part.
    """
    boxes = {"R5": (100, 100, 20, 20)}
    # Region starts inside R5 and extends well past it; its centre is outside.
    region = DiffRegion(bbox=(110, 110, 60, 60), area_px=3600)
    named = registration.name_regions([region], boxes)
    assert named[0].ref_des == "R5"


def test_non_overlapping_region_is_left_unnamed():
    """Better an unexplained region than a wrongly blamed component."""
    boxes = {"R5": (100, 100, 20, 20)}
    region = DiffRegion(bbox=(500, 500, 10, 10), area_px=100)
    named = registration.name_regions([region], boxes)
    assert named[0].ref_des is None


def test_largest_overlap_wins_when_boxes_compete():
    """Dense boards have overlapping footprints; the dominant one should win."""
    boxes = {"R1": (100, 100, 20, 20), "R2": (115, 100, 60, 20)}
    region = DiffRegion(bbox=(120, 100, 40, 20), area_px=800)
    named = registration.name_regions([region], boxes)
    assert named[0].ref_des == "R2"
