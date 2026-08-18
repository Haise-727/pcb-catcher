---
name: gerbereye-adr
description: Write Architecture Decision Records for GerberEye in the established format, and check the existing six-decision log before proposing anything that might conflict with a prior decision. Use whenever an architecturally significant choice is being made, when someone asks "why did we build it this way", or when tempted to add a GPU dependency, an agent framework, a cloud call, or an AGPL library — all four are already-settled decisions.
---

# GerberEye ADRs

*Derived from: architecture.md §10, adrs/ADR-001..006.*

## Check the log first

Before proposing an architecturally significant change, read the existing decisions. This is what prevents the same debate happening twice with different outcomes.

| ID | Decision | Settles |
|---|---|---|
| [ADR-001](../../docs/inception/adrs/ADR-001-modular-monolith.md) | Modular monolith + pipe-and-filter pipeline | Why not microservices; why stages are separable |
| [ADR-002](../../docs/inception/adrs/ADR-002-two-path-inspection.md) | Two-path: golden differencing + CAD registration | Why both paths exist; build order |
| [ADR-003](../../docs/inception/adrs/ADR-003-classical-cv-hot-path.md) | Classical CV on the hot path, no per-component deep inference | Why no CNN, no YOLO; why no labelled dataset is needed |
| [ADR-004](../../docs/inception/adrs/ADR-004-per-board-type-thresholds.md) | Thresholds as per-board-type configuration | Why BR-03/04/05/07 are not constants |
| [ADR-005](../../docs/inception/adrs/ADR-005-no-agent-framework.md) | No agent framework or LLM in the inspection path | Why not LangGraph; latency and egress reasoning |
| [ADR-006](../../docs/inception/adrs/ADR-006-permissive-licensing.md) | Permissive licensing only | Why not Ultralytics (AGPL-3.0) |

**Four recurring proposals are already decided:** adding a GPU/CUDA dependency (ADR-003 + CON-05), adding an agent framework (ADR-005), adding a cloud or hosted model call (ADR-005 + NFR-011), adding an AGPL library (ADR-006). Reopening any of them requires meeting the stated *Revisit if* condition, not just a preference.

## Format

```markdown
# ADR-00N — <decision in a sentence>

**Status:** Proposed | Accepted | Superseded by ADR-00M
**Date:** YYYY-MM-DD | **Deciders:** <who>
**Drivers:** D1..D5 or specific NFR/CON ids

## Context
What forces this decision now. State the constraints and the numbers.

## Options considered
**1. <option>** — pros, then the specific reason it was rejected.
**2. <option>** — ...

## Decision
The chosen option, stated plainly.

## Consequences
Both directions. What this buys, and what it costs.

## Revisit if
The concrete condition that reopens this. Not "if requirements change".
```

## Rules

- Write one when a choice was **genuinely contested**, **expensive to reverse**, or would make a future contributor ask "why?".
- Do not write one for a configuration value — that is noise, not decision history.
- **A short ADR beats no ADR.** Context, decision, consequences captured now beats an exhaustive one written from memory next month, if it is written at all.
- Record rejected options with the *specific* reason, not "not a good fit". The rejection reasoning is the part future readers need.
- If a decision was partly made for learning value rather than pure technical merit, **say so in the ADR**. Laundering a preference as a technical justification is what makes a decision log untrustworthy.
- The *Revisit if* clause must be a condition someone could actually observe — "false-call rate exceeds 1.0% after illumination is stabilised", not "if things change".
