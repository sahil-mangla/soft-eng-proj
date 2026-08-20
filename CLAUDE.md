# Predictive Green Corridor System — Project Context

This file is the canonical project brief. Claude Code (and any contributor) should
read this before working on the codebase. See also [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md)
for the step-by-step execution plan and [docs/DECISIONS.md](docs/DECISIONS.md) for the
architecture/tech-stack decisions this project has committed to.

## 1. What We're Building

A simulation-first system that predicts an emergency vehicle's (ambulance) route and
arrival time at each upcoming traffic signal, coordinates a "green corridor" ahead of
it across multiple junctions, and then intelligently restores normal signal timing
after it passes (instead of an abrupt reset).

This is **not** hardware integration with real traffic controllers (yet). The MVP is a
**simulated environment** that proves the algorithm works, produces visualizable
output, and can later be adapted to real signal APIs.

## 2. Core Problem Being Solved

Existing Emergency Vehicle Preemption (EVP) systems are mostly **reactive**: they
detect a vehicle only ~150-300m before an intersection and flip the signal
immediately, causing abrupt disruption to cross-traffic, and they "snap back" to
normal timing just as abruptly once the vehicle passes.

Our contribution is two algorithmic pieces that are still open problems in the
literature:
1. **Predictive, multi-junction coordination** — not just the next signal, but a
   corridor of signals timed ahead of the vehicle's predicted arrival.
2. **Graceful recovery** — after the vehicle passes each junction, ease the signal
   back into its normal cycle rather than an instant reset, to reduce secondary
   disruption to regular traffic.

## 3. MVP Scope (what to actually build first)

Build a **discrete-event traffic simulation**, not a live system. Concretely:

1. A synthetic or lightweight real road network (grid or small real-world extract)
   with junctions, each with a signal that has a fixed-cycle timing plan
   (red/green/yellow durations).
2. Background traffic flow (simple car agents moving on the network, generating
   "normal" congestion).
3. One ambulance agent with a start point (A) and destination (B, e.g. hospital).
4. A routing module that computes the fastest path from A to B given current network
   conditions.
5. An ETA prediction module that estimates the ambulance's arrival time at each
   junction along the route, updated as the ambulance moves (i.e., it should
   re-predict as new position data comes in, not just once at t=0).
6. A corridor coordination module that, for each junction ahead of the ambulance,
   schedules a green phase timed to the predicted arrival — subject to constraints
   (e.g. don't hold a junction green so long it starves a perpendicular direction
   beyond some threshold).
7. A recovery module that, once the ambulance clears a junction, transitions that
   junction back to its normal fixed-cycle timing smoothly (e.g. phase-shift back
   over N cycles) rather than an instant jump.
8. Metrics/output: ambulance transit time (with vs without corridor), average delay
   imposed on background traffic (with vs without corridor + with vs without
   recovery logic), and some visualization (even simple — a timeline chart or 2D
   grid animation) showing signal states over time.

**Definition of done for MVP**: running the simulation twice — once with baseline
reactive/no preemption, once with the predictive corridor + recovery — and getting a
clear before/after comparison on both ambulance transit time and background traffic
delay.

## 4. Suggested Tech Stack

- **Simulation engine**: Use **SUMO** (Simulation of Urban MObility) via its Python
  API (`traci`) — it's the standard open-source tool for exactly this kind of traffic
  modeling, has real signal-phase control, and can import real road networks from
  OpenStreetMap. This avoids building a traffic simulator from scratch.
  - Alternative if SUMO setup is too heavy for a first pass: a custom lightweight
    grid-based simulation in Python (simpler, faster to get a demo working, less
    realistic).
- **Language**: Python for the simulation, routing, and prediction/coordination logic.
- **Routing**: `networkx` for graph representation and shortest-path / time-weighted
  path computation. If using SUMO, it also has built-in routing (`duarouter`) that
  can be used or replaced with a custom weighted algorithm.
- **Visualization**: SUMO has a built-in GUI (`sumo-gui`) for real-time visualization.
  For custom charts (ambulance ETA vs actual, delay comparisons), use `matplotlib` or
  `plotly`.
