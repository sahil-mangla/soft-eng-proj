# Appendix B – UML and Data Flow Diagrams (DFD, Use Case, Activity, Sequence, Class)

> The pre-implementation notation set that supports [Chapter 6 – System Design](Chapter6-System-Design.md). The class diagram (D9) has been updated to match the code as built; the others describe the intended design, with changes noted in Chapter 6.

The formal design-notation set for the pre-implementation review: how data
moves through the system, what a user/agent can actually do, how one
simulation run unfolds step by step, how the modules talk to each other with
a clock attached, and the static shape of the classes that will implement
[CLAUDE.md](../../CLAUDE.md) §5–6. Where Appendix A's D1–D4 were informal
architecture sketches, these five are the standard SE documentation set,
drawn in **PlantUML**.

PlantUML doesn't render inline on GitHub the way Appendix A's Mermaid diagrams
do — view these with the PlantUML VS Code/JetBrains extension, `plantuml.com`'s
online server, or a local `plantuml.jar` + Graphviz install.

Companion docs: [CLAUDE.md](../../CLAUDE.md) · [BUILD-PLAN.md](../BUILD-PLAN.md)
· [DECISIONS.md](../DECISIONS.md) · [Appendix-A-Design-Sheets.md](Appendix-A-Design-Sheets.md)

Scope note: all five diagrams model the MVP as scoped in
[CLAUDE.md](../../CLAUDE.md) §3 — synthetic grid network, single ambulance,
three run modes (no-preemption baseline, naive-reactive, predictive
corridor + recovery). OSM import and SUMO are deferred per
[DECISIONS.md](../DECISIONS.md) D1/D2 and are not represented here.

---

## D5 — Data Flow Diagram

### D5a — Context Diagram (Level 0)

The whole system as one process. The only external entity for the MVP is the
person running scenarios — the ambulance and background traffic are
simulated *inside* the system, not real-world data sources, so they don't
appear as external entities here (contrast with the Use Case diagram below,
where they matter as actors).

```plantuml
@startuml D5a-context
skinparam rectangle {
  BackgroundColor<<process>> #1f7a4c
  FontColor<<process>> white
  BorderColor<<process>> #14532d
}
skinparam shadowing false

actor "Simulation\nOperator" as OP

rectangle "0\nPredictive Green\nCorridor System" <<process>> as P0

OP --> P0 : scenario config\n(grid size, A/B points,\ntraffic density, run mode)
P0 --> OP : comparison report\n(transit time, avg delay,\nsignal-state timeline)
@enduml
```

### D5b — Level 1 Decomposition

Process 0 opened up into the eight processes that correspond 1:1 with the
modules in [CLAUDE.md](../../CLAUDE.md) §5. This is the diagram that should
make the project structure self-evident: every arrow here is a function
call or return value that `core/*.py` and `simulation/*.py` will implement.

```plantuml
@startuml D5b-level1
skinparam rectangle {
  BackgroundColor<<process>> #1f7a4c
  FontColor<<process>> white
  BorderColor<<process>> #14532d
}
skinparam database {
  BackgroundColor #f5f5f5
}
skinparam shadowing false
left to right direction

actor "Simulation\nOperator" as OP

rectangle "1.0\nGenerate Network\n(generate_grid.py)" <<process>> as P1
rectangle "2.0\nSimulate Traffic\n(traffic_agents.py,\nrun_baseline/run_corridor)" <<process>> as P2
rectangle "3.0\nCompute Route\n(router.py)" <<process>> as P3
rectangle "4.0\nPredict ETA\n(eta_predictor.py)" <<process>> as P4
rectangle "5.0\nCoordinate Corridor\n(corridor_coordinator.py)" <<process>> as P5
rectangle "6.0\nRecover Signal\n(recovery.py)" <<process>> as P6
rectangle "7.0\nEvaluate Metrics\n(evaluate.py)" <<process>> as P7
rectangle "8.0\nVisualize\n(plots.py)" <<process>> as P8

database "D1\nNetwork Graph" as D1
database "D2\nVehicle/Tick Log" as D2
database "D3\nRoute" as D3
database "D4\nETA Predictions" as D4
database "D5\nSignal Schedule" as D5
database "D6\nComparison Report" as D6

OP --> P1 : scenario config
P1 --> D1 : junctions, edges,\nsignal plans

D1 --> P2
P2 --> D2 : positions, speed,\nsignal state per tick

D1 --> P3
D2 --> P3 : ambulance position
P3 --> D3 : shortest-time route

D3 --> P4
D2 --> P4 : ambulance position/speed
P4 --> D4 : ETA per junction\n(updated every tick)

D4 --> P5
D1 --> P5
P5 --> D5 : scheduled green,\nbounded ≤ X s
D5 --> P2 : signal override

D2 --> P6 : junction-cleared event
P6 --> D5 : phase-shift schedule\n(1-2 cycles)
D5 --> P2

D2 --> P7 : full tick log,\nall 3 run modes
P7 --> D6 : transit time,\navg background delay

D6 --> P8
D2 --> P8 : signal-state timeline
P8 --> OP : charts

@enduml
```

