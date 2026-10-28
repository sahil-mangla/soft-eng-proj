"""The one place the single-run command-line tools build a scenario from flags,
run a mode, and report it — through MetricsEvaluator, so the numbers are the
same ones demo.py and the sweeps print."""

import argparse

from metrics.evaluate import MetricsEvaluator
from simulation.engine import RunMode
from simulation.scenario import Scenario, run_scenario


def add_scenario_args(parser: argparse.ArgumentParser) -> None:
    defaults = Scenario()
    parser.add_argument("--grid-size", type=int, default=defaults.grid_size)
    parser.add_argument("--background-vehicles", type=int, default=defaults.background_vehicles)
    parser.add_argument("--seed", type=int, default=defaults.seed)


def scenario_from_args(args: argparse.Namespace) -> Scenario:
    return Scenario(grid_size=args.grid_size, background_vehicles=args.background_vehicles, seed=args.seed)


def run_and_report(scenario: Scenario, mode: RunMode) -> None:
    _, log = run_scenario(scenario, mode)
    m = MetricsEvaluator().summarize(log)
    print(f"Mode: {mode.value}")
    if log.ambulance_transit_time_s is None:
        print("Ambulance did not arrive within the tick limit")
    else:
        print(f"Ambulance transit time: {m.transit_s:.1f} s")
    print(f"Avg background delay: {m.avg_delay_s:.1f} s over {len(log.background_delays_s)} vehicles")
