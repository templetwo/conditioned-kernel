# RUN 00.6A.2 — Amendment Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6a-outcomes`  
**Starting commit:** `db668a91e32843c3e53de58325cc17fff4b9c746` (unchanged; no commit)  
**Authority:** Correct the final open finding from independent review of 00.6A / 00.6A.1  
**Disposition:** ledger facts separated from experiment headline policy; M0 remains `NO-GO`

## 1. Shared-infrastructure policy leak

### Finding

`TerminalLedger.diagnostic_counts()` hard-coded continuity-specific policy:

```text
headline_eligible = false
scientific_status = deferred_episode_a_lifecycle
headline_ineligible_reason = episode_a_accept_persist_reload_not_implemented
```

The ledger is shared with `run_matrix.py`, which has no Episode A lifecycle. A
matrix ledger containing a genuine `COMPLETED_VALID` row was still forced through
false Episode-A-specific ineligibility language.

### Architectural correction

| Layer | Responsibility |
|---|---|
| `TerminalLedger.diagnostic_counts()` | **Facts only** — planned/terminal/inference/final/candidate/accepted/scientific_completion/dry/failed counts |
| `run_continuity.continuity_headline_policy()` | Continuity experiment policy (Episode A deferred) |
| `run_matrix.matrix_headline_policy()` | Matrix experiment policy (unratified headline rule) |
| Product `pipeline.py` | No headline policy added |

## 2. Before / after examples

### Ledger with COMPLETED_VALID

**Before (00.6A.1):**

```json
{
  "accepted_n": 1,
  "scientific_completion_n": 1,
  "headline_eligible": false,
  "scientific_status": "deferred_episode_a_lifecycle",
  "headline_ineligible_reason": "episode_a_accept_persist_reload_not_implemented"
}
```

**After (00.6A.2):**

```json
{
  "planned_n": 1,
  "terminal_n": 1,
  "inference_completed_n": 1,
  "final_response_present_n": 1,
  "candidate_valid_n": 1,
  "accepted_n": 1,
  "scientific_completion_n": 1,
  "dry_run_n": 0,
  "failed_n": 0
}
```

No policy keys. No Episode-A text.

### Continuity event

Policy attached by `continuity_headline_policy()` after reading ledger facts:

```text
headline_eligible=false
scientific_status=deferred_episode_a_lifecycle
headline_ineligible_reason=episode_a_accept_persist_reload_not_implemented
```

### Matrix event

Policy attached by `matrix_headline_policy()`:

```text
headline_eligible=false
scientific_status=pending_ratified_headline_rule
headline_ineligible_reason=matrix_headline_rule_not_ratified
```

Never Episode-A language.

## 3. Exact location of headline policy after the fix

| Field | Source |
|---|---|
| Continuity report/event policy | `experiments/run_continuity.py` → `continuity_headline_policy()` |
| Matrix report/event policy | `experiments/run_matrix.py` → `matrix_headline_policy()` |
| Ledger counts | `src/conditioned_kernel/outcomes.py` → `TerminalLedger.diagnostic_counts()` |
| Product pipeline | no headline policy |

## 4. Matrix headline-policy disposition

**Status: unratified mechanical rule.**

`docs/EXPERIMENT_PROTOCOL.md` describes a paired-coverage / missingness gate for
a primary headline, but the current matrix runner does **not** implement a
versioned, Anthony-ratified eligibility function bound to those gates. RUN
00.6A.2 does **not** invent numeric thresholds.

Therefore matrix emits:

- `scientific_status = pending_ratified_headline_rule`
- `headline_ineligible_reason = matrix_headline_rule_not_ratified`
- `headline_eligible = false`

Source cited: protocol prose as *intent only*; no machine-bound ratified
eligibility function exists in the runner. Existing `paired_gain` / incomplete
coverage nulling remains for estimands and is unchanged.

## 5. Commands and exact results

```text
pytest -q tests/test_run_00_6a_2_policy_separation.py tests/test_run_00_6a_1_amendment.py
27 passed

pytest -q
127 passed in 2.73s

python -m ruff check src/conditioned_kernel/outcomes.py \
  experiments/run_matrix.py experiments/run_continuity.py \
  tests/test_run_00_6a_2_policy_separation.py tests/test_run_00_6a_1_amendment.py
All checks passed!

python -m mypy --follow-imports=skip src/conditioned_kernel/outcomes.py
Success: no issues found in 1 source file

python experiments/run_continuity.py --limit 1 --dry --out /tmp/ck-006a2-dry.json
# event: headline_eligible=false
# scientific_status=deferred_episode_a_lifecycle
# terminal_ledger.diagnostic_counts: no policy keys

# Direct TerminalLedger COMPLETED_VALID reproduction:
# diagnostic_counts keys are facts only; accepted_n=1 scientific_completion_n=1
```

No M0. No model scientific matrix. Thresholds untouched.

## 6. Files changed

| Path | Change |
|---|---|
| `src/conditioned_kernel/outcomes.py` | strip policy from `diagnostic_counts()` |
| `experiments/run_continuity.py` | `continuity_headline_policy()`; attach to report/event |
| `experiments/run_matrix.py` | `matrix_headline_policy()`; attach to report/event |
| `tests/test_run_00_6a_1_amendment.py` | stop expecting policy on ledger facts |
| `tests/test_run_00_6a_2_policy_separation.py` | **created** (8 tests) |
| `docs/adaptive/RUN_00_6A_2_AMENDMENT_RECEIPT.md` | this file |
| `docs/adaptive/RUN_00_6A_IMPLEMENTATION_RECEIPT.md` | note 00.6A.2 |
| `docs/adaptive/RUN_00_6A_CHANGE_MAP.md` | note 00.6A.2 |

## 7. Negative-action confirmation

- F1 structured violation classification: **not modified** (except preserved)
- F3 single-compute paths: **not modified**
- F4 EMPTY_MANIFEST: **not modified**
- no Episode A persistence
- no scorer / control / prompt / model / threshold changes
- no TerminalStatus taxonomy split
- no M0 / RUN 00.6B
- no commit / push

## 8. Ready for final re-review?

**Yes.** The shared-infrastructure policy leak is closed. Ledger reports facts;
continuity and matrix own their headline policies separately.

M0 remains `NO-GO`.
