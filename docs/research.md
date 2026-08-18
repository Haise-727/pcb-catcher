# Project Research: SIH 2026 Entry — Landscape Analysis + Problem Statement Selection
_Generated: 2026-08-13_

## Problem & Goal
Pick one problem statement from the 125 in the VITISH 2026 internal sheet that (a) wins the VIT internal round and (b) survives the SIH 2026 national grand finale. This brief reverse-engineers what actually wins SIH from the 2023–2025 editions, quantifies the hardware/software split, then scores the 125 statements against that pattern.

## Target Users
- **Primary:** a 6-member VIT team (SIH mandates 6 incl. ≥1 female participant) picking a PS in August 2026
- **Secondary:** the internal VITISH jury (faculty), then the SIH national jury (ministry/PSU officials + industry, not academics)

---

# PART 1 — What Actually Wins SIH (2023, 2024, 2025)

## Edition-over-edition data

| Metric | SIH 2023 | SIH 2024 | SIH 2025 |
|---|---|---|---|
| Problem statements | **231** | **254** | **271** |
| — Software PS | 176 (76.2%) | 186 (73.2%) | 191 (70.5%) |
| — Hardware PS | 55 (23.8%) | 68 (26.8%) | **80 (29.5%)** |
| Nodal centres | 48 | 51 | **60** (42 software + 18 hardware) |
| Teams at Grand Finale | ~2,000 (12,000+ participants) | 1,300+ | **1,360** (8,160 students, 727 institutes, 201 cities) |
| Idea submissions | ~50,000 from 44,000 teams | ~49,000 teams nationally recommended (86,000+ at institute level) | **72,165 from 68,766 teams** |
| Winners | 1 per PS, ₹1 L each, ₹2 Cr+ pool | **315 winning teams** | ₹1.5 L per winning team |
| Software finale format | 5-day | 2-day (Dec 11–12) | **36-hour** (Dec 8–9) |
| Hardware finale format | 5-day | 5-day (Dec 11–15) | **5-day** (Dec 8–12) |

### Hardware vs software: the number that should change your decision

**Hardware's share of problem statements has risen every year for three years: 23.8% → 26.8% → 29.5%.** In 2025 SIH ran a dedicated hardware track at 18 nodal hubs (IIT Roorkee, IIT Kharagpur, IIT Jammu among them) versus 42 software hubs — a 70/30 centre split matching the PS split.

Applying the 70.5/29.5 PS ratio to the 1,360 finale teams gives a **derived estimate of ~960 software teams and ~400 hardware teams** at the 2025 finale. SIH does not publish the exact per-edition team split, so treat this as an estimate, not an official figure.

The important asymmetry is not the raw count — it's **submissions per problem statement**. 68,766 teams chased 271 statements in 2025, but that demand is heavily skewed toward software: most college teams have no machine shop, no BOM budget, and no EE depth, so they self-select into software PS. Concretely, IIT Roorkee's hardware finale ran **just 23 shortlisted teams across 5 problem statements** (~4-5 teams per PS). Software PS routinely draw hundreds of idea submissions each.

**Takeaway: a hardware or hardware-flavoured PS is a materially better statistical bet — if your team can actually build the physical thing.**

## What the winners actually built

### SIH 2025 — Hardware Edition (IIT Roorkee)
| Team | PS | What they built |
|---|---|---|
| Caffeinated Coders (Lords Inst., Hyderabad) | SIH25267, Min. of Agriculture | **Low-cost portable jute ribboning machine** — lightweight, energy-efficient, uniform ribbon formation to accelerate in-situ retting |
| Mindsmiths | SIH25266, Min. of Agriculture | **Semi-automated cotton picking machine** — soft-grip mechanical arms + debris reduction, for small/marginal farmers |
| — | SIH25196, MHA (NSG/BSF) | **All-terrain weather-resilient surveillance system** — thermal imaging + autonomous drone patrol + real-time alert analytics |

Note what is *absent*: no foundation models, no novel silicon, no research-grade novelty. The winning hardware entries were **mechanically simple machines that a named user (a jute farmer, a cotton farmer) can operate tomorrow.**

