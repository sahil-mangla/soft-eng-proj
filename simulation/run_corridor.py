"""Runs the same scenario as run_baseline.py, but with predictive green-corridor
coordination (core/corridor_coordinator.py) and graceful recovery
(core/recovery.py) active. --no-recovery drops the recovery step, for the
with/without-recovery ablation.

Run from the repo root:  python -m simulation.run_corridor [--no-recovery]

See docs/BUILD-PLAN.md Steps 4-5.
"""

import argparse

from simulation.engine import RunMode
from simulation.scenario import Scenario, run_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-recovery", action="store_true")
    parser.add_argument("--grid-size", type=int, default=Scenario().grid_size)
    parser.add_argument("--background-vehicles", type=int, default=Scenario().background_vehicles)
    parser.add_argument("--seed", type=int, default=Scenario().seed)
    args = parser.parse_args()

    scenario = Scenario(
        grid_size=args.grid_size, background_vehicles=args.background_vehicles, seed=args.seed
    )
    mode = RunMode.CORRIDOR_NO_RECOVERY if args.no_recovery else RunMode.CORRIDOR_RECOVERY
    _, log = run_scenario(scenario, mode)

    print(f"Mode: {mode.value}")
    if log.ambulance_transit_time_s is None:
        print("Ambulance did not arrive within the tick limit")
    else:
        print(f"Ambulance transit time: {log.ambulance_transit_time_s:.1f} s")
    avg_delay = sum(log.background_delays_s) / max(1, len(log.background_delays_s))
    print(f"Avg background delay: {avg_delay:.1f} s over {len(log.background_delays_s)} vehicles")


if __name__ == "__main__":
    main()
