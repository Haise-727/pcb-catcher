# Non-Functional Requirements — GerberEye

**Version:** 0.2 | **Phase 5** | **Last updated:** 2026-08-14

13 NFRs. Each carries a metric, a target, a minimum value, the conditions under which the target applies, a measurement method, a rationale, and a source. Targets marked `[ASSUMED]` have a stated basis and a validation trigger rather than a stakeholder-confirmed number — see §5 note.

---

## Reference test bench

Every performance target below is stated against this bench. Without it the numbers are unfalsifiable.

| Parameter | Value |
|---|---|
| Host | x86-64 laptop, 4 physical cores at 2.0 GHz or above, 8 GB RAM, **no discrete GPU** |
| Capture | USB camera, 1920×1080, 30 fps, manual exposure/focus/white-balance control |
| Board under test | Single-sided, **≤ 250 inspected components**, largest dimension ≤ 160 mm |
| Illumination | Fixed diffused ring light; ambient contribution below 20% of total scene luminance |
| State | Registration state = registered (RMS residual ≤ 2.0 px) |

---

## Performance efficiency

### NFR-001 — Inspection cycle latency
- **Category:** Performance efficiency → Time behaviour
- **Statement:** On the reference bench, the interval from inspection trigger to rendered defect list shall be at or below 5.0 s at p95 and at or below 10.0 s at p99.
- **Metric:** Wall-clock trigger-to-render, p95 / p99
- **Target:** p95 ≤ 5.0 s · p99 ≤ 10.0 s
- **Minimum:** p95 ≤ 10.0 s — beyond 10 s the operator's attention is lost and the station becomes the line bottleneck
- **Conditions:** Reference bench; registered state; 250 components
- **Measurement:** Instrumented timer over 200 consecutive inspections; report the histogram, not the mean
- **Rationale:** Anchored to human perception — roughly 1 s preserves flow, roughly 10 s loses attention entirely. Persona Ravi handles 100+ boards per shift, so this cost is paid 100+ times daily
- **Source:** STK-104; perception thresholds
- **Priority:** Must | **Trace:** STK-104, FR-011, FR-012, FR-016, FR-018
- **Architectural impact:** **Rules out per-component deep-network inference on CPU.** This single NFR is the reason for the classical-CV hot path — see ADR-003

**Latency budget (p95 ≤ 5.0 s):**
```
  Frame capture + colour convert          100 ms
  Registration feature detection          300 ms
  Homography solve                         20 ms
  ROI extraction, 250 components          200 ms
  Classification, 250 components        1 500 ms
  Verdict derivation + overlay render     300 ms
  Record persist                          200 ms
  ─────────────────────────────────────────────
  Allocated                             2 620 ms
  Reserve (48%)                         2 380 ms
  Total                                 5 000 ms
```
Reserve is deliberately large — first estimates are optimistic. Revisit after the first bench run.

### NFR-002 — Resource ceiling
- **Category:** Performance efficiency → Resource utilization
- **Statement:** During sustained inspection the application shall consume at or below 2.0 GB resident memory and at or below 80% of 4 CPU cores.
- **Metric:** Peak RSS; mean CPU across a 10-minute run
- **Target:** RSS ≤ 2.0 GB · CPU ≤ 80% of 4 cores
- **Minimum:** RSS ≤ 3.5 GB — above this an 8 GB shop laptop begins swapping and NFR-001 fails
- **Conditions:** Reference bench; continuous inspection for 10 minutes
- **Measurement:** Process sampler at 1 Hz during a 10-minute soak
- **Rationale:** The target host is a shop laptop also running other work, not a dedicated machine
- **Source:** CON-05 | **Priority:** Must | **Trace:** STK-110, CON-05, NFR-001
- **Architectural impact:** Forbids holding all component regions in memory simultaneously for large boards

### NFR-003 — Capture throughput on the Raspberry Pi
- **Category:** Performance efficiency → Capacity
- **Statement:** When the Raspberry Pi operates as capture node, it shall deliver frames at or above 15 fps at 1920×1080.
- **Metric:** Sustained delivered frame rate
- **Target:** ≥ 15 fps · **Minimum:** ≥ 10 fps
- **Conditions:** Raspberry Pi 4 or later; USB camera attached; no inference running on the Pi
- **Measurement:** Frame counter over 5 minutes
- **Rationale:** Below 10 fps the live overlay reads as laggy and the operator loses the sense of direct manipulation
- **Source:** CON-05; OQ-03 | **Priority:** Should | **Trace:** STK-104, CON-05, FR-006
- **Note:** Applies **only** if OQ-03 resolves to Pi-as-capture-node. If the Pi becomes the inference host, NFR-001 must be re-derived against Pi hardware and will almost certainly fail its target.

