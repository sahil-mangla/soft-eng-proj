# Architecture & Tech-Stack Decisions

Log of decisions that materially shape the codebase. Anything here was chosen by
the project owner, not assumed by default — see [CLAUDE.md](../CLAUDE.md) §4 for
the candidate options each decision was drawn from.

Status: **D1–D3 decided** (2026-08-20). D4 deferred, non-blocking.

## D1 — Simulation engine

- **Options considered**: SUMO + `traci` (full-featured microscopic traffic
  simulator with real signal-phase control and OSM import) vs. a custom
  lightweight grid-based simulation in pure Python (simpler, faster to stand up,
  less realistic, no external simulator dependency).
- **Decision**: **Custom Python sim first, port to SUMO later.** Build and
  validate routing, ETA prediction, corridor coordination, and recovery on a
  pure-Python discrete-event grid simulation (no external system dependency).
  Once that logic is proven (Steps 1–7 in
  [BUILD-PLAN.md](BUILD-PLAN.md)), optionally port the same algorithms onto
  SUMO/traci for a more realistic final demo with a real GUI.
- **Rationale**: Fastest path to a working, debuggable scaffold; avoids
  front-loading SUMO's system-level install/setup risk before the core
  algorithms (the actual novel contribution) are even validated. SUMO is added
  later as a realism upgrade, not a blocking dependency for early milestones.
- **Consequence**: `network/generate_grid.py`, `simulation/*.py`, and `core/*.py`
  are implemented as plain Python/`networkx` first. A `traci`-based variant is a
  later, additive step — not a rewrite, since the module boundaries
  (router / eta_predictor / corridor_coordinator / recovery) stay the same
  regardless of which engine drives the simulation loop underneath.

## D2 — Road network data source

- **Options considered**: purely synthetic grid network (N×N junctions,
  generated in code) vs. a real road-network extract imported via OpenStreetMap
  (`osmnx`).
- **Decision**: **Synthetic grid first, real OSM extract later.** Default to a
  5×5 (configurable) generated grid for all development and algorithm
  validation; `network/osm_import.py` is implemented later as an optional
  addition for a "real city" demo once the algorithm works on synthetic data.
- **Rationale**: Synthetic data is fully controllable and easiest to debug
  (known junction count, known distances, reproducible). Matches D1's
  "prove-it-simple-first" sequencing.

## D3 — Python environment / dependency management

- **Options considered**: `venv` + `pip` + `requirements.txt` (simplest,
  matches the scaffolded repo structure) vs. Poetry (lockfile, stricter
  reproducibility) vs. Conda (useful if SUMO's system-level deps need it).
- **Decision**: **`venv` + `pip` + `requirements.txt`.**
- **Rationale**: Simplest option, no extra tooling ceremony, matches the
  `requirements.txt` already scaffolded in the repo root. Revisit only if/when
  the SUMO port (D1) turns out to need Conda for its system-level dependencies.

## D4 — Version control / remote hosting

- **Options considered**: local git only (already initialized in this repo) vs.
  also pushing to a hosted remote (e.g. GitHub) now.
- **Decision**: Local git only for now (already `git init`'d, no commits made
  yet). Non-blocking — add a remote whenever you're ready to push; ask if/when
  you want that set up.
- **Rationale**: Doesn't affect any implementation work; safe to defer.

---

`requirements.txt` and the module stubs have been updated to match D1–D3.
Step 0 in [BUILD-PLAN.md](BUILD-PLAN.md) is now unblocked — Step 1 (network
foundation) can start.
