---
name: gerbereye-inspection-pipeline
description: Internals, latency budget, and failure modes of the GerberEye inspection pipeline — capture, registration (CAD-to-camera homography), ROI extraction, classification, golden-board differencing, and verdict derivation. Use when implementing, debugging, or tuning anything inside the inspection path, when accuracy or latency is off target, or when deciding which of the two inspection paths applies to a board type.
---

# GerberEye Inspection Pipeline

*Derived from: architecture.md §4–§5, ADR-001/002/003/004, system-model.md §2–§3, NFR-001/004/005/006.*

## Two paths, one verdict stage

```
CAD path        Capture → Registration → ROI extraction → Classification ─┐
                                                                          ├→ Verdict
Differencing    Capture → Golden diff ──────────────────────────────────┘
```

**Precedence (FR-015 AC-015.4):** where a component map exists, the CAD path runs and differencing does **not**. A board type with no pick-and-place file runs differencing only.

Why two paths (ADR-002): the team holds boards without design files and design files without boards. The paths have *different data prerequisites*, so no single blocker takes out both. **Build the differencing path first** — it needs no CV depth and it is the demo that cannot fail.

## Latency budget — p95 ≤ 5.0 s, 250 components, CPU only

```
  Frame capture + colour convert          100 ms
  Registration feature detection          300 ms
  Homography solve                         20 ms
  ROI extraction, 250 components          200 ms
  Classification, 250 components        1 500 ms   ← ~6 ms per component
  Verdict + overlay render                300 ms
  Record persist                          200 ms
  Allocated 2 620 ms · Reserve 2 380 ms · Total 5 000 ms
```

**~6 ms per component is why there is no per-component CNN** (ADR-003). Template matching, edge density, and colour statistics fit; a neural net does not. If you are reaching for a model, re-read ADR-003 first — and note that no labelled assembly-defect dataset of usable size exists publicly.

## Stage contracts

| Stage | In | Out | Failure mode |
|---|---|---|---|
| Capture | — | frame | Disconnect → `NoCamera` ≤2 s. **Exposure, focus, WB must be locked** — auto modes silently destroy frame comparability |
| Registration | frame, component map | transform + RMS residual px | <4 correspondences or collinear points → `RegistrationFailed`, emit no verdicts. Scale outside 0.5×–2.0× → reject as mis-detection |
| ROI extraction | transform, component map, thresholds | one region per component | Region partly outside frame → `not-inspectable`, **never** `absent` |
| Classification | regions, thresholds | verdict + confidence 0.0–1.0 per component | Saturated region → `not-inspectable`, **never** `absent` |
| Golden diff | frame, golden image | differing regions | Runs only when no component map exists |
| Verdict | component verdicts | pass / fail / review | BR-06 |

## Registration states (NFR-006)

| RMS residual | State | Behaviour |
|---|---|---|
| ≤ 2.0 px | `registered` | Normal |
| 2.0 – 5.0 px | `degraded` | Proceed; mark the inspection degraded |
| > 5.0 px | `failed` | **Emit no component verdicts.** Offer manual 4-point fallback |

Registration error propagates into every ROI. A 5 px error on an 0402 package is a large fraction of the component and manufactures false calls at the smallest sizes.

## The insight that removes the labelled-data problem

**The pick-and-place file is the label source.** It states exactly what should sit at every coordinate. That means:
- No annotation is required to know ground truth.
- Seeded defects can be generated *digitally* — mask a component ROI using its pick-and-place coordinate to synthesise "absent"; affine-rotate to synthesise "rotated".
- The seeded corpus for NFR-004 can be built in one afternoon from one board.

State this in the pitch: *"we do not need annotated data — the design file is the label."*

## When accuracy is off target, check in this order

1. **Illumination stability** (RSK-02) — dominates the false-call number more than any algorithm choice. Verify AC-006.2: mean per-pixel variation across 100 static frames below 2 levels on an 8-bit scale.
2. **Registration residual** — if above 2.0 px, fix that before touching classification thresholds.
3. **DNP exclusion** — a DNP reported absent is a guaranteed false call on every board of that type.
4. **Thresholds** (BR-03/04/05/07) — tune in the `thresholds` table, per board type. Never in code.
