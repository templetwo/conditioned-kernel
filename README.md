# Conditioned Kernel

> **The model supplies linguistic possibility; the substrate determines what becomes an answer.**

Local-first experiment harness for **substrate-conditioned generation**.
The language model is treated as a **replaceable text-transduction kernel**.
Effective system behavior is relocated into the substrate that surrounds inference:
persistent state, context compilation, validation, repair, acceptance, and rendering.

**Temple of Two** research project. Fully local. No cloud dependency. No sensors. No autonomous tools in v0.

| | |
|---|---|
| **Research name** | Substrate-Conditioned Generation (working synonym) |
| **Project / package** | Conditioned Kernel (`conditioned-kernel` / `ck`) |
| **Runtime** | Ollama at `localhost:11434` |
| **v0 target** | Measurable *substrate gain* over bare generation on the same small model |

## Thesis

Once a local model crosses a minimum linguistic threshold, **substrate design should predict system behavior more strongly than model identity does**.

Bare models may differ widely. When run through the same compiled arrival packet, constrained output schema, deterministic validation, and one repair loop, they should converge toward the same *functional* behavior (state updates, constraint obedience, continuity)—not stylistic sameness.

## Success condition (v0)

> Conditioned Kernel succeeds if the same small local model, when run through the substrate, becomes more coherent, more state-faithful, more continuous, and more repairable than when run bare—and if those gains survive a model swap within the tested size band.

## Quick start

```bash
cd conditioned-kernel
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Requires Ollama running locally with a small model, e.g.:
#   ollama pull qwen2.5:0.5b
ollama serve   # if not already running

ck status
ck smoke
ck ask "Summarize the current design intent in one short paragraph."
```

Offline tests (no Ollama required):

```bash
pytest -q
```

## Architecture

```
terminal → substrate_state → compile(arrival packet)
        → generate(Ollama) → return_path(parse → validate → assess)
        → accept | repair(one pass) | reject
        → terminal render + persistent receipts
```

| Module | Role |
|---|---|
| `state` | Load/write filesystem substrate |
| `compile` | Bound arrival packet from state + input |
| `generate` | Ollama client (`chat_json` / `generate_raw`) |
| `return_path` | Parse, validate, assess, repair, accept |
| `cli` | Terminal surface |

v0 does **not** stream model tokens to the terminal. The substrate buffers the full candidate before acceptance.

## Default models

Primary experimental window: **0.5B–1.5B**. Stretch lower with SmolLM2-class probes; stretch upper carefully on Jetson Orin Nano 8GB.

This machine already has useful Ollama tags for first runs: `qwen2.5:0.5b`, `qwen2.5:1.5b`, `granite4:350m`, `tinyllama:1.1b`.

## Experiment discipline

See [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md).

Conditions include bare, budget-matched bare, static persona, full Conditioned Kernel, and ablations. Metrics split **structural recovery** (parse/schema/repair) from **semantic substrate gain** (faithfulness/continuity on valid candidates).

## Lineage

Synthesis of Temple Two public work:

- **Context Field Conditioning** — structure of delivery changes outcomes
- **Phenomenological Compass** — organizing posture separate from answering model
- **T2Helix** — pre/post chokepoints, local storage, redaction
- **Sovereign Stack** — continuity and governance outside any single model instance

v0 does **not** import the full stack. Bridge surfaces are P3 after the core experiment stabilizes.

## Repo layout

```
conditioned-kernel/
├── src/conditioned_kernel/   # package
├── state/                    # default substrate files
├── logs/                     # receipts / history (local writes)
├── experiments/              # matrix runners + probes
├── tests/                    # offline unit tests
└── docs/                     # thesis, architecture, protocol
```

## License

Apache-2.0. Copyright 2026 Anthony J. Vasquez Sr. / Temple of Two.
