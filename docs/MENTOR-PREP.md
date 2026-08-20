# Mentor Prep Brief — Predictive Green Corridor System

Use this before/during your mentor meeting. It covers: the problem, what's novel, decisions made, build plan, risks, and questions for the mentor.

---

## 30-second pitch

We're building a traffic simulation that tests a smarter Emergency Vehicle Preemption (EVP) system for ambulances. Instead of reacting to an ambulance 200m away and snapping back to normal timing instantly (how real systems work today), we predict its arrival at *each* upcoming junction and pre-schedule a coordinated green corridor — then ease signals back to normal smoothly rather than abruptly. The MVP is a simulation (not hardware) that measures ambulance transit time and cross-traffic delay under three modes (no preemption / naive-reactive / predictive+recovery) on the same scenario.

---

## 1. The Problem We're Solving

**Status quo (reactive EVP):**
- Signal only detects ambulance ~150–300m away
- Flips to green immediately, no coordination across junctions
- Resets to normal cycle instantly once ambulance clears → creates secondary traffic shockwave

**Our gap:** existing research shows predictive multi-junction coordination + gradual recovery can reduce non-emergency traffic delay by ~43% vs. reactive alone — but no system actually does it yet. This project *builds* and *measures* that combination.

---

## 2. What's Novel (Why This Matters)

Two algorithmic contributions:
1. **Predictive multi-junction corridor**: estimate ambulance's arrival at each upcoming junction (not just the next one), update in real-time as it moves, schedule green phases *ahead of time*.
2. **Graceful recovery**: don't snap signals back to normal; phase-shift back over 1–2 cycles so queued traffic clears first.

Neither is trivial — they're both currently open research problems.

---

## 3. MVP Scope (What We're Actually Building)

**Included:**
- Synthetic 5×5 grid road network, each junction with a fixed-cycle signal plan
- Background traffic (ordinary cars creating congestion)
- One ambulance, A→B routing via shortest-*time* path (updated per live congestion)
- ETA predictor (per-junction arrival time, updated every tick)
- Corridor coordinator (pre-schedule green phases, bounded cross-traffic hold time)
- Recovery module (phase-shift back to normal over 1–2 cycles)
- Three comparison modes: no-preemption baseline, naive-reactive baseline, predictive corridor+recovery
- Automated metrics (transit time, avg delay) and visualization (signal timeline + ambulance position)

**Explicitly out of scope:**
- Real hardware/V2X integration
- Live GPS feed (simulated instead)
- Multi-ambulance conflict resolution
- ML-based traffic prediction (heuristics only)
- Production deployment, role-based access, etc.

Why this scope? Focusses on the core research question (does coordinated+recovery preemption work better?) without scope creep into hardware/ops/ML.

---

## 4. Key Decisions Made (Locked in docs/DECISIONS.md)

| Decision | Choice | Why |
|----------|--------|-----|
| **D1: Simulation engine** | Custom Python discrete-event sim first; SUMO port later | Fast iteration, low setup risk, no external system dependency needed early. SUMO is added as a realism upgrade once the algorithms are proven, not a blocker for starting. |
| **D2: Road network** | Synthetic 5×5 grid first; real OSM extract later | Fully controllable, reproducible, easy to debug. Real map data is added later for a compelling final demo, not needed for algorithm validation. |
| **D3: Env / deps** | `venv` + `pip` + `requirements.txt` | Simplest option, already scaffolded, matches the repo structure. Revisit only if SUMO port needs Conda for system-level deps. |
| **D4: Git/remote** | Local git only (for now) | Non-blocking. Add GitHub remote whenever ready. |

---

## 5. Build Plan — Steps 0–8

Each step produces something runnable before the next. Status: **Step 0 done** (scaffold, decisions, report Chapters 1–2 drafted).

| Step | What | Done? | Purpose |
|------|------|-------|---------|
| **0** | Decisions, scaffold, report Intro+Feasibility | ✅ | Lock architecture; unblock implementation |
| **1** | `generate_grid.py` — synthetic 5×5 grid network + signal plans | ⬜ | Build the world |
| **2** | Background traffic, ambulance router, **baseline simulation** (no preemption) | ⬜ | **First working end-to-end simulation** — milestone / control group |
| **3** | ETA predictor (per-junction, rolling update) | ⬜ | Input for corridor coordinator |
| **4** | Corridor coordinator (pre-schedule greens, bounded cross-traffic) | ⬜ | **Core novel logic** |
| **5** | Recovery module (graceful phase-shift back) | ⬜ | The research shows recovery alone saves ~21% delay |
| **6** | Naive-reactive baseline (detect ~200m, reset instantly) | ⬜ | "Existing systems" comparison arm |
| **7** | Metrics & visualization (3-way comparison) | ⬜ | Answer: does it work? by how much? |
| **8** | Final demo script + remaining report chapters | ⬜ | Ship: run all modes, show comparison, document results |

**Key principle:** Steps 1–2 must be rock-solid before touching 3–8. The baseline is the foundation; everything else layers on top without rework.

---

## 6. Success Criteria (Measurable MVP Definition)

For Step 8 (final demo) to pass, we need to show:

✅ **Ambulance transit time**: corridor mode is meaningfully lower than no-preemption baseline (target: >10% reduction).

