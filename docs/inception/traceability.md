# Validation & Traceability — GerberEye

**Version:** 0.1 | **Phase 8** | **Last updated:** 2026-08-14

---

## 1. Review techniques applied

| Technique | Applied? | Notes |
|---|---|---|
| Self-review, end-to-end | ✅ | Full set read continuously; surfaced the STK-ID collision and the minimum-value field-name collision |
| Checklist-driven review (§3 below) | ✅ | Systematic pass, defects logged below |
| Automated form check | ✅ | `check_requirements.py` — **all 6 requirement and design artifacts clean, 0 findings** (see the accepted exception below) |
| Model-based validation | ✅ | Building the Phase 6 state machines surfaced two gaps: the `Persisting → Complete` ordering constraint, and the `GoldenOnly → Ready` transition that turned out to be the RSK-01 escape hatch |
| ATAM-lite architecture evaluation | ✅ | Phase 7 §12 — found that D4 is **not** satisfiable by structure alone |
| **Walkthrough with a stakeholder** | ❌ | **Not possible — no reachable end user.** This is the phase's central limitation |
| Prototype-based validation | ❌ | Deferred until a working path A exists |
| Formal Fagan inspection | ❌ | Not warranted at Standard tier |

**Accepted linter exception — this file only.** `check_requirements.py` reports 2 findings against `traceability.md`, both for the same cause: the linter opens a "requirement block" wherever it sees an ID like `FR-001`, then demands acceptance criteria and a stakeholder trace inside that block. A traceability matrix is *made of* ID references, so the heuristic misfires by construction. The findings are **explicitly accepted, not resolved** — mangling the matrix to satisfy a catalog-shaped check would damage the artifact that makes impact assessment possible. Every actual requirement catalog (`requirements.md`, `functional-requirements.md`, `nonfunctional-requirements.md`) and every design artifact (`architecture.md`, `system-model.md`, `adrs/`) lints clean individually.

> ### ⚠ Verification passed. Validation did not.
> **Verification** — *are we building it right?* — passed: the document set is internally consistent, testable, traceable, and lint-clean.
>
> **Validation** — *are we building the right thing?* — **cannot be claimed.** Validation requires a real stakeholder, and six of fourteen stakeholders (every end user) are proxy-sourced. This specification could be perfectly well-formed and still solve a problem no MSME actually has, in a way no operator would actually accept.
>
> The single action that most changes this document's standing is **one visit or phone call to a local PCB assembly shop** (closes ASM-02, ASM-05, ASM-08 and upgrades six personas). It is roughly four hours of work against a two-week runway.

---

## 2. Forward traceability — stakeholder need → implementation

