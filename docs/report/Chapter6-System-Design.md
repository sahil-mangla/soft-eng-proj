# Chapter 6 – System Design

The notation set drawn before implementation is kept in [Appendix A](Appendix-A-Design-Sheets.md) (design sheets) and [Appendix B](Appendix-B-UML-and-DFD.md) (DFD, use case, activity, sequence and class diagrams in PlantUML). This chapter describes the design **as built**; where the build differs from the early drawings, the difference is noted.

## 6.1 System Architecture

```mermaid
flowchart TB
    U(["Researcher / Evaluator"])
    subgraph PRES["Presentation layer: frontend/ (browser)"]
        UI["index.html, app.js, styles<br/>map, timeline, ledger, junction detail"]
    end
    subgraph APP["Application layer: api/ (Python, local HTTP)"]
        H["server.py<br/>GET /api/replay, /api/compare, /api/suite, static files"]
        RP["replay.py<br/>runs the four modes and packs the frames"]
    end
    subgraph DOM["Domain layer: simulation, core, network"]
        ENG["simulation/engine.py<br/>one tick loop, four RunModes, guarded shift writes"]
        COR["core/<br/>router, ETA predictor, corridor coordinator, recovery"]
        NET["network/generate_grid.py<br/>grid, signals, edges, queues"]
        TRF["simulation/traffic_agents.py<br/>vehicles, queues, arterial demand"]
    end
    subgraph MET["Evaluation layer: metrics, viz"]
        M["evaluate.py, sweep.py, eta_accuracy.py, serialize.py"]
        V["viz/plots.py"]
    end
    subgraph DATA["Stored artefacts (no database)"]
        F["frontend/data/sample.js<br/>outputs/sweep_results.json<br/>CSV exports, PNG charts"]
    end
    U --> UI --> H --> RP --> ENG
    H --> M
    ENG --> COR --> NET
    ENG --> TRF --> NET
    M --> ENG
    V --> M
    M --> F
    UI -. file:// fallback .-> F
```

Reading it top to bottom: the user works in the browser; the page calls the local service; the service builds scenarios and asks the engine to run them; the engine uses the domain modules; metrics are computed from the run logs; results can be written to files.

## 6.2 Architectural Design

Four architectural ideas are combined, each chosen for a reason:

| Style | Where | Why |
| --- | --- | --- |
| **Layered** | The four layers in 6.1; each depends only on the one below | A change to the interface cannot break the simulation, and the simulation can be run from the command line with no web code at all |
| **Client–server (local)** | Browser and Python service over HTTP and JSON | The simulation needs Python and `networkx`; the interface needs a browser. A thin JSON interface keeps them independent (decision F1) |
| **Pipeline of small modules** | Router → ETA predictor → coordinator → recovery, all driven by one engine | The brief names these as separate algorithms to build in order; each has its own tests, and a SUMO port could replace the engine without rewriting them (decision D1) |
| **Single write path with guards** | Every phase shift goes through `SimulationEngine._set_shift` | Signal safety and the cross-traffic bound are enforced in **one** place, so no mode can bypass them by accident (decisions M6, M7) |

A design choice that matters for fairness: all four modes run through the **same** tick loop and differ only in how a signal's `phase_offset_shift` gets set. The comparison between modes therefore compares control strategies, not simulators.

## 6.3 UML Diagrams

The full PlantUML set is in Appendix B. The diagrams below are the as-built versions most relevant to the design.

### Class diagram

See Appendix B, diagram D9, rewritten to match the code (vehicles, network, signals, engine, coordinator, recovery, scenario, metrics, API).

### Component diagram

```mermaid
flowchart LR
    subgraph Browser
        APPJS["app.js"]
    end
    subgraph Python["Python process (api.server)"]
        HANDLER["Handler"]
        REPLAY["replay.build_replay"]
        SWEEP["sweep.compare_modes"]
        ENGINE["SimulationEngine"]
        POOL[("shared<br/>process pool")]
    end
    APPJS -- "GET /api/replay" --> HANDLER --> REPLAY --> ENGINE
    APPJS -- "GET /api/compare" --> HANDLER --> SWEEP --> POOL --> ENGINE
```

