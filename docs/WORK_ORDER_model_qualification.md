# Work order — model qualification gate (Grok Build seat)

**Why this exists:** we ran experiments on models we had never qualified, and it cost us.
`qwen3.5:0.8b` produced 16,214 characters of reasoning and a **zero-character final response**, and
we recorded that as a quality score of 0.000 across two ladder runs before catching it. **That
would have been caught in thirty seconds by a qualification gate.** Anthony's read is correct: this
should have been caught earlier, and model choice has to stop being incidental.

**Deliverable:** `experiments/qualify_models.py` + `experiments/MODEL_QUALIFICATION.md` +
`tests/test_model_qualification.py`.

**Not in scope:** scoring, the continuity corpus, the scorer, any experiment rerun. The scorer
redesign is **HALTED** pending a project re-grounding (see below).

## The gate

A model is **QUALIFIED** for Conditioned Kernel experiments only if it passes every check. Any
failure is disqualifying and must be recorded with the reason — a disqualified model is a result,
not a gap.

| # | Check | Pass condition | Why |
|---|---|---|---|
| 1 | Capability probe | `/api/show` returns capabilities; record whether `thinking` is present | We never checked this before running |
| 2 | **Final response observed** | `/api/chat` returns non-empty `message.content` | The qwen3.5 trap. Reasoning is not an answer |
| 3 | Reasoning channel measured | record `thinking` chars separately, never as output | Channels must not merge |
| 4 | `think:false` honoured | if the model has thinking, setting `think:false` yields a final response | Determines if it can run as a direct-output kernel |
| 5 | Latency under budget | full round trip < the profile `timeout_s` (90 s on `orin_nano_8gb`) | Edge product constraint |
| 6 | Schema compliance | with `format=CANDIDATE_FORMAT`, returns parseable JSON with the required keys | The substrate depends on it |
| 7 | Fits memory | loads on the 8 GB board without eviction thrash; record VRAM footprint | `gemma4:e2b` is 7.2 GB — nominally an "edge" model, unusable here |
| 8 | Raw path note | record whether `/api/generate` works | `gemma3:1b` and `gemma3:4b` return **HTTP 500** — they need the chat template |
| 9 | Determinism class | same prompt cold vs warm, twice each; record whether outputs are stable | Q4_K_M on CUDA is bimodal on some prompts — see `DETERMINISM.md` |

Use `OllamaClient.run()`, which already returns `RunStatus` and records
`thinking_chars` / `final_response_chars` / `quality_admitted` (commit `b42d3fb`). **Do not
reimplement extraction.** Do not modify `generate.py`.

## Candidates

Everything currently on the Jetson, plus anything you judge worth pulling. Include the failures —
a disqualification is evidence:

```
qwen2.5:0.5b   gemma3:1b   gemma3:4b   granite4:350m   functiongemma:270m
qwen3.5:0.8b   qwen3.5:2b  gemma4:e2b  gemma4:e4b
```

`qwen3.5` must be tested **both ways**: default, and with `think:false`. That answers a real
question we have not answered — *can it function as a direct-output kernel with reasoning
disabled?* Keep it separate from any continuity claim; it is a kernel-compatibility question.

## Output

`MODEL_QUALIFICATION.md` with one row per model, per check, plus a single verdict column
(`QUALIFIED` / `DISQUALIFIED: <reason>`). Record the raw evidence under
`experiments/runs/qualification_<date>/`.

Then state a **recommended default** with reasoning, and — importantly — **the models we should
stop using and why.**

## Constraints

- Frozen layer (`score.py`, `return_path/`, `generate.py`) is **read-only**. It unfreezes only on a
  red test plus a reproducer.
- Corpus is yours but **not part of this order** — leave it alone.
- `pytest -q` must stay green (80 tests at time of writing).
- Record findings to T2Helix domain `conditioned-kernel,coordination` with tag `SEAT-BOARD`.

## Context you need

The scorer is **known broken** and its redesign is halted. It measures token shotgunning, not
continuity: a 0.5B model outscored `gemma3:1b` by dumping every identifier it could see. **Do not
tune anything against current scores.** Qualification is about whether a model can participate in
an experiment at all, which is upstream of, and independent from, how well it does.

The governing law from today, earned five times over:

> Before evaluating an event, verify that the event being evaluated is the event that actually
> occurred.

Qualification is that law applied one level earlier — before we spend an experiment on a model, we
prove the model can produce the class of output the experiment intends to measure.