---

## Functional suitability (accuracy)

### NFR-004 — Defect recall
- **Category:** Functional suitability → Functional correctness
- **Statement:** Across the seeded-defect corpus, the system shall classify at or above 90% of seeded in-scope defects as defective.
- **Metric:** Recall = detected seeded defects / total seeded defects
- **Target:** ≥ 90% · **Minimum:** ≥ 80% — below this the QA case for deploying at all collapses
- **Conditions:** Registered state; in-scope defect classes only (absent, offset, rotated, reversed); corpus of at least 50 seeded instances spanning at least 3 package sizes
- **Measurement:** Seeded-defect test corpus, built per the Phase 1 RSK-01 mitigation — components deliberately removed, rotated, and reversed on real boards, plus digitally injected defects using pick-and-place coordinates
- **Rationale:** The QA supervisor's entire reason for adopting the station is escape reduction
- **Source:** STK-101, STK-102 | **Priority:** Must | **Trace:** STK-101, FR-012, FR-013, FR-014
- **Architectural impact:** Requires a labelled seeded corpus to exist before any accuracy claim is made — this is a **schedule** dependency, not just a test artifact

### NFR-005 — False call rate
- **Category:** Functional suitability → Functional correctness
- **Statement:** On correctly assembled boards, the system shall classify at or below 0.5% of inspected components as defective.
- **Metric:** Per-component false-positive rate on known-good boards
- **Target:** ≤ 0.5% · **Minimum:** ≤ 1.0%
- **Conditions:** Reference bench; registered state; at least 20 known-good boards
- **Measurement:** Inspect known-good boards; every reported defect is by definition a false call
- **Rationale:** **This is the adoption metric, not the quality metric.** At 0.5% a 250-component board yields roughly 1.25 false calls; at 1.0% it yields 2.5. Persona Ravi's stated threshold is *"if it cries wolf twice in a row I'll stop looking at it"* — so the minimum value sits exactly at the point where operator trust begins to fail
- **Source:** STK-108, STK-11 (negative stakeholder) | **Priority:** Must | **Trace:** STK-108, STK-112, FR-020
- **Tradeoff:** Directly opposes NFR-004. Resolution recorded as conflict C-01 — hold recall at target and buy false-call tolerance through the one-interaction override (FR-020), which lowers the *cost* of a false call rather than only its rate

### NFR-006 — Registration accuracy
- **Category:** Functional suitability → Functional correctness
- **Statement:** In the registered state, the transform mapping design coordinates to pixels shall exhibit an RMS residual at or below 2.0 px.
- **Metric:** RMS reprojection error across registration features
- **Target:** ≤ 2.0 px · **Minimum:** ≤ 5.0 px, reported as degraded state
- **Conditions:** Reference bench; at least 4 detected point correspondences
- **Measurement:** Reprojection error computed per frame and logged
- **Rationale:** Registration error propagates directly into every region extraction. A 5 px error on an 0402 package is a substantial fraction of the component, which manufactures false calls at the smallest sizes
- **Source:** FR-008 | **Priority:** Must | **Trace:** STK-101, FR-008, FR-009, FR-011, NFR-005
- **Architectural impact:** Residual must be a first-class runtime value surfaced to the operator, not an internal diagnostic

---

## Interaction capability (usability)

### NFR-007 — Learnability
- **Category:** Interaction capability → Learnability
- **Statement:** An operator who has not previously used the system shall complete a correct inspection within 5 minutes of first contact, without written instructions.
- **Metric:** Time from first contact to first correct unaided inspection
- **Target:** ≤ 5 min for 4 of 5 test subjects · **Minimum:** ≤ 15 min for 3 of 5
- **Conditions:** Board type already loaded by a technician; subject has no PCB assembly training
- **Measurement:** Timed trial with 5 subjects drawn from outside the project team
- **Rationale:** Persona Ravi has low tech proficiency and cannot leave the station to read a manual. Small shops also have high staff turnover, so training cost recurs
- **Source:** STK-111 `[proxy]` | **Priority:** Should | **Trace:** STK-111, FR-018, FR-019
- **`[ASSUMED]` basis:** No operator was observed. Validation trigger — run the trial with 5 non-team students as a proxy population before the internal round

