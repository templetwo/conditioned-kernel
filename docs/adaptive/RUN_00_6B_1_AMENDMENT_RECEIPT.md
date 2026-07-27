# RUN 00.6B.1 — Amendment Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6b-episode-a`  
**Starting commit:** `2b413ad4a3576325638632f6938b9d54afd73ed4` (worktree; baseline family `db668a9`)  
**Disposition:** candidate atomicity + receipt cardinality corrected; M0 remains `NO-GO`

## 1. Independent-review findings

### Finding 1 — Intra-candidate duplicate acceptance

`validate_assertions()` checked duplicates only against durable history. A single
candidate listing the same triple twice was accepted and produced multiple events.

### Finding 2 — Multi-receipt / multi-event per candidate

A multi-assertion candidate looped one event + one receipt per assertion, so
one `source_candidate_hash` mapped to multiple terminal receipts — violating
“exactly one ACCEPTED or REJECTED decision receipt per candidate.”

## 2. Cardinality before / after

| Metric | 00.6B (buggy) | 00.6B.1 (corrected) |
|---|---|---|
| Events per accepted candidate | = assertion count | **1** (batch) |
| Terminal receipts per candidate | = assertion count (accept path) | **1** |
| Events per rejected candidate | 0 | **0** |
| Rejection receipts per candidate | 1 | **1** |
| Event schema | v1 single triple fields | **v2 `assertions[]` batch** |

## 3. Candidate atomicity rule

The **candidate** is the atomic acceptance and audit unit.

- **ACCEPTED:** one decision, one append-only continuity event containing a
  canonical ordered assertion batch, one terminal receipt, one
  `source_candidate_hash`, one parent hash, one resulting hash (batch applied
  atomically).
- **REJECTED:** zero events, one terminal rejection receipt, zero state mutation,
  `resulting_state_hash == parent_state_hash` (unchanged).

Silent deduplication of model output is **forbidden**.

## 4. Duplicate-detection rule

Order of checks:

1. Parse all assertions.
2. Normalize to canonical triples `(subject_id, relation, object_id)`.
3. **Intra-candidate** duplicate scan → `DUPLICATE_ASSERTION` +
   `duplicate_triple` diagnostics → reject entire candidate.
4. Closed-set / combination / forbidden / durable-history validation
   (collect all reason codes; still all-or-nothing).

## 5. Mixed-validity behavior

Any invalid assertion in a multi-assertion candidate:

- rejects the **complete** candidate
- appends **zero** continuity events
- applies **no** valid subset
- writes **one** rejection receipt with all relevant reason codes

## 6. Test-first failures observed

New file `tests/test_run_00_6b_1_candidate_atomicity.py` written against the
prior one-event-per-assertion contract; implementation updated to v2 batch
events until the suite greened. Existing `test_run_00_6b_episode_a.py` updated
deliberately for v2 field layout (`assertions[]`).

## 7. Commands and exact results

```text
pytest -q tests/test_run_00_6b_1_candidate_atomicity.py tests/test_run_00_6b_episode_a.py
45 passed in 0.49s

pytest -q
172 passed in 3.22s

python -m ruff check src/conditioned_kernel/continuity_*.py \
  tests/test_run_00_6b_1_candidate_atomicity.py tests/test_run_00_6b_episode_a.py
All checks passed!

python -m mypy --follow-imports=skip \
  src/conditioned_kernel/continuity_events.py \
  src/conditioned_kernel/continuity_store.py \
  src/conditioned_kernel/continuity_replay.py \
  src/conditioned_kernel/continuity_gate.py
Success: no issues found in 4 source files
```

Prior full suite after 00.6B: 152. After 00.6B.1: **172** (+20 amendment tests).

## 8. Exact files changed

| Path | Change |
|---|---|
| `src/conditioned_kernel/continuity_events.py` | schema **v2**; `build_event(assertions=…)`; batch materialize |
| `src/conditioned_kernel/continuity_gate.py` | intra-candidate dupes; one event+receipt; all-or-nothing |
| `src/conditioned_kernel/continuity_replay.py` | v2 batch replay; reject duplicate/invalid batch |
| `src/conditioned_kernel/continuity_store.py` | `terminal_receipts()` / `append_terminal_receipt` |
| `tests/test_run_00_6b_1_candidate_atomicity.py` | **created** (20 tests) |
| `tests/test_run_00_6b_episode_a.py` | deliberate v2 field updates |
| `docs/adaptive/RUN_00_6B_1_AMENDMENT_RECEIPT.md` | this file |
| `docs/adaptive/RUN_00_6B_EVENT_SCHEMA.md` | updated to v2 |
| `docs/adaptive/RUN_00_6B_REPLAY_CONTRACT.md` | batch replay |
| `docs/adaptive/RUN_00_6B_CHANGE_MAP.md` | 00.6B.1 note |
| `docs/adaptive/RUN_00_6B_IMPLEMENTATION_RECEIPT.md` | 00.6B.1 note |

## 9. Negative-action confirmation

- no live continuity integration / `run_continuity.py` rewire
- no M0 / model matrix
- no controls, scorer, thresholds, prompts
- no semantic judge / adaptive dials / retrieval
- no partial candidate acceptance
- no TerminalStatus redesign
- no Sovereign Stack import
- no commit / push

## 10. Ready for focused re-review?

**Yes** — for candidate atomicity and receipt cardinality only. Core hash-chain,
atomic write, fresh-process, and reject-no-mutation properties retained under
the v2 batch event contract.

M0 remains `NO-GO`.
