# ADR-002 — Two-path inspection: golden differencing plus CAD registration

**Status:** Accepted | **Date:** 2026-08-14 | **Deciders:** Dev team (STK-10)
**Drivers:** D5 (CON-03 runway), RSK-01, RSK-05

## Context
The differentiating mechanic of PS #82 is registering design data onto a camera image of the same board. **The team currently holds physical boards without their design files, and can obtain design files without the matching board** (CON-07, RSK-01). Separately, no team member has prior computer-vision experience (RSK-05), so registration may not be working by the jury gate.

A single-path architecture fails in both scenarios: CAD-only cannot demo without a matched pair, and golden-only discards the differentiator and looks like every other PCB project.

## Options considered

**1. CAD registration only**
- Maximum differentiation
- Undemonstrable until RSK-01 closes; nothing to show if registration slips. Rejected

**2. Golden-board differencing only**
- Works today with boards already held; needs no design files and no CV depth
- Discards the entire differentiator. Setup requires per-board-type manual teaching, which is precisely the adoption barrier STK-03 identifies. Rejected

**3. Both paths, converging on a shared verdict stage**
- Path A (differencing) works with what the team has now and requires no CV depth — it is the demo that cannot fail
- Path B (CAD registration) carries the differentiation
- The two paths have *different data prerequisites*, so RSK-01 and RSK-05 cannot take out both
- Costs a second code path and a precedence rule

## Decision
Option 3. Both paths produce component-or-region verdicts; the `Verdict` stage is agnostic to origin. Precedence: where a component map exists, the CAD path runs and the differencing path does not (FR-015 AC-015.4).

## Consequences
- A working demo exists independent of whether the differentiating feature lands
- Build order is forced: path A first (no CV depth needed), path B second — which also front-loads the parts the team can definitely finish
- Two code paths to maintain and two sets of accuracy characteristics to explain
- Gives an honest fallback narrative: path B can be demonstrated on rendered Gerbers with digitally injected defects even with zero matched physical pairs

## Revisit if
A matched CAD-plus-board pair is secured early and registration proves stable — at which point path A becomes a fallback rather than a co-equal path, though it should not be deleted.
