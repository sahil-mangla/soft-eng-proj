"""Local server for the frontend: serves frontend/ as static files and the
simulation as JSON. Standard library only (D3: no extra dependencies).

    python -m api.server [--port 8000]

  GET /api/replay?seed=42&vehicles=80&hold=15&horizon=60&recovery=2&slew=&trigger=200
      -> four-mode replay of one scenario (see api/replay.py)
  GET /api/compare?seeds=12&vehicles=80&...
      -> multi-seed means with 95% CIs for every mode (metrics/sweep.py)
  GET /api/suite
      -> the last `python -m metrics.sweep` output, if present

Binds to localhost only. Parameter ranges are clamped so one request cannot
ask for an unbounded amount of simulation.
"""

import argparse
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from api.replay import build_replay
from metrics.sweep import ALL_MODES, _jsonable, compare_modes
from simulation.scenario import Scenario

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT, "frontend")
SUITE_PATH = os.path.join(ROOT, "outputs", "sweep_results.json")


def _num(q: dict, key: str, cast, lo, hi, default):
    raw = q.get(key, [""])[0]
    if raw == "":
        return default
    try:
        return min(max(cast(raw), lo), hi)
    except ValueError:
        raise ValueError(f"{key} must be a number")


def scenario_from_query(q: dict) -> Scenario:
    slew_raw = q.get("slew", [""])[0]
    slew = None if slew_raw in ("", "off", "none") else min(max(float(slew_raw), 0.02), 1.0)
    d = Scenario()
    return Scenario(
        grid_size=_num(q, "grid", int, 3, 8, d.grid_size),
        background_vehicles=_num(q, "vehicles", int, 0, 400, d.background_vehicles),
        seed=_num(q, "seed", int, 0, 10_000, d.seed),
        corridor_horizon_s=_num(q, "horizon", float, 10, 180, d.corridor_horizon_s),
        corridor_max_hold_s=_num(q, "hold", float, 0, 40, d.corridor_max_hold_s),
        recovery_cycles=_num(q, "recovery", int, 0, 6, d.recovery_cycles),
        reactive_trigger_m=_num(q, "trigger", float, 50, 400, d.reactive_trigger_m),
        slew_rate=slew,
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "GreenCorridor/1.0"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, separators=(",", ":"), default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path == "/api/replay":
                return self._json(build_replay(scenario_from_query(q)))
            if url.path == "/api/compare":
                seeds = _num(q, "seeds", int, 2, 40, 12)
                result = compare_modes(scenario_from_query(q), list(range(seeds)), ALL_MODES)
                return self._json({"seeds": seeds, "modes": _jsonable(result)})
            if url.path == "/api/suite":
                if not os.path.exists(SUITE_PATH):
                    return self._json({"error": "run python -m metrics.sweep first"}, HTTPStatus.NOT_FOUND)
                with open(SUITE_PATH) as f:
                    return self._json(json.load(f))
        except ValueError as e:
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
        return self._static(url.path)

    def _static(self, path: str):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        full = os.path.realpath(os.path.join(FRONTEND_DIR, rel))
        if not full.startswith(os.path.realpath(FRONTEND_DIR) + os.sep) or not os.path.isfile(full):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Serving http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
