# Model ladder — where does the substrate start working?

**Date:** 2026-07-22
**Device:** Jetson Orin Nano 8GB (`tony-jetson`), aarch64, JetPack L4T R36.4.7
**Power:** MAXN_SUPER, `jetson_clocks` locked, headless (`multi-user.target`), swap off
**Runtime:** Ollama 0.24.0, CUDA
**Profile:** `orin_nano_8gb` (ctx 2048), 4 probes, `--prime` on, frozen state

This targets the open thread `thread_min_model`: *what is the minimum viable model size?*
The README's thesis is that **past a minimum linguistic threshold**, substrate design should
predict behavior more strongly than model identity. That threshold has been asserted, never
measured. This is the measurement, from below.

## Protocol

Models run one at a time, ascending by size. Full model eviction before each run, then a primed
matrix, so every model is measured from an identical load state. No concurrent GPU work — an
earlier attempt was discarded because an orphaned run was sharing the GPU, which invalidates the
load-state control established in [DETERMINISM.md](DETERMINISM.md).

## Results

| model | GB | quant | CK struct | CK sem | CK accept | distinct | goal echo | BM struct | BM sem | headline | run s |
|---|---:|---|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| `functiongemma:270m` | 0.30 | Q8_0 | 0.562 | 0.250 | 0.00 | 2/4 | 0.00 | 0.750 | 0.000 | +0.031 | 245 |
| `granite4:350m` | 0.71 | BF16 | 0.625 | 0.500 | 0.00 | 3/4 | 0.50 | 0.750 | 0.500 | −0.062 | 85 |
| `qwen2.5:0.5b` | 0.40 | Q4_K_M | 0.562 | 0.312 | 0.00 | 2/4 | 0.75 | 0.750 | 0.375 | **−0.125** | 66 |
| `gemma3:1b` | 0.82 | Q4_K_M | **0.812** | **0.562** | **0.50** | **4/4** | 0.25 | 0.750 | 0.625 | 0.000 | 64 |
| `qwen3.5:0.8b` | 1.04 | Q8_0 | — | — | — | — | — | — | — | — | timeout |
| `qwen3.5:2b` | 2.74 | Q8_0 | — | — | — | — | — | — | — | — | timeout |

`qwen2.5:0.5b` at −0.125 independently reproduces the controlled figure from the priming
verification in DETERMINISM.md F-D5. Two separate runs, same number.

## The threshold is visible, and it is around 1B

`accept`, `distinct_answers` and `goal_echo` are the columns that matter here, not the composite.
Below ~1B every model is degenerate in some way, and **nothing is ever accepted**. At `gemma3:1b`
the substrate starts working: fully distinct answers, and the first real accepts on the ladder.

Qualitatively, in ascending order:

**`functiongemma:270m`** — echoes the *system prompt* rather than the goal:

> `"short reply that mentions the goal."`

and once returned the entire system prompt verbatim. Google's own guidance says it is not intended
as a direct dialogue model, and that is exactly what this shows. It is not a bad model; it is the
wrong instrument for this harness without fine-tuning.

**`granite4:350m`** — goal-echoes 2 of 4, and produces one confidently wrong answer:

> `"The system is allowed to call cloud APIs or use sensors in v0, but not for the first time."`

**`qwen2.5:0.5b`** — the project's current default. Goal-echoes 3 of 4, and on the fourth it echoes
the *question* back verbatim. This is the degenerate behavior the M1 audit found, still present and
now correctly scored as failure rather than as +0.60.

**`gemma3:1b`** — first model on the ladder that works. Two accepted, genuinely responsive answers:

> `"The minimum viable model size on Jetson Orin Nano 8GB is 2GB. This matters because it's a small, loc…"`
> `"The goal is to demonstrate how a conditioned-kernel substrate can outperform bare generation on a sm…"`

Still imperfect: it goal-echoes on `probe_intent`, and on `probe_local` it emitted the literal
schema type name `"STRING"`.

## Caveat that limits the accepted answers

The first accepted answer above states the minimum viable model size "is 2GB." **That is
fabricated** — the open thread is a question, not a finding. It was accepted because the probe's
`answer_key` only requires the phrase "minimum viable" to appear.

So the harness still cannot detect a hallucinated specific inside an otherwise responsive answer.
`must_not_contradict_facts` catches contradictions with packet facts; nothing catches invention of
facts not in the packet. That is a real gap and it is now demonstrated, not theoretical.

## qwen3.5 did not fail — the harness timed out on it

Both Qwen3.5 models returned `Ollama request failed: timed out` on **every** row. The
`orin_nano_8gb` profile sets `timeout_s: 90`; Qwen3.5's thinking mode runs far past it.

Their initial aggregate scores of `0.000` are **harness timeouts, not model quality**, and must not
be read as results. `run_matrix.py` now takes `--timeout` to override the profile, and a rerun at
900s is in progress.

The latency itself is a product finding regardless of what the rerun shows:

| model class | full matrix (12 inferences) |
|---|---:|
| non-thinking (`gemma3:1b`, `qwen2.5:0.5b`, `granite4:350m`) | 64–85 s |
| thinking (`qwen3.5:0.8b`, `qwen3.5:2b`) | 1092–1102 s, still timing out per-call |

That is a 16x wall-clock difference. For an edge node with an interactive budget, thinking mode at
this size is disqualifying on latency alone, whatever it does for quality. If Qwen3.5 is to be used
here it should be evaluated in non-thinking mode.

## What this does not show

- Single run per model, 4 probes. No seeds, no repeats. These are directional, not statistical.
- `gemma3:1b` beating the others does not establish substrate gain. Its headline is **0.000** —
  CK ties budget-matched bare. The ladder shows where the substrate *starts functioning*, not
  where it starts *winning*.
- No model on this ladder yet shows positive substrate gain on the product target.
