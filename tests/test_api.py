import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from api.replay import build_replay
from api.server import Handler, scenario_from_query
from simulation.scenario import Scenario


@pytest.fixture(scope="module")
def replay():
    return build_replay(Scenario(background_vehicles=20, seed=1))


def test_replay_shape(replay):
    assert set(replay["modes"]) == {"no_preemption", "naive_reactive", "corridor_no_recovery", "corridor_recovery"}
    assert len(replay["network"]["junctions"]) == 25
    assert len(replay["network"]["edges"]) == 40
    mode = replay["modes"]["corridor_recovery"]
    n = len(mode["frames"]["t"])
    assert n == len(mode["frames"]["ambulance"]) == len(mode["frames"]["ns"]) == len(mode["frames"]["background"])
    assert all(len(row) % 3 == 0 for row in mode["frames"]["background"])
    assert mode["metrics"]["transit_s"] > 0


def test_replay_is_json_serialisable(replay):
    json.dumps(replay)


def test_non_finite_numbers_are_rejected_not_clamped():
    for key in ("slew", "hold", "horizon", "trigger"):
        with pytest.raises(ValueError):
            scenario_from_query({key: ["nan"]})
    with pytest.raises(ValueError):
        scenario_from_query({"horizon": ["inf"]})


def test_query_is_clamped():
    sc = scenario_from_query({"vehicles": ["99999"], "grid": ["1"], "slew": ["0.25"]})
    assert sc.background_vehicles == 400 and sc.grid_size == 3 and sc.slew_rate == 0.25
    with pytest.raises(ValueError):
        scenario_from_query({"seed": ["abc"]})


def test_server_serves_api_and_blocks_traversal():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/replay?vehicles=10&seed=2"))
        assert data["route"][0] == "J0_0"
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/..%2f..%2fetc/passwd")
        assert e.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/replay?seed=abc")
        assert e.value.code == 400
    finally:
        httpd.shutdown()


def test_compare_modes_returns_per_seed_samples():
    from metrics.sweep import compare_modes
    from simulation.engine import RunMode

    out = compare_modes(Scenario(background_vehicles=10), [0, 1, 2], (RunMode.NO_PREEMPTION, RunMode.CORRIDOR_RECOVERY), workers=1)
    s = out[RunMode.CORRIDOR_RECOVERY]
    assert len(s.transit_samples) == len(s.delay_samples) == 3
    assert abs(s.transit.mean - sum(s.transit_samples) / 3) < 1e-9


def test_server_answers_nan_with_400_and_compare_with_samples():
    import urllib.error

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        for bad in ("slew=nan", "hold=nan", "horizon=nan"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/replay?{bad}")
            assert e.value.code == 400
        data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/compare?seeds=2&vehicles=10"))
        assert len(data["modes"]["corridor_recovery"]["transit_samples"]) == 2
    finally:
        httpd.shutdown()


def test_unfinished_runs_serialise_as_null_not_nan():
    from metrics.evaluate import ModeMetrics
    from metrics.serialize import to_jsonable

    m = ModeMetrics(transit_s=float("nan"), avg_delay_s=1.0, p95_delay_s=1.0, total_delay_s=1.0, unfinished=1, max_nongreen_s=26.0)
    text = json.dumps(to_jsonable(m), allow_nan=False)  # raises if NaN leaked through
    assert json.loads(text)["transit_s"] is None


def test_export_accepts_a_bare_filename(tmp_path, monkeypatch):
    import sys

    from api import export

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["export", "--seeds", "2", "--out", "sample.js"])
    export.main()
    assert (tmp_path / "sample.js").read_text().startswith("window.__REPLAY__=")


def test_replay_carries_a_route_per_mode(replay):
    for key, mode in replay["modes"].items():
        assert mode["route"][0] == "J0_0" and mode["route"][-1] == "J4_4", key
