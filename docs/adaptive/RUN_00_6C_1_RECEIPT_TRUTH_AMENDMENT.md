# RUN 00.6C.1 — Receipt Truth Amendment

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6c-live-continuity`  
**Base commit:** `1cc44826e680e8bce8efee97db3b6e83d819920f`  
**Disposition:** durable receipt scope corrected; M0 remains `NO-GO`

## 1. Original defect (reproduced)

In RUN 00.6C, `process_episode_a_candidate` wrote accept receipts with:

```python
"scientific_completion": False if dry_run else True
```

So a live-plumbing accept (non-dry store path) persisted:

```json
{
  "decision": "accepted",
  "scientific_completion": true
}
```

with **no** `execution_scope` field.

`run_episode_a_live` then post-patched only the returned in-memory object:

```python
if gate.scientific_completion:
    gate = EpisodeAResult(..., receipt={**gate.receipt, "scientific_completion": False, ...})
```

**Root cause:** scientific completion was inferred from “accepted + not dry_run” instead of from an explicit execution scope decided **before** persistence. The public report was “accidentally correct” via hardcoded zeros, while the audit-of-record receipt lied.

## 2. Corrected receipt schema

**Version:** `ck.continuity_receipt.v2`

Required durable fields:

| Field | Live-plumbing ACCEPTED | Live-plumbing REJECTED |
|---|---|---|
| `receipt_schema_version` | `ck.continuity_receipt.v2` | same |
| `execution_scope` | `live_plumbing` | `live_plumbing` |
| `scientific_completion` | `false` | `false` |
| `decision` | `accepted` | `rejected` |
| `source_candidate_hash` | set | set |
| `event_id` | event id | `null` |
| `parent_state_hash` | set | unchanged hash |
| `resulting_state_hash` | set | unchanged hash |
| `reason_codes` | set | set |

### ExecutionScope (closed enum)

- `offline_test` (default for unit tests; never scientific)
- `dry_run`
- `live_plumbing`
- `scientific_experiment` (only scope that may set `scientific_completion=true` on ACCEPTED)

`scientific_completion = (scope == scientific_experiment) and accepted`

## 3. Before / after persisted accept receipt

**Before (disk, 00.6C):**

```json
{
  "decision": "accepted",
  "scientific_completion": true
}
```

**After (disk, 00.6C.1 re-smoke):**

```json
{
  "receipt_schema_version": "ck.continuity_receipt.v2",
  "decision": "accepted",
  "execution_scope": "live_plumbing",
  "scientific_completion": false,
  "event_id": "cevt_…",
  "parent_state_hash": "…",
  "resulting_state_hash": "…"
}
```

## 4. Event/receipt consistency

- Events carry `execution_scope` (additive field on event schema v2).
- `verify_event_receipt_pair(event, receipt)` checks agreement on:
  - `source_candidate_hash`, `event_id`, `execution_scope`,
  - `parent_state_hash`, `resulting_state_hash`, `episode_id`
- Fails if `execution_scope ∈ {live_plumbing, dry_run, offline_test}` and
  `scientific_completion=true`.
- Gate verifies **before write** and after **disk re-read**.
- `run_live_plumbing` reloads disk receipts, re-verifies pairs, aborts if any
  receipt claims scientific completion.

## 5. Test-first failures observed

New tests in `tests/test_run_00_6c_1_receipt_truth.py` were written to open
the on-disk receipt. Against unfixed code they would observe
`scientific_completion == true` and missing `execution_scope`. After the fix:

```text
pytest -q tests/test_run_00_6c_1_receipt_truth.py
… passed
```

## 6. Commands and results

```text
pytest -q
205 passed in 3.80s

ruff (touched files): All checks passed!
mypy --follow-imports=skip continuity_gate/live/events: Success

# Bounded re-smoke (same frozen packet, no prompt change)
python experiments/run_continuity.py --live-plumbing \
  --tasks experiments/probes/live_plumbing_task.json --limit 1 \
  --out /tmp/ck-006c1-live-smoke.json \
  --store-dir /tmp/ck-006c1-live-stores \
  --invoke-episode-b-model
```

### Re-smoke disk values

| Field | Value |
|---|---|
| Model | `qwen2.5:0.5b` |
| terminal_decision | `accepted` |
| execution_scope | `live_plumbing` |
| scientific_completion | **false** |
| receipt_schema_version | `ck.continuity_receipt.v2` |
| event/receipt verify | OK |
| CK_EVENT scientific_completion_n | **0** |
| headline_eligible | **false** |
| scientific_status | **live_plumbing_only** |
| Distinct PIDs | 98439 / 98442 |

## 7. Files changed

| Path | Change |
|---|---|
| `src/conditioned_kernel/continuity_gate.py` | `ExecutionScope`, scope-based sci flag, verify pair, disk re-read |
| `src/conditioned_kernel/continuity_events.py` | receipt v2; event `execution_scope` |
| `src/conditioned_kernel/continuity_live.py` | pass `LIVE_PLUMBING`; remove post-persist patch |
| `src/conditioned_kernel/continuity_replay.py` | allow `execution_scope` field |
| `experiments/run_continuity.py` | verify disk receipts; derive sci_n from disk |
| `tests/test_run_00_6c_1_receipt_truth.py` | **created** |
| `docs/adaptive/RUN_00_6C_1_RECEIPT_TRUTH_AMENDMENT.md` | this file |
| `docs/adaptive/RUN_00_6C_LIVE_INTEGRATION_RECEIPT.md` | note 00.6C.1 |
| `docs/adaptive/RUN_00_6C_CHANGE_MAP.md` | note 00.6C.1 |

## 8. Negative-action confirmation

- no prompt / universe / control / scorer / threshold changes
- no M0 / matrix
- no adaptive work
- no event schema v3 (v2 retained; additive `execution_scope`)
- no push of corrective commit (pending review)

## 9. Ready for focused re-review?

**Yes** — for durable receipt truth and artifact consistency under live plumbing.

M0 remains `NO-GO`.
