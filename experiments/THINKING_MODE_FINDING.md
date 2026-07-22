# Qwen3.5 returned nothing, not a low score

**Date:** 2026-07-22
**Status:** correction to [MODEL_LADDER.md](MODEL_LADDER.md), which understated this.
**Device:** Jetson Orin Nano 8GB, Ollama 0.24.0, CUDA, MAXN_SUPER

## The measurement

Plain `/api/generate` — no packet, no schema, no `format=`, default options, one neutral prompt:

| model | elapsed | eval_count | `thinking` field | `response` field |
|---|---:|---:|---:|---:|
| `qwen2.5:0.5b` | 2.1 s | 117 | absent | **644 chars** |
| `gemma3:1b` | — | — | — | HTTP 500 |
| `qwen3.5:0.8b` | 121.0 s | 4090 | **16,214 chars** | **0 chars** |
| `gemma3:4b` | — | — | — | HTTP 500 |

## What this corrects

`MODEL_LADDER.md` says thinking mode is *"disqualifying on latency alone, whatever it does for
quality."* That is true but it is not the main fact, and stating it that way implies we observed
poor quality. **We never observed its output at all.**

`OllamaClient.extract_text` reads `message.content` (chat mode) or `response` (generate mode). It
**never reads `thinking`**:

```python
def extract_text(response, mode):
    if mode == "chat_json":
        msg = response.get("message") or {}
        return (msg.get("content") or "").strip()
    return (response.get("response") or "").strip()
```

So Qwen3.5 spent 4,090 tokens reasoning into a field our harness does not look at, and returned an
empty string through the path it does look at. Its ladder scores of `0.000` were **not a quality
measurement**. They were an empty read.

It failed twice over, independently:

1. **121 s > the 90 s edge profile timeout** — the call never returned.
2. **Even on return, `response` is empty** — because the content went to `thinking`.

Fixing only the timeout would not have helped. That is the part the earlier write-up got wrong.

## Scope — what is NOT affected

**The continuity results stand.** Both models carrying every continuity number have no thinking
capability at all:

```
qwen2.5:0.5b   capabilities: ['completion', 'tools']   thinking: False
gemma3:1b      capabilities: ['completion']            thinking: False
```

Verified via `/api/show`, and confirmed empirically above: `qwen2.5:0.5b` produced a normal 644-char
response with no `thinking` field. So the token-shotgunning finding, the M1/M2 numbers, and the
structure observations are not contaminated by hidden reasoning traces.

Thinking was never enabled anywhere — we never set a `think` parameter, so Ollama's per-model
default applied, and for these two models that default is "no such mode".

## To evaluate Qwen3.5 fairly

Either is defensible; the choice should be preregistered, not made at run time:

- **`think: false`** — measures the model in the deployment mode an edge product would actually use.
- **read the `thinking` field** — measures what the model produced, at the true latency cost.

What is *not* defensible is the current situation: reading an empty string and scoring it as
performance. The existing correction artifacts under
`runs/ladder_20260722/corrections/` record those runs as timeouts; the empty-response mechanism is
a second, independent reason those numbers are void.

## Secondary

`gemma3:1b` and `gemma3:4b` return **HTTP 500 on `/api/generate`** — they require the chat template
and have no raw completion path. Harmless for this harness, which uses `/api/chat` throughout, but
it means any future `generate_raw` mode silently excludes the gemma3 family.

## Why this kept happening

Fifth instance today of the same class: a number that looked like a measurement and was not.
Goal-echo scored 1.0. Silence scored 0.43. Question-parroting scored 0.571. Shotgunning scored 1.0.
And an empty read scored 0.000 and was reported as model quality.

The tell each time was the same — a value that no real system would produce, accepted because it
had a plausible shape.
