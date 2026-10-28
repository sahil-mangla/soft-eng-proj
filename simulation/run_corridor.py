"""Runs the same scenario as run_baseline.py, but with predictive green-corridor
coordination (core/corridor_coordinator.py) and graceful recovery
(core/recovery.py) active. --no-recovery drops the recovery step, for the
with/without-recovery ablation.

Run from the repo root:  python -m simulation.run_corridor [--no-recovery]

See docs/BUILD-PLAN.md Steps 4-5.
"""

import argparse

from simulation.cli import add_scenario_args, run_and_report, scenario_from_args
from simulation.engine import RunMode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-recovery", action="store_true")
    add_scenario_args(parser)
    args = parser.parse_args()
    mode = RunMode.CORRIDOR_NO_RECOVERY if args.no_recovery else RunMode.CORRIDOR_RECOVERY
    run_and_report(scenario_from_args(args), mode)


if __name__ == "__main__":
    main()
