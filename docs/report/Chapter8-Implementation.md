# Chapter 8 – Implementation

## 8.1 Technology Stack

| Concern | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.15 (3.13 or newer) | One language for the simulation, service, metrics and charts |
| Simulation | Custom discrete-time simulator (1 s tick) | Decision D1: proven first, SUMO later |
| Graph and routing | `networkx` 3.x | Shortest-time path with a custom edge weight |
| Charts | `matplotlib` 3.x | Comparison, timeline, ETA and sweep charts |
| Service | Python standard library (`http.server`, `concurrent.futures`) | No web framework: one dependency fewer, nothing to learn or secure (decision F1) |
| Frontend | HTML, CSS, vanilla JavaScript, SVG | No build step. Design system: Cobalt (Hallmark), light and dark |
| Database | None | Section 6.4 |
| APIs | Own JSON API: `/api/replay`, `/api/compare`, `/api/suite` | Section 8.5 |
| Testing | `pytest`, `pytest-cov`, `puppeteer-core` with Chrome | Chapters 9 and 10 |
| Environment | `venv` and `pip` (decision D3) | `requirements.txt` |

## 8.2 Module-wise Implementation

| Module | Files | Responsibility |
| --- | --- | --- |
| **Network** | `network/generate_grid.py` | N × N grid (`RoadNetwork`), bidirectional edges with an axis (NS or EW), per-junction `Signal` and `CyclePlan` (20 s green, 3 s yellow, two phases), per-edge vehicle count and stop-line queue |
| **Traffic** | `simulation/traffic_agents.py` | One movement routine for every vehicle (the ambulance obeys the same signals unless a mode moves them); random-walk background traffic; arterial traffic along the ambulance's corridor; stop-line queue with first-in-first-out discharge |
| **Router** | `core/router.py` | Shortest-time path; the weight is length divided by the congestion-adjusted speed |
| **ETA predictor** | `core/eta_predictor.py` | Seconds to each junction ahead from position and current road speeds, recomputed every tick |
| **Corridor coordinator** | `core/corridor_coordinator.py` | For junctions inside the look-ahead, the smallest change to the phase shift that makes the approach green at the predicted arrival, bounded by the maximum hold; optional eased (rate-limited) shifts |
| **Recovery** | `core/recovery.py` | Decays a junction's shift linearly to zero over N cycles; skips junctions that were never shifted |
| **Engine** | `simulation/engine.py` | The tick loop for all four modes; the guarded write path; re-routing; the starvation tracker; recording of ticks and frames |
| **Scenario** | `simulation/scenario.py` | One configuration object used by the demo, the CLIs, sweeps and the API |
| **Metrics** | `metrics/evaluate.py`, `eta_accuracy.py`, `sweep.py`, `serialize.py` | Per-run summary, confidence intervals and paired differences, ETA error by time to junction, the standard sweep suite, JSON-safe output |
| **Charts** | `viz/plots.py`, `scripts/make_report_figures.py` | All figures |
| **Service** | `api/server.py`, `replay.py`, `export.py` | Replay packing, local HTTP service, sample export |
| **Frontend** | `frontend/index.html`, `app.js`, `structure.css`, `themes/cobalt/` | The interface |
| **Command line** | `demo.py`, `simulation/run_baseline.py`, `run_corridor.py`, `cli.py` | Single runs and the demo |

## 8.3 Important Algorithms

### Phase shift: the one control mechanism

Each signal shows `phase_at(t + shift)` of its fixed cycle. Every mode controls a junction only by setting this one number, which is what lets recovery ease out of exactly what preemption put in.

### Choosing a shift (`Signal.best_shift_for_green`)

```
candidates = all whole-second shifts in [-max_hold, +max_hold], plus the band edges and the current shift
sort candidates by distance from the current shift       # hysteresis (decision M4)
return the first candidate that makes the approach GREEN at the predicted arrival time,
       else the candidate that is closest to green (yellow beats red)
```

Ranking by distance from the **current** shift, not from zero, is what stopped a jittering arrival estimate from flipping a junction between −12 s and +11 s.

### The guarded write (`SimulationEngine._set_shift` and `_admissible`)

```
move toward the target one second at a time
for each step, accept the candidate shift only if
    (1) signal safety:  comparing what was displayed on the previous tick with what the
        candidate displays now, no direction goes green->red, red->yellow or yellow->green
    (2) wait bound (corridor modes only):  for each direction not green under the candidate,
        run_so_far + ceil(time until it is green again) <= (cycle - green) + max_hold
stop at the first refused step; the rest is attempted on later ticks
```

The wait bound uses `CyclePlan.nongreen_remaining`, a closed-form calculation of how long until a direction is next green. The naive reactive mode skips check (2) on purpose; it is the unbounded "existing system".

### Stop-line queue

A vehicle at the end of a road may cross only if its signal is open, nobody queued ahead of it is still waiting, and at least `discharge_headway_s` (2 s) have passed since the last crossing. The ambulance obeys the same rule. This is what gives a late green a cost: the queue built during red has not drained when the ambulance arrives.