### Sequence diagram: one simulation tick

```mermaid
sequenceDiagram
    participant E as SimulationEngine
    participant P as ETAPredictor
    participant C as CorridorCoordinator
    participant G as _set_shift (guard)
    participant S as Signal
    participant V as Vehicles
    E->>P: predict(route, position)
    P-->>E: seconds to each junction ahead
    alt corridor mode
        E->>C: coordinate(t, etas)
        C->>G: write shift for junction j
        G->>G: legal? (no skipped yellow) within the wait bound?
        G->>S: apply as far as admissible
    else naive reactive within 200 m
        E->>G: write shift
        G->>S: apply if legal
    end
    E->>E: ease recovering junctions, retry held-back resets
    E->>V: advance background vehicles, then the ambulance
    V-->>E: junction cleared?
    opt junction cleared
        E->>G: return its shift to zero (recovery or instant)
        E->>E: maybe reroute
    end
    E->>E: record tick and frame
```

### Activity diagram: one run

```mermaid
flowchart TD
    A([Scenario, mode, seed]) --> B[Build grid and signals]
    B --> C[Route the ambulance by shortest time]
    C --> D[Spawn background vehicles]
    D --> E{Ambulance arrived and all vehicles finished<br/>and signals back on schedule?}
    E -- no --> F[Predict arrivals]
    F --> G[Set shifts by mode, through the guard]
    G --> H[Move vehicles, queues drain 1 per 2 s]
    H --> I[Release cleared junctions, maybe reroute]
    I --> J[Record tick and frame]
    J --> E
    E -- yes --> K[Compute transit, delay per vehicle, longest wait, ETA error]
    K --> L([RunLog])
```

### State diagrams

**Signal phases** (one direction; the other is the mirror image half a cycle later). The legal changes caused by a shift are the same arrows; the three arrows that are *not* drawn (green to red, red to yellow, yellow to green) are refused by the guard.

```mermaid
stateDiagram-v2
    [*] --> Green
    Green --> Yellow: 20 s elapsed, or shift lands in yellow
    Yellow --> Red: 3 s elapsed
    Red --> Green: other direction's yellow ends
```

**Junction preemption and recovery** (per junction on the route):

```mermaid
stateDiagram-v2
    [*] --> OnSchedule
    OnSchedule --> Shifted: ETA inside look-ahead and a legal shift exists
    Shifted --> Shifted: ETA changes, shift adjusts (anchored, bounded)
    Shifted --> Recovering: ambulance cleared, recovery mode, shift not zero
    Shifted --> OnSchedule: ambulance cleared, no recovery, reset legal
    Shifted --> Shifted: reset held back until legal
    Recovering --> OnSchedule: shift decayed to zero after N cycles
    OnSchedule --> OnSchedule: ambulance cleared, never shifted
```

**Ambulance:**

```mermaid
stateDiagram-v2
    [*] --> Moving
    Moving --> Waiting: signal not open or queue ahead
    Waiting --> Moving: green, first in queue, 2 s headway
    Moving --> Rerouted: remainder 10% faster by another path
    Rerouted --> Moving
    Moving --> Arrived: last road finished
    Arrived --> [*]
```

### Deployment diagram

```mermaid
flowchart LR
    subgraph Laptop["Developer laptop (single machine)"]
        subgraph B["Browser"]
            PAGE["Static page and app.js"]
        end
        subgraph P["python -m api.server  (127.0.0.1:8000 only)"]
            SRV["ThreadingHTTPServer"]
            WORK["worker process pool<br/>(one per core)"]
        end
        FS[("Files:<br/>frontend/, outputs/, docs/")]
    end
    PAGE <-- "HTTP, JSON" --> SRV
    SRV --> WORK
    SRV --> FS
```

