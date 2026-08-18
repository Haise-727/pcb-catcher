"""Board verdict derivation.

BR-06, simplified for the MVP. Both inspection paths converge here: the
differencing path supplies anonymous regions, the CAD path supplies regions
carrying a reference designator. This stage is deliberately agnostic to which
produced them, which is what makes the two-path design in ADR-002 structural
rather than two parallel prototypes glued together.
"""

from __future__ import annotations

from enum import Enum

from .differencing import DiffRegion


class BoardVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


def derive_verdict(regions: list[DiffRegion]) -> BoardVerdict:
    """A board fails when at least one region survived area filtering.

    The full design also carries a `for-review` state for low-confidence
    classifications (BR-07). That needs per-component confidence, which only
    the classical-feature classifier produces, so the MVP is deliberately
    binary -- a region either cleared the noise threshold or it did not.
    """
    return BoardVerdict.FAIL if regions else BoardVerdict.PASS


def summarise(regions: list[DiffRegion]) -> dict:
    """Compact summary for the operator UI and the inspection record."""
    named = [r for r in regions if r.ref_des]
    return {
        "verdict": derive_verdict(regions).value,
        "region_count": len(regions),
        "named_count": len(named),
        "designators": sorted(r.ref_des for r in named if r.ref_des),
    }
