# Determinism findings — load state, quantization, and backend

**Date:** 2026-07-22
**Status:** raw findings, published as measured. No claim is promoted beyond what the hashes support.

Hashes below are `md5 | cut -c1-12` of the final answer line from `ck ask`. Identical hash =
byte-identical answer. Substrate state hash was captured before and after every sequence and
never changed (`ab670e93`), so persistent state is excluded as a variable.

## Why this file exists

The post-audit matrix produced **+0.031** and then **−0.125** from the same command on the same
machine. The cause was not the scorer. It was that `run_matrix.py` does not control whether the
model is resident in VRAM when a run starts.

## F-D1 — Bimodal determinism under Q4_K_M on CUDA

Jetson Orin Nano 8GB, `qwen2.5:0.5b` (Q4_K_M, digest `a8b0c515…`), Ollama 0.24.0, MAXN_SUPER,
clocks locked. Prompt: *"Name one open research thread from the current substrate and why it matters."*

| Sequence | Hash |
|---|---|
| COLD_A (after eviction) | `2a8061e5c31c` |
| WARM_A | `8cef27259503` |
| WARM_B | `8cef27259503` |
| COLD_B (after eviction) | `2a8061e5c31c` |
| COLD_C (after eviction) | `2a8061e5c31c` |

Not noise. Two attractors, each perfectly stable within itself. First inference after a model
load lands in one; every subsequent inference lands in the other.

## F-D2 — The Mac does not reproduce it, and agrees with COLD

Apple Silicon, Metal, Ollama 0.20.7, **identical model digest and byte size**. Same prompt.

| Sequence | Hash |
|---|---|
| COLD_A, WARM_1, WARM_2, WARM_3, WARM_4, COLD_B, WARM_5 | `2a8061e5c31c` (all seven) |

The Mac is stable in both load states, and its answer equals the Jetson's **cold** answer exactly.
The Jetson's warm mode is the deviant one.

## F-D3 — fp16 eliminates it

Jetson, same prompt, `qwen2.5:0.5b-instruct-fp16` (F16, 0.99 GB vs 0.40 GB).

| Sequence | Hash |
|---|---|
| COLD_A, WARM_1, WARM_2, WARM_3, COLD_B, WARM_4 | `1021fe01697d` (all six) |

Moving precision from Q4_K_M to F16 removes the effect entirely. This is the controlled variable:
same device, same runtime, same prompt, same load-state protocol.

## F-D4 — SCOPE LIMIT: it is prompt-specific, not systematic

The finding above is real but narrower than it first appeared. Same device, same Q4_K_M model,
three additional prompts:

| Prompt | Cold | Warm | Verdict |
|---|---|---|---|
| "State the current design intent in two sentences. Cite the goal." | `df8f63fd92` | `df8f63fd92` | stable |
| "Is this system allowed to call cloud APIs or use sensors in v0?" | `a89d05c133` | `a89d05c133` | stable |
| "What is the active edge profile?" | `7fb14cfea2` | `7fb14cfea2` | stable |

**1 of 4 prompts affected.** The honest claim is not "Q4 on CUDA is nondeterministic." It is that
*some* generations sit near a token decision boundary where Q4_K_M rounding plus a change in CUDA
kernel path (cold vs warm) is enough to flip the outcome. At F16 the precision headroom is large
enough that the boundary is not reached.

This scope is sufficient to explain the matrix variance: `probe_threads` is one of four probes, and
one probe flipping is exactly the observed magnitude between +0.031 and −0.125.

## Consequences for the harness

1. **`run_matrix.py` must control load state.** Either evict before every run, or burn a priming
   inference and discard it. Until then a run's result depends on whether the model happened to be
   resident, which is not a property of the substrate under test.
2. **Reproducibility claims must state load state and quantization.** "Same seed, same temperature"
   is insufficient on this stack.
3. **Cross-device comparison remains confounded.** Mac Ollama 0.20.7 vs Jetson 0.24.0 is
   uncontrolled. Model digest is verified identical, so the model is not the confound.
4. **Consider F16 for the measurement path.** 0.99 GB vs 0.40 GB buys determinism on a device with
   ~6.8 GB free. Q4_K_M remains the deployment-realistic condition and should be measured, but
   separately and with load state pinned.

## Raw matrix runs behind this

| Run | Device | Load state | headline vs budget_matched |
|---|---|---|---:|
| `jetson_run1` | Jetson | cold start | +0.03125 |
| `jetson_run2` | Jetson | warm (back-to-back) | +0.03125 |
| `jetson_clean` | Jetson | cold (post-cleanup) | **−0.125** |
| `runC` / `runD` | Mac | back-to-back | +0.09375 (both) |

No substrate-gain number in this table should be cited. They are recorded to show the spread,
not to support a claim.

## Environment

| | Mac | Jetson |
|---|---|---|
| arch / system | arm64 / Darwin 25.5.0 | aarch64 / Linux, JetPack L4T R36.4.7 |
| Ollama | 0.20.7 | 0.24.0 |
| backend | Metal | CUDA |
| power | n/a | MAXN_SUPER, `jetson_clocks` locked |
| model digest | `a8b0c51577010a279d933d14c2a8ab4b…` | identical |
| model bytes | 397,821,319 | identical |
| quantization | Q4_K_M | Q4_K_M |

`run_matrix.py` now records this block as `environment` in every artifact, because two runs
labelled with the same profile are not comparable without it.