**Reading it:**
- **D5 (Signal Schedule) is written by two different processes** — 5.0
  (Coordinate Corridor) and 6.0 (Recover Signal) — and both write back into
  the same store that 2.0 (Simulate Traffic) reads from every tick. That
  shared store is the mechanism behind Appendix A's "two write paths into the
  signal, not one."
- **4.0 (Predict ETA) sits in a cycle with 2.0**, not a one-shot pipeline —
  it's fed the ambulance's position every tick and re-emits a sharper ETA
  each time, per [CLAUDE.md](../../CLAUDE.md) §6.2.
- **7.0 only ever reads D2**, never writes to a live store the simulation
  consumes — same "metrics observe, never influence" guarantee as
  Appendix A's D1.

---

## D6 — Use Case Diagram

Actors: the human **Simulation Operator**, plus the **Ambulance** and
**Background Traffic** as simulated actors that drive the system from
inside the simulation loop (per the project's own scope, there is no live
GPS feed or real driver — CLAUDE.md §8 — so "Ambulance" here means the
simulated agent, not a real vehicle).

```plantuml
@startuml D6-usecase
left to right direction
skinparam packageStyle rect

actor "Simulation\nOperator" as Operator
actor "Ambulance\n(simulated agent)" as Ambulance
actor "Background\nTraffic\n(simulated agents)" as Traffic

rectangle "Predictive Green Corridor System" {
  usecase "Configure Scenario" as UC1
  usecase "Select Run Mode\n(baseline / naive-reactive /\ncorridor+recovery)" as UC2
  usecase "Run Simulation" as UC3
  usecase "Generate Background\nCongestion" as UC4
  usecase "Compute Ambulance Route" as UC5
  usecase "Predict Junction ETA" as UC6
  usecase "Coordinate Green Corridor" as UC7
  usecase "Apply Naive Reactive\nPreemption" as UC8
  usecase "Recover Signal Timing" as UC9
  usecase "View Comparison Metrics" as UC10
  usecase "View Signal-State\nTimeline" as UC11
}

Operator --> UC1
Operator --> UC2
Operator --> UC3
Operator --> UC10
Operator --> UC11

Traffic --> UC4
Ambulance --> UC5

UC3 ..> UC4 : <<include>>
UC3 ..> UC5 : <<include>>
UC3 ..> UC6 : <<include>>
UC5 ..> UC6 : <<include>>

UC3 ..> UC7 : <<extend>>\n[mode = corridor+recovery]
UC3 ..> UC8 : <<extend>>\n[mode = naive-reactive]
UC7 ..> UC9 : <<include>>

UC10 ..> UC3 : <<include>>
@enduml
```

**Reading it:**
- **UC7/UC8 are mutually exclusive extends** on the same base use case —
  this is the diagram-level statement that corridor+recovery and
  naive-reactive are alternate modes over the same "Run Simulation" scaffold,
  never active together, matching [BUILD-PLAN.md](../BUILD-PLAN.md) Steps
  4–6.
- **Recover Signal Timing is only reachable through Coordinate Green
  Corridor**, never standalone — recovery has no meaning without a prior
  preemption to recover from.
- **The Ambulance and Background Traffic actors only trigger generation/
  routing use cases** — they never touch "View Comparison Metrics" or
  "Configure Scenario", which stay Operator-only, keeping the human/agent
  boundary explicit.

---

## D7 — Activity Diagram: One Full Simulation Run (Corridor + Recovery Mode)

Swimlanes separate what the Operator triggers, what the simulation loop
does every tick, what the two novel algorithms decide, and what happens
once at the end. This is the same control flow as
[BUILD-PLAN.md](../BUILD-PLAN.md) Steps 2–8, drawn as one continuous run.

```plantuml
@startuml D7-activity
|Operator|
start
:Configure scenario\n(network, A/B, traffic density);
:Select mode = corridor + recovery;
:Start simulation;

|Simulation Engine|
:Generate network (grid);
:Spawn background traffic;
:Spawn ambulance at A;

repeat
  :Advance one tick;
  :Move background traffic\nper current signal states;
  :Update ambulance position;

  |Core Algorithms|
  if (Route stale or\nnot yet computed?) then (yes)
    :Compute shortest-time route (Router);
  else (no)
  endif
  :Predict ETA at each\nupcoming junction (ETA Predictor);

  if (Upcoming junction within\ncorridor horizon?) then (yes)
    :Corridor Coordinator schedules\ngreen phase, capped at ≤ X s;
    :Apply schedule to junction signal;
  else (no)
  endif

  if (Ambulance just cleared\na junction?) then (yes)
    :Recovery Manager begins\nphase-shift interpolation;
    :Advance junction toward\nnormal cycle over 1-2 cycles;
  else (no)
  endif

  |Simulation Engine|
  :Log tick (positions, signal\nstates, delays) to run log;
repeat while (Ambulance reached B?) is (no)
->yes;

|Simulation Engine|
:Stop simulation, close run log;

|Metrics & Viz|
:Compute transit time\nand avg background delay;
:Compare against baseline\nand naive-reactive runs;
:Render signal-state timeline\nand comparison charts;

|Operator|
:View comparison report;
stop
@enduml
```

