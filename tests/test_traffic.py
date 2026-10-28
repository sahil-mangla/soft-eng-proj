from network.generate_grid import generate_grid
from simulation.traffic_agents import BackgroundVehicle, advance_vehicle, spawn_background_traffic


def _drive(vehicle, net, start_t, ticks):
    cleared = []
    for t in range(start_t, start_t + ticks):
        c = advance_vehicle(vehicle, net, float(t), 1.0)
        if c:
            cleared.append((t, c))
    return cleared


def test_vehicle_waits_at_red_and_crosses_on_green():
    net = generate_grid(n=3, edge_length_m=100)
    # The EW approach is red for t in [0, 23) of each 46s cycle, then green.
    v = BackgroundVehicle(id="a", route=["J0_0", "J0_1", "J0_2"])
    assert _drive(v, net, 0, 23) == []
    assert v.speed_mps == 0.0  # stopped at the line
    assert _drive(v, net, 23, 5)  # crosses once green


def test_queue_is_first_in_first_out_with_discharge_headway():
    net = generate_grid(n=3, edge_length_m=100)
    cars = [BackgroundVehicle(id=f"q{i}", route=["J0_0", "J0_1", "J0_2"]) for i in range(3)]
    crossing = {}
    for t in range(0, 60):  # all arrive during red; signal turns green at t=23
        for c in cars:
            cleared = advance_vehicle(c, net, float(t), 1.0)
            if cleared:
                crossing[c.id] = t
    assert [crossing[c.id] for c in cars] == sorted(crossing.values())
    times = sorted(crossing.values())
    assert all(b - a >= 2 for a, b in zip(times, times[1:]))  # headway 2s


def test_ambulance_does_not_count_toward_congestion():
    from simulation.engine import Ambulance

    net = generate_grid(n=2, edge_length_m=400)
    amb = Ambulance(id="amb", route=["J0_0", "J0_1"])
    advance_vehicle(amb, net, 0.0, 1.0)
    assert net.edge("J0_0", "J0_1").vehicle_count == 0


def test_spawn_is_deterministic_for_a_seed():
    net = generate_grid(n=5)
    a = spawn_background_traffic(net, count=20, seed=7)
    b = spawn_background_traffic(net, count=20, seed=7)
    assert [(v.route, v.spawn_tick) for v in a] == [(v.route, v.spawn_tick) for v in b]
