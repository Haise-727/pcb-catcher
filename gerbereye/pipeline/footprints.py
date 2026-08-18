"""Package footprint dimensions.

BR-03 defines a component's region of interest as its package footprint extent
scaled by 1.20. The pick-and-place file gives a footprint *name* but no
dimensions, so this module maps the name onto a real size.

Why it matters: before this existed, every component got the same 3mm nominal
box. That is larger than an 0402 and much smaller than a SOIC-14, so a defect
at the edge of a large IC fell outside its own box and came back unnamed — the
operator saw "something changed here" instead of "U1". Region naming is the
whole point of the CAD path, so a box that does not cover its component
quietly removes the feature's value.

Dimensions are body sizes in millimetres, taken from standard package
definitions (IPC-7351 nominal land patterns and common vendor datasheets).
Where a package is unknown the nominal fallback is used and the caller is told,
so an unmatched footprint shows up as a setup warning rather than silently
degrading accuracy.
"""

from __future__ import annotations

import re

# Fallback when a footprint name matches nothing below. Deliberately modest:
# an oversized default swallows neighbouring components on a dense board and
# attributes defects to the wrong part.
NOMINAL_MM = (3.0, 3.0)

# Chip passives, by imperial code. (length, width) in mm, body dimensions.
_CHIP_PASSIVES: dict[str, tuple[float, float]] = {
    "01005": (0.4, 0.2),
    "0201": (0.6, 0.3),
    "0402": (1.0, 0.5),
    "0603": (1.6, 0.8),
    "0805": (2.0, 1.25),
    "1206": (3.2, 1.6),
    "1210": (3.2, 2.5),
    "1812": (4.5, 3.2),
    "2010": (5.0, 2.5),
    "2512": (6.3, 3.2),
}

