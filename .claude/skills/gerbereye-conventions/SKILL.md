---
name: gerbereye-conventions
description: Coding conventions, project structure, licensing policy, and cross-cutting patterns for GerberEye (Python 3.11 + FastAPI + OpenCV + SQLite + React). Use for any code written in this repository — especially before adding a dependency (strict no-AGPL/GPL rule), binding a network socket (loopback only, this is a security boundary), writing a persistence call (append-only), or handling a parse/registration failure (expected control flow, not exceptions).
---

# GerberEye Conventions

*Derived from: architecture.md §6–§7, ADR-001, ADR-006, nonfunctional-requirements.md NFR-011/012/013.*

## Three rules that are load-bearing — breaking any one breaks a core claim

### 1. Loopback only. Never `0.0.0.0`.
The HTTP server binds to `127.0.0.1` and nothing else. An MSME's design files are **its customer's confidential IP**. Binding to all interfaces exposes them to the factory LAN and breaks NFR-011, which is the strongest security claim this project makes. Assert this in a test — do not leave it to review.

### 2. No AGPL or GPL in shipped dependencies.
Permitted: MIT, Apache-2.0, BSD, public domain. **Ultralytics YOLO is AGPL-3.0 — do not add it.** apertus/pcb-aoi is GPL-3.0: read it, never vendor it. If a desktop shell is ever needed use PySide6 (LGPL), not PyQt6. Check the licence before adding any dependency. See ADR-006.

### 3. Verdict tables are append-only.
The persistence layer exposes **no update or delete** for `inspection`, `component_verdict`, or `override`. A correction is a new `override` row. Retention deletes *image files* and nulls their path column; it never removes a row. This is what makes the audit trail real rather than policy.

## Stack

| Layer | Use | Licence |
|---|---|---|
| Language | Python 3.11 | PSF |
| Vision | OpenCV (`opencv-python`) | Apache-2.0 |
| Gerber/PnP | `pygerber` (fallback `gerbonara`) | MIT / Apache-2.0 |
| API | FastAPI + Uvicorn | MIT |
| UI | React + Vite; video via `<img src="/stream.mjpg">` | MIT |
| Store | SQLite, WAL mode | Public domain |
| Tests | pytest | MIT |

No GPU. No CUDA. No TensorRT. No cloud client libraries of any kind.

## Layering (ADR-001)

```
presentation   FastAPI routes, MJPEG streaming, React UI
orchestration  InspectionOrchestrator — owns the state machine
domain         pipeline filters, verdict rules — NO framework imports
infrastructure OpenCV capture, SQLite persistence, Gerber parsing
```

The domain layer importing no framework is what delivers the 5-minute threshold change (NFR-013). If you `import fastapi` in a filter, that target is gone.

## Cross-cutting patterns

**Configuration — two tiers.** App config (paths, camera index, port) in TOML at startup. **Classification thresholds per board type in the `thresholds` table**, loaded once per board-type load and cached for the session. Never per-component lookups — that costs 250× the indirection.

**Errors are values, not exceptions.** Every pipeline stage returns a result carrying an output *or* a typed failure. Gerber parse failure and registration failure are **expected control flow** — they are normal operating states, not bugs. Modelling them as exceptions is what makes the app crash on a malformed customer file.

**Idempotency.** `startInspection` is guarded by the orchestrator state machine — a trigger arriving while not `Idle` is discarded. One physical board yields exactly one inspection row.

**Logging.** Structured JSON lines to a size-capped local file. Every inspection must log `registration_residual_px`, per-stage duration, and component count — these three fields are what let you diagnose both latency and accuracy regressions.

**Consistency.** Single-writer, single-process, local SQLite. Strong consistency throughout; no distributed concerns exist because there are no distributed components.
