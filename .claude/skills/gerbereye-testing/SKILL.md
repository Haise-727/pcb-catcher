---
name: gerbereye-testing
description: Testing strategy, acceptance-criteria reference, and the seeded-defect corpus method for GerberEye. Use when writing or reviewing tests, before marking any FR or user story done, and especially before making any accuracy claim about recall or false-call rate — those targets are unverifiable until the seeded corpus exists.
---

# GerberEye Testing

*Derived from: functional-requirements.md (AC catalog, coverage sweeps), nonfunctional-requirements.md, traceability.md §4–§5.*

## ⚠ Accuracy claims are blocked until the corpus exists (defect D-01)

NFR-004 (recall ≥90%) and NFR-005 (false calls ≤0.5%) **cannot be verified** without a seeded-defect corpus. Until it exists, present these as *targets*, never as measured results. Saying "we achieve 90% recall" without the corpus is an unevidenced claim, and an industry juror is exactly the person who will ask how it was measured.

### Building the corpus — one afternoon, do it early

1. Capture golden references for every available board.
2. **Digitally seed** using pick-and-place coordinates: mask an ROI → `absent`; affine-rotate → `rotated`; flip 180° → `reversed`. Hundreds of labelled instances from one board, ground truth free.
3. **Physically seed** for what synthesis cannot fake: desolder components, rotate parts, reverse a diode. 10 boards × 5 defects.
4. Target: **≥50 seeded instances across ≥3 package sizes**, plus **≥20 known-good boards** for the false-call measurement.

Physical seeding doubles as the live jury demo — hand them a board, let them pull a component, re-run.

## Verification method per class

| Requirements | Method |
|---|---|
| FR-001–005 ingestion | Unit tests against 3 published open-hardware archives |
| FR-006–010 capture, registration | Bench test, fixed jig, reprojection error logged per frame |
| FR-011–016 classification | Seeded-defect corpus |
| FR-017–020 operator | Manual walkthrough + timed trial |
| FR-021–024 records | Unit tests + kill-process test |
| FR-025–027 cross-cutting | Packet capture with interfaces disabled; SHA-256 assertions |
| NFR-001–003 | Instrumented timing over 200 inspections; 10-min soak |
| NFR-004–006 | Seeded corpus + 20 known-good boards |
| NFR-007–008 | 5-subject timed trial; greyscale + deuteranopia screenshot check |
| NFR-009–013 | Fault injection; code review; timed change scenario |

## Tests that must exist because a claim depends on them

- **Loopback bind** — assert the server is not reachable on any non-loopback interface. NFR-011 is the strongest security claim and one character breaks it.
- **Source files unmodified** — SHA-256 before and after ingestion (AC-001.5).
- **Offline workflow** — full ingest→inspect→override→export with every network interface disabled (AC-025.1).
- **Kill-process durability** — kill at 20 random points; verify record count and ≤30 s relaunch (NFR-009).
- **Append-only** — assert no exposed operation mutates a persisted verdict (AC-021.3).
- **Idempotent trigger** — double-trigger yields exactly one inspection row (AC-017.3).
- **Frame stability** — 100 static frames, mean per-pixel variation <2 levels (AC-006.2).
- **DNP exclusion** — a DNP designator emits no result of any kind (AC-002.1).

## Standing coverage sweeps — re-run when adding any entity or workflow

CRUD · lifecycle (every state × event) · role × capability · system lifecycle (first-run, empty state) · failure (every dependency: unavailable, slow, malformed) · time (timezones, retention, expiry) · concurrency · observability.

The Phase 4 run of these raised OQ-08 (board type delete), OQ-09 (operator identity), OQ-10 (first-run state) and OQ-11 (timezone) — all still open with defaults.
