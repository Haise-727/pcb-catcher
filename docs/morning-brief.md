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

**Five issues closed:** #31 DNP exclusion, #33 structured logging, #34
retention, #36 footprint sizing, #37 defect classification, plus #40 defect
trends (created and closed overnight).

**Test suite went 30 → 127 passing.** The six failures are still Yuvaraj's
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

All three are pinned by regression tests.

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

**#44 is the national-round hook** — naming a real IPC standard and having
emitted messages against it is the difference between "student project" and
"could sit on our line". It is explicitly deferred until past the internal gate,
so it is the right thing to start *after* this round, not before.
