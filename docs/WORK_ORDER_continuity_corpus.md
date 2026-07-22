# Work order — continuity task corpus (Grok Build seat)

**Parallel with:** the continuity harness runner + Episode B scoring (Claude/opus seat).
**Interface:** `experiments/probes/continuity_tasks.json`, schema fixed below. Do not change the
schema without agreement — the runner is being written against it right now.
**Read first:** [CONTINUITY_EXPERIMENT.md](CONTINUITY_EXPERIMENT.md). This work order only makes
sense against that preregistration.

## Why this is split from the scorer

Whoever writes the tasks and the scorer together will unconsciously write tasks their scorer
passes. Separating them is a safeguard, not just parallelism. **You own task admissibility. The
other seat owns scoring. Neither should quietly absorb the other.**

## What you are building

A corpus of continuity tasks. Each task defines an **Episode A** (do work, leave state) and an
**Episode B** (resume across a process boundary). The harness runs both; you decide what makes a
task admissible and write the corpus.

### Hard admissibility rules

The preregistration puts two of the seven continuity dimensions out of mechanical reach —
*"chooses the correct next action"* and *"produces measurable task progress"* — and handles them by
constraining task selection instead. That constraint is your job:

1. **The correct next action must be derivable from Episode A state alone.** If a competent reader
   with the frozen artifacts and no other context cannot say what should happen next, reject the
   task.
2. **Progress must leave a checkable trace.** A named artifact, a state field, a thread id, a
   countable item. If judging progress needs an opinion, reject the task.
3. **Episode B must be unanswerable without Episode A state.** Write the probe so a model with no
   carried state cannot get it right by general knowledge or by guessing. This is the single most
   important property — it is what makes the experiment about continuity rather than trivia.
4. **Fits the edge budget.** `orin_nano_8gb`, ctx 2048, packet ≤ 6000 bytes. If it does not fit, it
   is not a task.
5. **No task may require more than one repair pass**, matching the v0 substrate contract.

### Target

**12–20 tasks.** Enough that one dropout does not dominate (see the missingness bounds in
`EXPERIMENT_PROTOCOL.md` — at n=4 a single loss leaves 25% of the estimand unobserved). Spread them
across the four categories below, not clustered.

## Schema — fixed, do not drift

```json
{
  "id": "cont_thread_resume_01",
  "category": "goal_recovery | constraint_persistence | thread_resume | failure_avoidance",
  "episode_a": {
    "prompt": "…work to perform, which will write state…",
    "seed_state": {
      "goal": "…",
      "threads": [{"id": "thread_x", "title": "…"}],
      "facts": ["…"]
    },
    "expected_state_writes": {
      "thread_touch": ["thread_x"],
      "proposed_note_contains": ["…"]
    }
  },
  "episode_b": {
    "prompt": "…question that is unanswerable without Episode A state…",
    "answer_key": {
      "must_mention_any": [["…", "…"]],
      "must_not_mention_any": ["…"],
      "min_words": 8
    },
    "grounded_claims": {
      "numeric_claims_must_appear_in_packet": true,
      "forbidden_inventions": ["…specific fabrications this task invites…"]
    },
    "correct_next_action": {
      "derivable_from": ["goal", "thread_x"],
      "accept_any_of": ["…", "…"]
    },
    "progress_trace": {
      "kind": "state_field | thread_id | named_artifact",
      "check": "…mechanically checkable assertion…"
    }
  },
  "notes": "why this task is admissible under rules 1-5"
}
```

`forbidden_inventions` matters: it is how continuity dimension 5 (*does not invent unsupported
prior findings*) gets teeth per task. The live example is `gemma3:1b` asserting *"the minimum viable
model size is 2GB"* — a fabricated specific that passed because the answer key only required the
phrase "minimum viable" to appear. **For each task, name the plausible fabrications it invites.**

## Deliverables

1. `experiments/probes/continuity_tasks.json` — the corpus.
2. A short `## Admissibility` section appended to `CONTINUITY_EXPERIMENT.md` recording any task you
   **rejected** and why. Rejections are evidence about the design, not waste.
3. Tests in `tests/test_continuity_corpus.py`: every task validates against the schema, every task
   declares `forbidden_inventions`, no duplicate ids, categories balanced.

## Boundaries — please do not cross

- **Do not touch `src/conditioned_kernel/score.py`, `return_path/`, or `generate.py`.** The
  measurement layer is frozen at 54 passing tests. It unfreezes only on a red test plus a
  reproducer (cosmic convention).
- **Do not write the harness runner or Episode B scoring.** That is the other seat, in flight.
- **Do not expand the model ladder.** Out of scope per the preregistration's drift list.
- Run `pytest -q` before pushing; 54 tests must stay green.

## Optional second task, only if the corpus lands early

Add condition **C2 `prompted_persona`** to `experiments/run_matrix.py` — a static long system prompt
carrying the state, with no live compile. It is declared in `EXPERIMENT_PROTOCOL.md`'s conditions
table and has never been implemented, and it answers a sharp question cheaply: **if a static persona
matches CK, the live compile step earns nothing.** It needs no changes to the frozen scorer —
`score_output` is condition-agnostic.
