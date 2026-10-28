"""Writes a self-contained sample (default scenario replay + a multi-seed
comparison) as frontend/data/sample.js, so the frontend opens straight from
disk, or as a static site, without the API server.

    python -m api.export [--seeds 12] [--out frontend/data/sample.js]
"""

import argparse
import json
import os

from api.replay import build_replay
from metrics.sweep import ALL_MODES, _jsonable, compare_modes
from simulation.scenario import Scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--out", default="frontend/data/sample.js")
    args = parser.parse_args()

    scenario = Scenario()
    replay = build_replay(scenario)
    compare = {
        "seeds": args.seeds,
        "modes": _jsonable(compare_modes(scenario, list(range(args.seeds)), ALL_MODES)),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("window.__REPLAY__=" + json.dumps(replay, separators=(",", ":")) + ";\n")
        f.write("window.__COMPARE__=" + json.dumps(compare, separators=(",", ":"), default=str) + ";\n")
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
