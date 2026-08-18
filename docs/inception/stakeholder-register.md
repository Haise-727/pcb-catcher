# Stakeholder Register — GerberEye

**Version:** 0.2 | **Phase 2** | **Last updated:** 2026-08-14

> ### ⚠ Proxy-source warning — read before trusting anything below
> The team has **no confirmed access to any real MSME PCB assembly shop**. Stakeholders STK-01 through STK-06 are therefore **proxy-sourced**: derived from the problem statement text, industry practice, and reasoning — *not from talking to anyone who does this work*.
>
> Proxy-derived requirements are systematically distorted. They describe how work *should* happen rather than how it does. **One site visit or phone call to a local assembly shop would upgrade six stakeholders from provisional to grounded and is the highest-value four hours available to this project** (see ASM-02, ASM-05, ASM-08).
>
> Until then: every persona is `[PROVISIONAL]`, and any figure quoted to a jury must be presented as an assumption, not a finding.

---

## 1. Register

| ID | Role | Category | Population | Influence | Interest | Attitude | Access |
|----|------|----------|-----------|-----------|----------|----------|--------|
| STK-01 | Line Operator | Primary | 1–5 per shop; continuous, whole shift | Low | High | Neutral → Skeptical | **None — proxy** |
| STK-02 | QA Supervisor | Primary | 1 per shop; several times/day | Medium | High | Supportive | **None — proxy** |
| STK-03 | Board-Type Setup Technician | Primary / Operational | 1 per shop; once per new board type | Medium | High | Neutral | **None — proxy** |
| STK-04 | MSME Owner / Production Manager | Secondary (buyer) | 1 per shop; weekly summary | **High** | Medium | Supportive | **None — proxy** |
| STK-05 | Rework Technician | Secondary | 1–2 per shop; per flagged board | Low | Medium | Supportive | **None — proxy** |
| STK-06 | OEM Customer of the MSME | Secondary / External | n/a; audit events | Medium | Low | Neutral | **None — proxy** |
| STK-07 | VITISH Internal Jury (VIT faculty) | Governance | ~3–5 evaluators; one gate | **High** | Medium | Neutral | Indirect — via rubric/mentor |
| STK-08 | SIH 2026 National Jury (ministry / industry) | Governance | ~3–5 per PS; one gate | **High** | Medium | Neutral | Indirect — via published criteria |
| STK-09 | Faculty Mentor / HOD | Governance | 1; periodic | Medium | Medium | Champion | **Direct** |
| STK-10 | Development Team (5 CSE + 1 ECE) | Operational | 6; continuous | **High** | **High** | Champion | **Direct** |
| STK-11 | Displaced Manual Inspector | **Negative** | 1–3 per shop | Low | High | **Skeptical → Opposed** | **None — proxy** |
| STK-12 | IPC (standards body) | External | n/a | Low | Low | Neutral (non-negotiating) | Published standards only |
| STK-13 | Capture Subsystem (camera + jig) | **Non-human** | 1 | n/a | n/a | n/a | Direct (we build it) |
| STK-14 | Local Datastore | **Non-human** | 1 | n/a | n/a | n/a | Direct (we build it) |

---

## 2. Detail per stakeholder

### STK-01 — Line Operator `[PROXY]`
- **Category:** Primary
- **Population / frequency:** 1–5 per shop, using the station continuously across a full shift
- **Goals:** Get through the board queue without being blamed for an escape
- **Pain points today:** Cross-referencing hundreds of designators against a paper drawing under a magnifier lamp; eye fatigue late in shift; no way to prove a board was checked properly
- **Success criteria (their words):** *"It tells me what's wrong without me having to read the drawing, and it doesn't cry wolf."*
- **Domain expertise:** Intermediate (knows boards, not CAD) · **Tech proficiency:** Low
- **Engagement plan:** Proxy → **upgrade to observation** if a shop visit is arranged
- **Note:** This stakeholder has the highest-quality requirements and the least authority — the classic pattern that produces a product the buyer approves and the users route around. Weight their input above their influence rating.

