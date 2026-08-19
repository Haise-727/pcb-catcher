# Pipeline Status & Blockages

**Last updated:** 2026-08-19 (overnight session)
**Purpose:** what is built, what is blocked on what, and who clears each blocker.

The software is complete and integration-verified. **Everything still open on
the engineering side is blocked on physical hardware existing** — not on more
code being written.

What changed 2026-08-19: the hardware-dependent *behaviour* is now demonstrable
without the hardware. A virtual bench (`gerbereye/bench.py`) simulates the jig,
ring light and sensor, so the frame-stability gate (#3), the degraded-capture
state (#35) and RSK-02's illumination claim can all be shown to a jury. This
does **not** unblock the hardware issues — it removes their cost to the demo.

---

## 1. What now works, end to end

With no camera and no board, from a clean clone:

```bash
.venv/bin/python tools/seed_demo.py
GERBEREYE_DEMO=1 .venv/bin/python run.py
```

gives a running station that will:

- inspect a board and return **PASS/FAIL** in ~100 ms
- name each defect by **reference designator**
- classify it as **absent / rotated / offset**, with the measurement behind it
- exclude **do-not-populate** designators so they are never falsely reported
- show a **magnified crop** of any finding
- accept a **one-click override**, appended not edited
- aggregate **recurring defects** by designator
- **export CSV** (#16), and expire images while keeping every record
- allow **live threshold retuning** with no restart
- switch **bench conditions** and watch a good board fail under bad light

**154 tests pass, none fail.** `tools/check_integration.py` additionally starts
the real server and drives all 29 endpoint interactions the UI performs: 29/29.

---

## 2. The dependency chain

```
#2  jig + camera locked        (Yuvaraj, physical)
     │
     ├──> #35 driver refuses manual exposure   [BUG — may block #3]
     │         └── simulated by bench profile `unlocked`, so the failure
     │             mode is demonstrable while the fix stays open
     v
#3  frame stability < 2 levels  (Yuvaraj, physical)   ◄── THE GATE
     │         └── gate logic verified against the bench; the real
     │             measurement still needs the real camera
     │
     ├────────────────┬───────────────────┐
     v                v                   v
#4  golden ref    #9 tune thresholds   #38 real latency figure
     │
     v
#20 seeded defects ──> #21 backup video ──> #22 fallback ──> #23 pitch

#5  ArUco markers taped (Yuvaraj)  ──>  #32 measure real marker positions
#16 CSV export                     ──>  DONE 2026-08-19
```

Unassigned, available to any teammate: **#41** polarity, **#42** bottom-side
inspection, **#43** offline installer, **#44** IPC-CFX, **#45** vernacular UI.

---

## 3. The gate: why #3 blocks so much

`#3` (frame stability below 2 grey levels, AC-006.2) gates all threshold work.
This is not process ceremony.

Golden-board differencing compares two images pixel by pixel. If the camera is
still auto-adjusting, or the light drifts, pixels change for reasons unrelated
to the board. A threshold tuned against those frames encodes the drift — it
looks correct in the session it was tuned in and stops being correct the moment
the light changes.

**Lighting stability moves the false-call rate more than any algorithm change
available to us.** Tuning before the gate passes produces a number that has to
be thrown away.

`#35` is the known obstacle: the dev laptop's camera driver refuses manual
exposure control. Options in that issue, in preference order — force manual
mode via `v4l2-ctl`, try a different UVC camera, or control ambient light so
aggressively that auto-exposure has nothing to react to.

---

## 4. Measurements taken so far, and what they are not

| Figure | Value | Status |
|---|---|---|
| Inspection latency, p95 | 114 ms | **Demo mode only.** Reads bundled images, so capture time is unrepresentative. Not an NFR-001 result |
| Inspection latency, p99 | 117 ms | as above |
| Classification cost | ~2 ms per flagged component | inside ADR-003's 6 ms budget |
| Footprint coverage | 19/19 on the demo board | real |
| Defect classification | 4/4 seeded classes correct | on synthetic boards |
| Recall (NFR-004) | — | **not measured.** Needs #20 |
| False-call rate (NFR-005) | — | **not measured.** Needs #20 and real boards |
| Simulated stability, `locked` | 0.84 levels | **Simulated.** Verifies the gate passes clean conditions |
| Simulated stability, `harsh` | 7.97 levels | **Simulated.** Verifies the gate catches bad ones |
| Integration checks | 29/29 | real — every endpoint the UI calls |

The accuracy figures are the two that matter for the pitch, and neither exists
yet. `docs/demo-script.md` covers how to answer that honestly: offer live
falsifiability instead of a number that cannot be defended.

---

## 5. Honest read on the critical path

The riskiest remaining item is still **#35**. If the camera cannot hold a fixed
exposure, frame stability never passes, thresholds never tune properly, and the
false-call rate on the day is unpredictable.

What contains it, none of which fixes it:

- The station reports a **degraded** capture state rather than pretending
  settings are locked, so the failure is visible.
- ECC translation alignment absorbs board placement shift, removing one major
  source of frame-to-frame difference independently of exposure.
- **Demo mode** now provides a complete working station with no camera at all,
  which is the RSK-07 contingency made real rather than promised.
- The **virtual bench** turns #35 from a hole in the demo into a talking point:
  the failure mode can be shown deliberately, alongside the guard built for it.

That last point materially changed the risk picture overnight: a hardware
failure on the day no longer costs the demo, only the claim that it runs on
real boards.