### SIH 2025 — Software Edition
| Team | What they built |
|---|---|
| Vision Hackers | Gamified environmental education platform for student disaster preparedness |
| Tech Pravaha | Immersive digital learning ecosystem for environmental education |
| NEXAURA 2.3 | **Offline-first** AI agricultural advisory for small/marginal farmers |
| Phantom Techies | Smart curriculum management application |
| — (Dept. of Higher Ed., Punjab) | AI-driven timetable generation aligned with NEP 2020 |
| Coding Krew (Chennai Inst. of Tech) | Secure closed-group communication platform (Min. of Defence) |

### SIH 2024
| Team | What they built |
|---|---|
| Radar Vision (led by Chethan AC) | Full-stack prototype, PS 1606 |
| Mad Astra (IIIT Bhopal) | AI/ML optimisation of aluminium wire-rod properties for **NALCO** — predictive insights on production efficiency |
| Bhoomik (AKGEC Ghaziabad) | Digital solution enforcing Citizens Charter norms across India Post public interfaces ("Bridging the Measurability Gap") |
| Solar Masters | Single-axis solar tracking system in **MATLAB / Simulink / Simscape** (MathWorks PS) |

2024 winner concentration by PS-issuer: AICTE/MIC Student Innovation (largest block), Ministry of Jal Shakti, Ministry of Power, NTRO, Ministry of Defence, Ministry of Social Justice & Empowerment.

### Pattern extracted across all three years

1. **Boring beats brilliant.** Timetable generators, grievance routing, curriculum management, Citizens Charter compliance, a jute machine. Judges are ministry officers scoring *"can my department deploy this?"* — not researchers scoring novelty.
2. **A named user, not a market.** Every winner names one user: an NSG patrol team, a jute farmer, a NALCO plant engineer, an India Post counter clerk.
3. **Full-stack completeness > component sophistication.** Winners ship frontend + backend + ML integrated and working. A brilliant model with no UI loses to a mediocre model inside a polished, deployable product.
4. **Constraint-aware engineering is a differentiator.** "Offline-first" (NEXAURA), "low-cost" (jute/cotton machines), "commodity hardware" — Indian deployment constraints are explicitly rewarded.
5. **Hardware winners are mechanically simple and physically present.** Working metal in the room beats a slide of a CAD render.
6. **The clock is brutal on the software track.** SIH 2025 software was a **36-hour** sprint (down from 5 days in 2023). You must arrive at the finale with a working build; the finale is for iteration, integration, and pitching, not for starting.

### How winning projects are actually built (stack patterns)
Observed across SIH winner repos and writeups (github.com/topics/smart-india-hackathon, github.com/topics/sih):

| Layer | What SIH winners use |
|---|---|
| Frontend | React / Next.js, plain JS+HTML for speed; React Native + Expo for mobile |
| Backend | Python (FastAPI / Django REST), Node.js + Express |
| ML/CV | Python + PyTorch/TensorFlow, YOLO-family detectors, Jupyter for the model story |
| Mobile | Kotlin/Java Android, React Native |
| Domain-specific | MATLAB/Simulink/Simscape where the PS issuer is MathWorks; blockchain layers on traceability PS |
| Hardware | ESP32/Arduino + off-the-shelf sensors; commodity cameras; simple mechanical fabrication |

## Evaluation criteria (what the score is actually out of)
Judged on **novelty of idea, complexity, clarity/completeness of the prescribed format, feasibility, practicability, sustainability, scale of impact, user experience, and potential for future progression.** Scoring is 1–20 per criterion per round, weighted into a final score out of 100, across three rounds: internal → national shortlisting → grand finale jury.

**Implication:** feasibility, impact scale and UX are each worth as much as novelty. A team optimising purely for technical novelty is optimising ~1/6th of the rubric.

## SIH 2026 official themes (18) — from sih.gov.in
Smart Automation · Fitness & Sports · Space Technology · Heritage & Culture · MedTech/BioTech/HealthTech · Agriculture, FoodTech & Rural Development · **Smart Vehicles** · Transportation & Logistics · Robotics and Drones · Clean & Green Technology · Tourism · Renewable/Sustainable Energy · Blockchain & Cybersecurity · Smart Education · Disaster Management · **Games & Toys** · Miscellaneous · **Fintech**

