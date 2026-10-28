# Results (simulation v2)

Reproduce: `python -m metrics.sweep --seeds 24` (writes `outputs/sweep_results.json`).
Scenario: 5×5 grid, 400 m edges, 20 s green / 3 s yellow, 80 background vehicles,
ambulance J0_0 → J4_4, 24 seeds; every mode runs the identical traffic per seed.
Values are means ± 95% CI.

## Main comparison

| Mode | Transit (s) | Avg bg delay (s) | Longest non-green (s) |
| --- | --- | --- | --- |
| No preemption | 307.9 ± 4.0 | 68.3 ± 1.6 | 26.0 |
| Naive reactive | 260.8 ± 7.4 | 68.1 ± 1.6 | 32.1 ± 1.2 |
| Corridor, no recovery | 259.8 ± 6.8 | 68.3 ± 1.6 | 38.1 ± 2.1 |
| Corridor + recovery | 259.8 ± 7.0 | 68.7 ± 1.7 | 38.4 ± 3.3 |

## Findings

1. **Preemption works**: −47 to −48 s (about 15%) for the ambulance, any mode.
2. **Corridor ≈ naive reactive on transit** at every load tested (20–200 vehicles); the
   reactive trigger distance (100–400 m) barely matters either.
3. **No measurable background-delay effect** from preemption or from recovery
   (paired differences −0.2 to +0.5 s, intervals include zero). The brief's literature
   claim that recovery recovers ~21% of delay is not reproduced; this model is
   probably too insensitive to show it (see Limitations).
4. **Corridor lets a signal stay non-green longer** than naive (38 s against 32 s, fixed cycle 26 s). `max_hold`
   bounds the phase shift, not the wait: a shift of −12 s followed by +10 s as the ETA
   moves leaves one direction waiting up to about 2 × max_hold longer.
5. **Slew (eased shifts) trades ambulance time for fairness**: rate 0.25 s/s gives
   265.8 s transit with a 33 s longest non-green; 0.1 s/s gives 306 s (no benefit).
6. **ETA prediction works**: mean absolute error is 0.4 s at arrival, 1.2 s at 10–20 s out,
   and 5 s at 60–90 s out (corridor mode, seed 42).

## Model changes that were required to get here

- The ambulance no longer counts itself as congestion (it slowed itself ~15%).
- Background delay is measured over every vehicle until the run ends, not just those
  that finished before the ambulance (that sample differed by mode).
- Stop-line queues with a 2 s discharge headway, so a late green costs something.
- Coordinator hysteresis: a jittering ETA used to flip a junction between −12 s and +11 s.

## Limitations

- Signals jump phase instantly; there is no minimum green or all-red clearance.
- Vehicles do not interact except through queue order and a density-based speed.
- Background vehicles random-walk; there is no arterial demand.
- One network, one route. Re-routing is not implemented.
- The thesis (predictive beats reactive) is not supported by this simulator. A higher
  fidelity model (SUMO, per decision D1) is the natural next test before drawing conclusions.
