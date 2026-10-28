# Chapter 11 – Deployment and Maintenance

## 11.1 Deployment Environment

The system is a **local research tool**: it is installed and run on one machine, and nothing is hosted (Chapter 1.5, 1.7).

| Component | Where it runs | Notes |
| --- | --- | --- |
| Simulation, metrics, charts | A Python process on the user's machine | No network needed at run time |
| Local service | `python -m api.server`, listening on `127.0.0.1:8000` | Loopback only; no authentication because it is not reachable from other machines |
| Interface | Any current browser, loading `http://127.0.0.1:8000/` | Web fonts load from the internet if available; system fonts are used otherwise |
| Static fallback | `frontend/` plus `data/sample.js` | The interface also opens from disk or from any static host, showing one fixed sample run; scenarios cannot be changed without the service |

Reference configuration used for the measurements in Chapter 10: macOS on Apple silicon (10 logical CPUs), Python 3.15.0, Chrome.

## 11.2 Installation Procedure

From the repository root:

```bash
# 1. Create the environment and install
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Check the installation (about 12 seconds)
.venv/bin/python -m pytest -q                 # expect: 121 passed

# 3. Run the demo (four modes, one seed, charts written to outputs/)
.venv/bin/python demo.py

# 4. Make the sample data for the interface, then start the service
.venv/bin/python -m api.export
.venv/bin/python -m api.server                # http://127.0.0.1:8000
```

Optional, for the browser tests: install Node 18 or newer, run `npm i puppeteer-core` in any folder, start the service, then `PUPPETEER_DIR=<that folder> node frontend/tests/smoke.mjs` (expect: 19 of 19 checks pass).

**Verifying the install.** The demo prints a table of four modes; the interface shows "Live run, seed 42" in its top bar.

**Reproducing the report's numbers.**

```bash
.venv/bin/python -m metrics.sweep --seeds 24          # outputs/sweep_results.json (a few minutes)
.venv/bin/python -m scripts.make_report_figures        # docs/report/figures/
.venv/bin/python -m scripts.blackbox_report            # docs/report/generated/blackbox-results.md
.venv/bin/python -m scripts.benchmark                  # docs/report/generated/benchmark.md
.venv/bin/python -m pytest --cov                       # coverage
```

**Problems met in practice**

| Symptom | Cause | Fix |
| --- | --- | --- |
| `.venv/bin/python: no such file` after a system Python upgrade | The virtual environment pointed at a Python that was removed | Recreate it: `python3 -m venv --clear .venv` and reinstall |
| `ModuleNotFoundError: network` when running a script directly | Scripts are modules | Run from the repository root with `python -m simulation.run_baseline` |
| The page says "Sample run" although the service is running | The page was opened from disk, not from the service | Open `http://127.0.0.1:8000/` |
| An old behaviour after changing the code | The running service still has the old code loaded | Stop it (`pkill -f api.server`) and start it again |
| `RuntimeError` about bootstrapping when using the sweep functions from your own script | The process pool needs a main guard on macOS | Put the call under `if __name__ == "__main__":` |
| Charts fail on a machine with no display | matplotlib backend | `MPLBACKEND=Agg` |

## 11.3 User Manual

![The interface](figures/ui-light.png)

**The screen.** Left: *Scenario*. Centre: the *Replay* (mode buttons, verdict, signal grid, controls) and the *signal timeline*. Right: the *mode table*, the *across-seeds* results and the *ETA error* table. A *junction detail* panel appears at the top of the right column when you open a junction.

**Common tasks**