Registration: 6-member teams, ≥1 female member, individual registration mandatory, signed HOD+mentor form. Submission deadline stated as **10 August 2026** — verify against sih.gov.in as this has already passed for some institutional flows.

> **Strategic note:** *Smart Vehicles*, *Fintech* and *Games & Toys* are newly prominent themes for 2026 — less historical competition and fewer canned reference projects floating around. Conversely, **Defence, Semiconductor, Green Hydrogen, Carbon Capture, Synthetic Biology and Pharma are NOT standalone SIH 2026 themes** — 15 Defence and 5 Semiconductor statements in the VITISH sheet have no clean carry-over path into an SIH 2026 theme (ministry PS still exist, but they surface under Robotics & Drones / Blockchain & Cybersecurity / Smart Automation).

---

# PART 2 — Choosing From the 125 VITISH Problem Statements

## What the sheet contains
125 statements across 35 sectors. Largest blocks: **Defence 15**, Artificial Intelligence 8, HealthTech 8, then Semiconductor / AgriTech / Manufacturing / EnergyTech at 5 each. Several carry an external sponsor tag: *Agritech Challenge*, *THRIVE Agrifood*, *IWMI*, *Emerging Technologies Hackathon 2026*, *Kalpataru*, *Industry Innovation Hackathon 2026*, *Datathon 2026*, *BGI Hackathon*.

## Scoring model
Six axes, 1–5 each, weighted. Max 50.

| Axis | Weight | Question |
|---|---|---|
| Build feasibility | ×2 | Can 6 students ship a working demo in 36h (SW) / 5 days (HW)? |
| Demo impact | ×2 | Does it produce a visible "wow" moment in a 5-minute jury slot? |
| Data / BOM access | ×1.5 | Are public datasets or a <₹10k BOM available *today*? |
| SIH 2026 theme carry-over | ×1.5 | Does it map cleanly to one of the 18 official themes? |
| Low crowding | ×2 | How many other teams will pitch the same thing? |
| Impact story | ×1 | Is there a named user with a quantifiable pain? |

## Ranked shortlist

| # | PS | Sector | Feas | Demo | Data/BOM | Theme | Uncrowded | Impact | **Score** |
|---|---|---|---|---|---|---|---|---|---|
| **1** | **#82 Low-cost Optical Inspection for PCB Assembly** | Manufacturing | 5 | 5 | 4 | 5 | 5 | 4 | **47.5** |
| **2** | **#43 AI Clinical Documentation Assistant** | HealthTech | 5 | 5 | 5 | 5 | 3 | 5 | **46.0** |
| **3** | **#77 Water Quality Monitoring** | WaterTech | 5 | 4 | 5 | 5 | 4 | 4 | **45.0** |
| 4 | #99 Structural Health Monitoring for Bridges | ConstructionTech | 4 | 4 | 4 | 5 | 5 | 5 | 44.5 |
| 5 | #88 Battery Health & RUL Prediction | EV | 5 | 3 | 5 | 5 | 4 | 4 | 43.0 |
| 6 | #75 Smart Groundwater Management | WaterTech | 4 | 3 | 5 | 5 | 4 | 5 | 42.0 |
| 7 | #105 Predictive Maintenance for Solar Farms | EnergyTech | 4 | 4 | 4 | 5 | 4 | 4 | 41.5 |
| 8 | #90 Adaptive Smart Traffic Signal Control | Mobility | 4 | 5 | 4 | 5 | 2 | 5 | 40.5 |
| 8= | #84 Deep-Learning Steel Defect Detection | Manufacturing | 5 | 4 | 5 | 4 | 3 | 3 | 40.5 |
| 10 | #45 AI Radiology Interpretation Assistant | HealthTech | 4 | 4 | 5 | 5 | 2 | 5 | 40.0 |
| 10= | #117 AI Cold Chain Optimisation | Cold Chain | 4 | 4 | 4 | 4 | 4 | 4 | 40.0 |
| 12 | #100 Construction Site Safety (PPE detection) | ConstructionTech | 5 | 4 | 5 | 4 | 1 | 4 | 37.5 |
| 13 | #113 Digital Carbon Credit Verification (MRV) | Carbon Markets | 3 | 3 | 3 | 4 | 5 | 4 | 36.5 |
| 14 | #23 / #97 Document Intelligence / Grievance Classification | AI / Smart Cities | 5 | 3 | 4 | 3 | 2 | 4 | 34.5 |
| 14= | #26 / #63 Agri Advisory / Precision Irrigation | AgriTech | 4 | 3 | 4 | 5 | 1 | 5 | 34.5 |
| 16 | #21 Multilingual AI Assistant for Govt Services | AI | 4 | 3 | 4 | 4 | 1 | 5 | 33.0 |

