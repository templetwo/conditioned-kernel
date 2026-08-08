"""ACT-1 Authority Crossover Test — Step 0 validation instrument + live TUI.

See docs/ACT1_authority_crossover.md. Not a ladder test. Not Step 1.
"""

from conditioned_kernel.act1.runner import Act1Config, run_act1
from conditioned_kernel.act1.tui import run_tui

__all__ = ["Act1Config", "run_act1", "run_tui"]
