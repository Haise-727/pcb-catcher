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
    default_size_mm: float = 3.0,
) -> dict[str, tuple[int, int, int, int]]:
    """Map each component's design coordinate to a pixel bounding box.

    Package dimensions are not in the pick-and-place file, so every component
    gets the same nominal box scaled by roi_scale (BR-03). That is coarse but
    sufficient for naming which component a defect region falls inside, which
    is all the MVP overlay needs.

    Returns {ref_des: (x, y, w, h)} in pixel coordinates.
    """
    if not components:
        return {}

    half = (default_size_mm * roi_scale) / 2.0
    boxes: dict[str, tuple[int, int, int, int]] = {}

    # Project all four corners of each component's box, then take the axis
    # aligned bounds -- a rotated board makes the projected box non-rectangular.
    for component in components:
        x_mm, y_mm = component["x_mm"], component["y_mm"]
        corners = np.array(
            [
                [x_mm - half, y_mm - half],
                [x_mm + half, y_mm - half],
                [x_mm + half, y_mm + half],
                [x_mm - half, y_mm + half],
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
    """Attach a reference designator to each defect region, where one overlaps.

    This is the join that turns an anonymous differencing result into a named
    one: the region says *where* something changed, the component map says
    *what* should be there. A region matching no component keeps ref_des None
    rather than being dropped -- an unexplained change is still worth showing
    the operator.
    """
    for region in regions:
        rx, ry, rw, rh = region.bbox
        region_centre = (rx + rw / 2.0, ry + rh / 2.0)

        best_ref, best_distance = None, float("inf")
        for ref_des, (cx, cy, cw, ch) in component_boxes.items():
            inside = cx <= region_centre[0] <= cx + cw and cy <= region_centre[1] <= cy + ch
            if not inside:
                continue
            # Several component boxes can overlap on a dense board; the nearest
            # centre is the most defensible attribution.
            component_centre = (cx + cw / 2.0, cy + ch / 2.0)
            distance = float(
                np.hypot(region_centre[0] - component_centre[0], region_centre[1] - component_centre[1])
            )
            if distance < best_distance:
                best_ref, best_distance = ref_des, distance

        region.ref_des = best_ref

    return regions
