"""Interior View observability layer.

A thin, read-only trace around the existing turn path (`pipeline.run_turn`).
It reports what the pipeline did; it never changes what the pipeline does
and it never infers model psychology. See `trace.py` for the reconstruction
technique, `compute.py` for the computed-values honesty contract (spec §10),
and `replay.py` for the build-time model-input replay engine (spec §7).
"""

from conditioned_kernel.observatory.trace import PassTrace, StageTrace, TurnTrace, run_traced_turn

__all__ = [
    "TurnTrace",
    "StageTrace",
    "PassTrace",
    "run_traced_turn",
]