### NFR-008 — Verdict legibility without colour
- **Category:** Interaction capability → Inclusivity
- **Statement:** Every pass, fail, and review state shall be distinguishable by a non-colour visual attribute in addition to colour.
- **Metric:** Count of states distinguishable when the interface is rendered in greyscale
- **Target:** 3 of 3 states distinguishable · **Minimum:** 3 of 3 — this is binary, there is no partial credit
- **Conditions:** Interface rendered through a greyscale filter and through a deuteranopia simulation
- **Measurement:** Screenshot inspection under both filters
- **Rationale:** Red-green colour vision deficiency affects roughly 1 in 12 men. An inspection tool whose entire output is a red or green marker is unusable by a substantial fraction of the shop-floor population, and that fraction skews to exactly this workforce
- **Source:** Accessibility baseline | **Priority:** Should | **Trace:** STK-111, STK-101, FR-018, AC-018.4
- **Note:** WCAG 2.2 does not map cleanly onto a desktop machine-vision application, so a full conformance claim is not made. This single requirement captures the part that materially matters here. Retrofitting it later costs more than building it in now.

---

## Reliability

### NFR-009 — Recoverability from unexpected termination
- **Category:** Reliability → Recoverability
- **Statement:** Following unexpected process termination, the system shall lose at most the single in-flight inspection and shall return to operational state within 30 s of relaunch.
- **Metric:** RPO in inspections; RTO in seconds
- **Target:** **RPO = 1 inspection** (the in-flight one) · **RTO ≤ 30 s**
- **Minimum:** RPO = 1 · RTO ≤ 120 s
- **Conditions:** Process killed without signal handling during an active inspection
- **Measurement:** Kill the process at 20 randomly chosen points; verify record count and relaunch time
- **Rationale:** The manual fallback is visual inspection, which is always available — so an outage is genuinely low-cost and does not justify paying for a stronger RPO. But *silently losing completed inspection records* destroys the audit trail that justifies the whole system
- **Source:** STK-106, STK-14 | **Priority:** Must | **Trace:** STK-106, FR-021, AC-021.2
- **Architectural impact:** Each inspection record must be committed durably before the inspection reports complete. Rules out buffering records in memory for batch write

### NFR-010 — Degraded modes per dependency
- **Category:** Reliability → Fault tolerance
- **Statement:** For each external dependency, the system shall enter its defined degraded mode within 2 s of detecting the fault rather than terminating.

| Dependency | Fault | Defined degraded mode | Detection budget |
|---|---|---|---|
| Camera | Disconnected mid-session | Halt inspection, show disconnected state, retain loaded board type, resume on reconnect | ≤ 2 s |
| Camera | Manual capture control unavailable | Continue with automatic settings; mark every inspection in the session degraded-confidence | At session start |
| Local storage | Write fails | Retain record in memory, show storage warning, retry; do not report the inspection complete | ≤ 2 s |
| Design files | Unparseable | Offer golden-board-only mode; create no partial board type | At ingestion |
| Registration | Features undetectable | Report failed state; offer manual 4-point fallback; emit no component verdicts | ≤ 1 frame |

- **Target:** 5 of 5 dependencies have an implemented degraded mode · **Minimum:** 5 of 5
- **Measurement:** Fault injection per row
- **Rationale:** A system with no specified degraded mode fails completely when any dependency fails. The dependency list is short **because** CON-01 eliminated every network dependency — that constraint bought reliability, and the pitch should say so
- **Source:** STK-13, STK-14 | **Priority:** Must | **Trace:** STK-116, STK-104, FR-006, FR-009, FR-015, UC-01

---

## Security

### NFR-011 — Design file confidentiality
- **Category:** Security → Confidentiality
- **Statement:** The system shall not transmit design files, board images, or inspection records off the host machine by any mechanism.
- **Metric:** Count of outbound network connections observed during a full workflow
- **Target:** 0 · **Minimum:** 0
- **Conditions:** Full workflow — ingest, inspect, override, export — with packet capture active
- **Measurement:** Packet capture on all interfaces; repeat with every interface disabled to confirm the workflow still completes
- **Rationale:** **Data classification: an MSME's design files are its customer's confidential intellectual property.** A contract assembler leaking a customer's Gerbers is a commercial and legal event, not merely a privacy one. This reframes CON-01 from a cost decision into a security property — and it is a materially stronger pitch than "it works offline"
- **Source:** CON-01; data classification | **Priority:** Must | **Trace:** STK-105, STK-114, CON-01, FR-025, FR-026

