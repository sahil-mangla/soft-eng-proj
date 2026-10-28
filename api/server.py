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
import atexit
import json
import math
import mimetypes
import os
import sys
import threading
from concurrent.futures import ProcessPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from api.replay import build_replay
from metrics.serialize import to_jsonable
from metrics.sweep import ALL_MODES, compare_modes
from simulation.scenario import Scenario

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT, "frontend")
SUITE_PATH = os.path.join(ROOT, "outputs", "sweep_results.json")


_pool: ProcessPoolExecutor | None = None
_pool_lock = threading.Lock()
_compare_slots = threading.Semaphore(2)  # at most two comparisons run at once; the rest wait


def _shared_pool() -> ProcessPoolExecutor:
    """One process pool for the whole server, so concurrent /api/compare requests
    share the CPUs instead of each spawning their own."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ProcessPoolExecutor(max_workers=os.cpu_count() or 2)
            atexit.register(_pool.shutdown, wait=False, cancel_futures=True)
        return _pool


def _finite(key: str, raw: str, cast):
    try:
        value = cast(raw)
    except (ValueError, OverflowError):
        raise ValueError(f"{key} must be a number")
    if not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    return value


def _num(q: dict, key: str, cast, lo, hi, default):
    raw = q.get(key, [""])[0]
    if raw == "":
        return default
    return min(max(_finite(key, raw, cast), lo), hi)


def scenario_from_query(q: dict) -> Scenario:
    slew_raw = q.get("slew", [""])[0]
    slew = None if slew_raw in ("", "off", "none") else min(max(_finite("slew", slew_raw, float), 0.02), 1.0)
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
        body = json.dumps(to_jsonable(payload), separators=(",", ":"), allow_nan=False).encode()
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
                scenario = scenario_from_query(q)
                with _compare_slots:
                    result = compare_modes(scenario, list(range(seeds)), ALL_MODES, executor=_shared_pool())
                return self._json({"seeds": seeds, "modes": result})
            if url.path == "/api/suite":
                if not os.path.exists(SUITE_PATH):
                    return self._json({"error": "run python -m metrics.sweep first"}, HTTPStatus.NOT_FOUND)
                with open(SUITE_PATH) as f:
                    return self._json(json.load(f))
        except ValueError as e:
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
        except Exception as e:  # a simulation bug must not drop the connection
            print(f"{self.path}: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json({"error": "The simulation failed for these settings."}, HTTPStatus.INTERNAL_SERVER_ERROR)
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
