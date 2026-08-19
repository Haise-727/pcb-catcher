"""Per-component defect classification.

FR-012, FR-013, FR-014. Differencing says *where* something changed; this says
*what* is wrong with it. "C14 missing" tells a rework technician what to do;
"C14 differs" makes them go and look.

Classical features only, no learned model. ADR-003's reasoning still holds: the
latency budget allows roughly 6ms per component on a CPU, and no public
labelled dataset of PCB *assembly* defects exists at usable size (the
well-known ones are bare-board trace defects, a different problem at a
different stage).

## How it works

The golden board supplies a template for every component: the exact pixels that
part occupies when correctly placed. Classification is then a search — take the
golden crop, look for it in the live frame around where it should be, and read
the answer off *where* and *how well* it matched:

    not found anywhere        -> absent
    found, but displaced      -> offset
    found only when rotated   -> rotated
    found where expected      -> present

That framing needs no training data, because the reference is the board itself.

## Why not thresholding

An earlier version segmented each region with Otsu and compared coverage. It
was abandoned because the segmentation is not reliable enough to build on: on
an 0603 the pads occupy more than half the footprint, so a "the component is
the minority region" heuristic selects the board instead of the part, and a
region whose component has been removed is nearly uniform and gives Otsu
nothing real to split. Both produced confident, wrong answers.

Template matching sidesteps segmentation entirely — it never has to decide
which pixels *are* the component.

Thresholds come from BR-04 (offset > 25% of the smaller package dimension) and
BR-05 (rotation > 15 degrees). Those are inferred starting values refined
against measured results, not IPC-A-610 citations, and must not be presented
as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np


class DefectClass(str, Enum):
    """What is wrong with a component.

    PRESENT exists so the classifier can positively clear a region that
    differencing flagged. A difference caused by lighting or a smudge is not a
    defect, and saying so is more useful than staying silent.
    """

    PRESENT = "present"
    ABSENT = "absent"
    OFFSET = "offset"
    ROTATED = "rotated"
    UNKNOWN = "unknown"


# Normalised correlation below which the component is not considered found.
# Chosen well below a clean match (which scores above 0.9) but above the score
# a template gets against unrelated board texture.
MATCH_FLOOR = 0.55

# BR-04: offset when the centroid deviates by more than this fraction of the
# smaller package dimension.
OFFSET_FRACTION = 0.25

# BR-05: rotated when orientation deviates by more than this many degrees.
ROTATION_DEGREES = 15.0

# How far around the footprint to search. A part displaced by more than its own
# size again is missing for practical purposes, so this bounds the work.
SEARCH_FACTOR = 2.6

# Minimum search margin per side, in millimetres. A hand-placed part can sit a
# couple of millimetres out; below this margin such a part falls outside the
# window and is reported missing instead of offset.
SEARCH_PAD_MM = 2.0
SEARCH_PAD_FALLBACK_PX = 18

# Angles tried when testing for rotation. Coarse on purpose: distinguishing 90
# from 92 degrees is not useful, and every extra angle costs a full match pass
# against the per-component latency budget.
ROTATION_CANDIDATES = (90.0, 180.0, 270.0, 30.0, 45.0, 60.0)

# A rotated match must beat the upright one by this margin before the component
# is called rotated. Without it, noise decides between two near-equal scores
# and a correctly-placed symmetric part gets reported as rotated.
ROTATION_MARGIN = 0.06

# How far a rotated match may sit from the expected position, as a multiple of
# the component's own size, before it is disbelieved.
#
# This guard is essential on a dense board. A panel of identical 0603s means the
# search window is full of parts that look exactly like the template, so a
# rotated template will happily match a *neighbour* and score highly -- making a
# genuinely missing component report as rotated. A part that has actually turned
# has not also travelled, so a distant match is evidence of the wrong component,
# not a rotated one.
ROTATION_MAX_DRIFT = 1.0

# Upper bound on a displacement still called an offset, as a multiple of the
# component's own size.
#
# BR-04 sets a lower bound but no upper one, and physically there has to be
# one. At a full component length the part no longer overlaps its intended
# footprint at all -- it is not sitting badly, it is somewhere else, and its
# own pads are bare.
#
# This also settles the dense-board case. Identical 0603s sit 2.5mm apart on a
# tight layout, so a template will match a neighbour that looks exactly like
# it; without this bound a genuinely missing part reports as offset, blaming a
# component that is simply not there.
OFFSET_MAX_FACTOR = 1.0

# Match quality required before a displacement is called an offset.
#
# This is the primary defence against neighbour confusion, and it separates the
# two cases far more cleanly than distance does. A genuinely displaced part is
# the *same part*, so it matches its own template almost perfectly -- measured
# 0.98-1.00 across real and synthetic offsets. A template landing on a
# lookalike neighbour only partially overlaps it and scores 0.41-0.62.
#
# Below this bar we have not actually found the component, so the honest answer
# is that it is missing rather than displaced.
OFFSET_MIN_SCORE = 0.80

# Templates below this are too small to match meaningfully.
MIN_TEMPLATE_PX = 6


@dataclass
class Classification:
    defect: DefectClass
    confidence: float
    # Shown to the operator, so it states what was measured rather than naming
    # an internal feature.
    detail: str

    def as_dict(self) -> dict:
        return {
            "defect": self.defect.value,
            "confidence": round(self.confidence, 3),
            "detail": self.detail,
        }


def _crop(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray | None:
    x, y, w, h = bbox
    height, width = image.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, width), min(y + h, height)
    if x1 <= x0 or y1 <= y0:
        return None
    return image[y0:y1, x0:x1]


def _expand(
    bbox: tuple[int, int, int, int], factor: float, min_pad_px: int = 0
) -> tuple[int, int, int, int]:
    """Grow a box about its centre.

    `min_pad_px` sets a floor on the margin on each side. A pure scale factor
    is not enough for small parts: 2.6x on a 15px-wide 0603 leaves only 12px of
    slack, so a part displaced 22px falls outside the search window entirely
    and reads as missing rather than offset. The margin has to be expressed in
    absolute terms because a displacement is a physical distance, not a
    fraction of the component.
    """
    x, y, w, h = bbox
    pad_x = max(int(w * (factor - 1) / 2), min_pad_px)
    pad_y = max(int(h * (factor - 1) / 2), min_pad_px)
    return x - pad_x, y - pad_y, w + pad_x * 2, h + pad_y * 2


def _grey(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _rotate(template: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate a template about its centre, expanding the canvas to fit.

    The expansion matters: rotating in place would clip the corners of a
    non-square part and depress its match score for the wrong reason.
    """
    height, width = template.shape[:2]
    centre = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(centre, degrees, 1.0)

    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(height * sin + width * cos)
    new_h = int(height * cos + width * sin)
    matrix[0, 2] += new_w / 2.0 - centre[0]
    matrix[1, 2] += new_h / 2.0 - centre[1]

    return cv2.warpAffine(
        template, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _best_match(
    haystack: np.ndarray, needle: np.ndarray
) -> tuple[float, tuple[float, float]] | None:
    """Best normalised-correlation match of `needle` within `haystack`.

    Returns (score, centre_xy_in_haystack), or None when the template does not
    fit inside the search window.
    """
    if needle.shape[0] > haystack.shape[0] or needle.shape[1] > haystack.shape[1]:
        return None
    if min(needle.shape[:2]) < MIN_TEMPLATE_PX:
        return None

    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
    centre = (
        max_loc[0] + needle.shape[1] / 2.0,
        max_loc[1] + needle.shape[0] / 2.0,
    )
    return float(max_val), centre


def classify_component(
    live: np.ndarray,
    golden: np.ndarray,
    bbox: tuple[int, int, int, int],
    package_mm: tuple[float, float] | None = None,
    px_per_mm: float | None = None,
) -> Classification:
    """Classify one component against its appearance on the golden board.

    Args:
        live: full live frame.
        golden: full golden reference frame.
        bbox: the component's pixel region, from its projected footprint.
        package_mm: package extent, used to scale the BR-04 offset threshold.
        px_per_mm: image scale, needed to convert that threshold to pixels.
    """
    template = _crop(golden, bbox)
    if template is None or template.size == 0:
        return Classification(DefectClass.UNKNOWN, 0.0, "region lies outside the frame")
    if min(template.shape[:2]) < MIN_TEMPLATE_PX:
        return Classification(
            DefectClass.UNKNOWN, 0.2, "component is too small to classify at this resolution"
        )

    pad_px = int(SEARCH_PAD_MM * px_per_mm) if px_per_mm else SEARCH_PAD_FALLBACK_PX
    search_box = _expand(bbox, SEARCH_FACTOR, min_pad_px=pad_px)
    window = _crop(live, search_box)
    if window is None or window.size == 0:
        return Classification(DefectClass.UNKNOWN, 0.0, "search window lies outside the frame")

    template_grey = _grey(template)
    window_grey = _grey(window)

    # A featureless template (uniform soldermask) cannot be matched, and any
    # score against it would be meaningless. That means the projected box is
    # wrong, not the board -- say so rather than blaming the part.
    if float(template_grey.std()) < 4.0:
        return Classification(
            DefectClass.UNKNOWN, 0.2,
            "no distinguishable component in the reference at this position",
        )

    upright = _best_match(window_grey, template_grey)
    if upright is None:
        return Classification(
            DefectClass.UNKNOWN, 0.2, "component does not fit the search window"
        )
    upright_score, upright_centre = upright

    # Where the component should appear within the search window.
    expected_centre = (
        bbox[0] + bbox[2] / 2.0 - search_box[0],
        bbox[1] + bbox[3] / 2.0 - search_box[1],
    )

    # --- Rotated ----------------------------------------------------------
    # Tested before displacement: a rotated part still sits on its pads, so it
    # would otherwise read as present or slightly offset.
    # Rotation is only believed when the match lands on this component rather
    # than on an identical neighbour -- see ROTATION_MAX_DRIFT.
    drift_limit = max(bbox[2], bbox[3]) * ROTATION_MAX_DRIFT
    best_rotation, best_rotation_score = None, -1.0
    for angle in ROTATION_CANDIDATES:
        rotated = _rotate(template_grey, angle)
        match = _best_match(window_grey, rotated)
        if not match:
            continue
        score, centre = match
        drift = float(np.hypot(
            centre[0] - expected_centre[0], centre[1] - expected_centre[1]
        ))
        if drift > drift_limit:
            continue
        if score > best_rotation_score:
            best_rotation, best_rotation_score = angle, score

    if (
        best_rotation is not None
        and best_rotation_score >= MATCH_FLOOR
        and best_rotation_score > upright_score + ROTATION_MARGIN
    ):
        # A 180-degree match on a symmetric part is indistinguishable from
        # upright, so only report an angle the evidence actually supports.
        confidence = float(min(1.0, 0.55 + (best_rotation_score - upright_score)))
        return Classification(
            DefectClass.ROTATED, confidence,
            f"matches the reference only when rotated {best_rotation:.0f} degrees",
        )

    # --- Absent -----------------------------------------------------------
    if upright_score < MATCH_FLOOR:
        # Not found anywhere in the neighbourhood, at any tested orientation.
        confidence = float(min(1.0, 0.6 + (MATCH_FLOOR - upright_score)))
        return Classification(
            DefectClass.ABSENT, confidence,
            f"component not found near its position (best match {upright_score:.2f})",
        )

    # --- Offset -----------------------------------------------------------
    shift_px = float(np.hypot(
        upright_centre[0] - expected_centre[0], upright_centre[1] - expected_centre[1]
    ))

    # BR-04 is defined against the package's physical size, so converting it to
    # pixels needs the image scale. Without that, fall back to a fraction of
    # the box -- the same rule in the only units available.
    if package_mm and px_per_mm:
        limit_px = OFFSET_FRACTION * min(package_mm) * px_per_mm
    else:
        limit_px = OFFSET_FRACTION * min(bbox[2], bbox[3])
    limit_px = max(limit_px, 2.0)

    # Displaced, or a lookalike neighbour? Two independent guards, because
    # getting this wrong sends a technician to reposition a component that is
    # simply not there.
    max_shift_px = max(bbox[2], bbox[3]) * OFFSET_MAX_FACTOR
    if shift_px > limit_px and (
        upright_score < OFFSET_MIN_SCORE or shift_px > max_shift_px
    ):
        return Classification(
            DefectClass.ABSENT, 0.7,
            f"component not found at its position; the nearest match scores "
            f"{upright_score:.2f} at {shift_px:.0f}px away and is likely a "
            f"neighbouring part",
        )

    if shift_px > limit_px:
        confidence = float(min(1.0, 0.55 + (shift_px / limit_px - 1.0) * 0.2))
        millimetres = f" ({shift_px / px_per_mm:.2f}mm)" if px_per_mm else ""
        return Classification(
            DefectClass.OFFSET, confidence,
            f"component sits {shift_px:.1f}px{millimetres} from its intended position",
        )

    # --- Present ----------------------------------------------------------
    # Differencing flagged this region, but the component matches the reference
    # in place and orientation. Usually lighting, a smudge, or flux residue.
    return Classification(
        DefectClass.PRESENT, float(min(1.0, upright_score)),
        f"component matches the reference in place (score {upright_score:.2f}); "
        "the change may be surface or lighting",
    )


def classify_regions(
    regions: list,
    live: np.ndarray,
    golden: np.ndarray,
    component_boxes: dict[str, tuple[int, int, int, int]],
    component_index: dict[str, dict] | None = None,
    px_per_mm: float | None = None,
) -> list:
    """Attach a defect class to every named region.

    Unnamed regions are left alone: with no component-map entry there is no
    reference geometry to compare against, and guessing a class would be
    fabrication rather than measurement.
    """
    component_index = component_index or {}

    for region in regions:
        if not region.ref_des:
            continue
        box = component_boxes.get(region.ref_des)
        if box is None:
            continue

        component = component_index.get(region.ref_des, {})
        result = classify_component(
            live, golden, box,
            package_mm=component.get("package_mm"),
            px_per_mm=px_per_mm,
        )
        # Attached dynamically: DiffRegion stays a plain geometry carrier, and
        # only the CAD path has the reference needed to classify.
        region.defect_class = result.defect.value
        region.confidence = result.confidence
        region.detail = result.detail

    return regions
