# ID Registry — GerberEye

Append-only. Never reuse or renumber an ID, even if the item is withdrawn.
**Block allocation:** `STK-01..99` = stakeholder roles · `STK-100+` = stakeholder requirements.
*(CR-01, 2026-08-14: requirements were originally `STK-R01..R16`; renumbered into the 100-block because the `R` broke trace matching. Semantics unchanged.)*

## STK — roles (added 2026-08-14)
STK-01 Line Operator · STK-02 QA Supervisor · STK-03 Board-Type Setup Technician · STK-04 MSME Owner
STK-05 Rework Technician · STK-06 OEM Customer · STK-07 VITISH Jury · STK-08 SIH Jury
STK-09 Faculty Mentor · STK-10 Dev Team · STK-11 Displaced Manual Inspector (negative) · STK-12 IPC
STK-13 Capture Subsystem (non-human) · STK-14 Local Datastore (non-human)

## STK — requirements (added 2026-08-14)
STK-101 Determine board matches design · STK-102 Deviations named by designator · STK-103 Inspectable from design files
STK-104 Within cycle-time budget · STK-105 No network, no fee · STK-106 Durable exportable record
STK-107 Overrule in one action · STK-108 False alarms rare · STK-109 Recurring defects visible
STK-110 Cost within operating cash · STK-111 Untrained operator · STK-112 Operator is the authority
STK-113 Deliverable evidences scoring criteria · STK-114 Design files unmodified · STK-115 Storage bounded
STK-116 Capture repeatable

## BR (added 2026-08-14)
BR-01 Designator uniqueness · BR-02 Coordinate convention · BR-03 ROI scale ×1.20 (High volatility)
BR-04 Offset >25% (High) · BR-05 Rotation >15° (High) · BR-06 Board fail rule · BR-07 Confidence floor 0.60 (High)

## FR (added 2026-08-14)
FR-001 Ingest design data · FR-002 Exclude DNP · FR-003 Identify polarity-sensitive · FR-004 Persist board type
FR-005 Capture golden reference · FR-006 Locked capture settings · FR-007 Detect registration features
FR-008 Compute transform · FR-009 Report registration state · FR-010 Manual registration fallback
FR-011 Extract ROIs · FR-012 Classify presence · FR-013 Classify placement · FR-014 Classify polarity
FR-015 Golden differencing · FR-016 Derive board verdict · FR-017 Trigger inspection · FR-018 Render overlay
FR-019 Named defect list · FR-020 One-action override · FR-021 Persist record · FR-022 Export records
FR-023 Aggregate by designator · FR-024 Retention policy · FR-025 Operate offline · FR-026 Protect design files
FR-027 Event logging

## NFR (added 2026-08-14)
NFR-001 Cycle latency · NFR-002 Resource ceiling · NFR-003 Pi capture throughput · NFR-004 Defect recall
NFR-005 False call rate · NFR-006 Registration accuracy · NFR-007 Learnability · NFR-008 Colour-independent legibility
NFR-009 Recoverability · NFR-010 Degraded modes · NFR-011 Design file confidentiality · NFR-012 Record integrity
NFR-013 Threshold modifiability

## UC / US (added 2026-08-14)
UC-01 Inspect a board · UC-02 Define a board type · UC-03 Override a verdict · UC-04 Export records
UC-05 Review defect trends · UC-06 Register board to design
US-001 Show which components are wrong · US-002 Load design files · US-003 Dismiss in one click · US-004 Export last month

## CON (added 2026-08-14)
CON-01 Zero network dependency · CON-02 ≤₹10 000 BOM · CON-03 2-week runway · CON-04 5 CSE + 1 ECE
CON-05 Laptop CPU + Pi, no GPU · CON-06 USB webcam · CON-07 No matched CAD↔board pair · CON-08 No AGPL/GPL
CON-09 6 members incl. ≥1 female · CON-10 IPC-A-610 / IPC-2591 alignment · CON-11 Uncontrolled shop lighting

## ASM (added 2026-08-14)
ASM-01 AOI capex ₹15–50 L · ASM-02 MSMEs hold design files · ASM-03 Jig+light repeatability
ASM-04 Fiducials detectable · ASM-05 English UI acceptable · ASM-06 Single top-down camera sufficient
ASM-07 Open-hardware Gerbers obtainable · ASM-08 Manual inspection 2–5 min

## RSK (added 2026-08-14)
RSK-01 No matched CAD↔board pair · RSK-02 Lighting variance · RSK-03 No fiducials · RSK-04 Self-declared identity
RSK-05 No CV experience · RSK-06 No seeded corpus in time · RSK-07 Demo-day hardware failure · RSK-08 Pi on factory LAN

## IF (added 2026-08-14)
IF-01 Camera · IF-02 Design archive · IF-03 Local store · IF-04 Record export · IF-05 Operator UI (loopback) · IF-06 IPC-CFX (deferred)

## ADR (added 2026-08-14)
ADR-001 Modular monolith + pipe-and-filter · ADR-002 Two-path inspection · ADR-003 Classical CV hot path
ADR-004 Per-board-type thresholds · ADR-005 No agent framework · ADR-006 Permissive licensing

## OQ (added 2026-08-14)
OQ-01 Reference board · OQ-02 Microscope+light budget · OQ-03 Pi role · OQ-04 THT/SMD · OQ-05 Shop access
OQ-06 Override reason code · OQ-07 Retention period · OQ-08 Board type delete · OQ-09 Operator identity
OQ-10 First-run state · OQ-11 Timestamp timezone · OQ-12 Install method

## Defects (Phase 8, added 2026-08-14)
D-01 Accuracy unverifiable until corpus exists (High) · D-02 Thresholds inferred not IPC-sourced (Medium)
D-03 FR-027 weak necessity trace (Low) · D-04 All end-user requirements proxy-sourced (High, unresolved)

## CR — change log
CR-01 2026-08-14 STK-R01..R16 → STK-101..116
