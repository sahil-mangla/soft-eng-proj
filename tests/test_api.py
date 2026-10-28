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