## 🏆 Recommendation: **PS #82 — Low-cost Optical Inspection for PCB Assembly**

> *"MSME electronics manufacturers cannot afford automated optical inspection systems. Develop an edge AI solution that overlays PCB Gerber files on live camera feeds, detects assembly defects and guides operators."* — tagged *Emerging Technologies Hackathon 2026*. Maps to SIH 2026 theme **Smart Automation**.

**Why this one wins:**
- **It is written like a real SIH-winning PS.** Named user (MSME PCB assembler), named constraint (cannot afford commercial AOI — real systems run ₹15–50 lakh), named technical mechanic (Gerber overlay on live camera). That specificity is exactly the shape of the jute-ribboner and cotton-picker winners.
- **Best demo in the entire sheet.** Point a webcam at a populated PCB → live overlay snaps to the board → missing / rotated / tombstoned / wrong-polarity components light up in red on screen in real time. That is a 20-second, unambiguous, physically-present wow. Compare with a battery-RUL dashboard, which is a line chart.
- **Hardware credibility with software-team economics.** BOM is a webcam or 8MP USB microscope + a ring light + a laptop or Jetson Orin Nano + a jig. Under ₹10k if you already own a laptop. You get the low-crowding advantage of the hardware track without needing a machine shop.
- **Almost nobody else will pick it.** It requires knowing what a Gerber file is. That domain barrier is your moat — it filters out the 90% of teams who default to CV-on-a-common-dataset.
- **Verifiable accuracy story.** You can hand the jury a board, let them remove a component, and re-run. Live falsifiability is the single most persuasive thing at a jury table.

**The 36-hour build shape:**
1. Gerber/pick-and-place parser → component reference designators + XY + rotation + package footprint (`pcb-tools` / `gerbonara`)
2. Homography alignment: detect board fiducials in camera frame → warp Gerber coordinates onto live pixels (OpenCV `findHomography`)
3. Per-component ROI classification: present / absent / misaligned / rotated / polarity-reversed. Golden-board differencing as the fast baseline; a small CNN or YOLO head on cropped ROIs as the ML layer
4. Operator UI: live feed + red/green overlays + defect list + one-click "mark false positive" retraining loop
5. Edge deployment: ONNX/TensorRT on Jetson, or plain CPU inference to prove the "commodity hardware" claim
6. Report export: per-panel defect log, CSV/PDF for the QA record

