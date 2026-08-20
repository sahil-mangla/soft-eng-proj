# Build Plan — Predictive Green Corridor System

Step-by-step execution plan. Each step should produce something runnable before
moving to the next — do not parallelize across steps until the foundation (Steps
0–2) is working end-to-end. Detailed algorithm behavior for each module is defined
in [CLAUDE.md](../CLAUDE.md).

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## Step 0 — Decisions & repo scaffold

- [x] Repo structure created (`network/`, `simulation/`, `core/`, `metrics/`,
      `viz/`, `docs/`).
- [x] Project report Chapter 1 (Introduction) and Chapter 2 (Feasibility Study)
      drafted.
- [x] **Architecture / tech-stack decisions made and logged** — see
      [DECISIONS.md](DECISIONS.md): custom Python sim first (SUMO port later),
      synthetic grid first (OSM import later), venv + pip.
- [x] `requirements.txt` filled in (`networkx`, `matplotlib`; SUMO/osmnx added
      later per D1/D2).

## Step 1 — Network foundation

- [ ] `network/generate_grid.py`: generate a synthetic N×N grid network (default
      5×5) of junctions and edges, each junction with a fixed-cycle signal plan
      (red/green/yellow durations configurable).
- [ ] (Optional, later) `network/osm_import.py`: import a small real road-network
      extract for a "real city" demo, once the algorithm is validated on
      synthetic data.
- [ ] Sanity check: print/plot the generated network and confirm junction/edge
      counts match expectations.

## Step 2 — Background traffic + baseline simulation

- [ ] `simulation/traffic_agents.py`: generate simple background vehicle agents
      that move across the network according to the fixed-cycle signals (no
      preemption logic yet), producing "normal" congestion.
- [ ] `core/router.py`: shortest-*time* path computation (not shortest-distance)
      for the ambulance, weighted by current travel time/congestion.
- [ ] `simulation/run_baseline.py`: run one ambulance agent from A to B through
      the network with **no preemption at all**, alongside background traffic.
      This is the working scaffold / control condition.
- [ ] **Milestone check**: baseline simulation runs end-to-end and reports
      ambulance transit time. This is the "definition of done" floor for the
      whole project — everything after this step is additive.

## Step 3 — ETA prediction

- [ ] `core/eta_predictor.py`: given the ambulance's current position/speed and
      route, estimate seconds-to-arrival at each upcoming junction.
- [ ] Prediction updates on a rolling basis (every simulation tick or every N
      metres traveled) as the ambulance moves — not computed once at t=0.
- [ ] Validation: log predicted vs. actual arrival time per junction per run;
      confirm error shrinks as the ambulance gets closer.

## Step 4 — Green corridor coordination (the core novel logic)

- [ ] `core/corridor_coordinator.py`: for each junction ahead of the ambulance on
      its route, schedule a green phase timed to the ETA prediction from Step 3.
- [ ] Enforce a bound on how long perpendicular/cross traffic can be held (start
      with a simple threshold rule: extend the current phase or truncate the
      opposing phase by at most X seconds — no more sophisticated optimization
      yet).
- [ ] `simulation/run_corridor.py`: run the same scenario as Step 2's baseline,
      but with corridor coordination active.

## Step 5 — Graceful recovery

- [ ] `core/recovery.py`: once the ambulance clears a junction, interpolate that
      junction back to its normal fixed-cycle position over the next 1–2 cycles
      (rather than resetting instantly), so queued traffic clears before normal
      timing resumes.
- [ ] Wire recovery into `simulation/run_corridor.py` so corridor mode always
      includes recovery.

## Step 6 — Naive reactive baseline (for a fair three-way comparison)

- [ ] Implement a naive reactive-preemption mode: signal only reacts once the
      ambulance is within ~200m, and resets instantly (no gradual recovery) once
      it clears. This is the "existing systems" comparison point, distinct from
      the no-preemption baseline in Step 2.

## Step 7 — Metrics & visualization

- [ ] `metrics/evaluate.py`: compute, for each run —
      - Ambulance total transit time.
      - Average delay imposed on background traffic.
  - Compare across all three modes: no-preemption baseline, naive-reactive,
    predictive corridor + recovery.
- [ ] `viz/plots.py`: before/after comparison charts, plus a Gantt-style
      red/green signal-state timeline per junction with the ambulance's position
      overlaid.

## Step 8 — Final demo & report

- [ ] A single script/notebook that runs all three modes on the same scenario
      (same network, same background traffic, same ambulance A→B) and prints the
      comparison table + renders the charts from Step 7.
- [ ] Confirm the MVP "definition of done" from [CLAUDE.md](../CLAUDE.md) §3:
      corridor mode has meaningfully lower ambulance transit time, and
      corridor+recovery mode does not dramatically worsen background-traffic
      delay relative to no-preemption (and ideally beats naive-reactive).
- [ ] Wrap the report: Chapters 1–2 already drafted in
      [docs/report/](report/); add subsequent chapters (design, implementation,
      testing, results) as the corresponding build steps complete.

## Explicitly deferred (do not build in this plan)

Per [CLAUDE.md](../CLAUDE.md) §8: real hardware/V2X integration, live GPS
ingestion, multi-ambulance conflict resolution, and ML-based traffic prediction.
