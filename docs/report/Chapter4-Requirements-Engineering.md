# Chapter 4 – Requirements Engineering

## 4.1 Requirement Elicitation

The users of this system are researchers and evaluators running a simulation, not a public user base, so interview- and questionnaire-based elicitation was not appropriate and was **not** used. The techniques actually used were:

| Technique | What it produced |
| --- | --- |
| **Existing-system and literature analysis** | The two weaknesses of reactive preemption (short detection horizon, abrupt recovery), the ~200 m reactive trigger distance used for the baseline, and the published improvement figures (Chapter 1.3, Chapter 2) |
| **Analysis of the project brief** (`CLAUDE.md`) | The MVP scope, the eight system modules, the metrics, and the definition of done (FR-01 to FR-12) |
| **Mentor-meeting preparation** (`docs/MENTOR-PREP.md`) | The open questions about scope and success criteria. The answers were not recorded, so no requirement here is attributed to them |
| **Prototype review with the project owner** | Three interface prototypes were compared, which fixed the interface requirements (FR-14, NFR-06) |
| **Evaluation-driven elicitation** | Reviews found requirements nobody had written down: the cross-traffic wait bound (FR-06), signal safety (FR-07), re-routing (FR-03) and input validation (FR-15). Each is traced to the defect or finding that revealed it (Chapter 10.5) |

## 4.2 Functional Requirements

Priority: **M** must, **S** should. "Verified by" points to tests described in Chapters 9 and 10.

| ID | Requirement | Pri | Verified by |
| --- | --- | --- | --- |
| FR-01 | The system shall generate an N × N grid road network (3 ≤ N ≤ 8) of signalised junctions, each with its own fixed-cycle signal. | M | `test_network`, TC-19, TC-20 |
| FR-02 | The system shall generate background traffic that is identical for the same seed in every control mode. | M | `test_traffic`, `test_engine::test_background_population_is_identical_across_modes` |
| FR-03 | The system shall route the ambulance by shortest travel time and shall recompute the route when the remainder becomes at least 10% faster. | M | `test_core` (router), `test_engine::test_ambulance_reroutes_*` |
| FR-04 | The system shall predict the ambulance's arrival at every upcoming junction and update the prediction every tick. | M | `test_core` (ETA), `test_engine::test_eta_error_shrinks_*` |
| FR-05 | The system shall schedule green at each junction within the look-ahead horizon, timed to the predicted arrival, never shifting a signal by more than the maximum hold. | M | `test_core` (coordinator), TC-24 to TC-26 |
| FR-06 | In corridor modes, no signal shall show a non-green to one direction for longer than the fixed cycle's own stretch plus the maximum hold. | M | `test_engine::test_corridor_never_starves_*`, TC-24 to TC-26 |
| FR-07 | No signal change caused by preemption shall skip a yellow phase. | M | `test_engine::test_signals_never_skip_a_yellow`, TC-27, TC-31 |
| FR-08 | After the ambulance clears a junction, the system shall ease that junction back to its cycle over a configured number of cycles; junctions that were never shifted shall not enter recovery. | M | `test_core` (recovery), TC-28 to TC-30 |
| FR-09 | The system shall run four control modes (no preemption, naive reactive, corridor without recovery, corridor with recovery) on identical scenarios. | M | `test_engine`, TC-32, TC-33 |
| FR-10 | The system shall report ambulance transit time, average and 95th-percentile background delay, longest non-green wait, and ETA error by time to junction. | M | `test_engine`, `test_viz_cli_server` |
| FR-11 | The system shall compare modes over many seeds, with means, 95% confidence intervals and differences paired by seed; runs that did not finish shall be left out and counted. | M | `test_engine::test_estimates_*`, TC-34 |
| FR-12 | The system shall draw comparison, signal-state timeline, ETA and sweep charts. | S | `test_viz_cli_server::test_every_chart_is_written` |
| FR-13 | The system shall provide an HTTP interface: replay, multi-seed comparison, last sweep, and the frontend files. | M | `test_api`, TC-33 to TC-37 |
| FR-14 | The frontend shall let the user choose a scenario, replay a run, switch modes, inspect a junction, compare over seeds, export results, and choose a light or dark appearance. | M | `frontend/tests/smoke.mjs` (ST-01 to ST-18, 19 checks) |
| FR-15 | The system shall reject non-numeric and non-finite parameters with a clear error and clamp numbers to their valid range. | M | TC-01 to TC-18, `test_api` |

## 4.3 Non-Functional Requirements

