import math

import pytest

from metrics.eta_accuracy import eta_error_by_lead
from metrics.evaluate import MetricsEvaluator, estimate, paired_difference, percentile
from simulation.engine import RunMode
from simulation.scenario import Scenario, build_engine, run_scenario

SC = Scenario(background_vehicles=40, seed=3)


@pytest.mark.parametrize("mode", list(RunMode))
def test_every_mode_finishes_with_full_background_population(mode):
    engine, log = run_scenario(SC, mode)
    assert log.ambulance_transit_time_s is not None
    assert len(log.background_delays_s) == len(engine.background_vehicles)
    assert log.background_unfinished == 0
    assert all(d >= 0 for d in log.background_delays_s)


def test_background_population_is_identical_across_modes():
    counts = {len(run_scenario(SC, m)[1].background_delays_s) for m in RunMode}
    assert len(counts) == 1


def test_runs_are_deterministic():
    a = run_scenario(SC, RunMode.CORRIDOR_RECOVERY)[1]
    b = run_scenario(SC, RunMode.CORRIDOR_RECOVERY)[1]
    assert a.ambulance_transit_time_s == b.ambulance_transit_time_s
    assert a.background_delays_s == b.background_delays_s


def test_transit_cannot_beat_free_flow():
    engine, log = run_scenario(SC, RunMode.CORRIDOR_RECOVERY)
    free_flow_s = engine.route.total_length_m() / 13.9
    assert log.ambulance_transit_time_s >= free_flow_s - 1.0


def test_preemption_beats_no_preemption_for_the_ambulance():
    base = run_scenario(SC, RunMode.NO_PREEMPTION)[1].ambulance_transit_time_s
    for mode in (RunMode.NAIVE_REACTIVE, RunMode.CORRIDOR_RECOVERY):
        assert run_scenario(SC, mode)[1].ambulance_transit_time_s < base


def test_no_preemption_never_shifts_a_signal():
    _, log = run_scenario(SC, RunMode.NO_PREEMPTION)
    assert all(all(s == 0.0 for s in t.junction_shifts.values()) for t in log.ticks)
    assert log.max_nongreen_s == 26.0  # cycle 46 - green 20


def test_signals_return_to_schedule_after_run():
    engine, _ = run_scenario(SC, RunMode.CORRIDOR_RECOVERY)
    assert all(abs(j.signal.phase_offset_shift) < 1e-6 for j in engine.network.junctions.values())


def test_naive_resets_instantly_while_recovery_eases():
    def shifts_after_first_clear(mode):
        engine, log = run_scenario(SC, mode)
        first = engine.route.junction_ids[1]
        cleared_t = int(log.actual_arrival_s[first])
        return [log.ticks[i].junction_shifts[first] for i in range(cleared_t + 1, cleared_t + 6)]

    assert all(s == 0.0 for s in shifts_after_first_clear(RunMode.NAIVE_REACTIVE))
    eased = [abs(s) for s in shifts_after_first_clear(RunMode.CORRIDOR_RECOVERY)]
    assert eased == sorted(eased, reverse=True)  # decays monotonically, never jumps up


def test_recovery_cycles_zero_runs():
    _, log = run_scenario(SC.with_(recovery_cycles=0), RunMode.CORRIDOR_RECOVERY)
    assert log.ambulance_transit_time_s is not None


def test_same_start_and_end_is_rejected():
    with pytest.raises(ValueError):
        build_engine(SC.with_(start="J0_0", end="J0_0"), RunMode.NO_PREEMPTION)


def test_tick_limit_reports_no_transit_time_instead_of_crashing():
    engine = build_engine(SC, RunMode.NO_PREEMPTION)
    engine.max_ticks = 10
    log = engine.run()
    assert log.ambulance_transit_time_s is None
    assert math.isnan(MetricsEvaluator.compute_transit_time(log))


def test_frames_are_recorded_for_the_frontend():
    _, log = run_scenario(SC, RunMode.CORRIDOR_RECOVERY, record_frames=True)
    assert len(log.frames) == len(log.ticks)
    f = log.frames[10]
    assert len(f.ns) == len(f.ew) == 25 == len(f.shifts)
    assert set(f.ns) <= set("GYR")


def test_eta_error_shrinks_as_ambulance_nears_the_junction():
    _, log = run_scenario(SC, RunMode.CORRIDOR_RECOVERY)
    buckets = [b for b in eta_error_by_lead(log) if b.n >= 5]
    assert buckets[0].mae_s <= buckets[-1].mae_s
    assert buckets[0].mae_s < 2.0


def test_estimate_and_paired_difference():
    e = estimate([1.0, 2.0, 3.0])
    assert e.mean == 2.0 and e.ci95 > 0
    d = paired_difference([5.0, 6.0, 7.0], [4.0, 5.0, 6.0])
    assert d.mean == 1.0 and d.ci95 == 0.0
    with pytest.raises(ValueError):
        paired_difference([1.0], [1.0, 2.0])


def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([], 0.9) == 0.0
