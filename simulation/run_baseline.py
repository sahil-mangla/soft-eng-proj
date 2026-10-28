"""Runs one ambulance agent from a start junction (A) to a destination (B)
through the network with NO preemption at all, alongside background traffic.
This is the control condition / working scaffold milestone.

Also supports --mode naive, which runs the naive-reactive preemption variant
(reacts only within ~200m, resets instantly) as the "existing systems"
comparison point (CLAUDE.md section 6.5).

Run from the repo root:  python -m simulation.run_baseline [--mode naive]

See docs/BUILD-PLAN.md Step 2.
"""

import argparse

from simulation.cli import add_scenario_args, run_and_report, scenario_from_args
from simulation.engine import RunMode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["none", "naive"], default="none")
    add_scenario_args(parser)
    args = parser.parse_args()
    mode = RunMode.NAIVE_REACTIVE if args.mode == "naive" else RunMode.NO_PREEMPTION
    run_and_report(scenario_from_args(args), mode)


if __name__ == "__main__":
    main()