**Reading it:**
- **The route-recompute check is conditional, not every tick** — routing
  only reruns when conditions change materially, per
  [CLAUDE.md](../../CLAUDE.md) §6.1, while ETA prediction runs every tick
  unconditionally (§6.2).
- **The corridor-scheduling and recovery branches are independent
  conditions inside the same tick**, not sequential stages — a tick can
  schedule a green for a *future* junction while simultaneously running
  recovery on a junction the ambulance just cleared behind it.
- **Metrics/Viz only run once, after the loop exits** — confirming, at the
  activity level, the same "observes but never influences" separation as
  D5's data-store reads.

---

## D8 — Sequence Diagram: Detailed Module Interaction

A more complete version of Appendix A's D2, showing route computation,
the repeating ETA/corridor loop, junction crossing, recovery, and the
metrics handoff in one trace — this is the contract
`core/*.py` and `simulation/*.py` need to satisfy.

```plantuml
@startuml D8-sequence
participant "Simulation\nEngine" as SIM
participant "Router" as RT
participant "ETA\nPredictor" as ETA
participant "Corridor\nCoordinator" as CC
participant "Junction\nSignal (J1)" as J
participant "Recovery\nManager" as REC
participant "Metrics\nEvaluator" as MET

SIM -> RT : compute_route(network, A, B)
RT --> SIM : route [J1, J2, J3, ...]

loop every tick until ambulance reaches B
  SIM -> ETA : predict(route, position, speed)
  ETA --> SIM : ETA(J1)=42s (sharpens each tick)

  SIM -> CC : schedule(J1, eta=42s)
  CC -> CC : check cap: adjustment ≤ X s?
  CC -> J : apply_schedule(extend/truncate, target=42s)

  alt ambulance reaches J1 this tick
    SIM -> J : ambulance passes through
    J -> REC : junction_cleared(J1, offset=Δ)
    REC -> J : begin_recovery(Δ, cycles=2)
    loop each subsequent cycle
      REC -> J : interpolate(Δ → 0)
    end
    note over J : resumes normal fixed-cycle timing
  end

  SIM -> SIM : log tick (position, signal state, delay)
end

SIM -> MET : evaluate(run_log)
MET --> SIM : transit_time, avg_delay
@enduml
```

**Reading it:**
- **`compute_route` happens once before the loop**, but the loop itself
  never calls it again unless conditions force a recompute (elided here for
  clarity, shown explicitly as a branch in D7) — ETA prediction, not
  routing, is what runs unconditionally every tick.
- **The `alt` block is where D5's shared Signal Schedule store cashes out
  in real time**: Corridor Coordinator and Recovery Manager both send
  messages to the same Junction Signal object, at different points in the
  same trace.
- **Metrics Evaluator is called exactly once, after the loop**, never
  inside it — reinforcing the same boundary from D5/D7 at the message
  level.

---

## D9 — Class Diagram

The static shape the modules in [CLAUDE.md](../../CLAUDE.md) §5 are
expected to take. Method signatures are illustrative — exact interfaces
will settle during [BUILD-PLAN.md](../BUILD-PLAN.md) Steps 1–7 — but the
class boundaries and relationships are the actual design commitment.

