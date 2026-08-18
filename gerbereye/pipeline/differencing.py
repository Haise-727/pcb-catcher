"""Golden-board differencing — Path A.

FR-015, ADR-002. This is the path that works with a board already in hand: no
design files, no component map, no trained model. It compares a live frame
against a stored golden capture of a known-correct board and reports the
regions that differ.

Its accuracy rests entirely on the two frames being comparable, which is why
capture settings are locked (FR-006) and frame stability is gated before any
threshold here is tuned. Under stable light this is a genuinely reliable
detector; under drifting light no threshold value can save it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class DiffRegion:
    """One area where the live frame departs from the golden reference."""

    # Bounding box as (x, y, w, h) in live-frame pixel coordinates.
    bbox: tuple[int, int, int, int]
    area_px: int
    # Filled in by the CAD path when a component map is available; stays None
    # on the differencing-only path, where regions are anonymous.
    ref_des: str | None = None

    def as_dict(self) -> dict:
        return {"bbox": list(self.bbox), "area_px": self.area_px, "ref_des": self.ref_des}


@dataclass
class DiffResult:
    regions: list[DiffRegion] = field(default_factory=list)
    # Diagnostic: how many pixels changed at all, before area filtering. A
    # large value with no regions usually means global lighting drift rather
    # than a real defect, which is the signal to re-check the jig.
    changed_pixels: int = 0

    @property
    def defect_count(self) -> int:
        return len(self.regions)


def _to_grey(frame: np.ndarray, blur_kernel: int) -> np.ndarray:
    """Greyscale + blur. Blur suppresses single-pixel sensor noise, which would
    otherwise produce a scatter of tiny regions on every frame."""
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if blur_kernel and blur_kernel > 1:
        # OpenCV requires an odd kernel; round up rather than raising, since
        # this value is operator-tunable config and an even number is a
        # plausible typo rather than a programming error.
        k = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        grey = cv2.GaussianBlur(grey, (k, k), 0)
    return grey


def align_to_golden(live: np.ndarray, golden: np.ndarray) -> np.ndarray:
    """Correct small placement shifts between the live board and the golden one.

    The operator re-places the board by hand each time, so a few pixels of
    translation is normal and would otherwise light up every component edge as
    a difference. ECC finds a translation-only correction, which is enough for
    a board sitting flat in a jig.

    Returns the live frame warped into the golden frame's alignment. If the
    solver fails to converge the original frame is returned unchanged --
    differencing on a slightly misaligned frame is still better than refusing
    to inspect.
    """
    live_grey = cv2.cvtColor(live, cv2.COLOR_BGR2GRAY)
    golden_grey = cv2.cvtColor(golden, cv2.COLOR_BGR2GRAY)

    warp_matrix = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-4)
    try:
        cv2.findTransformECC(
            golden_grey, live_grey, warp_matrix, cv2.MOTION_TRANSLATION, criteria, None, 5
        )
    except cv2.error:
        return live

    height, width = golden_grey.shape
    return cv2.warpAffine(
        live, warp_matrix, (width, height),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )


def diff_against_golden(
    live: np.ndarray,
    golden: np.ndarray,
    diff_intensity: int = 40,
    min_region_area: int = 120,
    blur_kernel: int = 5,
    align: bool = True,
) -> DiffResult:
    """Compare a live frame against the golden reference.

    Args:
        live: BGR frame straight from the camera.
        golden: BGR reference capture of a known-correct board.
        diff_intensity: per-pixel grey delta above which a pixel counts as changed.
        min_region_area: contour area in px^2 below which a region is noise.
        blur_kernel: pre-blur size; suppresses sensor noise.
        align: run translation correction first. Disable only when the frames
            are known to be pixel-aligned already (e.g. synthetic test data).

    Returns a DiffResult whose regions are sorted largest-first, so the most
    significant defect leads the operator's list.
    """
    if golden.shape != live.shape:
        # Resizing here rather than refusing keeps a mismatched golden capture
        # usable, which matters when the reference was taken at a different
        # resolution than the current session.
        golden = cv2.resize(golden, (live.shape[1], live.shape[0]))

    aligned = align_to_golden(live, golden) if align else live

    live_grey = _to_grey(aligned, blur_kernel)
    golden_grey = _to_grey(golden, blur_kernel)

    delta = cv2.absdiff(live_grey, golden_grey)
    _, mask = cv2.threshold(delta, diff_intensity, 255, cv2.THRESH_BINARY)

    # Close small gaps so one physical defect reads as a single region rather
    # than a cluster of fragments in the operator's list.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions: list[DiffRegion] = []
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_region_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        regions.append(DiffRegion(bbox=(int(x), int(y), int(w), int(h)), area_px=area))

    regions.sort(key=lambda r: r.area_px, reverse=True)
    return DiffResult(regions=regions, changed_pixels=int(np.count_nonzero(mask)))