**Risks:** lighting sensitivity (mitigate with a diffused ring light and a fixed jig — and *own* that constraint in the pitch, don't hide it); homography drift on warped boards (mitigate with per-region local alignment); no public India-specific PCB defect dataset (mitigate by generating your own — deliberately depopulate/rotate components on a few boards, which also gives you a live jury demo).

### Runner-up if your team is pure software: **PS #43 — AI Clinical Documentation Assistant**
Ambient scribe: doctor speaks a consultation in Hindi/Tamil/Telugu → ASR → LLM → structured EHR note + discharge summary + prescription. Whisper/IndicWhisper + an Indic-tuned LLM + FHIR-shaped output. Demo is genuinely theatrical (speak, watch the note write itself), no PHI needed (use synthetic consults), maps cleanly to MedTech/HealthTech, and hits real doctor burnout. Differentiate on **multilingual + code-switched Hinglish + offline-capable on-device ASR** — that is the NEXAURA "offline-first" move that won in 2025.

### Dark horse if you have EE/civil strength: **PS #99 — Structural Health Monitoring for Bridges**
Maps to **Disaster Management** (a perennially strong SIH theme). Demo with a scale model bridge + MPU6050 accelerometers + a load; show vibration-signature anomaly detection plus crack detection from phone photos, feeding a digital twin. Very low crowding, very high impact narrative post-bridge-collapse news cycles.

---

## ❌ Do Not Pick

| PS | Why not |
|---|---|
| #29 Indigenous AI Foundation Models | You cannot pretrain an LLM in 36 hours. Guaranteed loss on feasibility. |
| #33–#37 Semiconductor (chip design, packaging, yield, test) | Needs licensed EDA tools and fab/ATE access. #34 (RISC-V on FPGA) is *technically* doable but 5 days is brutal and Semiconductor is not an SIH 2026 theme. |
| #53, #54, #55, #69, #120–#123 BioTech / Synthetic Biology / Bioeconomy | Wet lab, cell culture, weeks-long fermentation. Nothing to demo. |
| #56 AI-driven Drug Discovery | Cannot validate anything in-hackathon; the first jury question is "where is your wet-lab validation?" |
| #108–#110 Green Hydrogen, #111–#112 Carbon Capture | Capital equipment, pressure vessels, safety regulation. Not a hackathon build. |
| #115 Automated Battery Disassembly, #116 Critical Mineral Recovery | Industrial robotics cell / hydrometallurgy plant. Not buildable. |
| #4 Counter-UAV, #10 EW Spectrum Intelligence, #11 Swarm C2, #13 Mine Detection | Restricted data, unprocurable RF/EO-IR hardware, and Defence is not a standalone SIH 2026 theme. |
| #51 AI-assisted Surgical Navigation | Needs clinical imaging hardware + AR headset + a regulatory story you cannot tell. |
| #21 Multilingual Govt Assistant, #25 Healthcare Knowledge Assistant, #27 GenAI for Public Admin | All three are "RAG chatbot." The single most saturated category in Indian student hackathons. You will be the fourth team that day pitching it. |
| #100 PPE Detection | Excellent build, terrible differentiation — PPE detection is the most-repeated CV project in India. Only pick if you add something genuinely new (e.g. near-miss trajectory prediction). |

---

## Tech Recommendations (for PS #82)

| Layer | Recommendation | Reason |
|---|---|---|
| Gerber parsing | `gerbonara` (Python) | Actively maintained, handles Gerber X2 + Excellon; `pcb-tools` is the fallback |
| CV / alignment | OpenCV (`findHomography`, `matchTemplate`, ArUco/fiducial detect) | Zero-cost, runs on CPU, jury-explainable |
| Defect model | YOLOv8/v11 nano on cropped component ROIs + golden-board differencing baseline | Nano runs real-time on CPU; keep the classical baseline so you always have a working demo |
| Edge runtime | ONNX Runtime on CPU, TensorRT if a Jetson Orin Nano is available | Directly substantiates the "commodity hardware" claim in the PS |
| Backend | FastAPI + WebSocket for the live frame/defect stream | Fastest Python-to-UI path; matches the SIH winner stack pattern |
| Frontend | React + Vite, canvas overlay on the video element | Overlay rendering is trivial on canvas; no framework fight |
| Storage | SQLite (local) + CSV/PDF export | An MSME shop floor has no cloud. Local-first *is* the pitch. |
| Camera | 8MP USB microscope / industrial USB cam + diffused ring light + fixed jig | Repeatable lighting is the whole ballgame for AOI |

## Risks & Open Decisions

### Risks
- **36-hour software finale** — arrive with a working build; the finale is for polish and pitch, not first commits. Mitigation: freeze scope 2 weeks out, rehearse the demo 10+ times.
- **Demo failure on stage** — mitigation: pre-record a backup video, and hard-code a fallback "golden board" path that cannot fail.
- **Crowding on obvious PS** — mitigation: the whole point of the #82 recommendation. If you override it, pick your differentiator explicitly and state it in slide 2.
- **Jury is ministry/industry, not academic** — mitigation: lead with deployment cost, operator training time, and integration path. Put novelty on slide 6, not slide 1.
- **Theme carry-over gap** — Defence/Semiconductor/Green-Hydrogen VITISH statements do not map to an SIH 2026 theme. Mitigation: only pick a PS that maps to one of the 18 official themes.
- **SIH 2026 deadline** — 10 August 2026 was widely reported as the submission cutoff. Mitigation: **verify current dates on sih.gov.in immediately** — this brief is dated 13 Aug 2026.

### Open Decisions
- [ ] Confirm current SIH 2026 registration/submission deadline on sih.gov.in (reported date has passed)
- [ ] Does the team have EE/mechanical depth, or is it pure software? → decides #82/#99 vs #43
- [ ] Is a Jetson Orin Nano procurable in time, or do we commit to CPU-only inference?
- [ ] Can we source 5–10 populated PCBs + a bare board of the same design (for golden reference) from the VIT electronics lab?
- [ ] Who owns the pitch? Assign one dedicated presenter from day one — SIH is scored on delivery as much as build
- [ ] Team composition: 6 members incl. ≥1 female participant — locked?

## References
- [sih.gov.in](https://sih.gov.in/) — official portal, SIH 2026 themes (18), registration rules
- [SIH 2024 Grand Finale Results](https://www.sih.gov.in/sih2024/sih2024-grand-finale-result) — full winner list by PS/ministry
- [SIH 2025 Shortlisted Teams](https://sih.gov.in/sih2025/shortlisted-teams-grand-finale) — team/PS/nodal-centre mapping
- [github.com/topics/smart-india-hackathon](https://github.com/topics/smart-india-hackathon) — winner repo stack patterns (KisanSeva2 SIH2020 winner, treesense-imaging, ArogyaKrishi)
- [SIH 2025 PS browser](https://sih2025probelmstatement.vercel.app/) — theme-wise PS counts, software/hardware tagging

## Sources
- [Winners of SIH 2025 announced — Content Media Solution](https://contentmediasolution.com/news/winners-of-smart-india-hackathon-sih-2025-one-of-the-worlds-biggest-hackathons-announced/)
- [SIH finale kicks off with 8K students across 60 centres — The Tribune](https://www.tribuneindia.com/news/delhi/smart-india-hackathon-finale-kicks-off-with-8k-students-across-60-centres/)
- [IIT Roorkee hosts SIH 2025 Hardware Edition Grand Finale — Business News This Week](https://businessnewsthisweek.com/education/iit-roorkee-successfully-hosts-the-smart-india-hackathon-sih-2025-hardware-edition-grand-finale/)
- [Hyderabad students win SIH 2025 at IIT Roorkee — Deccan Chronicle](https://www.deccanchronicle.com/technology/in-other-news/lords-institute-students-win-smart-india-hackathon-2025-1924129)
- [Five teams win SIH 2025 software edition at CEC-CGC Landran — Babushahi](https://www.babushahi.com/view-news.php?id=214631)
- [SIH 2024 grand finale at KCG College — PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2084190&reg=48&lang=2)
- [SIH 2024 announces grand finale schedule — Careers360](https://news.careers360.com/smart-india-hackathon-2024-announces-grand-finale-schedule-begins-december-11)
- [SIH gets bigger, 7th edition sees 315 winning teams — Curriculum Magazine](https://curriculum-magazine.com/big-stories-of-2024-smart-india-hackathon-sih-gets-bigger-7th-edition-sees-315-winning-teams-this-year/)
- [SIH 2023 finale concludes at Manipal Institute of Technology — Careers360](https://news.careers360.com/smart-india-hackathon-2023-finale-concludes-at-manipal-institute-of-technology)
- [Solar Masters' winning journey at SIH 2024 — MathWorks Student Lounge](https://blogs.mathworks.com/student-lounge/2025/06/13/innovation-meets-excellence-solar-masters-winning-journey-at-smart-india-hackathon-2024/)
- [SIH project ideas with winning examples — PlacementPreparation](https://www.placementpreparation.io/blog/smart-india-hackathon-project-ideas/)
- [SIH 2026 registration, eligibility & internal hackathon rules — Where U Elevate](https://whereuelevate.com/blogs/smart-india-hackathon-2026)
- [SIH 2026 FAQs: complete student guide — The New Views](https://thenewviews.com/smart-india-hackathon-sih-2026-faqs-registration-eligibility-team-rules-more/)
