import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import matplotlib
import pytest

matplotlib.use("Agg")

import api.server as server  # noqa: E402
from metrics.eta_accuracy import eta_error_by_lead  # noqa: E402
from metrics.evaluate import MetricsEvaluator, estimate  # noqa: E402
from metrics.sweep import compare_modes, sweep_parameter  # noqa: E402
from simulation.engine import RunMode  # noqa: E402
from simulation.scenario import Scenario, run_scenario  # noqa: E402
from viz.plots import plot_comparison, plot_eta_accuracy, plot_signal_timeline, plot_sweep  # noqa: E402


@pytest.fixture(scope="module")
def runs():
    sc = Scenario(background_vehicles=20, seed=1)
    out, route = {}, None
    for mode in RunMode:
        engine, log = run_scenario(sc, mode)
        out[mode] = log
        route = engine.route.junction_ids
    return out, route


def test_every_chart_is_written(tmp_path, runs):
    logs, route = runs
    report = MetricsEvaluator().compare(logs)
    plot_comparison(report, str(tmp_path / "comparison.png"))
    plot_signal_timeline(logs[RunMode.CORRIDOR_RECOVERY], route, str(tmp_path / "timeline.png"))
    plot_eta_accuracy({m: eta_error_by_lead(logs[m]) for m in (RunMode.NO_PREEMPTION, RunMode.CORRIDOR_RECOVERY)}, str(tmp_path / "eta.png"))
    sweep = sweep_parameter(Scenario(background_vehicles=10), "background_vehicles", [10, 20], [0, 1], (RunMode.NO_PREEMPTION, RunMode.CORRIDOR_RECOVERY), workers=1)
    plot_sweep(sweep, "transit", "vehicles", str(tmp_path / "sweep.png"), "Transit by load")
    for name in ("comparison", "timeline", "eta", "sweep"):
        assert (tmp_path / f"{name}.png").stat().st_size > 1000, name


def test_timeline_handles_a_route_that_changed_mid_run(tmp_path, runs):
    logs, route = runs
    log = logs[RunMode.CORRIDOR_RECOVERY]
    assert all(isinstance(t.approach_states, dict) for t in log.ticks)
    plot_signal_timeline(log, route, str(tmp_path / "t.png"))


def test_run_scripts_report_through_the_shared_helper(capsys, monkeypatch):
    from simulation import run_baseline, run_corridor

    for module, argv, expected in (
        (run_baseline, ["x", "--background-vehicles", "10"], "no_preemption"),
        (run_baseline, ["x", "--mode", "naive", "--background-vehicles", "10"], "naive_reactive"),
        (run_corridor, ["x", "--background-vehicles", "10"], "corridor_recovery"),
        (run_corridor, ["x", "--no-recovery", "--background-vehicles", "10"], "corridor_no_recovery"),
    ):
        monkeypatch.setattr(sys, "argv", argv)
        module.main()
        assert f"Mode: {expected}" in capsys.readouterr().out


def test_demo_writes_its_charts(tmp_path, monkeypatch, capsys):
    import demo

    monkeypatch.setattr(sys, "argv", ["demo", "--vehicles", "10", "--out", str(tmp_path)])
    demo.main()
    assert {"comparison.png", "signal_timeline.png", "eta_accuracy.png"} <= set(os.listdir(tmp_path))
    assert "Corridor + recovery" in capsys.readouterr().out


def test_cli_reports_a_run_that_never_finished(capsys, monkeypatch):
    from simulation import cli
    from simulation.scenario import build_engine

    engine = build_engine(Scenario(background_vehicles=5), RunMode.NO_PREEMPTION)
    engine.max_ticks = 5  # far too few for the ambulance to arrive
    log = engine.run()
    monkeypatch.setattr(cli, "run_scenario", lambda sc, mode: (engine, log))
    cli.run_and_report(Scenario(background_vehicles=5), RunMode.NO_PREEMPTION)
    assert "did not arrive" in capsys.readouterr().out


def test_compare_modes_reports_unfinished_runs(monkeypatch):
    import metrics.sweep as sweep_module
    from metrics.evaluate import ModeMetrics

    def fake(job):
        scenario, mode = job
        return ModeMetrics(transit_s=float("nan") if scenario.seed == 1 else 100.0 + scenario.seed, avg_delay_s=1.0, p95_delay_s=1.0, total_delay_s=1.0, unfinished=0, max_nongreen_s=26.0)

    monkeypatch.setattr(sweep_module, "_run_one", fake)
    out = compare_modes(Scenario(), [0, 1, 2], (RunMode.NO_PREEMPTION, RunMode.CORRIDOR_RECOVERY), workers=1)
    summary = out[RunMode.CORRIDOR_RECOVERY]
    assert summary.unfinished_runs == 1 and summary.transit.n == 2 and estimate([1.0]).n == 1


def _serve():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def test_static_files_and_unsupported_methods():
    httpd, base = _serve()
    try:
        page = urllib.request.urlopen(f"{base}/")
        assert page.status == 200 and "text/html" in page.headers["Content-Type"]
        assert urllib.request.urlopen(f"{base}/app.js").headers["Content-Type"].startswith(("text/javascript", "application/javascript"))
        for path in ("/nope.html", "/%2e%2e/api/server.py", "/..%2fapi%2fserver.py", "/themes/../../README.md"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(f"{base}{path}")
            assert e.value.code == 404, path
        post = urllib.request.Request(f"{base}/api/replay", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(post)
        assert e.value.code == 501
    finally:
        httpd.shutdown()


def test_suite_endpoint_serves_the_last_sweep(tmp_path, monkeypatch):
    httpd, base = _serve()
    try:
        monkeypatch.setattr(server, "SUITE_PATH", str(tmp_path / "missing.json"))
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"{base}/api/suite")
        assert e.value.code == 404
        (tmp_path / "suite.json").write_text(json.dumps({"seeds": 3}))
        monkeypatch.setattr(server, "SUITE_PATH", str(tmp_path / "suite.json"))
        assert json.load(urllib.request.urlopen(f"{base}/api/suite")) == {"seeds": 3}
    finally:
        httpd.shutdown()


def test_unexpected_failures_return_a_500_not_a_dropped_connection(monkeypatch):
    httpd, base = _serve()
    try:
        monkeypatch.setattr(server, "build_replay", lambda sc: 1 / 0)
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"{base}/api/replay")
        assert e.value.code == 500
        assert "failed" in json.load(e.value)["error"]
    finally:
        httpd.shutdown()


def test_standard_suite_runs_every_section_and_serialises(tmp_path, monkeypatch):
    import metrics.sweep as sweep_module

    suite = sweep_module.run_standard_suite([0], Scenario(background_vehicles=10), workers=1)
    assert {"modes", "load", "max_hold", "horizon", "recovery_cycles", "slew", "arterial", "arterial_80", "reactive_trigger"} <= set(suite)
    monkeypatch.setattr(sys, "argv", ["sweep", "--seeds", "1", "--vehicles", "10", "--out", str(tmp_path), "--workers", "1"])
    sweep_module.main()
    written = json.loads((tmp_path / "sweep_results.json").read_text())  # strict JSON: no NaN
    assert written["seeds"] == 1 and "arterial" in written


def test_the_server_listens_on_loopback_only():
    httpd = server.make_server(0)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()