## 6.4 Database Design

**The system has no database, by decision.** Decision D3 chose the simplest toolchain (a virtual environment and pip). The data is regenerated from a scenario and a seed in milliseconds, and nothing needs to persist between runs, so a database would add install and migration cost and no benefit. No user accounts exist (Chapter 1.5), so there is nothing to store about people.

What does persist is files, and the logical data model is below. It is drawn as an ER diagram because that is how the data relates, even though it lives in memory and JSON, not tables.

```mermaid
erDiagram
    SCENARIO ||--o{ RUN : "is run in"
    RUN ||--|| RUN_METRICS : "summarised as"
    RUN ||--o{ FRAME : "records one per second"
    RUN ||--o{ ETA_SAMPLE : "logs predictions"
    RUN ||--o{ BACKGROUND_DELAY : "one per vehicle"
    SCENARIO ||--o{ SWEEP_CELL : "varied into"
    SWEEP_CELL ||--o{ MODE_SUMMARY : "holds one per mode"
    SCENARIO {
        int grid_size PK
        int seed PK
        int background_vehicles
        float arterial_share
        float corridor_max_hold_s
        float corridor_horizon_s
        int recovery_cycles
        float slew_rate
        bool reroute
    }
    RUN {
        string mode PK
        float transit_s
        float end_time_s
        int reroutes
    }
    RUN_METRICS {
        float avg_delay_s
        float p95_delay_s
        float max_nongreen_s
        int unfinished
    }
    FRAME {
        float t PK
        string ns_states
        string ew_states
        float_list shifts
        list ambulance_xy
        list background_xy
    }
    ETA_SAMPLE {
        float t PK
        string junction_id PK
        float predicted_arrival
    }
    BACKGROUND_DELAY {
        string vehicle_id PK
        float delay_s
    }
    SWEEP_CELL {
        string parameter PK
        string value PK
    }
    MODE_SUMMARY {
        string mode PK
        float transit_mean
        float transit_ci95
        float_list transit_samples
        int unfinished_runs
    }
```

**Keys.** Primary keys above are the natural keys of each record. Foreign keys are implicit in nesting: a run's frames sit inside the run's JSON object, and a sweep cell's summaries sit inside the cell. **Persisted files**:

| File | Content | Written by |
| --- | --- | --- |
| `frontend/data/sample.js` | One four-mode replay and one 12-seed comparison, as two JavaScript assignments | `python -m api.export` (not committed; regenerated) |
| `outputs/sweep_results.json` | The full sweep suite, strict JSON (non-finite numbers are `null`) | `python -m metrics.sweep` |
| `*.csv` | The mode table and the across-seeds table | *Export CSV* in the interface |
| `outputs/*.png`, `docs/report/figures/*.png` | Charts | `demo.py`, `scripts/make_report_figures.py` |

## 6.5 Data Flow Diagrams

**Level 0 (context).**

```mermaid
flowchart LR
    R(["Researcher / Evaluator"]) -- "scenario parameters" --> S(("Predictive Green<br/>Corridor System"))
    S -- "replay, metrics, charts, CSV" --> R
```

**Level 1.**

```mermaid
flowchart LR
    R(["Researcher"]) -- "parameters" --> P1(("1<br/>Validate<br/>and clamp"))
    P1 -- "Scenario" --> P2(("2<br/>Run modes"))
    P2 -- "RunLog per mode" --> P3(("3<br/>Compute<br/>metrics"))
    P3 -- "metrics, samples" --> P4(("4<br/>Package<br/>and serve"))
    P4 -- "JSON" --> P5(("5<br/>Render<br/>in browser"))
    P5 -- "views, CSV" --> R
    P3 --> D1[("D1 sweep_results.json")]
    P4 --> D2[("D2 sample.js")]
    D1 --> P4
```