### NFR-012 — Inspection record integrity and non-repudiation
- **Category:** Security → Integrity, Non-repudiation
- **Statement:** No operation exposed by the application shall modify a persisted inspection verdict, and every override shall record the identity that performed it.
- **Metric:** Count of exposed operations that mutate a persisted verdict; proportion of overrides carrying an operator identity
- **Target:** 0 mutating operations · 100% of overrides attributed
- **Minimum:** 0 · 100% — an audit trail with gaps has no audit value
- **Conditions:** Full application surface, including export and retention paths
- **Measurement:** Code review against the persistence layer plus a test asserting that every write path is append-only
- **Rationale:** STK-06's audit expectation is the reason inspection records exist. A mutable record satisfies nobody
- **Source:** STK-106, STK-102 | **Priority:** Must | **Trace:** STK-106, STK-102, FR-020, FR-021, AC-021.3, AC-020.2

### STRIDE pass — trust boundaries

Only two boundaries exist, both narrow, because there is no network and no multi-user model.

| Boundary | Threat | Assessment |
|---|---|---|
| Design archive → application | **T**ampering — a malformed archive triggers unsafe parsing | Real. Parsers process untrusted third-party files. Mitigate by treating parse failure as expected control flow (FR-001 E1), never by trusting file contents |
| Design archive → application | **I**nformation disclosure — customer IP leaves the host | Real, and the highest-value asset here. Addressed by NFR-011 |
| Operator → application | **R**epudiation — operator denies overriding a verdict | Real. Partially addressed by NFR-012; **fully unaddressed while identity is self-declared** (OQ-09). Accepted risk for MVP, recorded as RSK-04 |
| Operator → application | **S**poofing — one operator acts as another | Present but accepted; single shared station, self-declared identity (OQ-09) |
| — | **D**enial of service | Not applicable — single-user local application, no exposed service |
| — | **E**levation of privilege | Not applicable — no privilege model in MVP |

---

## Maintainability

### NFR-013 — Threshold modifiability without rebuild
- **Category:** Maintainability → Modifiability
- **Statement:** A change to any classification threshold shall take effect without recompiling, reinstalling, or modifying source code.
- **Metric:** Time and artifact count for a defined change scenario
- **Target:** ≤ 5 min · exactly 1 configuration file edited · 0 source files changed · 0 rebuilds
- **Minimum:** ≤ 15 min · ≤ 2 files
- **Conditions:** Change scenario — *"Adjust the offset threshold (BR-04) from 25% to 20% of the smaller package dimension, and confirm the new value is applied on the next inspection."*
- **Measurement:** Timed walkthrough by a team member who did not write the classification module
- **Rationale:** BR-03, BR-04, BR-05 and BR-07 are all **High volatility** — these thresholds will be tuned repeatedly during bench testing, then again per board type, then again on any lighting change. Under a two-week runway, a threshold change requiring a rebuild will be made dozens of times and will dominate the iteration loop
- **Source:** Business rule volatility analysis, Phase 4 | **Priority:** Must | **Trace:** STK-108, BR-03, BR-04, BR-05, BR-07, FR-013
- **Architectural impact:** **This is the most architecturally decisive NFR after NFR-001.** Thresholds must live in a per-board-type configuration record, not in code — recorded as ADR-004

---

## ISO 25010 sweep — explicit coverage

Categories deliberately marked not applicable, so the omission is a decision rather than an oversight.

| Characteristic | Sub-characteristic | Covered by | Status |
|---|---|---|---|
| Functional suitability | Completeness, Correctness | NFR-004, 005, 006 | Covered |
| | Appropriateness | FR catalog | Covered |
| Performance efficiency | Time behaviour | NFR-001 | Covered |
| | Resource utilization | NFR-002 | Covered |
| | Capacity | NFR-003 | Covered |
| Compatibility | Co-existence | NFR-002 (shared laptop) | Partial |
| | Interoperability | Deferred — IPC-CFX post-MVP | **Deferred** |
| Interaction capability | Learnability | NFR-007 | Covered |
| | Operability | FR-017, FR-018, FR-020 | Covered |
| | User error protection | FR-020 (override), AC-017.2 | Covered |
| | Inclusivity | NFR-008 | Covered |
| | User assistance | — | **Not applicable** — MVP interaction is a single trigger and a glance; a help system would exceed the interface it documents |
| | Engagement | — | **Not applicable** — an industrial inspection station is not an engagement-optimised product |
| Reliability | Faultlessness, Fault tolerance | NFR-010 | Covered |
| | Availability | — | **Not applicable as a percentage.** Single-user local application with an always-available manual fallback. An availability target would be theatre; NFR-009 RTO carries the real requirement |
| | Recoverability | NFR-009 | Covered |
| Security | Confidentiality | NFR-011 | Covered |
| | Integrity, Non-repudiation | NFR-012 | Covered |
| | Accountability, Authenticity | OQ-09 | **Accepted gap** — RSK-04 |
| | Resistance | STRIDE pass | Partial |
| Maintainability | Modifiability | NFR-013 | Covered |
| | Testability | NFR-004 measurement (seeded corpus) | Partial |
| | Modularity, Reusability, Analysability | — | **Deferred** — a 2-week single-deliverable codebase; premature to specify |
| Flexibility | Installability | — | **Gap** — logged as OQ-12 |
| | Adaptability, Replaceability | — | **Not applicable** at MVP |
| | Scalability | — | **Not applicable.** One station, one operator, one board at a time. Designing for scale here would buy complexity paid for daily and benefit never realised |
| Safety | All | — | **Not applicable.** The system observes and advises; it actuates nothing. A wrong verdict is caught by the operator (FR-020) or by downstream functional test. No hazard path exists |

