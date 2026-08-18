# Pipeline Status & Blockages

**Last updated:** 2026-08-18
**Purpose:** what is built, what is blocked on what, and who clears each blocker.

The framework is software-complete. Almost everything still open is blocked on
**physical hardware existing**, not on more code being written. That is the
single most important fact for planning the remaining hours: throwing more
coding effort at the problem right now does not move the critical path.

---

## 1. The dependency chain

```
#2  jig + camera locked        (Yuvaraj, physical)
     │
     ├──> #35 driver refuses manual exposure   [BUG — may block #3]
     │
     v
#3  frame stability < 2 levels  (Yuvaraj, physical)   ◄── THE GATE
     │
     ├────────────────────────────────┐
     v                                v
#4  golden reference           #9  tune diff thresholds   (Haise)
     │                                │
     v                                v
#20 seeded defect corpus  ────────────┤
     │                                │
     ├──> #37 defect-class            │
     │                                v
     v                          #38 latency measurement
#21 backup video                       ▲
#22 fallback path                      │
#23 pitch                        #33 structured logging
```

Separately, and **not** blocked on hardware:

```
#5  ArUco markers taped (Yuvaraj)  ──>  #32 measure real marker positions (Haise)
#16 CSV export (Yuvaraj)           ──>  nothing; fully isolated
#31 DNP exclusion (Haise)          ──>  needs BOM ingestion, no hardware
#34 retention policy (Haise)       ──>  nothing
```

---

## 2. The gate: why #3 blocks so much

`#3` (frame stability below 2 grey levels, AC-006.2) is the gate before any
threshold work. This is not process ceremony.

Golden-board differencing compares two images pixel by pixel. If the camera is
still auto-adjusting, or the light drifts, pixels change for reasons that have
nothing to do with the board. A threshold tuned against those frames encodes
the drift — it will look correct in the session it was tuned in and stop being
correct the moment the light changes.

**Lighting stability moves the false-call rate more than any algorithm change
available to us.** Tuning before the gate passes is not "getting a head start",
it is producing a number that has to be thrown away.

### What #3 currently blocks

| Issue | Why it needs the gate |
|---|---|
| #9 tune diff thresholds | Tuning against unstable frames produces a value that does not survive the session |
| #20 seeded defect corpus | Corpus captured under unstable light cannot validate anything |
| #38 latency measurement | Needs the real capture path, not synthetic frames |

### What could unblock it

`#35` is the known obstacle — the dev laptop's camera driver refuses manual
exposure control. Options in that issue, in order of preference: force manual
mode via `v4l2-ctl`, try a different UVC camera, or control the ambient light
so aggressively that auto-exposure has nothing to react to.

---

## 3. Why #9 cannot be done now

`#9` (tune diff threshold against 5+ known-good frames) is assigned but
deliberately **not started**.

The current thresholds are seed values in `config.ThresholdDefaults`:

```python
diff_intensity  = 40    # grey levels
min_region_area = 120   # px^2
blur_kernel     = 5
```

These were chosen to behave correctly on synthetic test images. They are
starting points, not tuned values.

Tuning them requires real frames of a real board under the real light — which
requires #2, #3 and #4 to be done first. Tuning against synthetic images would
produce numbers that look good in `pytest` and fail on the bench.

**When it unblocks**, tuning is fast: capture 5+ known-good frames, raise
`min_region_area` until none of them produce a region, then verify a seeded
defect still trips it. The values go in the per-board-type `thresholds` table
via `PATCH /api/board-types/thresholds`, never back into code (ADR-004,
NFR-013).

---

## 4. Current status by stream

| Stream | State | Blocked on |
|---|---|---|
| 1 — Capture & golden | Software done, hardware pending | Physical jig (#2) |
| 2 — Differencing (Path A) | **Complete and tested** | Tuning needs #3 |
| 3 — CAD path (Path B) | Software done, needs real measurements | #5 then #32 |
| 4 — Backend / API | **Complete**, except CSV (#16) | — |
| 5 — Operator UI | **Complete** | — |
| 6 — Demo & pitch | Not started | #4, #20 |

---

## 5. Honest read on the critical path

The riskiest remaining item is not any piece of software. It is **#35** — if
the camera cannot be made to hold a fixed exposure, frame stability never
passes, thresholds never get tuned properly, and the false-call rate on the
day becomes unpredictable.

Mitigations already in place if that happens:
- The system reports a **degraded** capture state rather than pretending
  settings are locked, so the failure is visible instead of silent.
- ECC translation alignment absorbs board placement shift, which removes one
  major source of frame-to-frame difference independently of exposure.
- The demo can run on a single board in a controlled light with a fixed
  placement — the `#22` fallback path exists precisely for this.

None of those fix the underlying problem; they contain it.
