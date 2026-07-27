# RUN 00.6A.1 — Amendment Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6a-outcomes`  
**Starting commit:** `db668a91e32843c3e53de58325cc17fff4b9c746` (unchanged; no commit)  
**Authority:** Corrective amendment to RUN 00.6A after independent Claude Code review  
**Disposition:** four reviewed findings corrected; M0 remains `NO-GO`; RUN 00.6B not started

## 1. Scope

Correct **only** the four independently reviewed findings. No Episode A
lifecycle, scorer, control-matching, threshold, prompt, persistence, model,
or adaptive work.

## 2. Finding 1 — BLOCKER: structured violation classification

### Review finding

`classify_product_decision` used incidental substring membership
(`"next_state" in violation`), so:

| Violation | Was classified as |
|---|---|
| `required_section:next_state` | `SCHEMA_FAILED` (because `"next_state"` substring) |
| `required_section:answer` | `SEMANTIC_FAILED` (no marker hit) |
| `required_section:evidence_used` | `SEMANTIC_FAILED` |

These are the same required-section family and must share one class.

### Exact fix

- Added `classify_violation_token` / `classify_violations` with:
  - exact allowlists (`_SCHEMA_EXACT`, `_SEMANTIC_EXACT`)
  - documented prefixes only (`required_section:`, `parse_failed:`, …)
  - **no** free-form substring search
- All `required_section:<field>` → `SCHEMA_FAILED`
- Unknown categories → `ViolationClassificationError` / product path
  `COMPLETED_INVALID` with reason `UNKNOWN_VIOLATION_CATEGORY`
- Exact original violation text preserved in `reason_codes`

### Before / after

| Input | Before | After |
|---|---|---|
| `required_section:next_state` | SCHEMA_FAILED | SCHEMA_FAILED |
| `required_section:answer` | SEMANTIC_FAILED | **SCHEMA_FAILED** |
| `required_section:evidence_used` | SEMANTIC_FAILED | **SCHEMA_FAILED** |
| `required_section:unknown_field` | SEMANTIC_FAILED | **SCHEMA_FAILED** |
| `goal_echo` | SEMANTIC_FAILED | SEMANTIC_FAILED |
| `model mentioned next_state incorrectly` | SCHEMA_FAILED (substring) | **fail closed** |
| `""` / unknown token | SEMANTIC or SCHEMA guess | **UNKNOWN_VIOLATION_CATEGORY** |

### Tests proving fix

`tests/test_run_00_6a_1_amendment.py`:

- `test_all_required_section_violations_are_schema_failed` (parametrized)
- `test_unrelated_semantic_violation_is_semantic_failed`
- `test_malformed_violation_string_fails_closed`
- `test_required_section_not_misclassified_by_substring_next_state`
- `test_schema_precedes_semantic_when_mixed`
- `test_no_substring_marker_classifies_required_answer_as_semantic`

## 3. Finding 2 — HIGH: ambiguous continuity event

### Review finding

`CK_EVENT` used `rows_valid=0` and `scientific_completion_n=0` for both a
healthy diagnostic Episode B run and an all-failure run, so consumers could
not tell them apart and might treat either as scientific success/failure
ambiguously.

### Exact fix

`TerminalLedger.diagnostic_counts()` and continuity `CK_EVENT` now emit:

| Field | Meaning |
|---|---|
| `planned_n` | manifest size |
| `terminal_n` | terminal rows recorded |
| `inference_completed_n` | observed / quality-admitted inference |
| `final_response_present_n` | `output is not None` |
| `candidate_valid_n` | when determinable (accept or explicit receipt flag) |
| `accepted_n` | `COMPLETED_VALID` only |
| `scientific_completion_n` | always 0 until Episode A lifecycle exists |
| `dry_run_n` | dry plumbing rows |
| `failed_n` | operational/lifecycle failures without admitted answer |
| `scientific_status` | `"deferred_episode_a_lifecycle"` |
| `headline_eligible` | `false` |
| `headline_ineligible_reason` | `"episode_a_accept_persist_reload_not_implemented"` |

`rows_valid` is retained as a **legacy alias of `scientific_completion_n` only**
(never inference completion).

### Before / after

| Signal | Before (healthy vs fail) | After |
|---|---|---|
| Distinguish healthy vs all-timeout | both `rows_valid=0` | `inference_completed_n` / `failed_n` differ |
| Scientific success from inference | ambiguous | `headline_eligible=false`; sci n stays 0 |
| Dry plumbing | looked like completed science historically; 00.6A fixed status; counts now explicit | `dry_run_n` + sci 0 |

### Tests proving fix

- `test_healthy_diagnostic_run_differs_from_all_failure_run`
- `test_inference_completion_cannot_imply_scientific_success`
- `test_dry_run_counts_are_explicit_and_non_scientific`

### Dry smoke (2026-07-27)

```text
CK_EVENT … planned_n=3 terminal_n=3 inference_completed_n=0
final_response_present_n=0 accepted_n=0 scientific_completion_n=0
dry_run_n=3 failed_n=0 scientific_status=deferred_episode_a_lifecycle
headline_eligible=false
headline_ineligible_reason=episode_a_accept_persist_reload_not_implemented
```

## 4. Finding 3 — MEDIUM: duplicate computation

### Review finding

