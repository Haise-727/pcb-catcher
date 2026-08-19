# Demo Script

**For the internal round. Target: 90 seconds of screen time.**

The build is only half the score. This is the other half.

---

## Before you start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tools/seed_demo.py          # generates boards, seeds the station
GERBEREYE_DEMO=1 .venv/bin/python run.py     # terminal 1
cd web && npm install && npm run dev         # terminal 2
```

Open `http://127.0.0.1:5173`. The board type, golden reference, component map
and BOM are already loaded — no setup clicking in front of a jury.

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

## Questions you should expect

**"Is that a real board?"**
Be straight: it is a rendered board, because our camera hardware is still being
assembled. The pipeline is the production path — same code, same classifier.
Then offer: the physical demo runs the moment the jig is built.

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