✅ **Background traffic delay**: corridor+recovery mode does not dramatically worsen avg delay vs. no-preemption, and ideally beats naive-reactive (target: within 5–10% of baseline, or better).

✅ **Prediction accuracy**: ETA error shrinks as ambulance approaches (validate in Step 3).

✅ **Reproducibility**: same network, traffic, ambulance start/end across all three modes so comparison is apples-to-apples.

✅ **Visualization**: clear Gantt-style signal timeline showing the corridor effect and recovery behavior.

If these land, the MVP claim ("predictive corridor + recovery *does* reduce disruption") is proven.

---

## 7. Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **Simulation logic bug** | High | Project blocked | Validate baseline (Step 2) early and often; log vehicle positions/signal states per tick; write unit tests for router, ETA, coordinator independently before wiring. |
| **ETA prediction too inaccurate** | Medium | Corridor can't work | Step 3 is standalone validation — log predicted vs. actual, iterate on heuristic (speed/density model) before Step 4 depends on it. |
| **Corridor scheduler starves cross-traffic** | Medium | Unfair comparison | Threshold-based rule (max X seconds) is deliberately conservative — start with 5–10s, tune if needed. |
| **Recovery logic too gradual or too abrupt** | Medium | Recovery benefit unclear | Parameterize recovery duration (1–2 cycles) and test empirically; Step 5 has its own validation before final comparison. |
| **Scope creep (real hardware, multi-ambulance, ML)** | Low (but possible) | Timeline slip | Scope is locked in CLAUDE.md §8 (out of scope). Push back on feature requests; these are "Phase 2" items. |
| **Semester timeline tight** | Medium | Incomplete report | Build plan is phased — Steps 1–2 alone produce a working demo. Later steps (corridor/recovery/comparison) are additive; even partial completion has value. |

---

## 8. Questions for Your Mentor

**On the approach:**
- Is the incremental build order (baseline first, corridor second) sound? Or should we parallelize some steps?
- Does the risk mitigation (validate prediction and coordinator independently before final comparison) match your expectations?

**On scope:**
- Are the out-of-scope decisions (no real hardware, no multi-ambulance, no ML) reasonable for an academic project, or should we include any of these?
- Is synthetic-grid-first (real map data later) the right call, or should we start with OSM data?

**On success criteria:**
- The success targets (ambulance >10% faster, cross-traffic within 5–10% of baseline) — do these feel realistic given the algorithm complexity?
- Should we add additional metrics (e.g. worst-case single-junction delay, signal phase violations)?

**On dependencies:**
- Do you have any concerns with the custom-Python-first approach (SUMO as a later port)? Should we start with SUMO instead to reduce porting risk?
- Any recommended libraries/tools we should know about before Step 1?

**On feasibility:**
- Timeline: Steps 1–2 are ~1–2 weeks (network + baseline), Steps 3–5 are the novel logic (~2–3 weeks), Steps 6–8 are comparison+reporting (~1–2 weeks). Does that match a semester pace, or should we adjust?

**On evaluation:**
- For the final report, what should the balance be? (Algorithm novelty vs. implementation detail vs. experimental results?)
- Should we include a literature review section comparing our approach to existing EVP systems?

---

## 9. Current State & Next Steps

**Repo status:**
- ✅ Project structure scaffolded (`network/`, `simulation/`, `core/`, `metrics/`, `viz/`)
- ✅ Decisions locked (custom Python sim, synthetic grid, venv+pip)
- ✅ Report Chapters 1–2 drafted (Introduction, Feasibility Study)
- ✅ Build plan detailed (Steps 0–8)
- ⬜ Implementation begins with Step 1 (generate_grid.py) — awaiting go-ahead / mentor feedback

**Next immediate step:** build `network/generate_grid.py` (synthetic grid generator with networkx), then immediately move to Step 2 (baseline simulation) to get something runnable ASAP.

---

## 10. Questions to Clarify Before Starting Implementation

Before we commit to code, does the mentor want to weigh in on any of these?

1. **Simulation correctness**: how should we validate that vehicles obey signals correctly, that the network is connected properly, etc.?
2. **ETA heuristic**: should arrival prediction be based purely on speed/distance, or do we need something more sophisticated (queue length, signal state lookahead)?
3. **Corridor bounding rule**: "don't hold cross-traffic >X seconds" — what's a reasonable starting value? (5s? 10s? 15s?)
4. **Recovery duration**: 1 cycle? 2 cycles? Or parameterized so we can test both?
5. **Baseline modes**: no-preemption is clear, but for the "naive-reactive" baseline, should we assume ~200m detection radius or something else?
6. **Background traffic density**: how many regular cars? Should it be tunable, or fixed for reproducibility?

---

## Bottom Line

**We know what we're building, why it matters, and the order to build it in.** The decisions (custom sim first, synthetic grid first) are deliberately low-risk and low-friction, so we can validate the core algorithms fast. The mentor meeting should clarify:
- Any concerns with the sequencing or scope
- Guidance on the ETA/coordinator heuristics
- Timeline expectations
- Any domain-specific knowledge (e.g., real EVP systems' detection radius, signal control constraints)

Then we start Step 1 and ship the first runnable thing within a week.