Three compute-discard-recompute paths:

1. bare: `outcome_from_inference` then overwrite with `ExecutionOutcome(...)`
2. budget_matched_bare: same
3. ck_strict: `row["raw"]` assigned thrice under overlapping conditions

### Exact fix

- bare / budget_matched: **one** `exec_outcome` assignment per branch
  (observed → control outcome; else → `outcome_from_inference`)
- ck_strict: single `op_fail` gate sets `raw`/`scores` once

### Before / after

| Path | Before | After |
|---|---|---|
| bare observed | two ExecutionOutcome constructions | one |
| bare timeout | outcome_from_inference then unused path risk | only outcome_from_inference |
| ck_strict op fail | raw set, then cleared | raw=None once |

### Tests proving fix

- `test_control_observed_outcome_built_once_shape`
- `test_control_timeout_uses_outcome_from_inference_once`
- `test_ck_strict_operational_fail_null_raw_once`

Behavior of row fields preserved; full suite green.

## 5. Finding 4 — HIGH: empty manifest

### Review finding

Empty planned cells crashed or could produce an empty “completed” artifact.

### Exact fix

- `EmptyManifestError` with stable `reason_code = "EMPTY_MANIFEST"`
- `build_manifest(...)` raises when the Cartesian product is empty
- `TerminalLedger([])` raises `EmptyManifestError`
- matrix and continuity abort **before** generation/heartbeat work with
  exit code `3` and `CK_EVENT` `*.run.aborted` (no ordinary report file)

### Before / after

| Input | Before | After |
|---|---|---|
| 0 probes / 0 tasks | ledger init error or empty survivor report | `EMPTY_MANIFEST`, exit 3, no report |
| empty conditions | same | `EMPTY_MANIFEST` |

### Tests proving fix

- `test_empty_manifest_raises_empty_manifest_error`
- `test_empty_manifest_is_not_scientifically_complete`
- `test_empty_manifest_matrix_aborts_before_generation`
- `test_empty_manifest_continuity_aborts_before_generation`

Smoke:

```text
matrix empty rc 3
… reason_code":"EMPTY_MANIFEST" … scientific_completion_n":0
```

## 6. Commands and exact results

```text
pytest -q tests/test_run_00_6a_1_amendment.py
19 passed in 0.09s

pytest -q
119 passed in 2.28s

python -m ruff check src/conditioned_kernel/outcomes.py \
  src/conditioned_kernel/pipeline.py experiments/run_matrix.py \
  experiments/run_continuity.py tests/test_run_00_6a_1_amendment.py \
  tests/test_outcome_unification.py
All checks passed!

python -m mypy --follow-imports=skip \
  src/conditioned_kernel/outcomes.py src/conditioned_kernel/pipeline.py
Success: no issues found in 2 source files

# Note: full `mypy src/conditioned_kernel` still reports one pre-existing
# error in edge.py:170 (unrelated; not introduced by 00.6A/00.6A.1).

python experiments/run_continuity.py --limit 1 --dry --out /tmp/ck-006a1-dry.json
# event fields as above; scientific_completion_n=0; headline_eligible=false

# empty matrix probes → exit 3 EMPTY_MANIFEST
```

## 7. Files changed (this amendment)

| Path | Role |
|---|---|
| `src/conditioned_kernel/outcomes.py` | structured violations; EmptyManifestError; diagnostic_counts |
| `src/conditioned_kernel/pipeline.py` | unused var cleanup; still uses classify_product_decision |
| `experiments/run_matrix.py` | single-compute branches; EMPTY_MANIFEST preflight |
| `experiments/run_continuity.py` | diagnostic event fields; EMPTY_MANIFEST preflight |
| `tests/test_run_00_6a_1_amendment.py` | **created** — 19 amendment tests |
| `docs/adaptive/RUN_00_6A_1_AMENDMENT_RECEIPT.md` | this file |
| `docs/adaptive/RUN_00_6A_IMPLEMENTATION_RECEIPT.md` | updated |
| `docs/adaptive/RUN_00_6A_CHANGE_MAP.md` | updated |

## 8. Unresolved design debt (record only — not implemented)

`TerminalStatus` currently **conflates** four layers:

1. execution / transport outcome (`TIMEOUT`, `TRANSPORT_ERROR`, …)
2. candidate validity (`PARSE_FAILED`, `SCHEMA_FAILED`, `SEMANTIC_FAILED`)
3. lifecycle acceptance (`COMPLETED_VALID` vs reject)
4. scientific completion (flag on the same object)

A later bounded run should split these into orthogonal types (e.g.
`InferenceStatus` × `CandidateStatus` × `AcceptanceStatus` ×
`ScientificAdmission`) without a silent mid-experiment migration.
**Not in scope for 00.6A.1.**

## 9. Negative-action confirmation

Confirmed:

- no M0 execution
- no model matrix scientific run
- no Adaptive Riverbed / RUN 01 / RUN 00.6B
- no prompt, corpus, scorer formula, control contract, or threshold changes
- no Episode A accept/persist/reload implementation
- no broad taxonomy migration
- no commit
- no push

## 10. Ready for re-review?

**Yes — RUN 00.6A + 00.6A.1 is ready for independent re-review** of the four
amended findings. M0 remains `NO-GO`.
