"""Bill of Materials parsing, for do-not-populate exclusion.

FR-002. A DNP (do-not-populate) designator appears in the design but is
deliberately left empty on every assembled board. Reporting one as a missing
component is a guaranteed false call on *every* board of that type — the
fastest possible route to an operator switching the station off.

DNP information lives in one of two places, and this module handles both:

  1. A BOM file, which is the authoritative source. Vendors mark it in wildly
     different ways: a dedicated column, a populate flag, or the literal string
     "DNP" sitting in a value field.
  2. The pick-and-place file itself, when the exporter chose to include it.

Where the two disagree, the BOM wins — it is the document a human curates,
whereas the pick-and-place file is generated.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

# Column aliases that identify the reference designator in a BOM. BOMs group
# multiple parts on one line far more often than pick-and-place files do, so
# these fields routinely hold a comma-separated list.
_REF_ALIASES = ("designator", "designators", "refdes", "reference", "references", "ref")

# Columns that explicitly carry populate/DNP state.
_DNP_COLUMN_ALIASES = ("dnp", "dni", "nopop", "no populate", "do not populate", "populate", "fitted", "mounted")

# Free-text markers meaning "not fitted", matched against a whole cell value.
# Anchored so a legitimate part number containing "dnp" as a substring does not
# trip the match.
_DNP_VALUE_PATTERN = re.compile(
    r"^\s*(dnp|dni|do[\s_-]?not[\s_-]?populate|no[\s_-]?pop(ulate)?|not[\s_-]?fitted|nofit|unfitted|n/?a)\s*$",
    re.IGNORECASE,
)

# Values in a "populate"/"fitted" column that mean the part IS fitted. Anything
# else in such a column is treated as not fitted.
_FITTED_TRUE = {"yes", "y", "true", "1", "fit", "fitted", "populate", "populated"}
_FITTED_FALSE = {"no", "n", "false", "0", "dnp", "dni", "nofit", "not fitted"}


class BomParseError(ValueError):
    """Raised when a BOM cannot be read.

    Expected control flow, not a bug: customer BOMs are frequently exported by
    hand and the operator needs a specific reason they can act on.
    """


@dataclass
class BomEntry:
    ref_des: str
    do_not_populate: bool
    part_number: str | None = None
    value: str | None = None


def _normalise(header: str) -> str:
    return header.strip().strip('"').lower()


def _split_designators(cell: str) -> list[str]:
    """Expand a grouped BOM designator cell into individual designators.

    BOM rows commonly read `C1,C2,C5` or `R1 R2 R3` for parts sharing a value.
    Ranges like `C1-C3` are deliberately NOT expanded: the numbering is not
    guaranteed contiguous, and inventing designators that do not exist would be
    worse than missing a few.
    """
    parts = re.split(r"[,;\s]+", cell.strip().strip('"'))
    return [p.strip() for p in parts if p.strip()]


def _looks_dnp(row: list[str], dnp_column: int | None, fitted_semantics: bool) -> bool:
    """Decide whether a BOM row describes an unfitted part."""
    if dnp_column is not None and dnp_column < len(row):
        cell = row[dnp_column].strip().strip('"').lower()
        if fitted_semantics:
            # Column says whether the part IS fitted, so invert. An empty cell
            # is ambiguous; treat it as fitted, because wrongly excluding a
            # real component creates a blind spot (a missed defect), which is
            # worse than the false call we are trying to avoid.
            if not cell:
                return False
            return cell not in _FITTED_TRUE
        if cell:
            if cell in _FITTED_FALSE:
                return True
            if _DNP_VALUE_PATTERN.match(cell):
                return True
            if cell in _FITTED_TRUE:
                return False

    # No dedicated column, or it was inconclusive: look for a DNP marker
    # standing alone in any cell.
    return any(_DNP_VALUE_PATTERN.match(cell.strip().strip('"')) for cell in row if cell)


def parse_bom_text(text: str) -> list[BomEntry]:
    """Parse BOM content into per-designator entries.

    Grouped rows are expanded, so a row covering `C1,C2,C5` yields three
    entries sharing that row's populate state.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise BomParseError("BOM file is empty")

    try:
        delimiter = csv.Sniffer().sniff("\n".join(lines[:10]), delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","

    rows = [r for r in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter) if r]
    if len(rows) < 2:
        raise BomParseError("BOM has a header but no rows")

    headers = [_normalise(h) for h in rows[0]]
    data_rows = rows[1:]

    ref_column = next(
        (i for i, h in enumerate(headers) if any(h == a or h.startswith(a) for a in _REF_ALIASES)),
        None,
    )
    if ref_column is None:
        raise BomParseError(
            "could not find a designator column in the BOM. Header was: " + ", ".join(rows[0])
        )

    dnp_column = next(
        (i for i, h in enumerate(headers) if any(h == a or h.startswith(a) for a in _DNP_COLUMN_ALIASES)),
        None,
    )
    # "populate"/"fitted"/"mounted" columns carry the opposite polarity to a
    # "dnp"/"nopop" column, so the meaning has to be tracked alongside the index.
    fitted_semantics = (
        dnp_column is not None
        and any(headers[dnp_column].startswith(a) for a in ("populate", "fitted", "mounted"))
    )

    part_column = next((i for i, h in enumerate(headers) if h.startswith(("part", "mpn", "manufacturer part"))), None)
    value_column = next((i for i, h in enumerate(headers) if h.startswith(("value", "val", "comment"))), None)

    entries: list[BomEntry] = []
    for row in data_rows:
        if ref_column >= len(row):
            continue
        designators = _split_designators(row[ref_column])
        if not designators:
            continue
        dnp = _looks_dnp(row, dnp_column, fitted_semantics)

        def cell(idx: int | None) -> str | None:
            if idx is None or idx >= len(row):
                return None
            return row[idx].strip().strip('"') or None

        for ref_des in designators:
            entries.append(
                BomEntry(
                    ref_des=ref_des,
                    do_not_populate=dnp,
                    part_number=cell(part_column),
                    value=cell(value_column),
                )
            )

    if not entries:
        raise BomParseError("no usable BOM rows found")
    return entries


def dnp_designators(entries: list[BomEntry]) -> set[str]:
    """The set of designators that must never be inspected."""
    return {e.ref_des for e in entries if e.do_not_populate}


def apply_to_components(
    components: list[dict], entries: list[BomEntry]
) -> tuple[list[dict], list[str]]:
    """Mark components DNP according to the BOM.

    Returns the updated component list and the sorted designators excluded, so
    the count can be shown to the technician at setup (AC-002.2). A silent
    exclusion is nearly as dangerous as no exclusion — the technician needs to
    notice if the BOM knocks out half the board.
    """
    excluded = dnp_designators(entries)
    updated = []
    for component in components:
        component = dict(component)
        if component["ref_des"] in excluded:
            component["dnp"] = True
        updated.append(component)
    present = sorted(excluded & {c["ref_des"] for c in components})
    return updated, present
