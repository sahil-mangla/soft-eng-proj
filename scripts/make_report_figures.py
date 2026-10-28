"""Writes the report's charts from the real simulation and the last sweep.

    python -m scripts.make_report_figures        (after python -m metrics.sweep)
"""

import json
import os
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")

from metrics.eta_accuracy import eta_error_by_lead  # noqa: E402
from metrics.evaluate import MetricsEvaluator  # noqa: E402
from simulation.engine import RunMode  # noqa: E402
from simulation.scenario import Scenario, run_scenario  # noqa: E402
from viz.plots import plot_comparison, plot_eta_accuracy, plot_signal_timeline, plot_sweep  # noqa: E402

OUT = os.path.join("docs", "report", "figures")


def namespaced(obj):
    """JSON from the sweep back into attribute access, which plot_sweep expects."""
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: namespaced(v) for k, v in obj.items()}) if all(k.isidentifier() for k in obj) else {k: namespaced(v) for k, v in obj.items()}
    return obj


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    scenario = Scenario()
    runs, route = {}, None
    for mode in RunMode:
        engine, log = run_scenario(scenario, mode)
        runs[mode] = log
        route = engine.route.junction_ids
    plot_comparison(MetricsEvaluator().compare(runs), f"{OUT}/comparison.png")
    plot_signal_timeline(runs[RunMode.CORRIDOR_RECOVERY], route, f"{OUT}/signal-timeline-corridor.png")
    plot_signal_timeline(runs[RunMode.NO_PREEMPTION], route, f"{OUT}/signal-timeline-baseline.png")
    plot_eta_accuracy({m: eta_error_by_lead(runs[m]) for m in (RunMode.NO_PREEMPTION, RunMode.CORRIDOR_RECOVERY)}, f"{OUT}/eta-accuracy.png")

    with open(os.path.join("outputs", "sweep_results.json")) as f:
        suite = json.load(f)

    def sweep(section):
        return {k: {m: namespaced(v) for m, v in modes.items()} for k, modes in suite[section].items()}

    plot_sweep(sweep("load"), "transit", "background vehicles", f"{OUT}/sweep-load.png", "Ambulance transit time by traffic load")
    plot_sweep(sweep("max_hold"), "transit", "max hold (s)", f"{OUT}/sweep-max-hold.png", "Ambulance transit time by max hold")
    plot_sweep(sweep("max_hold"), "max_nongreen", "max hold (s)", f"{OUT}/sweep-max-hold-wait.png", "Mean longest non-green wait by max hold (worst case equals 26 + hold)")
    plot_sweep(sweep("arterial"), "transit", "share of traffic on the ambulance's corridor", f"{OUT}/sweep-arterial.png", "Transit time with arterial demand (200 vehicles, no re-routing)")
    plot_sweep(sweep("arterial"), "max_nongreen", "share of traffic on the ambulance's corridor", f"{OUT}/sweep-arterial-wait.png", "Longest non-green wait with arterial demand")
    print("figures written to", OUT, sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
