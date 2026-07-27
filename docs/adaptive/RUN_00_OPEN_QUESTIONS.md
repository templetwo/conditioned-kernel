# RUN 00 — Open Questions

These questions require Anthony's authority or a ratified contract. RUN 00 does not answer them by implementation.

## Stop decisions before RUN 01

### Q1 — Which plan is authoritative?

The latest repository plan says:

> Run M0 next, and only M0. Do not touch the scorer or advance the ladder until M0's gates pass.

See `docs/BUOYANCY_EVOLUTION.md:246-252` and `docs/RE_GROUNDING.md:253-263`.

The supplied Adaptive Riverbed run orders instead say:

```text
RUN 00 audit
→ RUN 01 adaptive contracts
→ RUN 02 typed event spine
→ RUN 03 deterministic sensors
→ independent review
```

Choose one:

1. Adaptive Riverbed supersedes the M0-only HALT.
2. M0 remains first; adaptive work pauses after RUN 00.
3. RUN 01 documentation may proceed, but code waits for M0.

Without this decision, RUN 01 is blocked by contradictory authority.

### Q2 — Is the current continuity instrument retired, repaired, or preserved only as evidence?

The code does not carry an accepted Episode A transition, the treatment omits corpus facts/threads, and the scorer is already marked void. Should the current runner:

- be explicitly marked non-scientific/legacy,
- be minimally repaired under a new preregistration, or
- remain untouched while a separate adaptive instrument is built?

### Q3 — What exact event must Episode A produce?

The corpus declares `expected_state_writes`, including `proposed_note_contains`, but production intentionally refuses to persist `proposed_note`. Define the accepted transition:

- which fields may change;
- whether a thread touch alone is sufficient progress;
- whether a new accepted-artifact ledger replaces proposed notes;
- what before/after hashes and receipts bind the transition;
- what happens when Episode A rejects, times out, or produces no final response.

### Q4 — What is the canonical information budget?

“Budget matched” currently has at least four possible meanings:

1. same state facts;
2. same serialized state bytes;
3. same entire model-visible prompt bytes including system/question/schema;
4. same token count under the tested model tokenizer.

Freeze one definition and specify permitted padding/truncation. The current C1 name should not survive without a mechanical equality check.

### Q5 — Which numeric thresholds are ratified?

The protocol marks coverage 0.90 and dropout imbalance ≤1 as proposals. The validator/scorer also contains unratified values for token lengths, overlap, evidence length, word minima, and composite bounds. Anthony should classify each value as:

- safety invariant (binding in code),
- scientific threshold (frozen config, signature required), or
- heuristic diagnostic (never an acceptance/headline gate).

### Q6 — May a void scorer emit named scientific fields?

Should a run using an unratified/void scorer be structurally unable to produce `M1`, `M2`, `headline`, or `gain`, even for dry runs? A recommended rule is to require a scorer id/version plus `ratified=true` before those keys can exist.

## Contract questions

### Q7 — What does “model output cannot directly mutate durable state” mean operationally?

Current behavior allows an accepted model-proposed `thread_touch` to update an existing thread timestamp. This is qualified and allowlisted, not unrestricted. Decide whether the adaptive law permits:

- model proposes → deterministic validator qualifies → writer applies, or
- model output may only be observed, while an independently derived substrate event chooses every mutation.

The answer changes the controller and receipt contracts.

### Q8 — Are “sensors” deterministic software observations or prohibited external sensors?

Repository law says “No sensors in v0.” The supplied plan introduces a “Sensor Layer” meaning deterministic classification of generation artifacts. Rename it to `observation`/`classifier` if “sensor” would blur the physical-sensor prohibition.

### Q9 — What is the hard passage/repair bound?

Profiles say one repair; callers can currently pass any integer. Adaptive routes add recompilation plus repair. Freeze separate counters and total bounds:

```text
generation attempts
repair attempts
adaptive recompiles
total model passages
wall-clock/token budget
```

Unknown or unset bounds should fail closed.

### Q10 — What is the expected trial identity?

`probe_id` alone cannot represent repeats or paired seeds. Define the immutable key, likely:

```text
(experiment_id, condition, model_tuple, probe_id, repeat_id, seed, arm)
```

The expected manifest must exist before inference and duplicates must be fatal.

### Q11 — What exact bytes count as evidence for grounding?

Current continuity grounding sees the CK packet plus all original artifacts for every arm. Decide whether scorer-only ground truth may be used only to detect violations, never to grant evidence credit. Each supported claim should identify the model-visible source bytes/evidence id.

### Q12 — What schema/version compatibility policy applies?

Current packet version is `ck.v0`; state and receipts have no versioned schema. Define:

- accepted packet/state/event/receipt versions;
- unknown-version behavior;
- migration versus rejection;
- canonical JSON serialization;
- content/state hash algorithms and scope.

### Q13 — What does deterministic replay prove?

Choose whether replay must reconstruct:

- only typed state transitions from recorded events;
- packet compilation bytes from a state snapshot;
- scoring and aggregates from recorded raw channels;
- all of the above.

Replay should not invoke the model, and a state-hash mismatch should be terminal.

## Product/science decisions

### Q14 — Which default model is meant by “default”?

- edge profile / README: `qwen2.5:0.5b`;
- qualification recommendation: `gemma3:1b`;
- repo history: 0.5B is smoke/floor, 1B is first non-degenerate band.

Separate `smoke_model`, `product_default_model`, and `primary_experiment_model` if they are intentionally different.

### Q15 — Does adaptive work preserve the current static C3 byte-for-byte or behavior-for-behavior?

“Static runtime unchanged” could mean no default routing change, identical request bytes, identical receipts, or identical outcomes. Specify the compatibility test. A new shared typed generation layer may change telemetry/status without changing accepted behavior; decide whether that is permitted before RUN 02.

### Q16 — Which conditions are in the next frozen experiment?

The repository defines C0–C5; the supplied plan reuses C0–C3 and defines adaptive C4–C8; the research report proposes S0–S7. Names currently collide. Ratify one namespace and mapping before code or artifacts use these ids.

### Q17 — Are old invalid numeric artifacts machine-resolvable as superseded?

Corrections exist beside original Qwen3.5 ladder artifacts, but the original JSON still contains a numeric headline and no embedded supersession pointer. Decide whether readers must consult an index/manifest that resolves active truth, and whether CI should reject unresolvable superseded claims.

## Coordination residuals

### Q18 — Repair Helix before a durable decision is recorded?

`cosmic-cli helix boot` succeeded, but recall/state failed because `better-sqlite3` was compiled for Node module ABI 115 while the active Node requires ABI 127. RUN 00 proceeded from repository and supplied documents. Before banking plan-of-record decisions, repair/rebuild the Helix dependency or explicitly work without that context.

## Recommended review order

1. Q1 — plan authority.
2. Q2/Q3 — whether and how continuity survives.
3. Q4/Q10/Q11 — fair information, trial identity, evidence basis.
4. Q5/Q6 — ratified thresholds and scorer admission.
5. Q7/Q9/Q12/Q13 — adaptive state, bounds, versions, replay.
6. Q14/Q16 — defaults and condition namespace.

