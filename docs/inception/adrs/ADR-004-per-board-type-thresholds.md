# ADR-004 — Classification thresholds as per-board-type configuration

**Status:** Accepted | **Date:** 2026-08-14 | **Deciders:** Dev team (STK-10)
**Drivers:** D3 (NFR-013), D1 (NFR-001)

## Context
Four business rules carry **High** volatility: BR-03 (ROI scale), BR-04 (offset threshold), BR-05 (rotation threshold), BR-07 (confidence floor). These will be tuned repeatedly during bench testing, again per board type, and again on any lighting change. NFR-013 requires a threshold change in ≤ 5 min touching one file with no rebuild.

Under a two-week runway a threshold change will be made dozens of times. If each requires a rebuild, that loop dominates the schedule.

## Options considered

**1. Constants in source**
- Simplest to write
- Every tuning iteration needs a rebuild. Breaches D3 outright and would consume the D5 runway. Rejected

**2. Single global configuration file**
- Satisfies the no-rebuild requirement
- Different board types need different thresholds — an 0402-dense board and a through-hole board cannot share an offset tolerance. Would force a bad global compromise. Rejected

**3. Per-board-type threshold record in the datastore, loaded at board-type load**
- Satisfies D3 fully; tuning is a data edit
- Correct granularity: thresholds are a property of a board type, matching the domain
- Indirection cost paid once per board-type load rather than 250 times per board, so D1 is unaffected
- Config can drift from code defaults; needs a documented default set

## Decision
Option 3. A `thresholds` row per board type, populated with defaults at ingestion, loaded into memory once per board-type load and cached for the session.

## Consequences
- Tuning becomes a data operation, which is what makes the two-week accuracy work feasible at all
- Thresholds ship as part of a board type, so a tuned board type is portable between installations
- A threshold edit applies at next board-type load, not instantly — accepted staleness
- Requires a documented default set and a reset path

## Revisit if
Thresholds need to vary per *component* rather than per board type — at which point the table gains a dimension and the 5-minute target needs re-testing.