# Named packages matched by pattern. Order matters: more specific first, since
# the first match wins and "SOIC-8" must not be captured by a bare "SO" rule.
_NAMED_PACKAGES: list[tuple[re.Pattern, tuple[float, float]]] = [
    (re.compile(r"sot[-_]?23[-_]?6", re.I), (2.9, 2.8)),
    (re.compile(r"sot[-_]?23[-_]?5", re.I), (2.9, 2.8)),
    (re.compile(r"sot[-_]?23", re.I), (2.9, 2.4)),
    (re.compile(r"sot[-_]?89", re.I), (4.5, 4.0)),
    (re.compile(r"sot[-_]?223", re.I), (6.5, 7.0)),
    (re.compile(r"sod[-_]?123", re.I), (2.8, 1.8)),
    (re.compile(r"sod[-_]?323", re.I), (1.8, 1.35)),
    (re.compile(r"sod[-_]?80", re.I), (3.5, 1.5)),
    (re.compile(r"melf", re.I), (3.6, 1.4)),
    (re.compile(r"do[-_]?214|smb|sma|smc", re.I), (5.6, 3.6)),
    (re.compile(r"tssop[-_]?(\d+)", re.I), (0.0, 0.0)),   # computed by pin count
    (re.compile(r"ssop[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"msop[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"soic[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"so[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"tqfp[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"lqfp[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"qfn[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"dip[-_]?(\d+)", re.I), (0.0, 0.0)),
    (re.compile(r"to[-_]?220", re.I), (10.2, 15.0)),
    (re.compile(r"to[-_]?92", re.I), (4.8, 3.8)),
    (re.compile(r"cp_?elec|c_?elec|panasonic|electrolytic", re.I), (6.6, 6.6)),
    (re.compile(r"tantal|case_?[abcd]\b", re.I), (3.5, 2.8)),
    (re.compile(r"crystal|hc49|abm\d", re.I), (11.5, 4.8)),
    (re.compile(r"conn|hdr|header|pinhdr|jst|molex|terminal", re.I), (0.0, 0.0)),
    (re.compile(r"led", re.I), (2.0, 1.25)),
    (re.compile(r"button|switch|sw_?push|tactile", re.I), (6.0, 6.0)),
    (re.compile(r"inductor|l_?\d|choke", re.I), (4.0, 4.0)),
]

# Pin-count driven families: (body_width_mm, pitch_mm, dual_row)
_PIN_FAMILIES: list[tuple[re.Pattern, float, float, bool]] = [
    (re.compile(r"tssop[-_]?(\d+)", re.I), 4.4, 0.65, True),
    (re.compile(r"ssop[-_]?(\d+)", re.I), 5.3, 0.65, True),
    (re.compile(r"msop[-_]?(\d+)", re.I), 3.0, 0.65, True),
    (re.compile(r"soic[-_]?(\d+)", re.I), 3.9, 1.27, True),
    (re.compile(r"so[-_]?(\d+)", re.I), 3.9, 1.27, True),
    (re.compile(r"dip[-_]?(\d+)", re.I), 7.6, 2.54, True),
    (re.compile(r"conn|hdr|header|pinhdr", re.I), 2.54, 2.54, False),
]

_QUAD_FAMILIES: list[tuple[re.Pattern, float]] = [
    (re.compile(r"tqfp[-_]?(\d+)", re.I), 0.8),
    (re.compile(r"lqfp[-_]?(\d+)", re.I), 0.5),
    (re.compile(r"qfn[-_]?(\d+)", re.I), 0.5),
]

_CHIP_CODE = re.compile(r"(?<!\d)(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)(?!\d)")


def _pin_count(pattern: re.Pattern, name: str) -> int | None:
    match = pattern.search(name)
    if match and match.groups():
        try:
            return int(match.group(1))
        except (ValueError, IndexError):
            return None
    return None


_CONNECTOR = re.compile(r"conn|hdr|header|pinhdr|jst|molex|terminal|screw", re.I)
# Pin count as written on connector footprints: "2P", "1x04", "_04x", "-4".
_CONNECTOR_PINS = re.compile(r"(\d+)\s*p\b|(\d+)x(\d+)|[-_](\d+)(?:[-_]|$)", re.I)
CONNECTOR_PITCH_MM = 2.54
CONNECTOR_BODY_MM = 5.0
# Sanity bound on a parsed pin count. Vendor part numbers are full of digits --
# "Molex_53398-0571" parses to 53398 "pins" if taken literally, producing a
# 135-metre box that would swallow the board and steal every defect region.
# Anything beyond this is a part number, not a pin count.
CONNECTOR_MAX_PINS = 80
CONNECTOR_DEFAULT_PINS = 2


def _connector_dims(name: str) -> tuple[float, float] | None:
    """Size a connector from its pin count.

    Connectors vary enormously and are among the largest things on a board, so
    falling back to the 3mm nominal would badly under-cover them.
    """
    if not _CONNECTOR.search(name):
        return None
    match = _CONNECTOR_PINS.search(name)
    pins = CONNECTOR_DEFAULT_PINS
    if match:
        groups = [g for g in match.groups() if g]
        try:
            if len(groups) >= 2:
                pins = int(groups[0]) * int(groups[1])
            elif groups:
                pins = int(groups[0])
        except ValueError:
            pins = CONNECTOR_DEFAULT_PINS

    # An implausible count means the digits came from a part number. Fall back
    # rather than trusting it -- an oversized box is far more damaging than a
    # slightly small one, because it captures its neighbours' defects too.
    if not 1 <= pins <= CONNECTOR_MAX_PINS:
        pins = CONNECTOR_DEFAULT_PINS

    return round(pins * CONNECTOR_PITCH_MM + 1.5, 2), CONNECTOR_BODY_MM


def lookup(footprint: str | None) -> tuple[tuple[float, float], bool]:
    """Body dimensions for a footprint name.

    Returns ((width_mm, height_mm), matched). `matched` is False when the
    nominal fallback was used, so the caller can report how many footprints
    went unrecognised rather than silently accepting a wrong box size.
    """
    if not footprint:
        return NOMINAL_MM, False

    name = footprint.strip()

    # Chip passives are the most common case and the most size-sensitive, so
    # they are checked first.
    chip = _CHIP_CODE.search(name)
    if chip:
        return _CHIP_PASSIVES[chip.group(1)], True

    connector = _connector_dims(name)
    if connector is not None:
        return connector, True

    # Quad packages: pins spread over four sides.
    for pattern, pitch in _QUAD_FAMILIES:
        pins = _pin_count(pattern, name)
        if pins:
            per_side = max(pins // 4, 1)
            side = per_side * pitch + 2.0
            return (round(side, 2), round(side, 2)), True

    # Dual-row packages: length grows with pins down each side.
    for pattern, body_w, pitch, dual in _PIN_FAMILIES:
        pins = _pin_count(pattern, name)
        if pins:
            per_side = max(pins // 2, 1) if dual else pins
            length = per_side * pitch + 1.0
            if dual:
                return (round(length, 2), body_w), True
            return (round(length, 2), body_w), True
        # Connector patterns carry no pin count; fall through to the named table.

    for pattern, dims in _NAMED_PACKAGES:
        if pattern.search(name) and dims != (0.0, 0.0):
            return dims, True

    return NOMINAL_MM, False


def extent_for(component: dict) -> tuple[float, float]:
    """Footprint extent in millimetres, accounting for placement rotation.

    A part rotated 90 degrees occupies its width along X and its length along
    Y, so the extents swap. Rotations that are not axis-aligned fall back to
    the bounding square of the two, which over-covers slightly rather than
    cropping the component.
    """
    (length, width), _matched = lookup(component.get("footprint"))
    rotation = float(component.get("rotation_deg", 0.0)) % 180.0

    if abs(rotation - 90.0) < 15.0:
        return width, length
    if rotation < 15.0 or rotation > 165.0:
        return length, width

    # Diagonal placement: use the bounding square so the box never crops the
    # part. Slight over-coverage is much safer than an unnamed defect.
    span = max(length, width)
    return span, span


def summarise_coverage(components: list[dict]) -> dict:
    """How many components got a real footprint match.

    Surfaced at setup so an unrecognised package library shows up as a warning
    instead of quietly degrading naming accuracy across the whole board.
    """
    unmatched = []
    for component in components:
        _dims, matched = lookup(component.get("footprint"))
        if not matched:
            unmatched.append(component["ref_des"])
    return {
        "total": len(components),
        "matched": len(components) - len(unmatched),
        "unmatched": len(unmatched),
        "unmatched_designators": sorted(unmatched)[:20],
    }