- **Data**: Start with a synthetic grid network (easiest to control and debug).
  Optionally pull a real small road network via OpenStreetMap (`osmnx`) for a
  "real city" demo once the algorithm works on synthetic data.

> **Status**: the engine choice (SUMO vs custom grid) and a few other stack
> questions are open decisions — see [docs/DECISIONS.md](docs/DECISIONS.md).

## 5. Project Structure

```
soft-eng-proj/
├── CLAUDE.md                 # this context file
├── README.md
├── requirements.txt
├── docs/
│   ├── BUILD-PLAN.md
│   ├── DECISIONS.md
│   └── report/
│       ├── Chapter1-Introduction.md
│       └── Chapter2-Feasibility-Study.md
├── network/
│   ├── generate_grid.py      # builds synthetic grid network (or SUMO .net.xml)
│   └── osm_import.py         # optional: real road network import
├── simulation/
│   ├── run_baseline.py       # simulation with no preemption / naive reactive preemption
│   ├── run_corridor.py       # simulation with predictive corridor + recovery
│   └── traffic_agents.py     # background traffic generation
├── core/
│   ├── router.py             # fastest-path computation for ambulance
│   ├── eta_predictor.py      # per-junction ETA prediction, updated over time
│   ├── corridor_coordinator.py  # schedules green phases ahead of ambulance
│   └── recovery.py           # graceful signal recovery logic after vehicle passes
├── metrics/
│   └── evaluate.py           # computes transit time, avg delay, comparison stats
└── viz/
    └── plots.py              # before/after comparison charts
```

## 6. Key Algorithms to Implement (in order)

1. **Shortest-time routing** (not shortest-distance) — weight edges by current travel
   time given traffic density, recompute if conditions change materially.
2. **ETA prediction per junction** — given ambulance speed/position and route,
   estimate seconds-to-arrival at each upcoming junction; update this prediction on a
   rolling basis (e.g. every simulation tick or every N meters traveled), not just
   once.
3. **Green corridor scheduling** — for each junction on the route, decide when to
   switch to/hold green so it aligns with predicted arrival, while bounding how long
   perpendicular traffic gets held (this is the core novel logic — start with a
   simple threshold-based rule, e.g. "extend current phase or truncate the opposing
   phase by at most X seconds," before attempting anything more sophisticated).
4. **Recovery scheduling** — after the ambulance clears a junction, don't instantly
   force the signal back to its scheduled fixed-cycle position; instead interpolate
   back over the next 1-2 cycles so vehicles queued during preemption clear out
   first, then resume normal timing.
5. **Baseline comparison mode** — implement a naive reactive baseline (signal only
   reacts within ~200m of the vehicle, and resets instantly after) so the demo can
   show clear "before vs after" numbers.

## 7. What "Good" Looks Like for a First Demo

- A short script or notebook that runs both baseline and corridor-mode simulations on
  the same scenario (same network, same background traffic, same ambulance
  start/end) and prints/plots:
  - Ambulance total transit time (corridor mode should be meaningfully lower).
  - Average delay to background traffic (corridor mode with recovery should NOT be
    dramatically worse than baseline, ideally better than naive-reactive
    preemption).
  - A visualization of signal states along the corridor over time (even a simple
    Gantt-style chart of red/green per junction, with the ambulance's position
    overlaid).

## 8. Explicitly Out of Scope for Now

- Real hardware/V2X integration with actual traffic controllers.
- Real-time live GPS feed ingestion (simulate GPS instead).
- Multi-ambulance conflict resolution (handle one emergency vehicle at a time first).
- Machine-learning-based traffic prediction (use simple density/speed-based
  heuristics first; ML can come later once the core pipeline works).

## 9. Reference Points / Why This Matters (for context, not implementation)

- Deployed EVP systems already show 14-50% response time improvements and up to 70%
  fewer EV-involved collisions in field studies — this validates that preemption in
  general works; our contribution is smarter coordination and recovery, not proving
  the basic concept.
- Research specifically on proactive preemption + recovery phases has shown up to 43%
  reduction in non-emergency traffic delay compared to reactive approaches, with the
  recovery phase alone contributing up to ~21% of that improvement — this is the gap
  we're targeting.
