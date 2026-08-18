# ADR-001 — Modular monolith with pipe-and-filter inspection pipeline

**Status:** Accepted | **Date:** 2026-08-14 | **Deciders:** Dev team (STK-10)
**Drivers:** D1 (NFR-001 latency), D2 (CON-01 no egress), D3 (NFR-013 modifiability), D5 (CON-03 runway)

## Context
One inspection station, one operator, one board at a time. No driver requires independent deployability or independent scaling. The team is 5 CSE + 1 ECE with a two-week runway and no distributed-systems or CV specialisation. The inspection path itself is a fixed acyclic sequence of transformations with no dynamic step selection.

## Options considered

**1. Microservices — capture, registration, classification as separate deployables**
- Independent scaling and deployment per stage
- Network hops land directly inside the D1 latency budget; operational complexity lands inside the D5 runway. No driver requires either capability. Rejected

**2. Modular monolith with a single monolithic inspection function**
- Simplest possible thing to build
- Thresholds end up embedded in the function that consumes them, breaching D3. Per-stage accuracy measurement becomes impossible, which makes D4 tuning guesswork. Rejected

**3. Modular monolith with the inspection path structured as pipe-and-filter**
- One deployable, one process, one datastore — fits D2 and D5
- Each filter independently testable against recorded inputs, so registration error and classification error can be measured and tuned separately — this is what makes D4 work tractable
- Thresholds injected into filters from configuration, satisfying D3
- Slightly more upfront structure than option 2

## Decision
Option 3. Layers: presentation (UI, API) → orchestration → domain (filters, verdict rules, no framework imports) → infrastructure (OpenCV, SQLite, Gerber parsing).

## Consequences
- D1, D2, D3, D5 all satisfied without distributed-systems burden
- Filter boundaries are drawn so a stage could later move to a separate process if a driver ever demands it
- Requires discipline to keep the domain layer free of framework imports; without that, D3's 5-minute threshold change degrades
- Per-stage timing instrumentation becomes near-free, which directly serves the D1 latency budget

## Revisit if
A second inspection station must share one backend, or component counts rise past ~600 per board and stage-level parallelism becomes necessary.
