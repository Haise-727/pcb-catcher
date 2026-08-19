# Morning Brief

**Overnight session, 2026-08-18 → 19.** Everything below is **committed
locally on `dev`, not pushed.** Nothing was sent to GitHub except issue
comments and closures.

---

## First thing: push and check

```bash
cd ~/Coding/Projects/pcb-catcher
git log --oneline main..dev        # review what landed
git push origin dev                # then PR dev -> main as usual
```

Then try it:

```bash
.venv/bin/python tools/seed_demo.py
GERBEREYE_DEMO=1 .venv/bin/python run.py
cd web && npm run dev
```

Open `http://127.0.0.1:5173`, press **space**, and click through the demo board
buttons. The whole flow works with no camera attached.

---

## What got done

**Seven issues closed:** #31 DNP exclusion, #33 structured logging, #34
retention, #36 footprint sizing, #37 defect classification, plus #40 defect
trends and #46 the threshold gap (both created and closed overnight).

**Test suite went 30 → 135 passing.** The six failures are still Yuvaraj's
`test_export.py` stubs (#16), failing by design.

The headline change: **findings now say what is wrong, not just that something
is.** `U1 rotated 90 degrees`, `C2 missing`, `R5 sitting 1.63mm off its pads` —
each with the measurement behind it.

**Demo mode** is the other big one. `GERBEREYE_DEMO=1` runs the entire pipeline
against bundled board images. Same code path, only the pixel source differs. It
is simultaneously the demo, the RSK-07 fallback, and the test corpus.

Also added: recurring-defect trends, live threshold tuning, storage management,
magnified defect crops, inspection history, and keyboard control (space to
inspect, D to cycle demo boards).

---

## Read this before presenting

**`docs/demo-script.md`** — the 90-second walkthrough, what to say in what
order, and honest answers to the two questions you should expect: *"is that a
real board?"* and *"what's your accuracy?"*

Short version of the second answer: **do not quote a number.** Recall and
false-call rate are unmeasured, because that needs the seeded corpus (#20) and
real boards. Offer live falsifiability instead — *"hand us a board, pull a
component, we'll re-run it in front of you."* An industry juror will respect
that far more than a figure that cannot be defended.

---

## The most important finding: a silent recall gap

Worth reading even if you skip everything else.

I benchmarked against a **221-component 0603 board**, because NFR-001 specifies
250 components and the demo board only has 20. **Two of five seeded defects were
missed — and both were `missing`, the class that should be easiest.**

A removed 0603 changes about 100 px² of contour area. The default noise floor is
120 px², perfectly sensible for the 0805 parts on the demo board. So the region
was discarded as noise and **the board reported PASS**.

That is the dangerous direction of failure. A false call is visible and
annoying; this is an escape, and it would never have shown up in testing on a
coarse board — it only appears as component size drops, which is exactly where
real boards go.

The station now computes the smallest component's expected change from its
footprint and warns when the threshold would hide it, with a recommended value.
Thresholds stay operator-controlled (ADR-004) rather than silently auto-tuning.

**This is worth mentioning at the jury table.** Finding a silent recall failure
in your own system, and building the guard that surfaces it, reads considerably
better than a system that has never been stress-tested.

## Three things I got wrong and had to fix

Worth knowing, because each was a confident-looking wrong answer:

1. **DNP column polarity.** Under a column headed `DNP`, the value `no` means
   the part *is* fitted. I had it inverted, which would have silently excluded
   every component on the board — the inspection would have reported `PASS`
   while checking nothing.

2. **Otsu-based classification.** My first classifier segmented each region
   independently. On an 0603 the pads occupy more than half the footprint, so
   "the component is the minority region" selects the *board*; and a region
   whose component was removed is nearly uniform, so Otsu partitions noise. A
   missing resistor classified as *present*. Rewritten around template
   matching, which never has to decide which pixels are the component.

3. **Connector pin-count parsing.** `Molex_53398-0571` parsed to 53398 pins →
   a 135-metre bounding box that would have swallowed the board and captured
   every defect. Now bounded.

4. **Neighbour confusion on dense boards.** On a tight 0603 layout every part
   looks identical, so a template happily matched a *neighbour* — making missing
   parts report as `rotated` or `offset`, sending a technician to reposition
   something that is not there. Fixed with a match-quality gate, which separates
   the cases cleanly: a genuine offset scores 0.98–1.00 because it is the same
   part, while a lookalike neighbour scores 0.41–0.62.

All four are pinned by regression tests.

---

## What is blocked on you and Yuvaraj

Nothing on the software side moves until hardware exists:

- **#35** is the critical-path risk — the camera driver refuses manual exposure
  lock. If that cannot be solved, frame stability (#3) never passes and
  thresholds (#9) cannot be tuned properly.
- **#3** gates #9, #20 and the real #38 latency figure.
- **#32** needs the physical jig measured before the CAD path is trustworthy on
  a real board.

My three remaining issues (#9, #32, #38) are all in that blocked set.

---

## Available for teammates

Five unassigned issues, each self-contained and written up with context so
someone can pick one up cold:

| # | Title | Size |
|---|---|---|
| 41 | Polarity verification for polarised components | M |
| 42 | Bottom-side board inspection | M |
| 43 | Single offline installer | M |
| 44 | IPC-CFX events for MES integration | L |
| 45 | Vernacular operator UI (Hindi / Tamil) | S |
| 47 | Offset fragments reported as a second unmatched region | S |

**#44 is the national-round hook** — naming a real IPC standard and having
emitted messages against it is the difference between "student project" and
"could sit on our line". It is explicitly deferred until past the internal gate,
so it is the right thing to start *after* this round, not before.
