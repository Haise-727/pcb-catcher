# ADR-003 — Classical CV on the hot path; no per-component deep inference

**Status:** Accepted | **Date:** 2026-08-14 | **Deciders:** Dev team (STK-10)
**Drivers:** D1 (NFR-001), D5 (CON-03/CON-04), CON-05, CON-08

## Context
NFR-001 allows p95 ≤ 5.0 s for a 250-component board, of which 1 500 ms is budgeted for classification — roughly **6 ms per component**. Available compute is a 4-core CPU with no GPU (CON-05). No labelled PCB *assembly* defect dataset of usable size exists publicly; the large well-known datasets (DeepPCB, PKU-Market-PCB) are bare-board trace defects, a different problem. The one assembly-focused public dataset found is ~175 images.

## Options considered

**1. Per-component CNN classifier**
- Higher ceiling on hard cases
- On CPU, a small CNN over 250 ROIs will not reliably hold 6 ms/component. Requires labelled training data that does not exist. Ultralytics is AGPL-3.0, breaching CON-08. Rejected for MVP

**2. Whole-board object detector (YOLO family)**
- Single forward pass rather than 250
- Still needs labelled assembly-defect data. Detects components, but the *deviation-from-design* judgement still requires the CAD comparison. Adds AGPL exposure. Rejected

**3. Classical features per ROI, referenced against CAD**
- Template matching, edge density, and colour statistics on small ROIs are microseconds-scale, comfortably inside 6 ms
- **Needs no labelled training data at all** — the pick-and-place file states what should be at every coordinate, so the design file is the label source
- All dependencies Apache-2.0 or MIT
- Lower ceiling on defect classes that classical features describe poorly

## Decision
Option 3 for MVP. Classification uses classical features on CAD-referenced ROIs. Anomaly detection (anomalib, Apache-2.0) remains a deferred path for classes classical features cannot cover.

## Consequences
- D1 latency budget is achievable on CPU-only hardware
- The labelled-data problem is dissolved rather than solved — a genuinely strong claim for the pitch: *"we do not need annotated data, the design file is the label"*
- CON-08 satisfied with no exceptions
- Accuracy ceiling is lower than a well-tuned CNN on subtle defects; accepted, and the deferred anomalib path exists for when it binds
- Illumination stability (RSK-02) matters far more than it would for a learned model, because classical thresholds do not generalise across lighting

## Revisit if
Measured false-call rate exceeds 1.0% (the NFR-005 minimum) after illumination is stabilised and thresholds tuned.

**Trace to:** STK-101, STK-108 (via NFR-001, NFR-005).
