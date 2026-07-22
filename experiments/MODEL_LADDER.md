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

**The aggregator now fails closed on this.** Before the guard, the timed-out Qwen3.5 artifact
reported `headline: +0.125` — computed from twelve rows that never observed a model output. The
errored CK rows even scored `semantic_score: 0.25` and `goal_referenced: true` on an *empty*
answer, because validation short-circuited before reaching the goal check and absence-of-violation
was read as success. Replaying that same artifact through the current code returns:

```json
{"composite": null, "valid": false, "failure_reason": "ck has no valid measurements",
 "ck_valid_n": 0, "control_valid_n": 0}
```

### The bug was one layer earlier than the aggregator

External review sharpened this correctly. Filtering invalid rows inside
`aggregate_condition` patched the symptom but preserved the ambiguity: a timed-out row still
looked like a completed inference (`output=""`, `error=None`), so nothing downstream could
distinguish a model that answered with nothing, a request that timed out before any response
existed, and a transport failure normalized to empty text.

> The Qwen3.5 result was not incorrectly scored. It was incorrectly **admitted** as a measurement.

The outcome is now classified where the Ollama call returns:

```
RunStatus = completed | timeout | transport_error | invalid_response
```

with `output=None` when nothing was observed and `""` **only** when the model genuinely answered
with nothing. An observed empty answer legitimately scores zero; a timeout has no score.

The primary figure is now `headline_paired_vs_budget_matched_bare`, which pairs CK against the
control per probe and requires **both sides observed**. Partial coverage yields no headline at
all — on a 4-probe experiment, silently averaging whatever survived changes the estimand. A
descriptive figure over surviving pairs is reported as `partial_observed_headline` alongside
`coverage`, and is never promoted.

The six raw artifacts are retained unmodified as evidence of the defect. Corrected derived
artifacts under `experiments/runs/ladder_20260722/corrections/` record the source commit, the
original artifact SHA-256, the correction reason, the original invalid headline, the corrected
`null`, the timeout count, and the harness-fix commits — superseding the number without erasing
the history.

`aggregate_condition` now partitions rows into valid and invalid (`error` set, or
`decision == "error"`), averages only over valid ones, and reports `valid_n` / `invalid_n` /
`failure_reasons`. `substrate_gain` refuses to emit a composite when either side has zero valid
measurements. A zero means the model completed and earned nothing; a timeout means the experiment
never observed the model. Merging them destroys the estimand.

The latency itself is a product finding regardless of what the rerun shows:

| model class | full matrix (12 inferences) |
|---|---:|
| non-thinking (`gemma3:1b`, `qwen2.5:0.5b`, `granite4:350m`) | 64–85 s |
| thinking (`qwen3.5:0.8b`, `qwen3.5:2b`) | 1092–1102 s, still timing out per-call |

That is a 16x wall-clock difference. For an edge node with an interactive budget, thinking mode at
this size is disqualifying on latency alone, whatever it does for quality. If Qwen3.5 is to be used
here it should be evaluated in non-thinking mode.

## Two thresholds, deliberately not merged

External review (2026-07-22) sharpened the framing, and the distinction is worth stating plainly:

1. **Functional threshold — found, ~1B.** Where the machinery becomes behaviorally live.
2. **Advantage threshold — not found.** Where CK beats the budget-matched control.

Keeping these separate is what stops this result inflating. The substrate begins operating at 1B;
it does not yet outperform bare generation given the same information.

The defensible claim is bounded to this configuration:

> Under this harness, packet, acceptance rule, quantization, runtime and device, functional
> conditioned-kernel behavior first appears between 0.5B and 1B parameters.

Not "1B is the universal minimum."

## Qualification on the −0.125 reproduction

Both runs used the same seed, temperature, prompts and model build, and the pipeline had already
been proven deterministic. So this is a **pipeline reproducibility receipt, not an independent
statistical replication.** It proves the same experiment now yields the same result instead of
drifting through ordering, parsing or aggregation. It says nothing yet about variance.

The next stronger receipt is to vary the generation seed while freezing everything else. Not done.

## The gap has a name

```
must_not_contradict_facts   ≠   must_be_supported_by_facts
```

The gate rejects statements that conflict with supplied evidence. It cannot reject a confident
statement about something the packet never established. The phrase-based answer key then *rewarded*
the fabrication because the string "minimum viable" appeared in it — the evaluator is vulnerable to
keyword laundering, where an answer satisfies the expected concept while asserting an unsupported
value.

The fix is evidence-bound acceptance, not a bigger blacklist. A candidate factual claim should
carry one of three statuses, with unmarked assertive claims rejected:

```
SUPPORTED   — cites packet evidence
DERIVED     — reproducibly computed from cited evidence
UNCERTAIN   — explicitly presented as hypothesis or unknown
```

**Open design tension, unresolved.** The natural implementation is proof-carrying output, where the
model emits per-claim `support_ids` the validator checks against the packet. That is much harder to
game than phrase matching. But this ladder just established that models below ~1B cannot produce
distinct answers at all, and asking a 1B model to additionally emit correct claim-level citations
may push the requirement *above* the linguistic threshold we are trying to operate under — which
would move work into the model and away from the substrate, against the project thesis.

The thesis-aligned alternative is substrate-side verification: mechanically extract factual and
numeric claims from the answer and check each against the packet, keeping the bookkeeping burden on
the substrate rather than the kernel. Which of the two survives contact with a 1B model is an
empirical question, and should be tested rather than assumed.

## What this does not show

- Single run per model, 4 probes. No seeds, no repeats. These are directional, not statistical.
- `gemma3:1b` beating the others does not establish substrate gain. Its headline is **0.000** —
  CK ties budget-matched bare. The ladder shows where the substrate *starts functioning*, not
  where it starts *winning*.
- No model on this ladder yet shows positive substrate gain on the product target.
