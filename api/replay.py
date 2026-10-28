"""Turns simulation runs into the JSON the frontend replays: network
geometry, and for each run mode a per-second frame list (ambulance and
background positions, signal states, preemption shifts) plus its metrics and
ETA-accuracy data.

Positions are rounded to whole metres and packed flat to keep a four-mode
replay of the default scenario around a megabyte.
"""

from dataclasses import asdict

from metrics.eta_accuracy import eta_error_by_lead
from metrics.evaluate import MetricsEvaluator
from simulation.engine import RunLog, RunMode, SimulationEngine
from simulation.scenario import Scenario, run_scenario


def _network_json(engine: SimulationEngine) -> dict:
    net = engine.network
    junctions = [
        {"id": jid, "row": j.row, "col": j.col, "x": net.xy(jid)[0], "y": net.xy(jid)[1]}
        for jid, j in net.junctions.items()
    ]
    seen = set()
    edges = []
    for (u, v) in net.edges:
        key = tuple(sorted((u, v)))
        if key not in seen:
            seen.add(key)
            edges.append(list(key))
    return {"spacing_m": net.spacing_m, "junctions": junctions, "edges": edges}


def _frames_json(log: RunLog) -> dict:
    return {
        "dt": 1.0,
        "t": [f.t for f in log.frames],
        "ambulance": [[round(f.ambulance[0]), round(f.ambulance[1])] for f in log.frames],
        # Flat [x, y, moving, x, y, moving, ...] per frame.
        "background": [
            [round(c) if i % 3 != 2 else c for v in f.background for i, c in enumerate(v)]
            for f in log.frames
        ],
        "ns": [f.ns for f in log.frames],
        "ew": [f.ew for f in log.frames],
        "shifts": [[round(s, 1) for s in f.shifts] for f in log.frames],
    }


def _eta_json(log: RunLog, route_ids: list[str]) -> dict:
    """Prediction history per route junction (sampled every 2s) next to the
    arrival that actually happened — the ETA-vs-actual panel."""
    per_junction: dict[str, list[list[float]]] = {j: [] for j in route_ids[1:]}
    for t, jid, predicted in log.eta_samples:
        if int(t) % 2 == 0 and jid in per_junction:
            per_junction[jid].append([t, round(predicted, 1)])
    return {
        "predicted": per_junction,
        "actual": {j: log.actual_arrival_s.get(j) for j in route_ids[1:]},
        "by_lead": [
            {"lo": b.lead_lo_s, "hi": None if b.lead_hi_s == float("inf") else b.lead_hi_s,
             "n": b.n, "mae": None if b.n == 0 else round(b.mae_s, 2)}
            for b in eta_error_by_lead(log)
        ],
    }


def build_replay(scenario: Scenario) -> dict:
    evaluator = MetricsEvaluator()
    modes: dict[str, dict] = {}
    network = route = None
    for mode in RunMode:
        engine, log = run_scenario(scenario, mode, record_frames=True)
        if network is None:
            network = _network_json(engine)
            route = engine.route.junction_ids
        metrics = evaluator.summarize(log)
        modes[mode.value] = {
            "label": mode.label,
            "metrics": asdict(metrics),
            "frames": _frames_json(log),
            "eta": _eta_json(log, route),
            "arrivals": {j: log.actual_arrival_s.get(j) for j in route[1:]},
            "end_time_s": log.end_time_s,
            "background_delays_s": [round(d, 1) for d in log.background_delays_s],
        }
    return {
        "scenario": asdict(scenario),
        "network": network,
        "route": route,
        "modes": modes,
    }
