from network.generate_grid import CyclePlan, SignalState, Signal, generate_grid


def test_grid_counts_and_bidirectional_edges():
    net = generate_grid(n=5)
    assert len(net.junctions) == 25
    # 2 * n * (n - 1) undirected segments, each stored in both directions.
    assert len(net.edges) == 2 * 2 * 5 * 4
    assert all((v, u) in net.edges for (u, v) in net.edges)


def test_edge_axes():
    net = generate_grid(n=3)
    assert net.edge("J0_0", "J0_1").axis == "EW"
    assert net.edge("J0_0", "J1_0").axis == "NS"


def test_coordinates_follow_spacing():
    net = generate_grid(n=3, edge_length_m=400.0)
    assert net.xy("J2_1") == (400.0, 800.0)
    assert net.position_xy("J0_0", "J0_1", 100.0) == (100.0, 0.0)


def test_each_junction_has_its_own_signal():
    net = generate_grid(n=3)
    net.junctions["J0_0"].signal.phase_offset_shift = 7.0
    assert net.junctions["J1_1"].signal.phase_offset_shift == 0.0


def test_cycle_never_shows_green_on_both_axes():
    plan = CyclePlan(20, 3)
    for t in range(0, 200):
        states = plan.phase_at(t)
        assert not (states["NS"] == SignalState.GREEN and states["EW"] == SignalState.GREEN)


def test_cycle_length():
    assert CyclePlan(20, 3).cycle_length == 46


def test_best_shift_zero_when_already_green():
    sig = Signal()
    assert sig.best_shift_for_green("NS", 5.0, max_shift=15) == 0.0


def test_best_shift_finds_green_within_bound():
    sig = Signal()
    # EW is red at t=5; green starts at t=23, so a shift of +18 (> bound 15) is
    # needed from that start, but near the edge of its green a small shift works.
    shift = sig.best_shift_for_green("EW", 20.0, max_shift=15)
    assert abs(shift) <= 15
    assert sig.cycle_plan.phase_at(20.0 + shift)["EW"] == SignalState.GREEN


def test_best_shift_respects_bound_even_if_green_is_out_of_reach():
    sig = Signal()
    shift = sig.best_shift_for_green("EW", 5.0, max_shift=5)
    assert abs(shift) <= 5


def test_best_shift_band_limits_search():
    sig = Signal()
    shift = sig.best_shift_for_green("EW", 20.0, max_shift=30, lo=-1.0, hi=1.0)
    assert -1.0 <= shift <= 1.0


def test_anchor_gives_hysteresis():
    # With the current shift already green at arrival, an anchored search stays
    # put rather than falling back to the smallest-magnitude shift.
    sig = Signal()
    arrival = 20.0
    green_shift = sig.best_shift_for_green("EW", arrival, max_shift=15)
    assert green_shift != 0.0
    bigger = green_shift + (1.0 if green_shift > 0 else -1.0)
    if sig.cycle_plan.phase_at(arrival + bigger)["EW"] == SignalState.GREEN:
        assert sig.best_shift_for_green("EW", arrival, max_shift=15, anchor=bigger) == bigger
