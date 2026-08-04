# Best Small Coding Models via Ollama for a Jetson Orin Nano 8GB (August 2026)

## TL;DR
- **Run two families: `qwen2.5-coder:3b` (1.9 GB, Qwen family) and `granite4:micro` (2.1 GB, IBM Granite family)** as your two independent local C-code generators. Both fit with wide margins inside the ~5 GB usable budget with room for a multi-thousand-token KV cache, both run on aarch64/Ollama, and they come from genuinely different model families for real cross-model agreement diversity.
- Avoid 4B+ models as your *primary* generators: on the 8GB Orin Nano only ~5.2 GB of unified memory is usable after OS overhead, and independent testing shows the device is memory-bandwidth-bound, so heavier models run slowly or stall. A 4B such as `qwen3:4b` (2.5 GB) or `qwen3.5:4b` (3.4 GB) *can* fit for single-stream use but leaves less KV headroom and is slower.
- Best coding-per-GB at ≤3B is **Qwen2.5-Coder-3B**, a purpose-built code model. Vendor-reported HumanEval is 84.1 (arXiv:2409.12186, Table 16), while an independent OpenCompass run reports 45.12 — the truth is in between, but even the low end beats general models of the same size. Granite 4.0 Micro is the strongest non-Qwen alternative with Apache-2.0 licensing and a 128K context.

## Key Findings
- **The hard limit is memory, not compute.** Eric X. Liu's 66-test benchmark ("Why Your Jetson Orin Nano's 40 TOPS Goes Unused") found: *"After running 66 inference tests across seven different language models ranging from 0.5B to 5.4B parameters... The bottleneck isn't computation—it's memory bandwidth,"* and lists *"Available VRAM: Approximately 5.2GB."* The 8GB is unified LPDDR5 shared by CPU+GPU; theoretical peak bandwidth is 68 GB/s on the original Orin Nano 8GB (raised to 102 GB/s and 67 TOPS on the Dec-2024 "Super" firmware).
- **Two sub-3B coding-capable models fit with wide margins:** `qwen2.5-coder:3b` at 1.9 GB and `granite4:micro` at 2.1 GB. A few-thousand-token KV cache adds only a few hundred MB, so total footprint stays ~2.5–3 GB — comfortably inside 5 GB.
- **Code-specialized beats general at this size.** For generating small correct C kernels from a spec, the dedicated Qwen2.5-Coder-3B outperforms general 4B models (Gemma, Llama, Phi). Phi-4-mini and Qwen3-4B are respectable generalists but not code-tuned.
- **The very newest 2026 releases don't win this tradeoff.** Qwen3.5's small series and Gemma 4 are either 4B+ (tighter fit, slower) or multimodal MoE designs whose GGUFs have had Ollama compatibility hiccups; none beats the dedicated 3B coder on fit-vs-code-quality.
- **Family diversity is satisfiable.** Qwen (Qwen2.5-Coder) and IBM Granite are architecturally and training-data distinct, giving meaningful independence for a cross-model agreement measurement.

## Details

### The memory budget (verify against ~5 GB, not 8 GB)
Liu's benchmark reports ~5.2 GB usable after OS overhead and recommends staying small to preserve KV-cache headroom. The memory-bandwidth wall is well documented: *"quantized sub-1B models hit 25-40 tokens/second, with Ollama consistently outperforming vLLM by 2-6×"* (Liu). A dense 3B is the practical ceiling for responsive single-stream use — NVIDIA's Jetson AI Lab benchmarks Llama 3.2 3B at 27.7 tok/s (cited by Liu: *"independent benchmarks from NVIDIA's Jetson AI Lab (Llama 3.2 3B at 27.7 t/s, SmolLM2 at 41 t/s)"*), and a stock-Ollama Q4_K_M run measured ~28.7 tok/s decode at 2.3 GB / 11.2 W. In the same 0.5B–5.4B sweep, larger 4B-class models are where single-stream memory-bandwidth limits begin to dominate — one multi-user benchmark (NavyaAI) found 4B models *"loaded but failed to complete requests under concurrent load."* For a single-stream research harness, a 3B Q4_K_M model is the safe sweet spot.

**Practical Jetson/Ollama note:** GPU acceleration on Jetson has historically depended on JetPack/CUDA versions and often required the ARM64 container builds (dusty-nv/jetson-containers) rather than the stock binary; recent Ollama versions run natively on aarch64, but confirm actual GPU offload with `ollama ps`. QAT variants and a reduced `num_ctx` are the two levers that make marginal models fit. Watch `jtop`/`tegrastats` — if swap climbs during inference, use a smaller model or shorter context rather than adding swap.

