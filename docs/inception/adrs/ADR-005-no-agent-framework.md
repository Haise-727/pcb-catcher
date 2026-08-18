# ADR-005 — No agent framework or LLM in the inspection path

**Status:** Accepted | **Date:** 2026-08-14 | **Deciders:** Dev team (STK-10)
**Drivers:** D1 (NFR-001), D2 (CON-01 / NFR-011), D5 (CON-03), CON-02

## Context
Multi-agent orchestration frameworks (LangGraph and similar) were considered for the core inspection pipeline. Comparable projects exist that take this approach. The decision is recorded because it is the question a reviewer is most likely to ask, and because the answer is the opposite of what one might expect if the prior is that more sophistication scores better.

## Options considered

**1. Agent framework orchestrating the inspection pipeline**
- Dynamic control flow, tool selection, LLM-driven reasoning between stages
- **The inspection path is a fixed acyclic DAG.** Every frame takes the identical route — no branching plan, no tool selection, no open-ended reasoning. Agent frameworks buy dynamic control flow where there is none to buy
- **Latency is disqualifying.** An LLM call is 300 ms–2 s; a small local model on constrained hardware is slower. The D1 budget allows ~6 ms per component. This is two-to-three orders of magnitude off, not a tuning gap
- **Breaches D2 outright.** Hosted model APIs require network egress, which would put customer design files — classified as confidential third-party IP under NFR-011 — outside the host. It would also introduce per-inspection cost against CON-02
- Adds state management, checkpointing, and retry semantics as debugging surface inside the D5 runway
- Rejected

**2. LLM assistance outside the inspection path**
- Messy BOM/pick-and-place column normalisation at ingest; defect-to-rework guidance; shift-end root-cause summaries; natural-language query over history
- These are genuinely LLM-shaped and sit off the critical path
- Still breaches D2 if hosted. Would require a local model, which CON-05 hardware does not comfortably support
- **Deferred**, not rejected on merit

**3. No LLM anywhere in MVP**
- Fully satisfies D1, D2, D5, CON-02

## Decision
Option 3 for MVP. Option 2 is deferred behind the same opt-in boundary as IPC-CFX, and if implemented must run locally so NFR-011 holds.

## Consequences
- The zero-egress claim (NFR-011) stays absolute, with no carve-outs to explain
- No per-inspection running cost — material to STK-04, who will not accept a subscription
- Forgoes the ingestion-robustness benefit of LLM-based file normalisation; mitigated by the explicit column-mapping fallback (FR-001 A2)
- Requires a prepared answer when asked "why not agentic AI?" — the answer is D1 and D2, and it is stronger than the alternative

## Revisit if
A local model runs within the D1 budget on target hardware, **and** it stays inside the host boundary. Note that even then it belongs in option 2's off-critical-path role, never in the frame loop.
