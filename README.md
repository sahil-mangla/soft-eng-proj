# Predictive Green Corridor System

A simulation-first system that predicts an ambulance's route and per-junction
arrival time, coordinates a "green corridor" of traffic signals ahead of it, and
eases signals back to normal timing after it passes — instead of the abrupt
detect-and-snap-back behavior of existing reactive Emergency Vehicle Preemption
(EVP) systems.

This is a simulation (not a hardware integration): it proves the coordination and
recovery algorithms work and produces a clear before/after comparison against a
naive reactive baseline.

## Start Here

- [CLAUDE.md](CLAUDE.md) — full project brief (problem, MVP scope, algorithms, tech
  stack candidates, what's out of scope).
- [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) — step-by-step execution plan, in order.
- [docs/DECISIONS.md](docs/DECISIONS.md) — architecture/tech-stack decisions log.
- [docs/report/](docs/report/) — academic project report (Chapter 1: Introduction,
  Chapter 2: Feasibility Study), written for this project.

## Status

Repo scaffold only. No implementation yet — pending the decisions in
[docs/DECISIONS.md](docs/DECISIONS.md).

## Project Layout

```
├── network/      # road network generation (synthetic grid / OSM import)
├── simulation/   # baseline vs corridor simulation runners, background traffic
├── core/         # router, ETA predictor, corridor coordinator, recovery logic
├── metrics/      # transit-time / delay evaluation
├── viz/          # comparison charts
└── docs/         # build plan, decisions log, project report
```