### Shortlist of candidates (≤~4–5B, ranked for this task)

| Model (Ollama tag) | Params | Q4 size | Context | Coding evidence | License | Fit on ~5 GB |
|---|---|---|---|---|---|---|
| **qwen2.5-coder:3b** | 3.09B | 1.9 GB | 32K | Code-specialized. HumanEval 84.1 / MBPP 73.6 (vendor, arXiv:2409.12186 Table 16); 45.12 HumanEval / 30.20 MBPP (independent OpenCompass, QwenLM Issue #420); HuggingFace baseline HumanEval pass@1 0.52; top-5 in 2026 SLM code study | Qwen Research (non-commercial) | ✅ excellent |
| **granite4:micro** | 3.4B | 2.1 GB | 128K | Granite code lineage strong on multi-language incl. C; FIM code-completion; enterprise/tool-calling focus | Apache 2.0 | ✅ excellent |
| granite4:micro-h (hybrid mamba-2) | 3.19B | 1.9 GB | 128K | Same family; hybrid arch may be less optimized in llama.cpp/Ollama | Apache 2.0 | ✅ excellent |
| qwen2.5-coder:1.5b | 1.5B | ~1.0 GB | 32K | HumanEval ~43.9, MBPP ~69.2; weaker but tiny, and Apache 2.0 | Apache 2.0 | ✅ huge margin |
| qwen3:4b | 4.02B | 2.5 GB | 256K | Strong generalist ("rivals Qwen2.5-72B"); not code-specialized | Apache 2.0 | ⚠️ fits, less KV headroom |
| qwen3.5:4b | 4.66B | 3.4 GB | 256K | Newer (Feb 2026) multimodal MoE; GGUF/Ollama compat caveats reported | Apache 2.0 | ⚠️ tight |
| phi4-mini (3.8B) | 3.8B | ~2.5 GB | 128K | Strong reasoning/math; good code for size; MIT license | MIT | ✅ good |
| gemma3:4b | 4B | 3.3 GB | 128K | Weak at code (Gemma 3 27B only ~48.8 HumanEval); multimodal overhead | Gemma license | ⚠️ tight, weak code |
| starcoder2:3b | 3B | ~1.7 GB | 16K | Older base FIM model, weaker instruct code-gen (HumanEval ~31.7) | BigCode OpenRAIL-M | ✅ fits but dated |
| deepseek-coder:1.3b | 1.3B | ~0.8 GB | 16K | 2023-era; HumanEval ~34.8 | DeepSeek license | ✅ fits but dated |
| llama3.2:3b | 3B | ~2.0 GB | 128K | General model, mediocre code | Llama license | ✅ fits, weak code |

### On the very newest models (recency check)
- **Qwen3.5 small series** (0.8B/2B/4B/9B, released Feb 2026, Apache 2.0): the 4B is 3.4 GB at Q4_K_M (params 4.66B) with 256K context. It's a multimodal Gated-DeltaNet/sparse-MoE design; Unsloth documented that some Qwen3.5 GGUFs did *not* initially work in Ollama due to separate mmproj vision files. Not code-specialized — fits, but no clear coding win over the 3B coder.
- **Qwen3.6** (April 2026): only 27B and 35B-A3B variants exist — far too large for 8GB.
- **Gemma 4** (April 2026, Apache 2.0): smallest official tags are e2b (7.2 GB) and e4b (9.6 GB default) — both exceed the budget at standard quant. Only the QAT build (e.g. `gemma4:e2b-it-qat` ~4.3 GB) fits, and Gemma remains comparatively weak at code.
- **IBM Granite 4.0** (Granite-4.0-Micro released October 2, 2025, Apache 2.0, ~15T training tokens, FIM code-completion, 128K validated context): the Micro (3B dense) and Micro-H (hybrid) are ideal-sized; Nano 350M/1B exist for extreme constraints.
- A dedicated small **Qwen3.5-Coder at ≤4B does not exist** in the official Ollama library as of August 2026 (only large community MoE uploads such as 35B).

### Why Qwen2.5-Coder-3B despite being "older"
It remains best-in-class among dedicated code models at 3B. It was trained specifically for code generation, reasoning, and repair across 40+ languages including C/C++, ships FIM support, and consistently ranks near the top of independent small-model code studies (a 2026 SLM study placed Qwen2.5-Coder-3B in the top five, pass@1 ~0.59, comparable to larger models). For generating small correct C kernels from a spec, a code-specialized 3B beats a general-purpose 4B. **One real caveat:** the 3B size is under the **Qwen Research License (non-commercial)** — unlike the 1.5B/7B/32B, which are Apache 2.0 (confirmed directly on the Ollama model pages). Fine for a research harness; for commercial productization, switch to `qwen2.5-coder:1.5b` (Apache 2.0) or the Granite pick.

## Recommendations

**Primary picks (two families):**

1. **Qwen2.5-Coder-3B** — best small dedicated C-code generator; fits with wide margin.
   ```
   ollama pull qwen2.5-coder:3b-instruct-q4_K_M
   ```
   (equivalently `ollama pull qwen2.5-coder:3b` — the identical 1.9 GB blob, digest `f72c60cabf62`). *Reason:* purpose-built code model, highest coding quality per GB at ≤3B, ~1.9 GB leaves ample KV headroom.

2. **IBM Granite 4.0 Micro** — strongest non-Qwen counterpart for family diversity.
   ```
   ollama pull granite4:micro
   ```
   *Reason:* different family and training corpus (true cross-model independence), Apache 2.0, 128K context, 2.1 GB fits easily.

**Backups (if a pick misbehaves or you need alternatives):**
- `ollama pull granite4:micro-h` — hybrid mamba-2 Granite, 1.9 GB, newest Granite arch (watch for llama.cpp/Ollama optimization maturity).
- `ollama pull qwen2.5-coder:1.5b` — Apache-2.0, ~1 GB, drop-down if you hit memory pressure or need a permissive license.
- `ollama pull phi4-mini` — MIT-licensed 3.8B generalist with solid code/reasoning; a third-family option (Microsoft) if you want maximum family separation from Qwen and Granite.

**Operational settings:** cap context (e.g. `PARAMETER num_ctx 4096`) — your kernels need only a few thousand tokens, which minimizes KV cache. Run `sudo nvpmodel -m 0 && sudo jetson_clocks` for max performance. Verify GPU offload with `ollama ps`; if it's CPU-only, use the jetson-containers Ollama image. Set `OLLAMA_KV_CACHE_TYPE=f16` if you observe accuracy degradation on longer prompts.

**Thresholds that would change the recommendation:**
- If measured single-stream throughput is unacceptably low (<5 tok/s) or you see swap activity in `jtop`/`tegrastats`, drop to `qwen2.5-coder:1.5b`.
- If you need commercial licensing, replace Qwen2.5-Coder-3B with the 1.5B (Apache 2.0) or rely on Granite.
- If the harness later needs large context or multi-file reasoning, neither pick suffices on 8GB — move to a Jetson AGX Orin.

## Caveats
- **No published benchmark tests `qwen2.5-coder:3b` by name on an Orin Nano 8GB.** The fit is certain (1.9 GB ≪ 5 GB usable). Throughput is inferred from same-class dense 3B models (Llama 3.2 3B ≈ 27.7 tok/s per NVIDIA Jetson AI Lab; ~28.7 tok/s in a stock-Ollama Q4_K_M run). Expect roughly 10–28 tok/s depending on backend, quant, and power mode; benchmark on your own device.
- **Vendor vs. independent benchmark gap.** Alibaba's own HumanEval 84.1 for the 3B (arXiv:2409.12186, Table 16) is far above the independent OpenCompass result of 45.12 (QwenLM Issue #420) and a HuggingFace baseline of 0.52. Treat vendor numbers as optimistic; your own harness (which measures execution correctness on C kernels) is the authoritative signal.
- **License:** Qwen2.5-Coder-3B is Qwen Research (non-commercial) — a genuine distinction from its Apache-2.0 siblings and from Granite/Phi-mini.
- **aarch64/Jetson GPU acceleration** has historically depended on JetPack/CUDA versions and container builds; confirm your Ollama build actually uses the GPU rather than silently running on CPU.
- Several 2026 "best model" blog posts contain forward-looking or promotional content and unverified benchmark numbers; this report prioritized official Ollama library pages, vendor model cards (Alibaba/IBM/Microsoft), arXiv technical reports, and NVIDIA developer sources. Tag sizes are as of August 2026 — re-verify with `ollama show <tag>` before committing.