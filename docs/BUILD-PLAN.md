# Build Plan — Predictive Green Corridor System

Step-by-step execution plan. Each step should produce something runnable before
moving to the next — do not parallelize across steps until the foundation (Steps
0–2) is working end-to-end. Detailed algorithm behavior for each module is defined
in [CLAUDE.md](../CLAUDE.md).

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## Step 0 — Decisions & repo scaffold

- [x] Repo structure created (`network/`, `simulation/`, `core/`, `metrics/`,
      `viz/`, `docs/`).
- [x] Project report Chapter 1 (Introduction), Chapter 2 (Feasibility Study),
      and Chapter 3 (Design Sheets — architecture, sequence, decision logic,
      output mockup) drafted.
- [x] **Architecture / tech-stack decisions made and logged** — see
      [DECISIONS.md](DECISIONS.md): custom Python sim first (SUMO port later),
      synthetic grid first (OSM import later), venv + pip.
- [x] `requirements.txt` filled in (`networkx`, `matplotlib`; SUMO/osmnx added
      later per D1/D2).

## Step 1 — Network foundation

- [x] `network/generate_grid.py`: generate a synthetic N×N grid network (default
      5×5) of junctions and edges, each junction with a fixed-cycle signal plan
      (red/green/yellow durations configurable).
- [ ] (Optional, later) `network/osm_import.py`: import a small real road-network
      extract for a "real city" demo, once the algorithm is validated on
      synthetic data.
- [x] Sanity check: `demo.py` / `simulation/run_baseline.py` confirm junction/edge
      counts and routing behave as expected on the default 5×5 grid.

## Step 2 — Background traffic + baseline simulation

- [x] `simulation/traffic_agents.py`: generate simple background vehicle agents
      that move across the network according to the fixed-cycle signals (no
      preemption logic yet), producing "normal" congestion.
- [x] `core/router.py`: shortest-*time* path computation (not shortest-distance)
      for the ambulance, weighted by current travel time/congestion.
- [x] `simulation/run_baseline.py`: run one ambulance agent from A to B through
      the network with **no preemption at all**, alongside background traffic.
      This is the working scaffold / control condition.
- [x] **Milestone check**: baseline simulation runs end-to-end and reports
      ambulance transit time (v1 sample scenario: 171.0s). This is the
      "definition of done" floor for the whole project — everything after this
      step is additive.

## Step 3 — ETA prediction

- [x] `core/eta_predictor.py`: given the ambulance's current position/speed and
      route, estimate seconds-to-arrival at each upcoming junction.
- [x] Prediction updates on a rolling basis (every simulation tick or every N
      metres traveled) as the ambulance moves — not computed once at t=0.
- [x] Validation: `metrics/eta_accuracy.py` logs predicted vs. actual arrival per
      junction; error shrinks from ~5 s at 60–90 s out to 0.4 s at arrival.

## Step 4 — Green corridor coordination (the core novel logic)

- [x] `core/corridor_coordinator.py`: for each junction ahead of the ambulance on
      its route, schedule a green phase timed to the ETA prediction from Step 3.
- [x] Enforce a bound on how long perpendicular/cross traffic can be held (v1:
      bounded shift search over `±max_hold_s`, default 15s — extends the
      current phase or truncates the opposing one, whichever scores higher,
      without exceeding the bound).
- [x] `simulation/run_corridor.py`: run the same scenario as Step 2's baseline,
      but with corridor coordination active.

## Step 5 — Graceful recovery

- [x] `core/recovery.py`: once the ambulance clears a junction, interpolate that
      junction back to its normal fixed-cycle position over the next 1–2 cycles
      (rather than resetting instantly), so queued traffic clears before normal
      timing resumes.
- [x] Wire recovery into `simulation/run_corridor.py` so corridor mode always
      includes recovery.

## Step 6 — Naive reactive baseline (for a fair three-way comparison)

- [x] Implement a naive reactive-preemption mode: signal only reacts once the
      ambulance is within ~200m, and resets instantly (no gradual recovery) once
      it clears. This is the "existing systems" comparison point, distinct from
      the no-preemption baseline in Step 2. (v1: `--mode naive` on
      `simulation/run_baseline.py`, or `RunMode.NAIVE_REACTIVE` on the shared
      `simulation/engine.py`.)

## Step 7 — Metrics & visualization

- [x] `metrics/evaluate.py`: compute, for each run —
      - Ambulance total transit time.
      - Average delay imposed on background traffic.
  - Compare across all three modes: no-preemption baseline, naive-reactive,
    predictive corridor + recovery.
- [x] `viz/plots.py`: before/after comparison charts, plus a Gantt-style
      hold timeline per junction with the ambulance's position overlaid (v1
      shows shift-active intervals rather than full red/green state; a true
      red/green Gantt is a follow-up refinement).

## Step 8 — Final demo & report

- [x] A single script/notebook that runs all three modes on the same scenario
      (same network, same background traffic, same ambulance A→B) and prints the
      comparison table + renders the charts from Step 7. (`demo.py` at repo
      root.)
- [x] Confirm the MVP "definition of done" from [CLAUDE.md](../CLAUDE.md) §3 — **met as a
      pipeline, not as a hypothesis.** Four modes run on identical scenarios and report
      transit, background delay and starvation, with multi-seed CIs
      ([RESULTS.md](RESULTS.md)). Any preemption saves ~15% of ambulance time; the
      predictive corridor is not distinguishable from naive reactive in this simulator.

## Step 9 — Hardening, evaluation, frontend (simulation v2)

- [x] Model fixes M1–M5 ([DECISIONS.md](DECISIONS.md)); `Scenario` config shared by all entry points.
- [x] Corridor-without-recovery mode (the recovery ablation); 48 pytest tests in `tests/`.
- [x] `metrics/sweep.py`: multi-seed CIs, paired differences, sweeps over load, hold,
      horizon, recovery cycles, slew and reactive trigger.
- [x] True red/green Gantt and ETA-accuracy chart in `viz/plots.py`.
- [x] `api/` (replay exporter + local server) and `frontend/` with three theme mocks.
- [x] Cobalt chosen and finalised: junction detail, per-seed bars, presets, CSV export, light/dark.
      Not done: frontend automated tests, `lock the system` design.md, SUMO-grade realism.
- [ ] Re-routing on changed conditions (CLAUDE.md §6.1); SUMO port (D1 phase 2).
- [ ] Wrap the report against the UCS503L structure — see [REPORT-STATUS.md](REPORT-STATUS.md).

## Explicitly deferred (do not build in this plan)

Per [CLAUDE.md](../CLAUDE.md) §8: real hardware/V2X integration, live GPS
ingestion, multi-ambulance conflict resolution, and ML-based traffic prediction.
