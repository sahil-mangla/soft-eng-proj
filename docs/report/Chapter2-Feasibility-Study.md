# Chapter 2 – Feasibility Study

## 2.1 Technical Feasibility

**Question: can the required technology support the system?** Yes, with mature,
widely-used open-source tools:

- **Simulation**: traffic simulation for exactly this kind of scenario (signalized
  junctions, vehicle flow, phase control) is a solved problem at the tooling
  level — either via a dedicated open-source microscopic traffic simulator with a
  Python control API, or via a custom lightweight discrete-event simulation
  written directly in Python. Both are well within reach of a student project;
  see [docs/DECISIONS.md](../DECISIONS.md) for which one this project uses.
- **Routing**: shortest-time path computation over a weighted graph is a standard
  graph algorithm (Dijkstra/A\*), available directly through common Python graph
  libraries.
- **Prediction**: the ETA prediction and corridor-scheduling logic required for
  the MVP are deterministic, heuristic (speed/density-based), not
  machine-learning-based — so no specialized ML infrastructure, training data, or
  GPU resources are needed.
- **Visualization**: plotting signal-state timelines and before/after comparison
  charts is standard charting-library work.
- **Team skill fit**: the project is implemented entirely in Python, a language
  the team already has proficiency in, which removes ramp-up time as a technical
  risk.

**Conclusion**: technically feasible with off-the-shelf, free tooling and no
hardware dependency.

## 2.2 Economic Feasibility

**Question: what are the development and operational costs?**

- **Development cost**: effectively $0 in licensing — every candidate component
  (simulation engine, graph/routing library, charting library, optional map-data
  library) is open-source and free to use. The only real cost is developer time.
- **Operational cost**: the system runs as a local simulation on a standard
  laptop; there is no server, cloud hosting, or paid API dependency required to
  run or demonstrate the MVP. If a real road-network extract is used, the map
  data source used is free and does not require a paid account for the volumes
  needed here.
- **Scaling cost (future)**: not a concern for this project's scope — any move
  toward a real deployment (hardware integration, live traffic-authority
  systems) would carry its own separate cost analysis, explicitly out of scope
  here (see Section 1.5/1.8).

**Conclusion**: economically feasible at $0 budget; the only resource consumed is
development time.

## 2.3 Operational Feasibility

**Question: can users practically operate the system?**

- At MVP stage, the "user" is the developer/evaluator running a simulation
  scenario and reading its output — there is no live operator, dispatcher, or
  traffic-control staff interacting with the system in real time, which keeps
  the operational burden low.
- Running a scenario is scripted (a runnable baseline script and a
  runnable corridor-mode script over the same configuration), so no specialized
  training is needed to reproduce a comparison.
- Output is automated (metrics + plots), removing manual data collection or
  interpretation burden from the user.
- If this were extended toward real operational use by a traffic authority, that
  would introduce a materially different operational-feasibility question
  (operator training, 24/7 reliability, integration with existing control-room
  workflows) — explicitly deferred, as this project only targets the simulation
  stage.

**Conclusion**: operationally feasible for its actual intended users (developer,
evaluators, researchers running comparative simulations).

## 2.4 Schedule Feasibility

**Question: can the system be developed within the semester?**

The MVP is intentionally scoped to be buildable incrementally, in the order laid
out in [docs/BUILD-PLAN.md](../BUILD-PLAN.md):

1. Repo scaffold, network generator, background traffic, ambulance router
   (foundation).
2. Baseline (no-preemption) simulation running end-to-end.
3. ETA prediction module.
4. Corridor coordination (predictive multi-junction preemption).
5. Recovery module (graceful reset).
6. Naive reactive-preemption baseline (for a three-way comparison).
7. Metrics + visualization, and the final before/after report.

Each stage produces a runnable artifact before the next is layered on, so
schedule risk is contained: even if later stages (corridor/recovery) run behind,
stages 1–2 alone already produce a working, demonstrable scaffold. This
incremental structure is what makes single-semester delivery realistic for a
student-sized team.

**Conclusion**: schedule-feasible, provided the phased build plan is followed in
order rather than attempting all modules in parallel.

## 2.5 Legal / Ethical Considerations

- The system uses only synthetic or publicly available open map data; no real
  personal data, real ambulance dispatch data, or real traffic-controller access
  is involved, so no data-privacy regulation applies at this stage.
- Because this is a **simulation**, not a live traffic-control deployment, none
  of its output ever affects a real signal, a real vehicle, or a real emergency
  response — it carries no real-world safety liability as built.
- Ethical note for any future extension: emergency-vehicle preemption is a
  safety-critical function in the real world. Were this project ever extended
  toward controlling real signal hardware, it would require formal safety
  testing, traffic-authority approval, and liability review before any live use
  — none of which is claimed or attempted here. This project's conclusions are
  scoped strictly to simulated performance comparisons.

**Conclusion**: no legal/ethical blockers for the project as scoped (simulation
only).

## 2.6 Feasibility Conclusion

Across all five dimensions — technical, economic, operational, schedule, and
legal/ethical — the Predictive Green Corridor System, scoped as a simulation-only
MVP built with free open-source Python tooling, is **feasible** to deliver within
a single academic semester by a student-sized team, at effectively zero monetary
cost, and without any legal or ethical blocker. The main risk is not feasibility
itself but sequencing: the phased build plan in
[docs/BUILD-PLAN.md](../BUILD-PLAN.md) must be followed in order so that a
working baseline exists early, with the more novel corridor-coordination and
recovery logic layered on top of a proven foundation rather than attempted all
at once.