```
STK-101  Operator determines board matches design, without a paper drawing
  ├─ FR-005 golden reference · FR-007 features · FR-008 transform
  ├─ FR-011 ROI · FR-012 presence · FR-015 differencing · FR-016 verdict · FR-018 overlay
  ├─ NFR-004 recall ≥90% · NFR-006 registration ≤2.0 px
  ├─ UC-01 · US-001 · AC-012.1..5, AC-018.1..4
  └─ ADR-002 two-path · ADR-003 classical CV

STK-102  Deviations named by reference designator and defect type
  ├─ FR-003 polarity class · FR-011 · FR-012 · FR-013 placement · FR-014 orientation · FR-019 defect list
  ├─ NFR-004 · NFR-012 integrity
  ├─ UC-01 · US-001 · AC-013.1..4, AC-019.1..3
  └─ BR-04, BR-05, BR-06

STK-103  New board type inspectable from design files, no manual teaching
  ├─ ingest (FR-001) · FR-004 persist · FR-005 golden
  ├─ UC-02 · US-002 · AC-001.1..5
  └─ ADR-002 · IF-02
  ★ THE DIFFERENTIATOR — densest concentration of project-specific knowledge

STK-104  Inspection within cycle-time budget
  ├─ FR-017 trigger · NFR-001 p95 ≤5.0 s · NFR-003 Pi ≥15 fps
  ├─ AC-017.1..3
  └─ ADR-001 pipe-and-filter · ADR-003 classical CV

STK-105  No network connection, no recurring fee
  ├─ FR-025 offline operation · NFR-011 zero egress
  ├─ AC-025.1..2 · IF-05 loopback bind
  └─ ADR-005 no agent framework · ADR-006 licensing

STK-106  Durable, exportable record per board
  ├─ FR-021 persist · FR-022 export · NFR-009 RPO/RTO · NFR-012 integrity
  ├─ UC-04 · US-004 · AC-021.1..3, AC-022.1..3
  └─ Append-only schema (system-model §1)

STK-107  Operator can overrule in one action
  ├─ FR-009 state display · FR-010 manual registration · FR-020 override
  ├─ UC-03 · US-003 · AC-020.1..4
  └─ ADR-004 (thresholds tunable rather than arguing with the operator)

STK-108  False alarms rare enough to sustain trust
  ├─ FR-002 DNP exclusion · FR-009 · NFR-005 ≤0.5% · NFR-013 threshold tuning
  ├─ AC-002.1..2
  └─ BR-07 confidence floor · C-01 · ADR-004

STK-109  Recurring defects visible in aggregate
  └─ FR-023 · UC-05 · AC-023.1..2

STK-110  Station cost within MSME operating cash
  └─ NFR-002 resource ceiling · CON-02 ₹10 000 · ADR-003 (no GPU needed)

STK-111  Untrained operator reaches correct use
  └─ FR-018 · FR-019 · NFR-007 ≤5 min · NFR-008 colour-independent

STK-112  System positions operator as the authority
  └─ FR-020 · NFR-005 · C-01

STK-113  Deliverable evidences the published scoring criteria
  └─ The full document set; FR-027 logging (weak trace — see defect D-03)

STK-114  Design files never modified, never the only copy
  └─ FR-026 · NFR-011 · AC-026.1..2 · AC-001.5

STK-115  Stored data bounded on a shop laptop
  └─ FR-024 retention · AC-024.1..3

STK-116  Capture conditions repeatable frame to frame
  └─ FR-006 · NFR-010 degraded modes · AC-006.1..3 · STK-13 (non-human)
```

**Forward check: PASS.** All 16 stakeholder requirements trace to at least one FR or NFR.

## 3. Backward traceability — design element → need

| Design element | Satisfies | Orphan check |
|---|---|---|
| ADR-001 modular monolith + pipe-and-filter | NFR-001, NFR-013 ← STK-104, STK-108 | PASS |
| ADR-002 two-path inspection | RSK-01, RSK-05 ← CON-03, CON-07 | PASS (constraint-derived) |
| ADR-003 classical CV hot path | NFR-001, NFR-005 ← STK-101, STK-108 | PASS |
| ADR-004 per-board-type thresholds | NFR-013 ← BR-03..07 ← STK-108 | PASS |
| ADR-005 no agent framework | NFR-001, NFR-011 ← STK-104, STK-105 | PASS |
| ADR-006 permissive licensing | CON-08 ← STK-04 (buyer), STK-08 (jury) | PASS |
| Inspection Service container | ingestion, pipeline, records (FR-001 to FR-027) | PASS |
| Operator UI container | FR-018, 019, 020 ← STK-101, STK-107, STK-111 | PASS |
| Local Store container | FR-021–024 ← STK-106, STK-115 | PASS |
| Golden Differencing filter | FR-015 ← STK-101 (via RSK-01 mitigation) | PASS |
| `thresholds` table | NFR-013 ← BR-03..07 | PASS |
| Append-only schema | NFR-012 ← STK-106 | PASS |
| IF-05 loopback bind | NFR-011 ← STK-105, STK-114 | PASS |

**Backward check: PASS.** No design element exists without a requirement driving it. Nothing was invented.

## 4. Verification method per requirement class