### New open question
| ID | Question | Owner | Deadline | Default if unresolved |
|---|---|---|---|---|
| OQ-12 | How is the application installed on a shop laptop, and how long does that take? | Team lead | Day 9 | Single offline bundle, target ≤ 15 min; not demonstrated at the internal round |

---

## Tradeoffs

| ID | Tension | Resolution | Recorded in |
|---|---|---|---|
| T-01 | **NFR-004 recall ↔ NFR-005 false calls** | Hold recall at 90%; buy false-call tolerance by making a false call cost one interaction (FR-020) rather than by lowering sensitivity. Resolve per defect class, not globally — absent-component detection can run at higher sensitivity than rotation detection because its failure mode is more visible to the operator | C-01, ADR-005 |
| T-02 | **NFR-001 latency ↔ NFR-004 accuracy** | Classical CV on the hot path; no per-component deep inference. Accuracy that cannot be delivered inside the latency budget is not deliverable at all | C-04, ADR-003 |
| T-03 | **NFR-013 modifiability ↔ NFR-001 latency** | Configuration indirection costs cycles. Resolved by loading thresholds once per board-type load, not per component — indirection cost is paid once per session, not 250 times per board | ADR-004 |
| T-04 | **NFR-011 confidentiality ↔ future interoperability** | Zero egress in MVP. IPC-CFX (deferred) is opt-in per site and must never become a default, because the default determines whether customer IP leaves the building | Deferred scope |
| T-05 | **Time-to-market ↔ everything** | CON-03 dominates. Every Should-priority NFR is a legitimate casualty if the two-week runway compresses. NFR-003, NFR-007, NFR-008 are the cut candidates, in that order | C-03 |

---

## Top 5 architectural drivers → Phase 7

Ranked by architectural significance — would relaxing this change the architecture?

| Rank | Driver | Why it drives architecture |
|---|---|---|
| **1** | **NFR-001** — p95 ≤ 5 s on CPU-only hardware | Eliminates per-component deep inference outright. Determines the entire processing pipeline shape |
| **2** | **CON-01 / NFR-011** — zero network egress | Eliminates every cloud service, hosted model API, and licence check. Collapses the dependency graph to camera plus local storage, which in turn makes NFR-010 tractable |
| **3** | **NFR-013** — thresholds changeable without rebuild | Forces configuration out of code and into per-board-type records. Shapes the data model |
| **4** | **NFR-005** — false calls ≤ 0.5% per component | Forces the override path (FR-020) into the core interaction loop rather than treating it as an edge case, and forces confidence to be a first-class value |
| **5** | **CON-03** — two-week runway | Forces the two-path architecture (classical baseline plus CAD registration) so that a working demo exists independent of the differentiating feature landing |

---

## Exit criteria — Phase 5

- [x] Full ISO 25010 taxonomy walked; 8 sub-characteristics explicitly marked not applicable with reasons
- [x] Every NFR carries metric, target, conditions, measurement method, rationale, and a minimum value
- [x] Latency stated at percentiles against a defined reference bench
- [x] Availability addressed — **explicitly rejected as a percentage target**, with RTO/RPO carrying the requirement instead
- [x] Degraded mode defined for all 5 external dependencies
- [x] STRIDE pass done per trust boundary; data classified (design files = customer confidential IP)
- [x] Accessibility addressed at the point that matters (NFR-008), with the scope of the claim stated honestly
- [x] Observability captured from non-human stakeholders (FR-027, NFR-010)
- [x] End-to-end latency decomposed into a per-stage budget with 48% reserve
- [x] 5 tradeoffs identified with per-class resolutions
- [x] Top 5 architectural drivers identified for Phase 7
- [x] `check_requirements.py` clean
