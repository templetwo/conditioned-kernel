# RUN 00.6B — Implementation Receipt

**Run:** Episode A external continuity (append-only events + replay)  
**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6b-episode-a`  
**Starting commit:** `db668a91e32843c3e53de58325cc17fff4b9c746`  
**Ending commit:** none created (no commit/push)  
**Disposition:** implementation complete for 00.6B; M0 remains `NO-GO`

## 1. Baseline

| Item | Value |
|---|---|
| Parent branch | `grok/ck-run-00-6a-outcomes` (carries 00.6A worktree) |
| New branch | `grok/ck-run-00-6b-episode-a` |
| Audited baseline commit | `db668a9` |

### Working tree before 00.6B edits

Uncommitted 00.6A artifacts present (outcomes, matrix/continuity wiring, docs).
00.6B adds only continuity event modules, tests, and 00.6B docs.

### Working tree after 00.6B

```text
## grok/ck-run-00-6b-episode-a
 M experiments/run_continuity.py   # from 00.6A
 M experiments/run_matrix.py       # from 00.6A
 M src/conditioned_kernel/pipeline.py  # from 00.6A
?? docs/adaptive/                  # 00 + 00.5 + 00.6A + 00.6B docs
?? src/conditioned_kernel/outcomes.py
?? src/conditioned_kernel/continuity_events.py
?? src/conditioned_kernel/continuity_store.py
?? src/conditioned_kernel/continuity_replay.py
?? src/conditioned_kernel/continuity_gate.py
?? tests/test_outcome_unification.py
?? tests/test_run_00_6a_1_amendment.py
?? tests/test_run_00_6a_2_policy_separation.py
?? tests/test_run_00_6b_episode_a.py
```

## 2. Exact files changed (00.6B production + tests + docs)

| Path | Action |
|---|---|
| `src/conditioned_kernel/continuity_events.py` | created |
| `src/conditioned_kernel/continuity_store.py` | created |
| `src/conditioned_kernel/continuity_replay.py` | created |
| `src/conditioned_kernel/continuity_gate.py` | created |
| `tests/test_run_00_6b_episode_a.py` | created |
| `docs/adaptive/RUN_00_6B_EVENT_SCHEMA.md` | created |
| `docs/adaptive/RUN_00_6B_REPLAY_CONTRACT.md` | created |
| `docs/adaptive/RUN_00_6B_CHANGE_MAP.md` | created |
| `docs/adaptive/RUN_00_6B_IMPLEMENTATION_RECEIPT.md` | created |

## 3. Architecture summary

```
raw candidate bytes
  → parse_continuity_candidate   (PARSE_* / SCHEMA_*)
  → validate_assertions          (closed-set + forbidden + duplicate)
  → Decision.ACCEPTED | REJECTED
  → on ACCEPTED: build event (parent/result hashes) + atomic append
  → on REJECTED: rejection receipt only (zero events)
  → process exit
  → ContinuityStore.open + replay_store  (fresh process)
  → episode_b_packet_relations           (accepted_relations only)
```

Model output never receives a filesystem write API. Trusted substrate code
constructs events from validated closed-set atoms only.

## 4. Event schema / hash / atomic write

See `RUN_00_6B_EVENT_SCHEMA.md` and `RUN_00_6B_REPLAY_CONTRACT.md`.

- **State hash:** SHA-256 of canonical JSON of
  `{schema_version, genesis_hash, accepted_relations}` with sorted triples.
- **Atomic write:** temp file → fsync → readback equality → `os.replace`.
- **Partials:** `*.tmp` never listed; moved to `quarantine/`.

## 5. Test-first discipline

1. Wrote `tests/test_run_00_6b_episode_a.py` defining the contract.
2. Observed collection/import failures until modules existed.
3. Implemented four modules to satisfy the contract.
4. One mid-implementation failure (`quarantine_partials` emptied by
   `replay_store`) — test adjusted to quarantine explicitly before replay
   assertion (behavior correct: partials never accepted).

## 6. Commands and results

```text
pytest -q tests/test_run_00_6b_episode_a.py
25 passed in 0.33s

pytest -q
152 passed in 3.05s

python -m ruff check src/conditioned_kernel/continuity_*.py \
  tests/test_run_00_6b_episode_a.py
All checks passed!

python -m mypy --follow-imports=skip \
  src/conditioned_kernel/continuity_events.py \
  src/conditioned_kernel/continuity_store.py \
  src/conditioned_kernel/continuity_replay.py \
  src/conditioned_kernel/continuity_gate.py
Success: no issues found in 4 source files
```

Baseline before 00.6B modules: **127 passed** (00.6A suite).  
After 00.6B: **152 passed** (+25).

No M0. No model matrix. No live Ollama required for these tests.

## 7. Fresh-process continuity proof

Test: `test_fresh_process_reconstructs_changed_state`

1. Episode A accepts valid assertion in parent process.
2. Event durable under `events/`.
3. Subprocess: `python -c` with only store path + `src` on `PYTHONPATH`.
4. Fresh `ContinuityStore.open` + `replay_store`.
5. Reconstructed hash equals parent `current_state_hash()`.
6. Relation triple present in `accepted_relations`.

Also: `test_episode_b_packet_contains_reconstructed_relation`,
`test_replay_byte_deterministic_across_fresh_processes` (3 processes),
`test_replacement_model_identity_can_receive_reconstructed_state`.

## 8. Rejection / no-mutation proof

Tests:

- `test_rejected_assertion_appends_no_continuity_event`
- `test_rejected_assertion_leaves_state_hash_unchanged`
- `test_fresh_process_sees_no_rejected_mutation`
- parametrized unknown subject/object/relation, invalid combination, contradiction

Result: zero events, unchanged state hash, rejection receipts retained.

## 9. Tamper detection proof

- Mutated `object_id` → `ReplayError` (resulting hash mismatch)
- Broken `parent_state_hash` → `ReplayError` (chain)
- Unknown schema version → `ReplayError`
- Partial `.tmp` → not listed; quarantined; empty accepted_relations

## 10. Known limitations

1. **Experiment runner (`run_continuity.py`) not yet rewired** to use this
   store for live Episode A model turns. Subsystem + tests prove the lifecycle;
   full orchestrator integration is a follow-on if Anthony authorizes.
2. **Product `pipeline.py` / existing `next_state.thread_touch` path** unchanged
   as the static control.
3. **Single-assertion candidates** are the primary tested shape; multi-assertion
   candidates append one event per assertion in order.
4. **M0 headline** remains ineligible (00.6A.2 policy); this run does not
   flip `headline_eligible`.
5. **Control matching / scorer repair** still out of scope.
6. **Structured `continuity_assertions` not yet forced** in the default product
   JSON schema for chat turns (additive API only).

## 11. Negative-action confirmation

- no Adaptive Riverbed / dials
- no retrieval / tools
- no control prompt or budget changes
- no continuity scorer changes
- no semantic model judge
- no scientific threshold changes
- no M0 / model matrix
- no TerminalStatus taxonomy rewrite
- no Sovereign Stack dependency
- no free-form model memory writes
- no commit / push

## 12. Ready for independent adversarial review?

**Yes — for RUN 00.6B scope** (append-only Episode A continuity lifecycle).

Reviewers should verify:

1. closed-set only; unknown ids/relations fail closed
2. reject leaves zero events and stable hash
3. atomic write + partial quarantine
4. replay fail-closed on tamper/version/chain breaks
5. fresh-process reconstruction without Episode A memory
6. prose never enters `accepted_relations`
7. dry-run isolation
8. existing 127 + 25 tests green; M0 still NO-GO