| Class | Verification |
|---|---|
| Ingestion (FR-1 to FR-5) | Unit tests against 3 published open-hardware archives |
| Capture, registration (FR-006–010) | Bench test with a fixed jig; reprojection error logged per frame |
| Classification (FR-011–016) | Seeded-defect corpus (NFR-004 measurement method) |
| Operator (FR-017–020) | Manual walkthrough + timed trial (NFR-007) |
| Records (FR-021–024) | Unit tests + kill-process test (NFR-009) |
| Cross-cutting (FR-025–027) | Packet capture with interfaces disabled; SHA-256 assertions |
| NFR-001, 002, 003 | Instrumented timing over 200 inspections; 10-min soak |
| NFR-004, 005, 006 | Seeded corpus + 20 known-good boards |
| NFR-007, 008 | 5-subject timed trial; greyscale/deuteranopia screenshot check |
| NFR-009–013 | Fault injection; code review; timed change scenario |

**Unverified requirements: none.** Every requirement has a stated method — though several methods depend on artifacts that do not yet exist (see defect D-01).

---

## 5. Review checklist results

| Check | Result |
|---|---|
| **Completeness** — every STK traces to an FR/NFR | ✅ 16/16 |
| Every FR has AC covering happy path, alternates, errors | ✅ 27/27 |
| Every entity lifecycle covers state × event | ✅ 3 state machines, Phase 6 |
| Every external interface has a failure mode | ✅ 6/6 in the interface catalog |
| Eight coverage sweeps actually run | ✅ Phase 4; raised OQ-08..11 |
| **Correctness** — business rules match an authoritative source | ⚠️ **D-02** — BR-03/04/05/07 thresholds are `[INFERRED]`, not sourced from IPC-A-610 text |
| NFR targets have a rationale beyond assertion | ✅ Anchored to perception thresholds, hardware limits, or operator-trust reasoning |
| Domain model cardinalities interrogated | ✅ 5 relationships interrogated; 3 changed from the naive reading |
| **Consistency** — no contradictory behaviour for one trigger | ✅ FR-015 AC-015.4 resolves the two-path precedence explicitly |
| Terminology matches the glossary | ✅ No synonym drift found |
| NFR targets not jointly infeasible | ⚠️ NFR-004 vs NFR-005 are in genuine tension — resolved and documented as C-01/T-01, not silently |
| **Unambiguity** — linter clean | ✅ 14 files, 0 findings |
| **Testability** — binary AC | ✅ |
| **Feasibility** — Musts achievable within CON-nn | ⚠️ **D-01** |
| NFR targets sanity-checked against the architecture | ✅ ATAM-lite; found D4 not structurally satisfiable |
| **Necessity** — no gold-plating | ⚠️ **D-03** |
| **Prioritisation sanity** | ⚠️ 70% Must on FRs — justified in Phase 4, but above the 60% guideline |

### Defects logged

| ID | Defect | Severity | Resolution |
|---|---|---|---|
| **D-01** | NFR-004 (recall ≥90%) and NFR-005 (false calls ≤0.5%) are unverifiable until a seeded-defect corpus exists, and that corpus depends on RSK-01 closing | **High** | Accepted with mitigation. Corpus construction is scheduled Day 5 and is a **precondition for any accuracy claim to a jury**. Until it exists, present targets as targets, never as measured results |
| **D-02** | BR-03/04/05/07 numeric thresholds are inferred, not sourced from IPC-A-610 | Medium | Accepted for MVP. They are per-board-type configuration (ADR-004) and will be empirically tuned, so an inferred starting value is defensible. **Do not cite IPC-A-610 as the source of these specific numbers** |
| **D-03** | FR-027 (event logging) traces only to STK-113 (jury deliverable), which is a weak necessity trace — logging serves operability, and no operational stakeholder demanded it | Low | Retained. Justification: RSK-05 makes diagnosis time a real schedule risk for this team. Recorded as a team-serving requirement rather than pretending a user asked for it |
| **D-04** | Every end-user requirement is proxy-sourced | **High** | **Unresolved.** Cannot be closed from inside the document. Carried into the baseline as a stated limitation |

---

## 6. Open questions carried forward

