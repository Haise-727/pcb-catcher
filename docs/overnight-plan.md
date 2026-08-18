# Overnight Implementation Plan

**Written:** 2026-08-18, before starting autonomous work
**Constraint:** no hardware, no human available, commit locally only (no pushes)

## Goal

Something demo-ready by morning. The hardware chain (#2 → #3 → #4) cannot move
while everyone is asleep, and the camera cannot currently hold a fixed exposure
(#35), so **the demo must not depend on a camera at all**.

---

## Phase 1 — Demo mode (top priority)

A `DemoCamera` that satisfies the same interface as the real one but serves
bundled sample board images. The entire pipeline — capture, differencing,
registration, naming, verdict, override, export — runs unchanged behind it.

Deliverables:
- Generated sample boards: one golden, several with seeded defects (missing,
  rotated, offset parts), rendered with ArUco markers so the CAD path works too
- Matching pick-and-place and BOM files, including a DNP designator so the #31
  exclusion is visible in the demo
- `GERBEREYE_DEMO=1` selects the demo source; nothing else changes
- One-command seed script that creates the board type and captures its golden
- UI banner making it unambiguous that demo mode is active

**Why this first:** it is simultaneously the demo, the RSK-07 fallback, and a
test fixture for every later feature. It also unblocks #37, which needs a
seeded-defect corpus that no longer has to wait for physical hardware.

## Phase 2 — Frontend polish

The jury sees the screen, not the architecture. Priorities in order:
1. Verdict presentation — large, unambiguous, readable across a room
2. Inspection history panel with per-board results
3. Defect detail: click a region, see it cropped and magnified
4. Setup flow that guides a first-time user through board type → golden → inspect
5. Keyboard trigger, so the operator never hunts for a button

## Phase 3 — Backend depth

- **#33 structured logging** — per-stage timings and residual; unblocks #38
- **#37 defect classification** — missing vs rotated vs offset, using the Phase 1
  corpus for tuning and validation
- **#36 footprint extents** — real package sizes instead of a 3mm nominal box
- **#34 retention sweep**

---

## Working rules while unattended

- **Commit locally only.** Nothing is pushed. Every issue comment says so
  explicitly, so nobody looks for code that is not on GitHub yet.
- **Checkpoint at every green state.** Full suite must pass (except the six
  known `test_export.py` stubs belonging to #16) before anything is committed.
- **One commit per logical unit**, prefixed `issue #N:` where one applies.
- **Never touch `main`.** Work happens on feature branches, merged into `dev`
  locally at working checkpoints.
- **If something is genuinely blocked, file an issue rather than guessing.**
  Anything requiring a physical board, a real camera, or a human decision gets
  written up and assigned rather than faked.

## What will NOT be attempted

- Anything needing physical hardware (#2, #3, #4, #5, #20, #21, #22, #35)
- #9 threshold tuning against real frames — synthetic tuning would produce
  numbers that fail on the bench, which is worse than leaving it untuned
- #32 marker measurements — requires the physical jig
- Pushing, merging to `main`, or anything else outward-facing
