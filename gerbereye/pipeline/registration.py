"""CAD-to-camera registration via printed ArUco markers.

FR-007/FR-008, de-risked. The full design detects the board's own copper
fiducials. Those are small, low-contrast, and easily confused with vias and
test points — a poor first target for a team with no prior CV experience
(RSK-05). Printed ArUco markers taped at known positions on the jig give the
same four point correspondences with a detector that is far more forgiving,
and they double as the RSK-03 fallback for boards carrying no fiducials at all.

Once four correspondences exist, the homography maps design millimetres onto
camera pixels, and every component's pick-and-place coordinate becomes a pixel
region. That is what lets the overlay say "C14" instead of "something changed
here".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np

from . import footprints

# 4x4_50 is the smallest dictionary that comfortably covers four markers.
# Smaller dictionaries decode more reliably at low resolution.
ARUCO_DICT = cv2.aruco.DICT_4X4_50


class RegistrationState(str, Enum):
    """Registration quality, surfaced to the operator rather than kept internal.

    Residual error propagates into every extracted region, so the operator
    needs to know when the mapping has drifted -- a 5px error on an 0402
    package is a large fraction of the component and manufactures false calls
    at the smallest sizes.
    """

    REGISTERED = "registered"
    DEGRADED = "degraded"
    FAILED = "failed"


# Thresholds in pixels, from NFR-006.
RESIDUAL_REGISTERED_MAX = 2.0
RESIDUAL_DEGRADED_MAX = 5.0


@dataclass
class RegistrationResult:
    state: RegistrationState
    # 3x3 design-mm -> pixel transform. None when state is FAILED.
    homography: np.ndarray | None = None
    residual_px: float | None = None
    marker_ids: list[int] = None
    message: str | None = None

    @property
    def ok(self) -> bool:
        """True when the transform is usable, including in the degraded band."""
        return self.homography is not None


def detect_markers(frame: np.ndarray) -> dict[int, np.ndarray]:
    """Find ArUco markers and return {id: centre_xy_pixels}.

    The centre is used rather than a specific corner because it is the most
    stable point under partial blur and slight perspective.
    """
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(grey)

    found: dict[int, np.ndarray] = {}
    if ids is None:
        return found
    for marker_corners, marker_id in zip(corners, ids.flatten()):
        found[int(marker_id)] = marker_corners.reshape(4, 2).mean(axis=0)
    return found


def compute_homography(
    marker_positions_mm: dict[int, tuple[float, float]],
    detected: dict[int, np.ndarray],
) -> RegistrationResult:
    """Solve the design-mm to pixel transform from marker correspondences.

    Args:
        marker_positions_mm: where each marker sits in design coordinates,
            measured once when the jig is built.
        detected: marker centres found in the current frame.
    """
    shared = sorted(set(marker_positions_mm) & set(detected))
    if len(shared) < 4:
        return RegistrationResult(
            state=RegistrationState.FAILED,
            marker_ids=shared,
            message=f"need 4 markers, found {len(shared)}",
        )

    source = np.array([marker_positions_mm[i] for i in shared], dtype=np.float32)
    destination = np.array([detected[i] for i in shared], dtype=np.float32)

    homography, _ = cv2.findHomography(source, destination, method=0)
    if homography is None:
        return RegistrationResult(
            state=RegistrationState.FAILED,
            marker_ids=shared,
            message="homography solve failed (markers may be collinear)",
        )

    # Reproject the known points and measure how far off they land. This is the
    # only honest measure of whether the transform can be trusted.
    projected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), homography).reshape(-1, 2)
    residual = float(np.sqrt(((projected - destination) ** 2).sum(axis=1).mean()))

    if residual <= RESIDUAL_REGISTERED_MAX:
        state = RegistrationState.REGISTERED
    elif residual <= RESIDUAL_DEGRADED_MAX:
        state = RegistrationState.DEGRADED
    else:
        # Above the degraded band the mapping is worse than useless: it would
        # place regions on the wrong components and blame the wrong parts.
        return RegistrationResult(
            state=RegistrationState.FAILED,
            residual_px=residual,
            marker_ids=shared,
            message=f"residual {residual:.1f}px exceeds {RESIDUAL_DEGRADED_MAX}px",
        )

    return RegistrationResult(
        state=state, homography=homography, residual_px=residual, marker_ids=shared
    )


def project_components(
    homography: np.ndarray,
    components: list[dict],
    roi_scale: float = 1.20,
) -> dict[str, tuple[int, int, int, int]]:
    """Map each component's design coordinate to a pixel bounding box.

    Box size comes from the component's actual package footprint scaled by
    roi_scale (BR-03). A single nominal size for every part does not work: it
    is larger than an 0402 and much smaller than a SOIC-14, so defects at the
    edge of a large IC fall outside their own box and come back unnamed.

    Returns {ref_des: (x, y, w, h)} in pixel coordinates.
    """
    if not components:
        return {}

    boxes: dict[str, tuple[int, int, int, int]] = {}

    # Project all four corners of each component's box, then take the axis
    # aligned bounds -- a rotated board makes the projected box non-rectangular.
    for component in components:
        x_mm, y_mm = component["x_mm"], component["y_mm"]
        extent_x, extent_y = footprints.extent_for(component)
        half_x = (extent_x * roi_scale) / 2.0
        half_y = (extent_y * roi_scale) / 2.0
        corners = np.array(
            [
                [x_mm - half_x, y_mm - half_y],
                [x_mm + half_x, y_mm - half_y],
                [x_mm + half_x, y_mm + half_y],
                [x_mm - half_x, y_mm + half_y],
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        projected = cv2.perspectiveTransform(corners, homography).reshape(-1, 2)
        x0, y0 = projected.min(axis=0)
        x1, y1 = projected.max(axis=0)
        boxes[component["ref_des"]] = (int(x0), int(y0), int(x1 - x0), int(y1 - y0))

    return boxes


def name_regions(
    regions: list, component_boxes: dict[str, tuple[int, int, int, int]]
) -> list:
    """Attach a reference designator to each defect region.

    This is the join that turns an anonymous differencing result into a named
    one: the region says *where* something changed, the component map says
    *what* should be there.

    Attribution is by **overlap area**, not by whether the region's centre sits
    inside a box. An offset component produces a region spanning both its
    intended and actual position, so its centre can land outside the footprint
    entirely while still clearly belonging to that part. Centre-testing misses
    exactly the defect class that most needs naming.

    Where nothing overlaps, the region is left unnamed rather than guessed at.
    An unexplained change is still worth showing the operator, but inventing a
    designator for it would blame a part that may be perfectly fine.
    """
    for region in regions:
        rx, ry, rw, rh = region.bbox
        r_x2, r_y2 = rx + rw, ry + rh

        best_ref = None
        best_overlap = 0.0
        best_distance = float("inf")

        for ref_des, (cx, cy, cw, ch) in component_boxes.items():
            c_x2, c_y2 = cx + cw, cy + ch

            # Axis-aligned intersection area.
            overlap_w = min(r_x2, c_x2) - max(rx, cx)
            overlap_h = min(r_y2, c_y2) - max(ry, cy)
            if overlap_w <= 0 or overlap_h <= 0:
                continue
            overlap = float(overlap_w * overlap_h)

            # Several boxes can overlap one region on a dense board. Prefer the
            # largest overlap; break ties on centre distance, which favours the
            # part the region actually sits on rather than a large neighbour
            # that happens to extend across it.
            distance = float(
                np.hypot(
                    (rx + rw / 2.0) - (cx + cw / 2.0),
                    (ry + rh / 2.0) - (cy + ch / 2.0),
                )
            )
            if overlap > best_overlap or (overlap == best_overlap and distance < best_distance):
                best_ref, best_overlap, best_distance = ref_des, overlap, distance

        region.ref_des = best_ref

    return regions


def merge_regions_by_component(regions: list) -> list:
    """Collapse fragments belonging to the same component into one region.

    A single physical defect rarely produces a single contour. A rotated IC
    lights up along each of its edges, so differencing returns four or five
    separate regions that all name the same part. Presenting those as four
    findings tells the operator the board is far worse than it is, and makes
    the station look like it is guessing.

    Fragments sharing a designator are merged into their bounding box, with
    areas summed. Unnamed regions are left alone: without a designator there
    is no evidence they belong together, and merging on proximity alone would
    fuse genuinely separate defects on a dense board.
    """
    if not regions:
        return regions

    merged: list = []
    by_designator: dict[str, list] = {}

    for region in regions:
        if region.ref_des is None:
            merged.append(region)
        else:
            by_designator.setdefault(region.ref_des, []).append(region)

    for ref_des, group in by_designator.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        x0 = min(r.bbox[0] for r in group)
        y0 = min(r.bbox[1] for r in group)
        x1 = max(r.bbox[0] + r.bbox[2] for r in group)
        y1 = max(r.bbox[1] + r.bbox[3] for r in group)

        primary = group[0]
        primary.bbox = (x0, y0, x1 - x0, y1 - y0)
        # Summed rather than recomputed from the bounding box: the box includes
        # unchanged pixels between fragments, and reporting those as changed
        # would overstate the defect's size.
        primary.area_px = sum(r.area_px for r in group)
        merged.append(primary)

    merged.sort(key=lambda r: r.area_px, reverse=True)
    return merged
