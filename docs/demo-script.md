# Demo Script

**For the internal round. Target: 90 seconds of screen time.**

The build is only half the score. This is the other half.

---

## Before you start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web && npm install && npm run build && cd ..   # build the UI once
.venv/bin/python tools/seed_demo.py               # generates boards, seeds the station
.venv/bin/python tools/check_integration.py       # confirm every button works
GERBEREYE_DEMO=1 .venv/bin/python run.py          # one process, UI included
```

Open `http://127.0.0.1:8000`. The board type, golden reference, component map
and BOM are already loaded — no setup clicking in front of a jury.

Building the UI means **one terminal, not two**, on demo day. Run
`check_integration.py` last: it drives every endpoint the UI calls and tells you
in five seconds whether anything on screen will 500.

**Rehearse this twice against a clock before presenting.**

---

## The 90 seconds

### 1. Frame the problem (15s) — before touching the screen

> "An MSME assembling this board inspects it by eye, against a printed
> drawing, cross-referencing two hundred component labels. A machine that does
> this automatically costs fifteen to fifty lakh. This does it for under ten
> thousand rupees."

Do not open with the technology. The jury is ministry and industry, not
academics — they are scoring whether their department could deploy it.

### 2. A good board (10s)

Select **golden**. Press **space**.

> "Correct board. Passes. Nothing flagged."

Let the `PASS` sit on screen for a beat. It establishes the baseline, and it
proves the system is not simply flagging everything.

### 3. The moment that matters (25s)

Select **defect_mixed**. Press **space**.

> "Same board, three faults. It found all three, and it named them."

Read the findings off the screen, out loud — this is the line that lands:

> "Not 'something is wrong here'. **U1 rotated ninety degrees. C2 missing. R5
> sitting one point six millimetres off its pads.** That is what a rework
> technician needs to know."

Click a finding to expand its magnified crop. Point at the outlined region.

### 4. Where the accuracy comes from (15s)

> "There is no trained model here, and no labelled dataset — which matters,
> because no public dataset of PCB assembly defects exists at usable size.
>
> The shop already owns the board's design files; they cannot manufacture
> without them. The pick-and-place file says exactly what should sit at every
> coordinate. **The design file is the label.**"

This is the strongest technical claim available. It is also true.

### 5. Trust and traceability (15s)

Click **False call** on a finding.

> "The operator always overrules the machine. One click, no form — because an
> operator who has to fill in a form stops dismissing false calls and starts
> ignoring the station."

Switch to **Trends**.

> "And it accumulates. This designator fails on forty per cent of boards —
> that is not a rework job, that is a feeder problem. The station stops being a
> detector and starts improving the line."

Click **Export CSV**.

> "Every board leaves a record. Today their answer to 'what did you inspect?'
> is a signature on a sheet."

### 6. Close on cost (10s)

> "USB camera, ring light, a jig, and the laptop they already own. Runs fully
> offline — the design files are their customer's confidential IP and never
> leave the machine."

---

## The follow-up that wins the technical argument (30s)

**Deploy this when a judge pushes on accuracy, robustness, or "what happens in
a real factory?"** It is the strongest thing you have, and it needs no hardware.

The demo bar has a second row: **Bench conditions**. Select **golden**, then
walk the three profiles.

**Jig locked** → press space.

> "Correct board, controlled light. Passes clean."

Click **Check stability**.

> "Frame stability 0.8 grey levels. Under two, so the thresholds mean something."

**Exposure unlocked (#35)** → click **Check stability**.

> "Same board. But now the camera driver won't hold manual exposure — which is
> the actual fault on our development laptop. Stability is 3 grey levels, and
> the station says so: **settings unlocked, degraded**. It doesn't pretend."

**Uncontrolled shop light (CON-11)** → press space, on the *good* board.

> "Overhead fluorescents, no enclosure, a board that shifts in the jig. Watch —
> **it fails a board that is perfectly fine.** Fourteen regions, all of them
> phantom."

Then the line that matters:

> "That is the honest answer to 'how accurate is it?'. The dominant term isn't
> our algorithm — it's whether the light is controlled. So we built the gate
> that refuses to trust thresholds tuned on unstable frames, and we surface the
> degraded state instead of hiding it. Most inspection demos show you the happy
> path. We'll show you ours breaking, and where the guard sits."

Set it back to **Jig locked** before you move on.

**Be precise about what this is:** a simulated bench, and say the word
*simulated* out loud. It models placement jitter, ring-light falloff, exposure
drift and sensor noise, and it drives the real pipeline — but it is not a
measurement of a real camera. The claim is *"this is why lighting stability is
the first thing we fix"*, not *"this is our false-call rate"*.

---

## Questions you should expect

**"Is that a real board?"**
Be straight: it is a rendered board, because our camera hardware is still being
assembled. The pipeline is the production path — same code, same classifier,
and the frames come through a simulated bench that models jitter, light falloff,
exposure drift and sensor noise rather than handing the pipeline perfect pixels.
Then offer: the physical demo runs the moment the jig is built.

**"Doesn't the simulation just make it look good?"**
The opposite, and you can prove it in five seconds — switch to **Uncontrolled
shop light** and fail a good board in front of them. A simulation built to
flatter would not have a setting that breaks it.

**"What is your accuracy?"**
Do **not** quote a number. Say: the seeded-defect corpus is built but recall
and false-call rate are measured on real boards, and we have not run that yet.
Offer the falsifiable version instead — *"hand us a board, remove a component,
we will re-run it in front of you."* An industry juror will respect that far
more than a figure you cannot defend.

**"Why not deep learning / YOLO?"**
Two reasons. The latency budget allows ~6ms per component on a CPU with no GPU.
And Ultralytics is AGPL-3.0 — an MSME deploying it would inherit a copyleft
obligation. Every dependency here is MIT, Apache-2.0 or BSD.

**"What happens with a board you have not seen?"**
Load its Gerber and pick-and-place; the component map builds itself. If there
are no design files at all, golden-board differencing still works — it just
cannot name the parts.

---

## If something breaks

1. Switch to a different demo board — one bad image does not end the demo.
2. Restart: `Ctrl-C`, then `GERBEREYE_DEMO=1 .venv/bin/python run.py`.
3. Play the backup video (issue #21).

Never debug live. Move to the next thing and keep talking.
