# Conditioned Kernel — agent notes

## What this is

Local experiment harness. Model = replaceable kernel. Substrate = persistent state + compile + validate + repair.

## Do first

1. Read `docs/NAME.md`, `docs/ARCHITECTURE.md`, `docs/EXPERIMENT_PROTOCOL.md`
2. `pip install -e ".[dev]"` from repo root
3. `pytest -q` then `ck smoke --dry` then `ck smoke` (needs Ollama)

## Hard rules for v0

- Fully local. No cloud providers.
- No sensors. No autonomous tools.
- Do not stream Ollama to terminal before acceptance.
- Do not score model self-reported confidence.
- Faithfulness checks are closed-set / mechanical, not NLI.
- Do not import full Sovereign Stack. Bridge is P3.
- Prefer one compile module until ablations demand select/order/compress split.

## Success sentence

Same small local model through substrate must beat bare on coherence, state-faithfulness, continuity, repairability — and gains should survive model swap in band.
