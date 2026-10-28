"""Runs all four modes (no-preemption, naive-reactive, corridor without
recovery, corridor + recovery) on the same scenario and prints/plots the
comparison — the MVP "definition of done" from CLAUDE.md section 3.

Usage: python demo.py [--seed N] [--vehicles N] [--out DIR]
"""

import argparse
import os

from metrics.eta_accuracy import eta_error_by_lead
from metrics.evaluate import MetricsEvaluator
from simulation.engine import RunLog, RunMode
from simulation.scenario import Scenario, run_scenario
from viz.plots import plot_comparison, plot_eta_accuracy, plot_signal_timeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=Scenario().seed)
    parser.add_argument("--vehicles", type=int, default=Scenario().background_vehicles)
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    scenario = Scenario(seed=args.seed, background_vehicles=args.vehicles)
    runs: dict[RunMode, RunLog] = {}
    route_ids: list[str] = []
    for mode in RunMode:
        engine, log = run_scenario(scenario, mode)
        runs[mode] = log
        route_ids = engine.route.junction_ids

    report = MetricsEvaluator().compare(runs)
    print(f"Scenario: {scenario.grid_size}x{scenario.grid_size} grid, {scenario.background_vehicles} "
          f"background vehicles, seed {scenario.seed}\n")
    print(f"{'Mode':<24}{'Transit (s)':>12}{'Avg delay (s)':>15}{'p95 delay (s)':>15}{'Max non-green (s)':>19}")
    for mode, m in report.metrics.items():
        print(f"{mode.label:<24}{m.transit_s:>12.1f}{m.avg_delay_s:>15.1f}{m.p95_delay_s:>15.1f}{m.max_nongreen_s:>19.1f}")
    print("\nOne seed is one traffic draw. For means with confidence intervals: python -m metrics.sweep")

    plot_comparison(report, os.path.join(args.out, "comparison.png"))
    plot_signal_timeline(runs[RunMode.CORRIDOR_RECOVERY], route_ids, os.path.join(args.out, "signal_timeline.png"))
    plot_signal_timeline(runs[RunMode.NO_PREEMPTION], route_ids, os.path.join(args.out, "signal_timeline_baseline.png"))
    plot_eta_accuracy(
        {m: eta_error_by_lead(runs[m]) for m in (RunMode.NO_PREEMPTION, RunMode.CORRIDOR_RECOVERY)},
        os.path.join(args.out, "eta_accuracy.png"),
    )
    print(f"Charts written to {args.out}/")


if __name__ == "__main__":
    main()