| I want to… | Do this |
| --- | --- |
| Try busier or quieter traffic | Press *Light*, *Typical* or *Rush hour* in the Scenario panel; the scenario re-runs |
| Change a setting | Edit a field, then press *Run scenario*. Until you do, the page says the replay still shows the last run |
| Watch the ambulance cross | Press *Play* (or the space bar). Use the slider or click the signal timeline to jump; choose 1×, 4× or 16× |
| Compare control modes at the same moment | Press a mode button; the time stays where it is. Arrow keys move between modes |
| Read what the run showed | The dark *verdict* panel states the transit time, the saving against no preemption, the background delay, and the longest wait |
| See whether a difference is real | Press *Compare over 12 seeds*. The table gives means with 95% intervals and paired differences; one bar per seed shows the spread. A sentence in the verdict says whether background delay is distinguishable from no preemption |
| Understand one junction | Click it (or focus it and press Enter). Press Escape to close; focus returns to the junction |
| Keep the numbers | Press *Export CSV* |
| Share a view | Copy the address: it records the scenario, mode, speed and time (`?seed=7&vehicles=200&mode=naive_reactive&t=150`) |
| Change appearance | *Light*, *Dark* or *System* in the top bar |

**Reading the grid.** Each junction has two bars: vertical for north-south, horizontal for east-west, coloured green, yellow or red (red is also dashed). A dashed ring means the controller has shifted that junction's phase. A blue-tinted road is the ambulance's route; the **+** marker is the ambulance. Small dots are background vehicles, and darker dots are stopped. The numbers beside junctions ahead are seconds until the predicted arrival.

**Command line**

| Command | Purpose |
| --- | --- |
| `python demo.py [--seed N --vehicles N --out DIR]` | Four-mode comparison and charts for one seed |
| `python -m simulation.run_baseline [--mode naive]` | One run without preemption, or naive reactive |
| `python -m simulation.run_corridor [--no-recovery]` | One corridor run |
| `python -m metrics.sweep --seeds N [--vehicles N --out DIR]` | Multi-seed comparison and the whole parameter suite |
| `python -m api.server [--port N]` | The service and interface |
| `python -m api.export [--seeds N --out FILE]` | The bundled sample |

**Service parameters** (query string for `/api/replay` and `/api/compare`): `seed`, `vehicles`, `grid`, `hold`, `horizon`, `recovery`, `trigger`, `slew`, `arterial`, `reroute`, and `seeds` for the comparison. Valid ranges are in Chapter 8.5.

## 11.4 Maintenance Strategy

| Type | What it means here | How it is handled |
| --- | --- | --- |
| **Corrective** | Fixing defects | Each defect is logged with its cause, correction and the test that guards it (Chapter 10.5); a fix is not accepted until a test that failed before it passes. Nineteen defects were handled this way during development |
| **Adaptive** | Keeping up with the environment | The environment already broke once, when a Python upgrade orphaned the virtual environment (11.2). Mitigations: a short `requirements.txt`, no web framework, no build step, and a documented rebuild. Browser features used by the page degrade gracefully where missing. When the simulator is ported to SUMO (decision D1), the module boundaries (router, ETA, coordinator, recovery) are kept so the port replaces the engine only |
| **Perfective** | Improving what works | New scenarios and parameters go through `Scenario` and the sweep suite, so a new experiment is a few lines; the report's numbers and charts regenerate from commands (11.2) |
| **Preventive** | Reducing the chance of future defects | 121 automated tests and a 90% coverage target; properties tested over every frame; modelling decisions recorded in `docs/DECISIONS.md`; both design linters run on the interface. Recommended next: run the tests automatically on every commit (continuous integration) and pin dependency versions |

## 11.5 Future Enhancements

1. **Port to SUMO** (decision D1, phase 2) for realistic car-following, lane changes and signal controllers; the main test is whether the corridor's advantage under arterial demand (Chapter 12.2) holds up and grows.
2. **Let the ambulance overtake queues.** The model makes the ambulance wait in the queue like any vehicle, which makes heavy demand look worse for preemption than it is in reality.
3. **Calibrate against real data**: real signal plans, flows and speeds for a real network (OpenStreetMap import, decision D2).
4. **Add the missing controller rules**: minimum green, an all-red interval, pedestrian phases.
5. **Adaptive base plans** instead of fixed cycles, and more than one ambulance (currently out of scope).
6. **Continuous integration** and a pinned dependency lock file.
7. **Frontend improvements**: tests in more than one browser, a scenario for arterial demand and re-routing in the form, shareable stored results.