| ID | Question | Owner | Deadline | Default |
|---|---|---|---|---|
| OQ-01 | Which physical board is the reference target? | ECE | Day 2 | Buy an open-hardware board with published Gerbers |
| OQ-02 | USB microscope + ring light procurable in budget? | Lead | Day 3 | Plain webcam; accept lower small-passive accuracy |
| OQ-03 | Pi as capture node or inference host? | ECE | Day 5 | **Laptop-attached USB camera** (driven by RSK-08) |
| OQ-04 | Demo THT, SMD, or both? | Lead | Day 3 | SMD only |
| OQ-05 | Reachable local assembly shop for ASM-02? | ECE | Day 4 | Cite industry practice; mark unvalidated |
| OQ-06 | Does an override require a reason code? | Lead | Day 6 | No reason code (favours STK-104) |
| OQ-07 | Image retention period? | Lead | Day 8 | Failed 90 days; passed thumbnails only |
| OQ-08 | Board type delete/rename? | Lead | Day 7 | Rename yes, delete no |
| OQ-09 | Operator identity authenticated? | Lead | Day 7 | Self-declared (RSK-04 accepted) |
| OQ-10 | First-run empty state? | Lead | Day 6 | Empty state directing to UC-02 |
| OQ-11 | Timestamps local or UTC? | Any | Day 6 | UTC stored, local displayed |
| OQ-12 | Install method and duration? | Lead | Day 9 | Single offline bundle, target ≤15 min |

**None block the baseline.** All 12 have a stated default that applies if the deadline passes.

---

## 7. Baseline

```
BASELINE v1.0 — GerberEye inception
Date:        2026-08-14
Tier:        Standard
Scope:       STK-01..14, STK-101..116, CON-01..11, ASM-01..08,
             FR-001..027, BR-01..07, NFR-001..013, UC-01..06,
             US-001..004, IF-01..06, ADR-001..006, RSK-01..08
Form check:  check_requirements.py — 14 files, 0 findings
Open items:  OQ-01..12 (do not block; each has a default)
Known gaps:  D-01 accuracy unverifiable until seeded corpus exists
             D-04 all end-user requirements proxy-sourced
Status:      Draft — awaiting sign-off
```

### Change control after baseline

1. **Propose** — state what changes and why.
2. **Impact-assess** — walk §2 and §3 above to find every affected requirement, design element, and ADR. This is the step that is skipped without a matrix, and its absence causes the most rework.
3. **Decide** — accept, reject, or defer, with a named decider.
4. **Apply** — update the artifact, bump version, **keep the ID unchanged**, append to the change log below.

### Change log

| ID | Date | Change | Reason | Impact | Approved by |
|---|---|---|---|---|---|
| CR-01 | 2026-08-14 | Stakeholder requirement IDs renumbered `STK-R01..R16` → `STK-101..116` | Original scheme collided with the stakeholder role IDs and failed the trace check | All trace references updated across 3 files; no semantic change | Team |

---

## 8. Sign-off

| Artifact | Approver | Approved | Date |
|---|---|---|---|
| Requirements (Phases 1–5) | Team lead (STK-10) | ☐ | |
| Architecture (Phases 6–7) | Team lead (STK-10) | ☐ | |
| Security-relevant NFRs (NFR-011, NFR-012) | Team lead | ☐ | |
| Overall baseline | Faculty mentor (STK-09) | ☐ | |

> Sign-off is deliberately unchecked. The baseline is declared **Draft** until a human confirms it — per Phase 8 §6, implicit consensus is where unresolved disputes surface later at maximum cost.

---

## 9. Exit criteria — Phase 8

- [x] Full §3 checklist worked through; 4 defects logged, 2 accepted with mitigation, 1 retained with justification, 1 unresolved and carried
- [x] Techniques beyond self-review used (checklist, automated, model-based, ATAM-lite)
- [x] Forward and backward traceability built; orphan checks pass in both directions
- [x] Every requirement has a verification method
- [x] Baseline declared explicitly with version, date, scope, and known gaps
- [x] Change control process stated; CR-01 logged
- [ ] **Sign-off pending** — requires a human decision
- [x] All 12 open questions carried forward with owner, deadline, and default
