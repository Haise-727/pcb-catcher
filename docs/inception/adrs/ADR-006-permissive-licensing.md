# ADR-006 — Permissive licensing only; AGPL and GPL excluded from shipped code

**Status:** Accepted | **Date:** 2026-08-14 | **Deciders:** Dev team (STK-10)
**Drivers:** CON-08, STK-04 (buyer), STK-08 (industry jury)

## Context
The product's premise is that an MSME deploys it commercially. The default computer-vision stack in comparable projects is Ultralytics YOLO, which is **AGPL-3.0** — a deploying business inherits a copyleft obligation over its own stack. The most closely related open-source AOI project (apertus/pcb-aoi) is GPL-3.0, so it can be learned from but not vendored.

This is a soft constraint by the Phase 1 test: violating it still yields a working demo. It costs credibility only under a specific question — which an industry juror is well placed to ask.

## Options considered

**1. Use whatever is quickest to adopt, address licensing if asked**
- Fastest
- The "MSMEs can deploy this" claim becomes false, and the failure surfaces in front of the people best equipped to notice. Rejected

**2. Permissive-only for shipped code; GPL/AGPL projects read but never vendored**
- Every dependency MIT / Apache-2.0 / public domain
- Rules out Ultralytics, which ADR-003 already removes the need for
- Constrains library choice slightly

## Decision
Option 2. Shipped dependencies restricted to MIT, Apache-2.0, BSD, or public domain. GPL/AGPL projects may inform the design; their code is not vendored.

## Consequences
- CON-08 satisfied with no exceptions across the entire stack
- Converts a compliance detail into a pitch differentiator: *"we chose Apache-licensed components so an MSME can deploy without legal exposure"* — a question most teams shrug at
- PySide6 (LGPL) rather than PyQt6 if a desktop shell is later added
- Requires a licence check before adding any dependency

## Revisit if
The project is released purely as a research artifact with no deployment claim, at which point the constraint is moot.
