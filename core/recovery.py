"""Once the ambulance clears a junction, interpolates that junction back to its
normal fixed-cycle position over the next 1-2 cycles (rather than an instant
reset), so vehicles queued during preemption clear out first.

See docs/BUILD-PLAN.md Step 5, CLAUDE.md section 6.4.
"""