### STK-02 — QA Supervisor `[PROXY]`
- **Category:** Primary
- **Goals:** Reduce escapes; be able to answer "what did you inspect" with evidence
- **Pain points today:** Inspection record is a signature on a sheet; no defect trend data; cannot identify which designator fails repeatedly
- **Success criteria:** *"I can show a customer what we checked, and I can see which part keeps failing."*
- **Domain expertise:** Expert · **Tech proficiency:** Medium

### STK-03 — Board-Type Setup Technician `[PROXY]`
- **Category:** Primary / Operational
- **Goals:** Get a new board type inspectable within one shift of receiving its design files
- **Pain points today:** On commercial AOI, "programming" a new board takes hours to days and is often vendor-billed — a major reason small shops don't adopt AOI even when they can afford the machine
- **Success criteria:** *"I load the design files and it just knows what the board should look like."*
- **Note:** **This stakeholder is why CAD-referenced inspection wins.** Golden-board-only systems require manual teaching per board type; CAD ingestion is near-instant. Setup cost, not unit cost, is the real adoption barrier — and it is the strongest argument in the pitch.

### STK-04 — MSME Owner / Production Manager `[PROXY]`
- **Category:** Secondary (the buyer)
- **Goals:** Win contracts requiring traceability; cut rework cost; avoid capital expenditure
- **Pain points today:** Cannot bid on work demanding inspection records; AOI capex unjustifiable at their volume
- **Success criteria:** *"It pays for itself this quarter and I didn't need a loan."*
- **Influence:** High — holds the purchasing decision · **Tech proficiency:** Low

### STK-05 — Rework Technician `[PROXY]`
- **Category:** Secondary
- **Goals:** Repair a flagged board without having to re-diagnose which component failed
- **Success criteria:** *"It tells me which designator and what's wrong with it, not just 'this board failed'."*
- **Note:** Drives the requirement that defect output is **per-designator and actionable**, not a board-level pass/fail.

### STK-06 — OEM Customer of the MSME `[PROXY]`
- **Category:** Secondary / External
- **Goals:** Assurance that delivered boards were inspected
- **Note:** Never touches the system. Their audit expectation is the entire reason inspection records must be exportable and tamper-evident.

### STK-07 / STK-08 — VITISH and SIH Juries
- **Category:** Governance — these two gates decide whether the project continues at all
- **Goals:** Select solutions that are novel, feasible, impactful, and deployable
- **Success criteria — published SIH scoring:** novelty of idea · complexity · **clarity and detail in the prescribed format** · feasibility · practicability · sustainability · **scale of impact** · user experience · potential for future progression. Scored 1–20 per criterion, weighted to 100, across three rounds.
- **Critical note:** Novelty is **one of nine** criteria. A team optimising purely for technical sophistication is optimising roughly one-ninth of the rubric. Feasibility, impact and UX together outweigh it heavily.
- **STK-08 composition:** ministry and industry officers, **not academics.** They score *"can my department or plant deploy this?"* — which is why deployment cost, operator training time, and integration path must lead the pitch, not model architecture.

### STK-09 — Faculty Mentor / HOD
- **Category:** Governance · **Access: Direct** — one of only three reachable stakeholders
- **Goals:** Team fields a credible entry; registration paperwork signed on time
- **Engagement:** Use this access. Mentor may also be the fastest route to an MSME introduction (closing ASM-02).

### STK-10 — Development Team
- **Category:** Operational · 5 CSE + 1 ECE
- **Constraint they impose:** No mechanical fabrication capability. Any requirement implying a machined jig, enclosure, or conveyor is **not deliverable** and must be bought, borrowed, or descoped.
- **Success criteria:** Ship something demoable inside 2 weeks without the team burning out before the jury sees it.