```plantuml
@startuml D9-class
skinparam classAttributeIconSize 0

class Vehicle {
  +id: str
  +route: list[str]
  +edge_index: int
  +distance_into_edge_m: float
  +speed_mps: float
  +counts_toward_congestion: bool
  +finished_tick: float
}
class Ambulance extends Vehicle {
  counts_toward_congestion = false
}
class BackgroundVehicle extends Vehicle

class RoadNetwork {
  +junctions: dict[str, Junction]
  +edges: dict[(str,str), Edge]
  +graph: DiGraph
  +spacing_m: float
  +discharge_headway_s: float
  +xy(junction_id)
  +position_xy(u, v, distance)
  +edge(u, v)
}
class Junction {
  +id: str
  +row: int
  +col: int
  +signal: Signal
}
class Edge {
  +axis: "NS" | "EW"
  +length_m: float
  +free_flow_speed_mps: float
  +vehicle_count: int
  +queue: list[str]
  +next_release_t: float
  +current_speed_mps()
}
class Signal {
  +cycle_plan: CyclePlan
  +phase_offset_shift: float
  +state_for_axis(axis, t)
  +best_shift_for_green(axis, arrival_t, max_shift, lo, hi, anchor)
}
class CyclePlan {
  +green_duration: float
  +yellow_duration: float
  +phase_at(t)
  +nongreen_remaining(axis, t)
}
enum SignalState {
  RED
  YELLOW
  GREEN
}

class Route {
  +junction_ids: list[str]
  +edges: list[Edge]
  +total_length_m()
}
class ETAPredictor {
  +predict(route, edge_index, distance_into_edge): dict[str, float]
}
class CorridorCoordinator {
  +horizon_s: float
  +max_hold_s: float
  +slew_rate: float?
  +coordinate(t, etas, axes, dt)
}
class RecoveryManager {
  +recovery_cycles: int
  +begin_recovery(junction_id, signal)
  +step(junction_id, signal, dt)
  +is_recovering(junction_id)
  +any_active()
}
enum RunMode {
  NO_PREEMPTION
  NAIVE_REACTIVE
  CORRIDOR_NO_RECOVERY
  CORRIDOR_RECOVERY
}
class SimulationEngine {
  +mode: RunMode
  +route: Route
  +ambulance: Ambulance
  +background_vehicles: list
  +run(): RunLog
  -_set_shift(junction_id, target)
  -_admissible(junction_id, old, candidate)
  -_maybe_reroute()
}
class RunLog {
  +ticks: list[TickRecord]
  +frames: list[Frame]
  +ambulance_transit_time_s
  +background_delays_s
  +eta_samples
  +max_nongreen_s
  +reroutes
}
class Scenario <<dataclass>> {
  +grid_size, edge_length_m, background_vehicles
  +seed, arterial_share, reroute
  +corridor_horizon_s, corridor_max_hold_s
  +recovery_cycles, slew_rate, reactive_trigger_m
}
class MetricsEvaluator {
  +summarize(log): ModeMetrics
  +compare(runs): ComparisonReport
}
class "metrics.sweep" as Sweep <<module>> {
  compare_modes(scenario, seeds, modes)
  sweep_parameter(base, name, values, seeds, modes)
  run_standard_suite(seeds, base)
}
class "api.server.Handler" as Handler {
  GET /api/replay
  GET /api/compare
  GET /api/suite
  GET static files
}

SimulationEngine "1" *-- "1" RoadNetwork
SimulationEngine "1" *-- "1" Ambulance
SimulationEngine "1" *-- "*" BackgroundVehicle
SimulationEngine "1" *-- "1" RunLog
SimulationEngine "1" --> "1" RunMode
SimulationEngine "1" *-- "1" CorridorCoordinator
SimulationEngine "1" *-- "1" RecoveryManager
SimulationEngine "1" *-- "1" ETAPredictor
SimulationEngine ..> Route : recomputes
RoadNetwork "1" *-- "*" Junction
RoadNetwork "1" *-- "*" Edge
Junction "1" *-- "1" Signal
Signal "1" *-- "1" CyclePlan
Signal ..> SignalState
CorridorCoordinator ..> Signal : writes shift\n(via engine guard)
RecoveryManager ..> Signal : eases shift\n(via engine guard)
ETAPredictor ..> Route : reads
Scenario ..> SimulationEngine : build_engine()
MetricsEvaluator ..> RunLog : reads
Sweep ..> Scenario
Sweep ..> MetricsEvaluator
Handler ..> Sweep
Handler ..> Scenario
@enduml
```

**Reading it:**
- **`CorridorCoordinator` and `RecoveryManager` both depend on `Signal`,
  never on each other** — they're decoupled the same way D5's data store
  and D8's `alt` block show, communicating only through the signal object's
  state, not directly.
- **`RunMode` is a single field on `SimulationEngine`**, not a subclass
  hierarchy — baseline, naive-reactive, and corridor+recovery are one
  engine with conditional behavior, not three separate simulator classes.
  This keeps Step 6's naive-reactive baseline and Step 4-5's corridor mode
  sharing the same tick loop, which is what makes the three-way comparison
  in [CLAUDE.md](../../CLAUDE.md) §7 fair.
- **`Ambulance` and `BackgroundVehicle` share the `Vehicle` base** but only
  `Ambulance` is ever passed to `Router`/`ETAPredictor`/`CorridorCoordinator`
  — background traffic is a `RoadNetwork` congestion input, never a
  preemption target, consistent with [CLAUDE.md](../../CLAUDE.md) §8's
  single-ambulance scope.

---

**Next step:** [BUILD-PLAN.md](../BUILD-PLAN.md) Step 1 —
`network/generate_grid.py`, now with both the informal (Appendix A) and
formal (this appendix) design set in place before implementation starts.
