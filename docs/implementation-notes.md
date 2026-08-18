# Implementation Notes

**Version:** 0.1 | **Last updated:** 2026-08-18
**Status:** MVP framework built, hardware tasks in progress

Records where the built code deliberately departs from the Phase 1–8 inception
docs, and why. The inception set was written against a two-week runway; the
first internal round is eight hours. Everything below is a scope compression,
not a change of direction — each entry names the doc it narrows and the
condition that would restore the full behaviour.

---

## 1. What exists

| Module | Covers | Doc reference |
|---|---|---|
| `gerbereye/config.py` | App config, threshold seed values | architecture.md §6 |
| `gerbereye/db.py` | SQLite schema, append-only verdicts | system-model.md §1 |
| `gerbereye/capture.py` | Locked exposure/focus/WB, stability check | FR-006, AC-006.2 |
| `gerbereye/pipeline/differencing.py` | Golden-board differencing (Path A) | FR-015, ADR-002 |
| `gerbereye/pipeline/verdict.py` | Board pass/fail | BR-06 |
| `gerbereye/pipeline/placement.py` | Pick-and-place parsing | FR-001, BR-01, BR-02 |
| `gerbereye/pipeline/registration.py` | ArUco homography, region naming | FR-007, FR-008, NFR-006 |
| `gerbereye/inspector.py` | Orchestration, path precedence | FR-015 AC-015.4 |
| `gerbereye/api.py` | HTTP API, MJPEG stream | IF-05, NFR-011 |
| `gerbereye/export.py` | CSV export — **stub, issue #16** | FR-022 |
| `web/` | Operator UI, overlay, override | FR-018, FR-019, FR-020 |
| `tools/` | Bench scripts for the hardware tasks | FR-006, RSK-02, RSK-03 |

---

## 2. Deliberate departures from the inception docs

### 2.1 Printed ArUco markers instead of copper fiducials

**Narrows:** FR-007 (detect registration features).

The docs specify detecting the board's own copper fiducials. Those are small,
low-contrast, and easily confused with vias and test points — a poor first CV
target for a team with no prior experience (RSK-05). Printed ArUco markers taped
at measured jig positions give the same four point correspondences with a far
more forgiving detector.

This is also the RSK-03 mitigation arriving early: it works on boards that carry
no fiducials at all, which the docs listed as a fallback and which turns out to
be the common case for the boards actually in hand.

**Restore condition:** a board with well-formed fiducials and time to tune a
detector for them. The `detect_markers()` seam takes any `{id: centre}` mapping,
so swapping the detector needs no change downstream.

### 2.2 Region-level differencing rather than per-component classification

**Narrows:** FR-012, FR-013, FR-014 (presence, placement, orientation classes).

The docs describe classical-feature classification per component ROI, producing
`present / absent / misaligned / rotated / polarity-reversed`. The MVP reports
*regions that differ from the reference*, then names them by which component
they overlap.

This detects the same physical defects and names them correctly. What it does
not do is say *which class* of defect occurred — a missing part and a rotated
part both read as "C14 differs".

**Restore condition:** once the seeded-defect corpus exists (issue #20), the
per-class features can be added inside `differencing.py` without touching the
orchestrator or the API, because `DiffRegion` already carries the fields.

### 2.3 Binary verdict, no `for-review` state

**Narrows:** BR-07 (confidence floor 0.60 → mark for-review).

`for-review` requires a per-component confidence value, which only the
per-class classifier produces. With region differencing there is no meaningful
confidence to threshold, so the verdict is binary.

**Restore condition:** follows 2.2 directly.

### 2.4 Nominal component box size

**Narrows:** BR-03 (ROI = footprint extent × 1.20).

Package dimensions are not in the pick-and-place file, and parsing footprint
libraries was not affordable in the runway. Every component currently gets the
same 3mm nominal box scaled by `roi_scale`.

Consequence: naming is reliable for through-hole and larger SMD, and gets
ambiguous on dense 0402 clusters where several boxes overlap. `name_regions()`
resolves ties by nearest centre, which is defensible but not exact.

**Restore condition:** parse footprint extents from the Gerber or a footprint
library, then feed real per-component dimensions into `project_components()`.

### 2.5 DNP exclusion and polarity classing not implemented

**Narrows:** FR-002, FR-003.

Both need BOM data the MVP does not ingest. **This is the one departure with a
live false-call risk**: a do-not-populate designator sits empty on every board,
so if it ever falls inside a flagged region it will be named and reported as a
defect on every single inspection — the fastest possible route to operator
distrust.

Mitigated for now by differencing against a golden board that *also* has the DNP
positions empty, so no difference appears there. The risk returns the moment the
CAD path runs against a board type whose golden reference is missing.

**Restore condition:** ingest the BOM, filter DNP designators out of the
component map at load time.

### 2.6 No latency instrumentation

**Narrows:** NFR-001 (p95 ≤ 5.0s, instrumented over 200 inspections).

Per-stage timing is not recorded. Observed round-trip on synthetic frames is
well inside budget, but that is not a measurement against the reference bench
and must not be quoted as one.

**Restore condition:** add per-stage timers in `inspector.run_inspection()` and
log them; the structured-logging requirement (FR-027) is also outstanding.

---

## 3. Carried through intact

These were not compromised and should not be quietly dropped later:

- **Loopback-only bind** (NFR-011) — asserted by test, not by review.
- **Append-only verdicts** (NFR-012) — no UPDATE/DELETE path exists for
  `inspection`, `region_verdict` or `override`.
- **Permissive licensing** (ADR-006, CON-08) — every dependency is MIT,
  Apache-2.0, BSD or public domain. Ultralytics is absent by decision.
- **Per-board-type thresholds** (ADR-004, NFR-013) — retunable at runtime via
  `PATCH /api/board-types/thresholds`, never constants in code.
- **Parse and registration failures as control flow** — malformed files return
  400 with a specific reason; registration failure degrades to unnamed regions
  rather than aborting the inspection.
- **Colour-independent verdict display** (NFR-008) — every signal carries a word
  or a stroke style, not colour alone.

---

## 4. Accuracy claims

**None are currently evidenced.** NFR-004 (recall ≥90%) and NFR-005 (false calls
≤0.5%) require the seeded-defect corpus, which is issue #20 and not yet built.

The synthetic tests in `tests/test_pipeline.py` show the detector behaves
correctly on constructed cases — a removed component is flagged at its location,
gaussian noise is not. That is a correctness check, not an accuracy measurement,
and the two should not be conflated in the pitch.
