# Edge Spec — Conditioned Kernel

**Primary deployment target:** NVIDIA Jetson Orin Nano 8 GB (ARM64).  
**Secondary:** any local host that can *simulate* the edge budget (dev on HQ Mac is fine if profiles stay edge-default).

This is not “desktop first, Jetson later.”  
If it does not fit the edge budget, it is not v0-complete.

## Hardware budget (Orin Nano 8 GB)

| Resource | Budget | Rule |
|---|---|---|
| Unified RAM | 8 GB total | OS + Ollama runtime + **one** model + substrate |
| Model slot | ≤ ~2.5 GB resident preferred | Q4/Q5 quant; never two models loaded |
| Context | **2048 default**, 4096 stretch | Stretch only after measure |
| CPU substrate | ≤ ~300 MB RSS target | stdlib + httpx only in v0 |
| Disk logs | rotate / cap | Append JSONL, no unbounded growth assumed free |
| Network | **none required** | localhost Ollama only |
| Sensors / tools | off | out of scope v0 |
| Power | 7–25 W class | Prefer short keep-alive; unload when idle |

Reference points (measure on device; do not treat as guarantees):

- Orin Nano 8 GB: 8 GB LPDDR5, up to ~68 GB/s (higher on MAXN SUPER profiles)
- Ollama ARM64 Linux install path is required on Jetson
- Bandwidth and thermal headroom matter as much as “parameter count”

## Software constraints

1. **One active model at a time.** Swaps are explicit, measured, and logged.
2. **Short arrival packets.** Compile must bound facts, threads, and serialized size.
3. **No streaming to the terminal before accept.** Buffer full candidate (edge-friendly: avoids partial UI work).
4. **CPU for substrate, GPU/NPU bandwidth for the model.**
5. **Quantization assumed.** Prefer instruction Q4-class tags on Ollama.
6. **Fail closed on budget exceed** in `edge` profile (reject compile or refuse generate) rather than thrashing.
7. **Cold start continuity from files**, not from model KV cache (KV is expensive on edge).

## Profiles

| Profile id | Role | num_ctx | max packet bytes | max repair | keep_alive |
|---|---|---|---:|---:|---|
| `orin_nano_8gb` | **default product** | 2048 | 6000 | 1 | 2m |
| `orin_nano_tight` | thermal/memory stress | 1024 | 3500 | 1 | 0 |
| `desktop_dev` | HQ velocity only | 4096 | 12000 | 1 | 5m |

Default CLI/runtime profile: **`orin_nano_8gb`**.  
`desktop_dev` is opt-in, never accidental.

## Model ladder under edge budget

| Tier | Params | Edge role | Notes |
|---|---|---|---|
| Probe | ~350M | floor / fail probe | `granite4:350m` class |
| Primary | 0.5B | main product band | `qwen2.5:0.5b` |
| Stretch | 1.5B | only if RSS + latency pass | `qwen2.5:1.5b` |
| Cap | ~1.7B | research only on Nano 8G | do not promise |

## Acceptance for edge readiness

A build is edge-ready when:

1. Full turn works under `orin_nano_8gb` profile defaults.
2. Packet compile enforces size bounds (test-covered).
3. Status reports profile + estimated memory class.
4. Logs include telemetry (eval counts/durations when Ollama provides them).
5. A cold-start second process resumes from `state/` without relying on model keep-alive.
6. Docs do not assume desktop RAM or multi-model load.

## Non-goals on edge v0

- Multi-model routing
- Long-context RAG
- Always-on keep-alive of large weights
- Cloud fallback
- GPU-accelerated substrate (Python path stays simple)

## Dev vs deploy

| Host | Allowed | Must still |
|---|---|---|
| Mac Studio / MacBook | Develop + matrix | Run with `orin_nano_8gb` profile as default |
| Jetson Orin Nano 8G | Product path | Measure RSS, tokens/s, thermal; record receipts |

Architecture is identical; only profile knobs change.
