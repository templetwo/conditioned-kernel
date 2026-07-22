# Continuity experiment — preregistration

**Status:** preregistered design, written before implementation. 2026-07-22.
**Supersedes nothing.** This is the experiment `EXPERIMENT_PROTOCOL.md` marked *(required)* and
that has never been built.

The measurement layer is frozen at **52 passing tests** for the duration of this build (see
[Freeze](#freeze)). This document is the thing to point the instrument at.

## Why this and not more evaluator work

The ladder answered a supporting question — how small the replaceable transducer can be before the
substrate stops functioning (between 0.5B and 1B). It did **not** test the project's actual claim.

Everything measured so far is single-turn Q&A, which is the case most favourable to a bare model
and least favourable to the thesis: a bare model handed the same information in its prompt *should*
tie on a one-shot question. The recorded "advantage threshold not found" is therefore a claim about
single-turn Q&A, not about the substrate.

> The central test: can the substrate preserve and restore useful task continuity across a genuine
> cold start better than a budget-matched bare condition?

## Experimental unit

Each probe is **two episodes separated by a real process boundary.**

1. **Episode A** — the model receives a task, goal, constraints, evidence, and an unresolved next
   step. Its accepted output and state writes are frozen as artifacts.
2. **Boundary** — the process terminates. No chat cache, no hidden transcript, no resident model
   state survives. Different PID on the far side, proven by receipt.
3. **Episode B** — a fresh invocation must resume the work.

## Arms (three, always)

One Episode A run produces **one frozen artifact set**. All arms derive from those same artifacts.
This is structural, not aspirational — "same amount of information" is not a measurable property,
so it is replaced by a construction rule:

| Arm | Episode B context | Role |
|---|---|---|
| `bare_serialized` | naive chronological dump of the frozen artifacts, truncated to budget | budget-matched control |
| `ck_packet` | the compiled arrival packet built from the same artifacts | treatment |
| `broken_packet` | deliberately corrupted packet (shuffled/blanked state) | **permanent floor control** |

Identical token budget, model, decoding settings, seed, and evaluation rule across arms. The only
difference is *how the same information is structured*.

The question is **not** "memory versus no information." It is:

> Does the structured substrate use a fixed context budget more effectively than an ordinary prompt
> carrying the same information?

**Whoever writes the bare condition decides the outcome.** Its serialization is specified here, in
the protocol, not chosen in an editor at run time. `broken_packet` stays in every run, not just a
one-off validation — it is what proves the instrument can still detect failure on the day it
matters.

## Continuity dimensions

Seven dimensions, scored separately rather than collapsed into one acceptance flag. Five reduce to
mechanical checks against Episode A artifacts:

| # | Dimension | Check |
|---|---|---|
| 1 | Recovers the active goal | match against frozen goal |
| 2 | Preserves explicit constraints | constraints present and uncontradicted |
| 3 | Identifies the unresolved state | names the open thread from Episode A |
| 4 | Avoids a previously discovered failure | does not repeat a recorded dead end |
| 5 | Does not invent unsupported prior findings | **grounding check, see below** |
| 6 | Chooses the correct next action | constrains task selection |
| 7 | Produces measurable task progress | constrains task selection |

Dimensions 6 and 7 cannot be made mechanical in general, so they constrain **task selection
instead**: only pick tasks where the correct next action is derivable from state and where progress
leaves a checkable trace. Keeping the evaluator small is the same drift rule applied to scoring.

### The grounding rule lives here

Dimension 5 *is* the narrow fix for the `"minimum viable model size is 2GB"` fabrication, wearing a
different name. It is built once, inside Episode B scoring, in service of this experiment:

> Unsupported numeric or categorical claims fail acceptance unless grounded in packet evidence.

It does **not** grow into a general truth-validation subsystem, and no proof-carrying-output format
is adopted before this experiment runs.

## Cold-start receipt

Every run must prove nothing crossed the boundary, and must carry the numerics established
2026-07-22 in [DETERMINISM.md](../experiments/DETERMINISM.md):

```
episode_a_process_id      episode_a_end_time
episode_b_process_id      episode_b_start_time
model_name_and_digest     model_quantization      runtime_version
continuity_packet_hash    bare_context_hash       broken_packet_hash
token_budget              generation_seed         load_state
```

Distinct PIDs and a fresh invocation are the point — without them this risks measuring ordinary
within-window context retention.

**Episode B primes** (one discarded generation) before scoring. Decided now, not at run time.
Episode B is by definition a cold load, and cold and warm are different numeric modes on boundary
prompts under Q4_K_M on CUDA. One discarded generation leaks nothing about the task and
standardises numerics against the matrix runs. Skipping it would let the continuity result be
confounded by exactly the bimodality already isolated.

## Two milestones, kept separate

**M1 — Functional continuity.** A fresh instance resumes correctly from the substrate more often
than `broken_packet`. This is an instrument-validity result: it shows the substrate carries
something. Expected to pass early.

**M2 — Substrate advantage.** `ck_packet` beats `bare_serialized` across preregistered continuity
tasks. This is the thesis.

### Expectations, set before the result

A **zero on M2 at 1B is a finding, not a project failure.** It would place the advantage threshold
above 1B, which is a real answer to a real question. It licenses exactly one further rung under a
*fresh preregistered question* — `gemma3:4b` fits the 8GB board. That is the sanctioned route back
to the ladder. Expanding the ladder without a new preregistered question remains drift.

## Freeze

The measurement layer (`score.py`, `return_path/`, `generate.py`) is frozen at 52 passing tests
during this build. Convention borrowed from cosmic-cli rather than invented: **frozen files unfreeze
legally on a red test plus a reproducer.** A blocker with evidence is a legal unfreeze; a
refactor-while-passing is not.

## Explicitly out of scope

Named so they cannot creep in:

- a general-purpose truth-validation architecture
- further acceptance-semantics refinement before continuity is tested
- ladder expansion without a new preregistered question
- Qwen3.5 thinking-mode runs on the edge-default question — already answered by the budget
  estimand; a long-budget run is a *different deployment regime* and must be labelled as such
- treating the benchmark headline as the product rather than as evidence about the substrate

## Admissibility

Corpus: `experiments/probes/continuity_tasks.json` (Grok Build seat, work order
`docs/WORK_ORDER_continuity_corpus.md`). **16 tasks**, four per category
(`goal_recovery`, `constraint_persistence`, `thread_resume`, `failure_avoidance`).

Hard rules applied (from the work order):

1. Correct next action derivable from Episode A state alone  
2. Progress leaves a checkable trace  
3. Episode B unanswerable without carried state (opaque codes / thread ids)  
4. Edge budget (`orin_nano_8gb` mass)  
5. At most one repair pass  

### Rejected task sketches (evidence, not waste)

| Sketch | Why rejected |
|---|---|
| "What is the capital of France?" after Episode A set a goal | Episode B answerable by world knowledge; fails rule 3 (trivia, not continuity). |
| "Write a better architecture essay about substrates" | Progress needs opinion; next action not uniquely derivable; fails rules 1–2. |
| "Pick the best model on the ladder and justify" | Correct next action is a value judgment, not state-derivable; fails rule 1. |
| "Continue the multi-file refactor across three modules" | No single checkable trace; multi-step tools out of v0; fails rules 2 and 5. |
| "Resume work" with empty seed_state | Unanswerable even *with* substrate; not a discrimination task. |
| Seed state with 40 facts + long transcripts | Exceeds edge packet room (rule 4). |
| Episode B: "Summarize AI safety in general" | Independent of Episode A; fails rule 3. |
| Task requiring `max_repair_passes: 3` | Violates v0 one-repair contract (rule 5). |
| "Confirm minimum viable size is 2GB" as Episode A *finding* | Would bake the fabrication into ground truth; inverted into `cont_failure_avoidance_04` as a **dead end** instead. |

Rejections pushed the corpus toward opaque sprint/goal codes, named dead ends, and
numeric locks that only exist in seed facts — so bare general knowledge cannot pass Episode B.

### Cross-seat feedback (scorer seat → corpus, 2026-07-22)

After Episode B scoring landed (`3bed7c3`), two corpus issues were handed back:

| ID | Issue | Fix |
|---|---|---|
| **G1** | Three tasks had `progress_trace.check` prose with **no extractable identifier**, so dimension 7 could never fire. | Every task now sets `progress_trace.accept_any_of` to concrete ids (thread ids / codes). Scorer honours `accept_any_of` first. |
| **G2** | `cont_goal_recovery_01/02/03` (and similar) embedded opaque codes **inside the goal string**, so a bare goal echo fired `progress_trace` (~0.714) without resuming threads — a rule-3 violation. | Goal prose is free of progress identifiers; codes live in **facts** only; `accept_any_of` prefers **thread ids** (and codes only when not substrings of the goal). Goal-echo now scores **0.143** with `progress_trace=false` across all 16 tasks. |

Neither fix touched the frozen measurement layer (`score.py` / `return_path/` / `generate.py`).
