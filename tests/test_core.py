import pytest

from core.corridor_coordinator import CorridorCoordinator
from core.eta_predictor import ETAPredictor
from core.recovery import RecoveryManager
from core.router import compute_route
from network.generate_grid import SignalState, generate_grid


def test_route_prefers_faster_path_over_congested_one():
    net = generate_grid(n=3)
    # Congest the straight top-row path; an alternative of equal hop count exists.
    for u, v in (("J0_0", "J0_1"), ("J0_1", "J0_2")):
        net.edge(u, v).vehicle_count = 50
    route = compute_route(net, "J0_0", "J0_2")
    assert route.junction_ids != ["J0_0", "J0_1", "J0_2"]


def test_route_is_a_connected_path():
    net = generate_grid(n=5)
    route = compute_route(net, "J0_0", "J4_4")
    assert route.junction_ids[0] == "J0_0" and route.junction_ids[-1] == "J4_4"
    assert all(net.edges.get(p) for p in zip(route.junction_ids, route.junction_ids[1:]))


def test_eta_is_increasing_along_route_and_skips_passed_edges():
    net = generate_grid(n=3, edge_length_m=400)
    route = compute_route(net, "J0_0", "J2_2")
    etas = ETAPredictor().predict(route, 0, 0.0)
    values = [etas[j] for j in route.junction_ids[1:]]
    assert values == sorted(values) and len(values) == len(route.junction_ids) - 1
    later = ETAPredictor().predict(route, 1, 100.0)
    assert route.junction_ids[1] not in later


def test_eta_shrinks_as_ambulance_advances():
    net = generate_grid(n=3, edge_length_m=400)
    route = compute_route(net, "J0_0", "J2_2")
    first = ETAPredictor().predict(route, 0, 0.0)[route.junction_ids[1]]
    nearer = ETAPredictor().predict(route, 0, 300.0)[route.junction_ids[1]]
    assert nearer < first


def test_eta_slows_with_congestion():
    net = generate_grid(n=3, edge_length_m=400)
    route = compute_route(net, "J0_0", "J2_2")
    free = ETAPredictor().predict(route, 0, 0.0)[route.junction_ids[1]]
    net.edge(route.junction_ids[0], route.junction_ids[1]).vehicle_count = 10
    assert ETAPredictor().predict(route, 0, 0.0)[route.junction_ids[1]] > free


def test_coordinator_ignores_junctions_beyond_horizon():
    net = generate_grid(n=3)
    CorridorCoordinator(net, horizon_s=30).coordinate(0.0, {"J0_1": 90.0}, {"J0_1": "EW"})
    assert net.junctions["J0_1"].signal.phase_offset_shift == 0.0


def test_coordinator_shift_never_exceeds_max_hold():
    net = generate_grid(n=3)
    coord = CorridorCoordinator(net, horizon_s=60, max_hold_s=8)
    for t in range(0, 200, 5):
        coord.coordinate(float(t), {"J0_1": 20.0}, {"J0_1": "EW"})
        assert abs(net.junctions["J0_1"].signal.phase_offset_shift) <= 8 + 1e-9


def test_coordinator_makes_green_at_predicted_arrival_when_reachable():
    net = generate_grid(n=3)
    sig = net.junctions["J0_1"].signal
    CorridorCoordinator(net, max_hold_s=15).coordinate(0.0, {"J0_1": 20.0}, {"J0_1": "EW"})
    assert sig.state_for_axis("EW", 20.0) == SignalState.GREEN


def test_coordinator_slew_limits_per_tick_change():
    net = generate_grid(n=3)
    coord = CorridorCoordinator(net, horizon_s=60, max_hold_s=15, slew_rate=0.25)
    prev = 0.0
    for t in range(0, 40):
        coord.coordinate(float(t), {"J0_1": 40.0 - t}, {"J0_1": "EW"}, dt=1.0)
        cur = net.junctions["J0_1"].signal.phase_offset_shift
        assert abs(cur - prev) <= 0.25 + 1e-9
        prev = cur


def test_recovery_eases_back_over_configured_cycles():
    net = generate_grid(n=2)
    sig = net.junctions["J0_0"].signal
    sig.phase_offset_shift = 12.0
    mgr = RecoveryManager(recovery_cycles=2)
    mgr.begin_recovery("J0_0", sig)
    mgr.step("J0_0", sig, 1.0)
    assert 11.0 < sig.phase_offset_shift < 12.0  # eased, not snapped
    for _ in range(int(2 * sig.cycle_plan.cycle_length)):
        mgr.step("J0_0", sig, 1.0)
    assert sig.phase_offset_shift == 0.0 and not mgr.is_recovering("J0_0")


def test_recovery_with_zero_cycles_resets_instantly():
    net = generate_grid(n=2)
    sig = net.junctions["J0_0"].signal
    sig.phase_offset_shift = 12.0
    mgr = RecoveryManager(recovery_cycles=0)
    mgr.begin_recovery("J0_0", sig)
    assert sig.phase_offset_shift == 0.0 and not mgr.any_active()