### STK-11 — Displaced Manual Inspector `[PROXY]` — **negative stakeholder**
- **Category:** Negative
- **Position:** Their visual inspection role is partly automated by this system
- **Why they matter:** A skeptical operator who does not trust the tool will bypass it, and a bypassed inspection station has *negative* value — it adds cycle time and produces records nobody believes. Every AOI deployment lives or dies on operator trust.
- **What this generates:** the false-call ceiling (NFR), the one-click false-call override, and the framing that GerberEye *assists* rather than replaces — the operator remains the authority, the machine is the second pair of eyes that never gets tired.

### STK-12 — IPC (standards body) — external, non-negotiating
- Defines **IPC-A-610** (defect acceptability taxonomy) and **IPC-2591 / CFX** (factory data exchange). We conform; we do not negotiate. Standards are paywalled — plan to work from public summaries and the CFX open SDK.

### STK-13 — Capture Subsystem — **non-human**
- **Needs (it has no voice, so recorded explicitly):** stable frame rate, locked exposure and white balance, fixed focal distance, repeatable board position. Auto-exposure and autofocus are **actively harmful** — they break frame-to-frame comparability and must be disabled.

### STK-14 — Local Datastore — **non-human**
- **Needs:** bounded growth. An unbounded per-board image archive fills a shop laptop's disk in weeks. Requires a retention policy — full images only for failed boards, thumbnails or crops otherwise.

---

## 3. Power / Interest Map

```
High influence │  KEEP SATISFIED              │  MANAGE CLOSELY
               │                              │
               │  STK-04 MSME Owner (buyer)   │  STK-10 Dev Team
               │  STK-07 VITISH Jury          │
               │  STK-08 SIH Jury             │
               ├──────────────────────────────┼──────────────────────────────
 Low influence │  MONITOR                     │  KEEP INFORMED
               │                              │
               │  STK-06 OEM Customer         │  STK-01 Line Operator ★
               │  STK-12 IPC                  │  STK-02 QA Supervisor
               │                              │  STK-03 Setup Technician
               │                              │  STK-05 Rework Technician
               │                              │  STK-11 Manual Inspector ⚠
               │                              │  STK-09 Mentor (Medium/Medium)
               └──────────────────────────────┴──────────────────────────────
                  Low interest                   High interest
```

**Engagement consequences:**
- **Manage closely (STK-10):** the team is its own most-engaged stakeholder — which is exactly the condition under which teams build what they find interesting rather than what users need. The proxy warning above is the counterweight.
- **Keep satisfied (STK-07/08):** juries are high-influence, low-interest — they engage once, briefly, at a gate. This is the classic "discovered late" failure mode. Mitigate by reading the scoring criteria *now* and designing the deliverable against them, not by hoping to impress on the day.
- **★ STK-01 is the highest-quality requirements source and has the lowest influence.** Systematically discounting them is the single most common way internal tools fail. Deliberately over-weight operator needs relative to their power rating.
- **⚠ STK-11 is the only opposed stakeholder** and is invisible in most hackathon analyses. Ignoring them produces a technically-correct system that gets switched off.

---

## 4. Personas

### PERSONA: Ravi, Line Operator `[PROVISIONAL — no interviews conducted]`