**Level 2 for process 2 (Run modes).** The tick loop of 6.3: predict, set shifts through the guard, move vehicles, release and reroute, record. The formal Level 1 and Level 2 diagrams drawn before the build are in Appendix B (D5).

## 6.6 Interface Design

The interface is a single working screen, a tool people operate rather than a page they read, so the design follows the conventions of dashboards: a top bar, a scenario panel on the left that stays in view, the replay in the centre, and results on the right. Three complete prototypes were built on the same renderer and compared (Cobalt, Blueprint, Coral); the project owner chose **Cobalt**.

![The interface, light appearance, with the 12-seed comparison and a junction's details open](figures/ui-light.png)

*Figure 6.1: Desktop, light appearance.*

| Region | Purpose | Design decision |
| --- | --- | --- |
| **Scenario rail** (left, fixed on scroll) | Presets and fields, grouped as Traffic, Corridor controller, Reactive baseline | Presets (Light, Typical, Rush hour) switch the load in one click; edits that have not been run are flagged |
| **Mode buttons** | Choose the control mode, each showing its transit time | The answer is on the control, not only in a table |
| **Verdict readout** (dark panel) | One sentence on what the run showed, with the multi-seed verdict once compared | The finding comes first, in the largest type on the page |
| **Signal grid** | The replay | Signals drawn large; dashed rings where the controller shifted the phase; a live countdown to the predicted arrival on junctions ahead; red uses a dashed line as well as colour |
| **Signal timeline** | State of each route junction's approach over time | Green, yellow and red with a hatched red; the ambulance's path drawn through it; click to seek |
| **Mode table, across-seeds table, per-seed bars** | Numbers and their spread | Differences are coloured by whether they helped; the bars show the seed-to-seed spread behind each average |
| **Junction detail** | Why one junction behaved as it did | Opens on click or Enter; Escape closes it and returns focus |

![Dark appearance](figures/ui-dark.png)

*Figure 6.2: Dark appearance (Light, Dark and System are offered; the choice is remembered in the browser).*

**States.** Every region that loads data has four states: *loading* (a skeleton grid), *error* (the server's reason, and *Try again*), *sample* (bundled data when opened from disk, with the limits explained) and *full*.

**Accessibility.** The page is keyboard operable; every interactive element has a visible focus ring; the mode switch is a radio group with arrow-key navigation, and the presets and appearance switch are labelled buttons; colours are never the only cue (signals also differ in line style, and the run state is stated in text); reduced-motion preferences switch off the count-up animation; the layout has no horizontal scrolling down to 390 px (ST-17).

![Phone width](figures/ui-mobile.png)

*Figure 6.3: Phone width (390 px). Tables scroll inside their panels.*

**Reference review.** Components from the ObsidianUI analytics dashboard and component library were reviewed (decision F2). Adopted: deltas coloured by whether they helped, rolling figures, scenario presets, a details panel that closes with Escape, status-bar strips (as the per-seed bars), export, and a light and dark setting. Not adopted: sparkline cards, sidebar pages, an assistant composer, and decorative motion.

## 6.7 Where the Build Differs from the Early Design

| Early design (Appendices A and B) | As built | Why |
| --- | --- | --- |
| Three run modes | Four (corridor without recovery added) | The recovery ablation the brief asks for needs it |
| `Signal.apply_schedule` and a `SignalSchedule` object | A single `phase_offset_shift` per signal, written through one guarded function | One mechanism lets recovery ease out of exactly what preemption put in, and puts the safety rules in one place |
| Route computed once | Recomputed on entering each road | CLAUDE.md 6.1 asks for it; the audit found it missing |
| Stop at the ambulance's arrival | Run until every vehicle finishes and signals are back on schedule | Delay must be measured over the same vehicles in every mode |
| No queue model | Stop-line queues, 2 s discharge | Without queues a late green costs nothing |
