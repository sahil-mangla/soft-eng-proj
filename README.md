# Predictive Green Corridor System

A simulation-first system that predicts an ambulance's route and per-junction
arrival time, coordinates a "green corridor" of traffic signals ahead of it, and
eases signals back to normal timing after it passes — instead of the abrupt
detect-and-snap-back behavior of existing reactive Emergency Vehicle Preemption
(EVP) systems.

This is a simulation (not a hardware integration): it compares four control
modes on the same scenario — no preemption, naive reactive, corridor without
recovery, corridor with recovery — and reports ambulance transit time,
background-traffic delay and cross-traffic wait.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python demo.py                     # four-mode comparison table + charts in outputs/
.venv/bin/python -m metrics.sweep --seeds 24 # multi-seed means, 95% CIs, parameter sweeps
.venv/bin/python -m pytest                   # 49 tests
.venv/bin/python -m api.export               # writes frontend/data/sample.js (see below)
.venv/bin/python -m api.server               # http://127.0.0.1:8000: the frontend + JSON API
```

Individual runs: `python -m simulation.run_baseline [--mode naive]`,
`python -m simulation.run_corridor [--no-recovery]`. Run everything from the repo root.

## What the numbers say (24 seeds, 80 background vehicles)

| Mode | Transit (s) | Against no preemption |
| --- | --- | --- |
| No preemption | 307.9 ± 4.0 | reference |
| Naive reactive | 260.8 ± 7.4 | −47.1 ± 5.4 |
| Corridor, no recovery | 259.8 ± 6.8 | −48.0 ± 4.7 |
| Corridor + recovery | 259.8 ± 7.0 | −48.1 ± 5.1 |

Any preemption saves the ambulance about 15%. In this simulator the predictive
corridor is **not** distinguishable from the naive reactive baseline on transit
time, and neither mode, nor recovery, produces a measurable change in
background delay (paired differences stay within ±0.5 s of a 68 s average).
Corridor mode also lets signals stay non-green longer (38 s against 32 s for
naive). See [docs/RESULTS.md](docs/RESULTS.md) for the sweeps and why.

## Layout

```text
├── network/      # synthetic grid, signals, stop-line queues
├── simulation/   # engine (one tick loop, four RunModes), Scenario, background traffic
├── core/         # router, ETA predictor, corridor coordinator, recovery
├── metrics/      # per-run metrics, CIs, multi-seed sweeps, ETA accuracy
├── viz/          # matplotlib charts (comparison, red/green Gantt, ETA, sweeps)
├── api/          # replay exporter + stdlib JSON/static server
├── frontend/     # replay UI: index.html + app.js, Cobalt theme, light/dark (see its README)
├── tests/        # pytest suite
└── docs/         # build plan, decisions, results, report chapters, report status
```

## Start here

- [CLAUDE.md](CLAUDE.md) — project brief. [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) — steps and status.
- [docs/DECISIONS.md](docs/DECISIONS.md) — architecture and modelling decisions.
- [docs/REPORT-STATUS.md](docs/REPORT-STATUS.md) — progress against the UCS503L report structure.
- [docs/report/](docs/report/) — report chapters. [docs/MENTOR-PREP.md](docs/MENTOR-PREP.md) — mentor brief.
