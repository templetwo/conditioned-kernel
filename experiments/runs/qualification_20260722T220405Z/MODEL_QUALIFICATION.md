# Model qualification

**Host:** Anthonys-MacBook-Pro.local arm64 (Mac Studio/Pro seat; Jetson re-run still needed for qwen3.5)  
**Profile budget:** orin_nano_8gb  
**Generated:** 2026-07-22T22:06Z  

Gate from `docs/WORK_ORDER_model_qualification.md`. Any failed required check is disqualifying.
Do **not** treat these verdicts as continuity quality — only as kernel-compatibility.

## Summary

| model | verdict | final | schema | latency_s | size_GB | thinking | raw_path | determinism |
|---|---|:---:|:---:|---:|---:|:---:|:---:|---|
| qwen2.5:0.5b | QUALIFIED | Y | Y | 1.309 | 0.37 | N | Y | stable |
| gemma3:1b | QUALIFIED | Y | Y | 10.533 | 0.759 | N | Y | stable |
| gemma3:4b | QUALIFIED | Y | Y | 11.48 | 3.11 | N | Y | stable |
| granite4:350m | QUALIFIED | Y | Y | 1.65 | 0.66 | N | Y | stable |
| functiongemma:270m | DISQUALIFIED: not installed on this host | N | N |  |  | N | N |  |
| qwen3.5:0.8b | DISQUALIFIED: not installed on this host | N | N |  |  | N | N |  |
| qwen3.5:2b | DISQUALIFIED: not installed on this host | N | N |  |  | N | N |  |
| gemma4:e2b | DISQUALIFIED: too_large:6.67GB_on_8.0GB_class; memory | Y | Y | 20.26 | 6.671 | N | Y | stable |
| gemma4:e4b | DISQUALIFIED: not installed on this host | N | N |  |  | N | N |  |

## Stop using

- **functiongemma:270m** — DISQUALIFIED: not installed on this host
- **qwen3.5:0.8b** — DISQUALIFIED: not installed on this host
- **qwen3.5:2b** — DISQUALIFIED: not installed on this host
- **gemma4:e2b** — DISQUALIFIED: too_large:6.67GB_on_8.0GB_class; memory
- **gemma4:e4b** — DISQUALIFIED: not installed on this host

## Recommended default

**gemma3:1b** — only models with observed final responses, schema compliance, and edge latency budget. gemma3:1b preferred when qualified (first ladder functional band). qwen2.5:0.5b may qualify as a kernel but is below the functional continuity threshold.


## Host note

This run was on **Apple Silicon (local HQ)**, not the Jetson. Verdicts for installed models
still hold as kernel-compat on this host. **`qwen3.5:*` and `functiongemma:270m` must be
re-qualified on Jetson** where they live — that is where the empty-read trap was observed
(#9868). Until that re-run, treat Jetson-only tags as **UNVERIFIED on Jetson** rather than
cleared.

## Stop using (product recommendation)

| model | why |
|---|---|
| **qwen3.5:0.8b / 2b (default thinking)** | #9868: thinking fills, final response empty; harness cannot read `thinking` as answer. Re-test with `think:false` on Jetson before any experiment. |
| **gemma4:e2b / e4b** | Memory: ~6.7GB+ on 8GB class after OS headroom — fails fit check. |
| **qwen2.5:0.5b as continuity subject** | Kernel-QUALIFIED here, but ladder says below functional threshold (goal-echo band). OK for harness smoke only. |
| **functiongemma:270m** | Not a dialogue kernel (ladder: echoes system prompt). |

## Recommended default

**gemma3:1b** — QUALIFIED kernel; first size band with non-degenerate ladder accepts; fits edge; chat path works.

Secondary for load tests: **granite4:350m** or **qwen2.5:0.5b** (smoke only).

**gemma3:4b** — QUALIFIED and fits; reserved for preregistered higher-threshold runs only.

## Notes

- Check 3 always records thinking_chars separately via `OllamaClient.run()`.
- Check 8 (raw path) is recorded; HTTP 500 on `/api/generate` is a note, not always disqualifying for chat-only harnesses.
- Determinism class `bimodal_cold_warm` matches DETERMINISM.md; not automatic disqualification.
- Models not installed are DISQUALIFIED for this host (re-run on Jetson for full candidate list).

