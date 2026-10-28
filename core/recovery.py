"""Once the ambulance clears a junction, interpolates that junction back to its
normal fixed-cycle position over the next 1-2 cycles (rather than an instant
reset), so vehicles queued during preemption clear out first.

See docs/BUILD-PLAN.md Step 5, CLAUDE.md section 6.4.
"""

from collections.abc import Callable
from dataclasses import dataclass

from network.generate_grid import Signal


@dataclass
class _RecoveryState:
    initial_shift: float
    duration_s: float
    elapsed_s: float = 0.0


class RecoveryManager:
    """Decays a junction's `phase_offset_shift` linearly to 0 over
    `recovery_cycles` normal cycles, instead of resetting it instantly —
    the ~21% delay-reduction lever CLAUDE.md section 9 cites for graceful
    recovery over a snap-back.
    """

    def __init__(
        self,
        recovery_cycles: int = 2,
        set_shift: Callable[[str, float], None] | None = None,
    ):
        self.recovery_cycles = recovery_cycles
        self._set_shift = set_shift
        self._active: dict[str, _RecoveryState] = {}

    def _apply(self, junction_id: str, signal: Signal, value: float) -> None:
        if self._set_shift is not None:
            self._set_shift(junction_id, value)
        else:
            signal.phase_offset_shift = value

    def begin_recovery(self, junction_id: str, signal: Signal) -> None:
        if junction_id in self._active:
            return
        if abs(signal.phase_offset_shift) < 1e-9:
            return  # never shifted: nothing to ease back, and no reason to keep the run alive
        duration_s = self.recovery_cycles * signal.cycle_plan.cycle_length
        if duration_s <= 0.0:
            self._apply(junction_id, signal, 0.0)  # recovery_cycles=0: instant reset
            return
        self._active[junction_id] = _RecoveryState(
            initial_shift=signal.phase_offset_shift, duration_s=duration_s
        )

    def step(self, junction_id: str, signal: Signal, dt: float) -> None:
        state = self._active.get(junction_id)
        if state is None:
            return
        state.elapsed_s += dt
        fraction_remaining = max(0.0, 1.0 - state.elapsed_s / state.duration_s)
        self._apply(junction_id, signal, state.initial_shift * fraction_remaining)
        if fraction_remaining <= 0.0:
            del self._active[junction_id]

    def any_active(self) -> bool:
        return bool(self._active)

    def is_recovering(self, junction_id: str) -> bool:
        return junction_id in self._active