```
Grounding:      PROVISIONAL. Derived from PS #82 text and general SMT
                shop-floor practice. No observation, no interview.

Context of use
  Environment:  Shop floor. Fluorescent overhead light, variable daylight
                from a window, ambient dust, some noise.
  Device:       A shared laptop on a bench next to the assembly station.
  Interruptions:Continuous — supervisor queries, part shortages, queue pressure.
  Frequency:    Every board, all shift. 100+ boards/day.
  Expertise:    Knows boards and components well. Has never opened a CAD file.

Goals
  Primary:      Clear the board queue without an escape traced back to him.
  Secondary:    Finish the shift without eye strain.

Frustrations today
  - Cross-referencing ~200 designators against a paper drawing, by eye.
  - Accuracy visibly drops in the last two hours of shift.
  - When a defect escapes, there is no record showing he did inspect it.

Workarounds
  - Marks up the paper drawing with a highlighter to keep his place.
  - Checks only the components that "usually go wrong" when the queue is long.
    ← This is an unmet requirement with evidence attached: he already
      prioritises by failure likelihood. The system should surface exactly that.

Success looks like
  "It shows me the bad ones and it's right. If it cries wolf twice
   in a row I'll stop looking at it."

Constraints
  - Frequently one hand on the board — interaction must work with one hand,
    or better, with no hands at all.
  - Cannot leave the station to go read a manual.
  - Low tolerance for any step that adds cycle time.

Quote (representative, not recorded)
  "I don't need it to be clever. I need it to be right."
```

**Design consequence of frequency:** 100+ boards/day is a *high-frequency* task. It needs a dense, memorisable, near-zero-interaction flow — place board, glance at screen, move on. Designing this like a low-frequency guided wizard, with confirmations and dialogs, is the most common usability failure in this class of tool and must be actively avoided.

### PERSONA: Meena, QA Supervisor `[PROVISIONAL]`

```
Grounding:      PROVISIONAL.

Context of use
  Environment:  Small office adjacent to the floor.
  Frequency:    Reviews aggregate data 2-3x/day; pulled to the floor on escalation.
  Expertise:    Expert in assembly defects. Comfortable with spreadsheets.

Goals
  Primary:      Cut escapes; produce evidence for customer audits.
  Secondary:    Identify which designator or process step fails repeatedly.

Frustrations today
  - Inspection evidence is a signature. It convinces no auditor.
  - Knows some parts fail often but has no data to prove it or fix the cause.

Workarounds
  - Keeps a personal notebook of "problem components" per board type.
    ← Another pre-validated requirement: defect aggregation by designator.

Success looks like
  "I can export last month's inspections and show the customer.
   And I can tell the line which pad to fix."

Constraints
  - Will not maintain a separate data-entry step. If it isn't automatic, it won't happen.
```

### PERSONA: Suresh, MSME Owner `[PROVISIONAL]`

```
Grounding:      PROVISIONAL.

Frequency:      Weekly glance at a summary. Will use this system approximately never.
Expertise:      Business, not technical.

Goals
  Primary:      Win higher-value contracts that demand traceability.
  Secondary:    Cut rework cost.

Frustrations today
  - Loses bids that require documented inspection.
  - Quoted AOI capex is not financeable at his volume. [ASM-01 — unvalidated]

Success looks like
  "It cost less than one month of rework and I can put it in a tender document."

Constraints
  - No capital approval process — it comes out of operating cash or not at all.
  - Will not pay a recurring subscription.  ← reinforces CON-01
```

---

## 5. Stakeholder Requirements

Solution-free statements. Every functional requirement in Phase 4 must trace to at least one of these.