| ID | Category | Requirement | Target | Measured (Chapter 10) |
| --- | --- | --- | --- | --- |
| NFR-01 | Performance | A single simulation run completes quickly | under 2 s at 400 vehicles | 64 ms |
| NFR-02 | Performance | The four-mode replay is served to the interface | under 1 s for the default scenario | about 0.2 s (0.95 s at 400 vehicles) |
| NFR-03 | Performance | A 12-seed comparison (48 runs) returns interactively | under 5 s | about 0.2 s with the shared process pool |
| NFR-04 | Reliability | Runs are deterministic for a given scenario and seed | identical results on repeat | `test_runs_are_deterministic` |
| NFR-05 | Reliability | No parameter combination inside the valid ranges crashes the system | no crash at any boundary | TC-10 to TC-26 |
| NFR-06 | Usability | The interface is keyboard operable, has visible focus, supports reduced motion, works at 390 px width, and has no horizontal scrolling | all four hold | Hallmark and Impeccable checks clean; ST-07, ST-17 |
| NFR-07 | Security | The server is reachable from the local machine only, serves only the frontend folder, and accepts only GET | loopback bind; traversal refused | `test_the_server_listens_on_loopback_only`, TC-37 |
| NFR-08 | Maintainability | Modules have one job and tests cover them | at least 90% statement coverage | 98.2% statements, 96.2% branches |
| NFR-09 | Portability | Runs with the standard Python distribution and pip packages only | no system packages | `requirements.txt`; tested on macOS, Python 3.15 |
| NFR-10 | Accuracy | The ETA error shrinks as the ambulance approaches | error at arrival below error 60 s out | 0.5 s against 6.9 s |

## 4.4 User Requirements

From the point of view of a researcher or evaluator:

- **UR-01** I can set up a traffic scenario (how busy, how long the controller may hold a signal, how far ahead it looks) and run it without writing code.
- **UR-02** I can watch the ambulance cross the grid and see the signals ahead turn green, and I can scrub to any moment.
- **UR-03** I can switch between the four control modes at the same moment and see the difference.
- **UR-04** I can tell, in one sentence, what the run showed, and see whether the difference is real or within the noise.
- **UR-05** I can inspect any junction: what its signal showed, how far it was shifted, and how accurate the prediction was.
- **UR-06** I can export the numbers for a report, and I can reproduce them from the command line.
- **UR-07** I get a clear message when I enter something invalid.

## 4.5 System Requirements

- The simulation shall be implemented in Python and shall run as a command-line tool and as a local web service.
- The service shall return JSON; non-finite numbers shall be sent as `null`.
- The interface shall be a static page that uses the service, with a bundled sample so that it can also open from disk.
- All results shall be reproducible from a scenario and a seed.

## 4.6 Hardware Requirements

| Item | Requirement |
| --- | --- |
| Processor | Any 64-bit CPU. A single simulation uses one core; the multi-seed comparison uses a process pool, so more cores make it faster. Measured on a 10-core Apple-silicon laptop |
| Memory | Measured peak of about 200 MB for the whole process including replay builds; 1 GB free is a safe estimate (not separately tested on smaller machines) |
| Storage | Under 50 MB for the code and virtual environment, plus the generated outputs |
| Display | Any modern display; the interface adapts from 390 px to wide desktop |
| Network | None at run time; internet access is only needed to install packages and to load web fonts (system fonts are used if offline) |

## 4.7 Software Requirements

| Item | Requirement |
| --- | --- |
| Operating system | Developed and tested on macOS; nothing in the code is platform specific |
| Language | Python 3.13 or newer (tested on 3.15.0) |
| Libraries | `networkx`, `matplotlib` (run time); `pytest`, `pytest-cov` (testing) |
| Browser | A current Chrome, Edge, Firefox or Safari; the page uses CSS `oklch()` and `color-mix()` and degrades gracefully where `corner-shape` is missing |
| Browser test tooling (optional) | Node 18+, `puppeteer-core`, and Google Chrome, for `frontend/tests/smoke.mjs` |
| Deferred | SUMO and `traci`, `osmnx` (decisions D1 and D2, phase 2) |

## 4.8 Requirement Traceability

Every functional requirement above has at least one test; the table in 4.2 is the matrix. Objectives from Chapter 1.4 map to requirements as follows: objective 1 (transit time) to FR-09 and FR-10; objective 2 (background delay) to FR-10 and FR-11; objective 3 (ETA accuracy) to FR-04 and NFR-10; objective 4 (bounded disruption) to FR-05, FR-06 and FR-07; objective 5 (automated reporting) to FR-10 to FR-14.
