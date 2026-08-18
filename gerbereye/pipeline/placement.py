"""Pick-and-place file parsing.

FR-001, simplified. The pick-and-place file is the single most important input
to the CAD path: it states, for every reference designator, exactly what should
sit at which coordinate. That is what removes the labelled-data problem —
the design file *is* the ground truth, so no annotation is needed to know what
a correct board looks like.

Vendors disagree about column names, units and even delimiters, so this parser
matches columns by pattern rather than by fixed position, and normalises
everything to millimetres with the Gerber convention (origin lower-left, X
right, Y up — BR-02).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

# Column aliases seen across KiCad, Altium, Eagle and JLCPCB exports. Matched
# case-insensitively against the header row.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "ref_des": ("designator", "refdes", "ref", "reference", "part", "name", "component"),
    "x_mm": ("mid x", "midx", "x", "posx", "ref x", "center-x(mm)", "center-x"),
    "y_mm": ("mid y", "midy", "y", "posy", "ref y", "center-y(mm)", "center-y"),
    "rotation_deg": ("rotation", "rot", "angle"),
    "side": ("layer", "side", "tb"),
    "footprint": ("footprint", "package", "pattern", "comment"),
}

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class PlacementParseError(ValueError):
    """Raised when a file cannot yield a usable component map.

    Parse failure is expected control flow here, not a bug -- customer files
    are routinely malformed, and the operator needs to be told which file and
    why rather than shown a stack trace.
    """


@dataclass
class Component:
    ref_des: str
    x_mm: float
    y_mm: float
    rotation_deg: float = 0.0
    side: str = "top"
    footprint: str | None = None

    def as_dict(self) -> dict:
        return {
            "ref_des": self.ref_des,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "rotation_deg": self.rotation_deg,
            "side": self.side,
            "footprint": self.footprint,
        }


def _normalise(header: str) -> str:
    return header.strip().strip('"').lower()


def _match_columns(headers: list[str]) -> dict[str, int]:
    """Map our field names onto the file's column indices.

    Longer aliases are tried first so "mid x" wins over a bare "x" when both
    could match, which matters because several formats carry both.
    """
    normalised = [_normalise(h) for h in headers]
    mapping: dict[str, int] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            for idx, header in enumerate(normalised):
                if header == alias or header.startswith(alias):
                    mapping[field] = idx
                    break
            if field in mapping:
                break
    return mapping


def _to_float(raw: str) -> float:
    """Pull a number out of a cell that may carry a unit suffix like '12.7mm'."""
    match = _NUMBER.search(raw or "")
    if match is None:
        raise PlacementParseError(f"expected a number, got {raw!r}")
    return float(match.group())


def _detect_units_are_inches(headers: list[str], rows: list[list[str]]) -> bool:
    """Infer the coordinate unit.

    An explicit 'mil'/'inch' marker in the header wins. Failing that, a board
    whose largest coordinate is under 20 is almost certainly inches -- a PCB
    that genuinely spanned 20mm would be smaller than most connectors.
    """
    joined = " ".join(_normalise(h) for h in headers)
    if "inch" in joined or "mil" in joined:
        return True
    if "mm" in joined:
        return False

    magnitudes = []
    for row in rows:
        for cell in row:
            match = _NUMBER.search(cell or "")
            if match:
                magnitudes.append(abs(float(match.group())))
    return bool(magnitudes) and max(magnitudes) < 20.0


def parse_placement_text(text: str) -> list[Component]:
    """Parse pick-and-place content into a component map."""
    # Strip comment lines; several exporters prefix metadata with '#'.
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise PlacementParseError("file is empty")

    # Sniff the delimiter so comma, semicolon and tab exports all work.
    sample = "\n".join(lines[:10])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    rows = [row for row in reader if row]
    if len(rows) < 2:
        raise PlacementParseError("file has a header but no component rows")

    headers, data_rows = rows[0], rows[1:]
    columns = _match_columns(headers)

    missing = [f for f in ("ref_des", "x_mm", "y_mm") if f not in columns]
    if missing:
        raise PlacementParseError(
            f"could not find required column(s): {', '.join(missing)}. "
            f"Header was: {', '.join(headers)}"
        )

    inches = _detect_units_are_inches(headers, data_rows)
    scale = 25.4 if inches else 1.0

    components: list[Component] = []
    seen: set[str] = set()
    duplicates: set[str] = set()

    for row in data_rows:
        if len(row) <= max(columns["ref_des"], columns["x_mm"], columns["y_mm"]):
            continue
        ref_des = row[columns["ref_des"]].strip().strip('"')
        if not ref_des:
            continue
        if ref_des in seen:
            duplicates.add(ref_des)
            continue
        seen.add(ref_des)

        def cell(field: str, default: str = "") -> str:
            idx = columns.get(field)
            return row[idx].strip().strip('"') if idx is not None and idx < len(row) else default

        side_raw = cell("side", "top").lower()
        side = "bottom" if side_raw.startswith(("b", "bot")) else "top"

        try:
            rotation = _to_float(cell("rotation_deg", "0")) if columns.get("rotation_deg") is not None else 0.0
        except PlacementParseError:
            rotation = 0.0

        components.append(
            Component(
                ref_des=ref_des,
                x_mm=_to_float(row[columns["x_mm"]]) * scale,
                y_mm=_to_float(row[columns["y_mm"]]) * scale,
                rotation_deg=rotation % 360.0,
                side=side,
                footprint=cell("footprint") or None,
            )
        )

    if duplicates:
        # BR-01: a designator identifies a component uniquely within a board
        # type. Duplicates mean the file is wrong, and silently keeping the
        # first would inspect the wrong coordinate for the rest of the run.
        raise PlacementParseError(
            "duplicate reference designators: " + ", ".join(sorted(duplicates))
        )
    if not components:
        raise PlacementParseError("no usable component rows found")

    return components


def parse_placement_file(path: Path) -> list[Component]:
    return parse_placement_text(Path(path).read_text(encoding="utf-8", errors="replace"))
