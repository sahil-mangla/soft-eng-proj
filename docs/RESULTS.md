# Results (simulation v3)

Reproduce: `python -m metrics.sweep --seeds 24` (writes `outputs/sweep_results.json`).
Scenario: 5×5 grid, 400 m edges, 20 s green / 3 s yellow, 80 background vehicles,
ambulance J0_0 → J4_4, 24 seeds; every mode runs the identical traffic per seed.
Values are means ± 95% CI. "Longest non-green" is the longest stretch any signal showed
red or yellow to one direction (mean over seeds, then the worst single run).

## Main comparison

| Mode | Transit (s) | Avg bg delay (s) | Longest non-green (s), mean / worst |
| --- | --- | --- | --- |
| No preemption | 300.4 ± 7.1 | 68.3 ± 1.6 | 26.0 / 26 |
| Naive reactive | 260.7 ± 7.4 | 68.1 ± 1.6 | 36.5 / 39 |
| Corridor, no recovery | 257.8 ± 5.3 | 68.5 ± 1.7 | 38.9 / 41 |
| Corridor + recovery | 257.6 ± 5.4 | 68.7 ± 1.7 | 36.2 / 41 |

Paired by seed: corridor + recovery against naive reactive is **−3.0 ± 4.9 s** on transit
(not distinguishable) and **+0.6 ± 0.3 s** on average background delay (borderline worse).
Recovery against no recovery: −0.1 ± 0.9 s transit, +0.2 ± 0.2 s delay.

## Findings

1. **Preemption works**: −40 to −43 s (about 14%) for the ambulance in any mode.
2. **The predictive corridor does not beat the naive reactive baseline here.** Transit is
   statistically tied at every load tested (20–200 vehicles) and the corridor adds about
   0.6 s of average background delay. The reactive trigger distance matters little
   (100 m: 272 s, 200–400 m: 261–263 s).
3. **The cross-traffic bound now holds.** The corridor refuses any shift that would let a
   signal show a non-green to one direction longer than the fixed cycle's own stretch plus
   `max_hold`. The worst single run in the sweep equals that cap and never exceeds it:
   31, 36, 41, 46 s for holds of 5, 10, 15, 20 s (cap = 26 + hold). The naive baseline is
   deliberately unbounded and reaches 39 s at a 200 m trigger and 49 s at 400 m.
4. **`max_hold` is the one parameter that visibly matters**: 5 s → 277.6 s transit,
   10 s → 263.5 s, 15 s → 257.6 s, and nothing further past 15 s.
5. **Recovery shows no benefit** on delay or transit at any setting (0 to 4 cycles). The
   brief's literature claim (recovery recovers ~21% of delay) is not reproduced; this model
   is probably too insensitive to show it.
6. **Eased shifts trade ambulance time for fairness**: a rate of 0.25 s per s gives 263.2 s
   transit with a 35 s worst wait; 0.1 s per s gives no benefit (299.6 s).
7. **The advantage shrinks with load**: −67 s at 20 vehicles to −23 s at 140–200.
8. **ETA prediction works**: mean absolute error 0.5 s at arrival, 1.0 s at 10–20 s out,
   3.5 s at 30–45 s, 6.9 s at 60–90 s (corridor mode, seed 42).

## Model rules that shape these numbers

- The ambulance does not count itself as congestion (M1); delay is measured on every
  vehicle until the run ends (M2); stop-line queues drain at 2 s per vehicle (M3).
- Shifts are anchored to the junction's current shift so a jittering ETA cannot flip it (M4).
- **Every shift write is guarded (M6):** a signal may only go green → yellow → red → green.
  A change that would skip a yellow is applied as far as is legal and finished once it is.
- **Corridor modes are starvation-bounded (M7);** naive reactive is not, by design.
- **The route is recomputed (M8)** each time the ambulance enters a road, and switched when
  the remainder is at least 10% faster at current speeds.

## Limitations

- No all-red interval or minimum green; yellow is enforced but nothing else of a controller.
- Vehicles interact only through queue order and a density-based speed.
- Background vehicles random-walk; there is no arterial demand.
- One network. Re-routing exists but is only checked at junctions.
- The thesis (predictive beats reactive) is not supported by this simulator. A higher
  fidelity model (SUMO, per decision D1) is the natural next test before drawing conclusions.
