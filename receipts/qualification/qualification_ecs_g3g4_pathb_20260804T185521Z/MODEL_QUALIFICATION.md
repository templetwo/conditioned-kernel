# Model qualification

**Host:** tony-jetson aarch64  
**Profile budget:** orin_nano_8gb  
**Generated:** 2026-08-04T18:56Z  

Gate from `docs/WORK_ORDER_model_qualification.md`. Any failed required check is disqualifying.
Do **not** treat these verdicts as continuity quality — only as kernel-compatibility.

## Summary

| model | verdict | final | schema | latency_s | size_GB | thinking | raw_path | determinism |
|---|---|:---:|:---:|---:|---:|:---:|:---:|---|
| qwen2.5-coder:3b | QUALIFIED | Y | Y | 3.969 | 1.797 | N | Y | stable |
| granite4:micro | QUALIFIED | Y | Y | 4.251 | 1.955 | N | Y | stable |

## Stop using

_None on this host run._

## Recommended default

**qwen2.5-coder:3b** — only models with observed final responses, schema compliance, and edge latency budget. gemma3:1b preferred when qualified (first ladder functional band). qwen2.5:0.5b may qualify as a kernel but is below the functional continuity threshold.

## Notes

- Check 3 always records thinking_chars separately via `OllamaClient.run()`.
- Check 8 (raw path) is recorded; HTTP 500 on `/api/generate` is a note, not always disqualifying for chat-only harnesses.
- Determinism class `bimodal_cold_warm` matches DETERMINISM.md; not automatic disqualification.
- Models not installed are DISQUALIFIED for this host (re-run on Jetson for full candidate list).


## F1 / environment provenance

- **hostname:** tony-jetson
- **machine:** aarch64
- **MemFree / MemAvailable (start):** 2751 / 6728 MB
- **barrier:** MemFree fail-closed (#9938/#13706/path b)
- **threshold_source:** harness/device/generators.json
- **thread_18:** path_b
