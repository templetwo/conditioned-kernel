# Experiment Protocol — Conditioned Kernel v0

## Question

Can a persistent local substrate make a small model more coherent, more state-faithful, more continuous across turns, and more repairable than the same model run bare?

Secondary: do those gains survive model swap within the tested size band?

## Eligibility floor (model fungibility contract)

A model is eligible if it can:

1. Accept a bounded 2K–4K context
2. Return valid JSON or near-valid JSON often enough to be repairable
3. Obey stop / length constraints
4. Produce a short coherent answer from a state-heavy arrival packet

Below that floor the substrate has nothing stable to condition.

## Conditions

| ID | Condition | Description |
|---|---|---|
| C0 | Bare | User input only (fair: same JSON format instructions as CK when measuring) |
| C1 | Budget-matched bare | Same state mass, unstructured dump — **headline control** |
| C2 | Prompted persona | Static long system prompt, no live state compile |
| C3 | CK strict | Compiled packet + schema + validation + one repair |
| C4 | CK ablated compile | Packet without ordered/labeled state |
| C5 | CK ablated validation | Packet only, no repair/acceptance loop |

**C1 is the headline comparison.** C0 may be reported only as *information-access context*, not substrate gain.

Fairness (post M1 audit): same `format=` / system rules for all scored conditions unless an ablation explicitly removes them.

## Metrics

Split structural from semantic:

| Metric | Layer | Scoring |
|---|---|---|
| Parse rate | structural | valid JSON after first pass |
| Schema pass rate | structural | required fields present |
| Repair recovery | structural | recovered / repairable failures |
| State-faithfulness | semantic | closed-set evidence ids + no forbidden inventions |
| Continuity | semantic | cold-start resume of goal/thread from files only |
| Coherence | semantic | human or rubric score on-task completeness |

Do **not** use model `confidence` as a metric.

### Substrate Gain (composite)

Normalize each delta to [−1, 1] vs bare (prefer C1 as primary control once available):

\[
SG = \frac{1}{4}(\Delta C + \Delta F + \Delta T + \Delta R)
\]

Report structural and semantic composites separately as well.

## Continuity harness (required)

1. Turn 1: set goal G and open thread T via accepted output / state write
2. Kill process; no chat history retained in model context
3. Turn 2: cold-start from filesystem only; ask a question that fails without G/T
4. Score resume correctness

If this fails, the system is a single-shot wrapper.

## Model ladder

| Tier | Candidate | Role |
|---|---|---|
| Threshold probe | ~135M–350M class | lower bound |
| Lower band | ~360M–0.5B | first working baseline |
| Main band | Qwen2.5 0.5B / 1.5B | primary |
| Stretch | ~1.7B | ease comparison |

## Sampling defaults (benchmark mode)

- temperature: 0.2–0.4
- seed: fixed (e.g. 42)
- num_ctx: 2048–4096
- stream: false
- keep_alive: 5m
- format: JSON schema when model tolerates it

## Milestones

| M | Scope | Pass signal |
|---|---|---|
| M0 | scaffold + Ollama round-trip + receipt | one accepted local run |
| M1 | compile + strict validation | malformed output down vs bare |
| M2 | repair + acceptance logging | measurable rescue |
| M3 | model swap ladder | fungibility floor located |
| M4 | ablation suite | which parts matter |
| M5 | Jetson hardening | stable on-device profile |

## Acceptance sentence

Conditioned Kernel succeeds if the same small local model, when run through the substrate, becomes more coherent, more state-faithful, more continuous, and more repairable than when run against a **budget-matched** control—and if those gains survive a model swap within the tested size band.

No gain number is citable until `experiments/M1_AUDIT.md` criteria 1–9 hold and the run is free of goal-echo degeneracy (`distinct_answers` ≈ probe count for accepted rows).