| ID | Statement | Source | Category | Priority | Rationale |
|----|-----------|--------|----------|----------|-----------|
| **STK-101** | An operator must be able to determine whether an assembled board matches its design, without consulting a paper drawing | STK-01 `[proxy]` | Primary | **Must** | The core job. Everything else is secondary |
| **STK-102** | Deviations must be identified **by reference designator and defect type**, not as a board-level pass/fail | STK-05, STK-02 `[proxy]` | Secondary | **Must** | A board-level verdict is not actionable; rework must know which part |
| **STK-103** | A new board type must become inspectable from its existing design files, without manual per-component teaching | STK-03 `[proxy]` | Primary | **Must** | Setup cost is the real AOI adoption barrier — the differentiating requirement |
| **STK-104** | Inspection must complete within the cycle-time budget stated in NFR-001, so the station does not become the line bottleneck | STK-01, STK-04 `[proxy]` | Primary | **Must** | A station exceeding its budget gets bypassed, and a bypassed station has negative value |
| **STK-105** | The system must operate with no network connection and no recurring fee | STK-04 `[proxy]`, CON-01 | Secondary | **Must** | Shop floor reality; owner will not accept a subscription |
| **STK-106** | Every inspected board must produce a durable, exportable record | STK-02, STK-06 `[proxy]` | Primary | **Must** | Unlocks traceability-gated contracts — the owner's actual business goal |
| **STK-107** | The operator must be able to overrule the system when it is wrong, in one action | STK-01, STK-11 `[proxy]` | Primary | **Must** | Trust mechanism. Without it, a false-call streak causes abandonment |
| **STK-108** | False alarms must be rare enough that the operator continues to trust the result | STK-01, STK-11 `[proxy]` | Primary | Should | Precision matters more than recall for *adoption*, even though recall matters more for *quality* — see conflict C-01 |
| **STK-109** | Recurring defects must be visible in aggregate so the underlying process can be corrected | STK-02 `[proxy]` | Secondary | Should | Meena's notebook workaround, automated |
| **STK-110** | Total cost of the station must be within an MSME's operating cash | STK-04 `[proxy]`, CON-02 | Secondary | **Must** | Without this the product does not exist for its intended user |
| **STK-111** | An untrained operator must reach correct use without formal training | STK-01 `[proxy]` | Primary | Should | Low tech proficiency; high staff turnover in small shops |
| **STK-112** | The system must position the operator as the authority and itself as an aid | STK-11 `[proxy]` | Negative | Should | Direct mitigation for the only opposed stakeholder |
| **STK-113** | The deliverable must evidence novelty, feasibility, impact and UX against the published scoring criteria | STK-07, STK-08 | Governance | **Must** | The gate. A brilliant unpresented system scores zero |
| **STK-114** | Design files ingested must never be modified or become the only copy | STK-03 `[proxy]` | Operational | Should | Design data is owned upstream; corrupting it is unrecoverable |
| **STK-115** | Stored inspection data must not grow without bound on a shop laptop | STK-14 (non-human) | Operational | Should | Disk exhaustion is a silent, total failure mode |
| **STK-116** | Capture conditions must be repeatable frame-to-frame | STK-13 (non-human) | Operational | **Must** | Auto-exposure/autofocus break differencing. A silent accuracy killer |

**MoSCoW honesty check:** 9 Must of 16 = **56%**, just inside the 60% ceiling. Each Must was tested with *"if we shipped without this, would an MSME still deploy it?"* — STK-108, R09, R11, R12, R14, R15 all survived as Should because a first deployment is viable, if imperfect, without them.

---

## 6. Conflicts

### CONFLICT C-01 — Recall vs false calls
```
Between:      STK-02 (QA: catch every defect — recall)
              STK-01/STK-11 (Operator: don't cry wolf — precision)
Nature:       Quality assurance vs operator trust. The classic AOI tradeoff,
              and the reason most AOI deployments underperform in practice.
Options:      (a) Maximise recall, accept false calls — QA happy, operator
                  stops trusting it within a week, station gets bypassed
              (b) Maximise precision, accept escapes — operator trusts it,
                  QA's core problem unsolved
              (c) Target recall ≥90% with false calls ≤5%, plus a one-click
                  operator override that records the correction
Decision:     (c)
Rationale:    Trust is the binding constraint, not accuracy. A system with
              95% recall that operators bypass delivers 0% recall in
              practice. Making the cost of a false call very low (one click)
              buys tolerance for a higher false-call rate than the raw
              number suggests, and each override becomes training data.
Decided by:   Team, 2026-08-14
Affects:      STK-107, STK-108, NFR (accuracy), FR (override)
```