### ETA prediction

For each remaining road, `remaining distance / current speed`, summed along the route and reported at each junction; speed falls as `1 / (1 + 0.15 × vehicles on the road)`. The ambulance does not count itself.

### Recovery

`shift(t) = initial_shift × (1 − elapsed / (cycles × cycle_length))`, written through the guard every tick. If a write is refused the target still keeps decaying, so the shift catches up once it is legal.

### Re-routing

When the ambulance enters a new road, the shortest-time path from the junction ahead is recomputed with current speeds; the route changes only if the remainder is at least 10% faster. Junctions on the abandoned path are released.

### Statistics

For `n` seeds, the mean and a 95% interval using Student's t critical values (1.96 beyond 30 degrees of freedom). Differences between modes are computed seed by seed (**paired**), which removes the large seed-to-seed variance in traffic. Runs where the ambulance did not arrive are excluded and counted.

## 8.4 Database Implementation

There is no database (Section 6.4). Persistence is by files written with the standard library: `sample.js` (replay), `sweep_results.json` (strict JSON, `allow_nan=False`), CSV from the browser, PNG from matplotlib. Because the simulation is deterministic, any result file can be regenerated from the scenario and seed it names.

## 8.5 Input Validation

All input arrives as URL query parameters at `/api/replay` and `/api/compare`, and is parsed by `api/server.py`:

| Parameter | Type | Valid range | Out of range | Not a finite number |
| --- | --- | --- | --- | --- |
| `seed` | int | 0 to 10 000 | clamped | 400 |
| `vehicles` | int | 0 to 400 | clamped | 400 |
| `grid` | int | 3 to 8 | clamped | 400 |
| `hold` (max hold, s) | float | 0 to 40 | clamped | 400 |
| `horizon` (look-ahead, s) | float | 10 to 180 | clamped | 400 |
| `recovery` (cycles) | int | 0 to 6 | clamped | 400 |
| `trigger` (reactive, m) | float | 50 to 400 | clamped | 400 |
| `slew` (eased shift) | float or `off` | 0.02 to 1.0 | clamped | 400 |
| `arterial` | float | 0 to 1 | clamped | 400 |
| `reroute` | int | 0 or 1 | clamped | 400 |
| `seeds` (compare) | int | 2 to 40 | clamped | 400 |

Clamping keeps one request from asking for an unbounded amount of simulation. NaN and infinity are rejected (not clamped) because they pass a clamp silently and then crash the simulation. Bounds take the parameter's own type (decision, BUG-17). Tests: TC-01 to TC-18.

On the page, number fields carry `min`, `max` and `step`, so the browser blocks out-of-range submission; values read from the URL are placed in fields as values, never as markup.

## 8.6 Exception and Error Handling

| Situation | Handling |
| --- | --- |
| Invalid parameter | `ValueError` becomes HTTP 400 with the parameter named; the page shows the reason (ST-16) |
| Unexpected failure inside a simulation | Logged to the server's error stream; the client gets HTTP 500 with a generic JSON message, never a dropped connection (`test_unexpected_failures_return_a_500_*`) |
| Ambulance does not arrive within the tick limit | Transit time is `None`; the CLI says so; aggregates skip the run and count it; JSON carries `null`; the page shows *n/a* |
| Start equals end | `ValueError` with a clear message |
| `recovery_cycles = 0` | Instant reset, no division by zero |
| A shift write refused by the guard | Applied as far as legal, finished on a later tick; a held-back reset keeps the run open until signals are back on schedule |
| Server unreachable (page) | Falls back to the bundled sample and says scenarios cannot be changed; if the server **rejects** input, its reason is shown instead (BUG-18) |
| Path outside the frontend folder, unknown file | HTTP 404 |
| Method other than GET | HTTP 501 |

## 8.7 Security Implementation

This is a single-user research tool with no accounts, so authentication, authorisation, passwords and sessions are out of scope (Chapter 1.5). The relevant controls are:

| Control | Implementation |
| --- | --- |
| **Network exposure** | The server binds to `127.0.0.1` only (`make_server`); it is not reachable from other machines (`test_the_server_listens_on_loopback_only`) |
| **Path traversal** | Requested paths are resolved and must stay inside `frontend/`; plain, encoded and `..` variants return 404 (TC-37, `test_static_files_and_unsupported_methods`) |
| **Methods** | Only GET is implemented; others get 501 |
| **Input sanitisation** | Strict parsing and clamping (8.5); NaN and infinity rejected |
| **Output encoding** | Error text and server messages are inserted with `textContent`, never as markup; URL parameters are placed in fields as values (ST-18) |
| **Resource limits** | Parameter clamps, at most two concurrent comparisons, one shared process pool (BUG-16) |
| **Session management** | None: state is in the URL; the only browser storage is the light or dark choice, in a `try` block so private windows still work |
| **Secrets and personal data** | None are used or stored |