### CONFLICT C-02 — Jury novelty vs buyer simplicity
```
Between:      STK-08 (SIH jury: novelty is a scored criterion)
              STK-04/STK-01 (MSME: low capital cost, short setup time, high reliability)
Nature:       What impresses an evaluator vs what a user will buy and run.
Options:      (a) Maximise technical sophistication for the jury
              (b) Maximise simplicity for the user
              (c) Locate novelty in the *mechanic*, not the *stack*:
                  CAD-referenced registration is simultaneously the novel
                  thing and the least complex thing
Decision:     (c)
Rationale:    Evidence from SIH 2023-25 winners: a jute ribboning machine and
              a cotton picker won the hardware track; timetable generation and
              curriculum management won software. Juries reward deployability
              over sophistication, and novelty is 1 of 9 criteria. Option (c)
              needs no tradeoff — using the design file as the reference is
              both genuinely uncommon and architecturally simpler than
              training a defect classifier.
Decided by:   Team, 2026-08-14
Affects:      STK-103, STK-113, ADR-001 (architecture style)
```

### CONFLICT C-03 — Scope vs the two-week deadline
```
Between:      STK-10 (Team: 2 weeks, 6 people, CON-03)
              STK-01..06 (Users: full defect coverage)
              STK-07 (VITISH jury: a complete-looking system)
Nature:       Ambition vs runway.
Options:      (a) Full scope, likely nothing works on demo day
              (b) Golden-board differencing only — works, but discards the
                  differentiator and looks like the other 40 PCB projects
              (c) Two-path MVP: classical golden-board diff as the
                  never-fails baseline, plus CAD registration as the
                  headline mechanic, with ML explicitly out of MVP
Decision:     (c)
Rationale:    (c) guarantees a working demo (path A) while still showing the
                  differentiator (path B). Also directly mitigates RSK-01,
                  since the two paths have different data prerequisites.
Decided by:   Team, 2026-08-14
Affects:      Scope §3, RSK-01, MVP cut line, ADR-002
```

### CONFLICT C-04 — Speed target vs CPU-only compute
```
Between:      STK-104 (inspection must not bottleneck the line, <10 s)
              CON-05 (laptop CPU + Raspberry Pi; no CUDA, no TensorRT)
Nature:       Performance requirement vs available hardware.
Options:      (a) Heavy CNN per component — misses the target on CPU
              (b) Classical CV on the hot path (homography + ROI diff +
                  cheap features), ML reserved for off-critical-path work
              (c) Drop the speed target
Decision:     (b)
Rationale:    Per-component classification over a few hundred small ROIs is
              well within CPU budget using classical features. Deep models
              are not required to hit the in-scope defect classes and would
              consume the entire runway. Recorded in ADR-003.
Decided by:   Team, 2026-08-14
Affects:      STK-104, C-01, ADR-003, NFR (latency)
```

### Unresolved — logged as open questions
| ID | Conflict | Deadline | Default if unresolved |
|---|---|---|---|
| OQ-06 | STK-11 (operator autonomy) vs STK-02 (supervisor wants override *audited*) — does an override need a reason code? | Day 6 | Log override silently with operator ID; no reason code (favours speed / STK-104) |
| OQ-07 | STK-14 retention vs STK-06 audit — how long must board images be kept? | Day 8 | Failed-board images 90 days, passed-board thumbnails only |

---

## 7. Exit criteria — Phase 2

- [x] All six categories swept, including operational, negative, and non-human
- [x] Register complete with influence, interest, attitude, access
- [x] Power/interest map produced; engagement approach set per quadrant
- [x] Personas for top 3 primary groups — **all labelled `[PROVISIONAL]`**
- [x] Stakeholder requirements written solution-free, with source and priority
- [x] MoSCoW honesty check passed (56% Must, under the 60% ceiling)
- [x] Conflicts logged with decision, rationale and decider; 2 deferred as OQ with defaults
- [x] **Unreachable stakeholder classes flagged as proxy-sourced** — 6 of 14, covering every end user
