# RUN 00.6A — Implementation Receipt

**Run:** Canonical typed outcomes + manifest terminal ledger  
**Date:** 2026-07-26  
**Agent:** Grok (xAI) on branch `grok/ck-run-00-6a-outcomes`  
**Authority sources:** RUN 00 audit + RUN 00.5 specs (controlling; not reinterpreted)  
**Disposition:** implementation complete for 00.6A; amended by **RUN 00.6A.1**
and **RUN 00.6A.2** (2026-07-27) per independent review — see
`RUN_00_6A_1_AMENDMENT_RECEIPT.md` and `RUN_00_6A_2_AMENDMENT_RECEIPT.md`.
M0 remains `NO-GO`

## 1. Baseline

| Item | Value |
|---|---|
| Starting commit | `db668a91e32843c3e53de58325cc17fff4b9c746` |
| Starting branch | `codex/ck-run-00-5-spec` (docs/adaptive untracked from prior runs) |
| Implementation branch | `grok/ck-run-00-6a-outcomes` (created from starting commit) |
| Ending commit | still `db668a91e32843c3e53de58325cc17fff4b9c746` (no commit created) |
| Push | not attempted |

## 2. Starting Git status

```text
## codex/ck-run-00-5-spec
?? docs/adaptive/
```

Then:

```text
git switch -c grok/ck-run-00-6a-outcomes
```

## 3. Ending working-tree status

As of RUN 00.6A.1 (post-amendment, still uncommitted):

```text
## grok/ck-run-00-6a-outcomes
 M experiments/run_continuity.py
 M experiments/run_matrix.py
 M src/conditioned_kernel/pipeline.py
?? docs/adaptive/
?? src/conditioned_kernel/outcomes.py
?? tests/test_outcome_unification.py
?? tests/test_run_00_6a_1_amendment.py
```

Tracked diffs (production/experiment only):

```text
 experiments/run_continuity.py      | 281 ++++++++++++++++++++++++++++++++-----
 experiments/run_matrix.py          | 258 ++++++++++++++++++++++++++++------
 src/conditioned_kernel/pipeline.py | 183 ++++++++++++++++++------
 3 files changed, 599 insertions(+), 123 deletions(-)
```

Untracked new implementation files:

- `src/conditioned_kernel/outcomes.py`
- `tests/test_outcome_unification.py`
- `docs/adaptive/RUN_00_6A_IMPLEMENTATION_RECEIPT.md`
- `docs/adaptive/RUN_00_6A_CHANGE_MAP.md`

Prior untracked RUN 00 / RUN 00.5 docs under `docs/adaptive/` were read and left unmodified.

## 4. Files changed (implementation)

| Path | Action |
|---|---|
| `src/conditioned_kernel/outcomes.py` | **created** — TerminalStatus, ExecutionOutcome, ManifestCell, TerminalLedger |
| `src/conditioned_kernel/pipeline.py` | **modified** — typed `.run()` path + `execution_outcome` |
| `experiments/run_matrix.py` | **modified** — typed `fair_generate`, ledger, no string status heuristics |
| `experiments/run_continuity.py` | **modified** — DRY_RUN_ONLY, ledger, no cell drop on Episode A failure |
| `tests/test_outcome_unification.py` | **created** — 15 tests covering the 10 required invariants |
| `docs/adaptive/RUN_00_6A_IMPLEMENTATION_RECEIPT.md` | **created** |
| `docs/adaptive/RUN_00_6A_CHANGE_MAP.md` | **created** |

## 5. Exact commands run

```text
git status
git rev-parse HEAD
git switch -c grok/ck-run-00-6a-outcomes
pytest -q                                          # baseline: 85 passed
pytest -q tests/test_outcome_unification.py        # red then green
pytest -q                                          # final: 100 passed
PYTHONPATH=src python experiments/run_continuity.py --limit 1 --dry \
  --out /tmp/ck-run006a-dry.json
```

No Ollama model matrix, no M0, no live scientific run.

## 6. Exact test counts and outcomes

### Baseline (pre-change)

```text
85 passed in 2.50s
```

### Focused new suite

```text
pytest -q tests/test_outcome_unification.py
15 passed in 0.06s
```

### Full offline suite (final, post-00.6A.2)

```text
pytest -q
127 passed in 2.73s
```

Exit status: `0`.  
Delta vs audited baseline: **+42 tests** (15 + 19 + 8 from 00.6A.2),
zero pre-existing tests weakened or deleted.

## 7. New terminal-state mapping

Canonical enum: `conditioned_kernel.outcomes.TerminalStatus`

| Status | Meaning | scientific_completion |
|---|---|---|
| `completed_valid` | Accepted / finalized valid observation | **yes** |
| `completed_invalid` | Inference or lifecycle reached a non-valid terminal (or provisional completed) | no |
| `timeout` | Typed timeout from `OllamaClient.run` | no |
| `transport_error` | Transport/runtime failure | no |
| `invalid_response` | Response envelope unusable | no |
| `no_final_response` | Thinking/telemetry without final | no |
| `parse_failed` | Observed final failed parse | no |
| `schema_failed` | Parsed candidate failed schema/closed-set | no |
| `semantic_failed` | Schema-ok candidate failed semantic checks | no |
| `not_run` | Planned cell never invoked (blocked) | no |
| `dry_run_only` | Synthetic / dry plumbing only | no |

Inference-layer `RunStatus` (`generate.py`) is preserved and projected via
`classify_inference` / `outcome_from_inference`. Unknown status tokens raise
`ValueError` (fail closed).

## 8. Proof: every planned cell receives one terminal row

### Unit proof

`tests/test_outcome_unification.py`:

- `test_every_planned_task_has_exactly_one_terminal_record`
- `test_duplicate_terminal_records_are_rejected`
- `test_missing_terminal_records_are_detected`
- `test_failed_cell_does_not_disappear_from_planned_denominator`

`TerminalLedger.record` rejects duplicates; `validate` rejects missing cells.
Planned denominator is the manifest size, never `len(survivor_rows)`.

### Continuity dry smoke

```text
python experiments/run_continuity.py --limit 1 --dry --out /tmp/ck-run006a-dry.json
```

Observed:

```text
planned_n = 3
terminal_n = 3
scientific_completion_n = 0
rows_expected = 3
rows_valid = 0
all row statuses = dry_run_only
```

Episode A failure path records `NOT_RUN` (or dry) for every arm instead of
`continue`-dropping the task.

### Matrix

`run_matrix.py` builds `build_manifest(task_ids=probe_ids, condition_ids=conditions)`
and records exactly one `ExecutionOutcome` per cell into `TerminalLedger`
before report emission (`terminal_ledger` block in artifact).

## 9. Proof: dry runs are excluded from scientific completion

### Unit

- `test_dry_run_cannot_count_as_completed_science`
- `test_dry_pipeline_marks_dry_run_only_not_scientific`

`ExecutionOutcome.dry_run_only` hard-fails construction if
`scientific_completion=True` or `output is not None`.

### Product dry plumbing

`dry_candidate_text` still exercises compile→parse→validate→accept for offline
circuit tests (`test_pipeline_dry.py` remains green), but
`TurnResult.execution_outcome.status == DRY_RUN_ONLY` and
`scientific_completion is False`.

### Continuity dry smoke

```text
dry_run: true
statuses: ['dry_run_only']
scientific_completion_n: 0
M1: null
M2: null
event: continuity.run.dry
rows_valid: 0
rows_expected: 3
```

Dry means no longer emit `status=completed` with M1/M2 numeric headlines.

## 10. Known limitations

1. **Episode A still does not accept/persist.** Continuity Episode B observed
   answers are marked `quality_admitted` with
   `scientific_completion=false` and reason
   `scientific_completion_deferred`. Full `COMPLETED_VALID` for continuity
   requires later lifecycle runs (00.6B+ / RUN 00.5 §3).
   Continuity events now set `scientific_status=deferred_episode_a_lifecycle`
   and `headline_eligible=false` with an explicit ineligibility reason.
2. **Matrix control observed answers** are `COMPLETED_INVALID` +
   `quality_admitted=True` (controls have no accept gate). Product
   `ck_strict` accept is the only path that sets `COMPLETED_VALID` in this
   lane. Inference-layer `status=completed` still drives existing
   quality-conditional scoring via `row_is_valid_measurement`.
3. **Control byte-matching and scorer repair** remain unrepaired (out of scope).
4. **Persistence / append-only continuity events** out of scope.
5. **Structured `continuity_assertions`** out of scope.
6. **Qualification raw-path empty-success** (CK-R00-009) not addressed.
7. **Parser `next_state` normalization** (CK-R00-008) not addressed.
8. Existing unpaired matrix headline object still emitted (scoring/aggregation
   unchanged by design).
9. **Taxonomy design debt (recorded, not fixed in 00.6A.1/00.6A.2):**
   `TerminalStatus` conflates execution outcome, candidate validity,
   lifecycle acceptance, and scientific completion. Split in a later
   bounded run — see amendment receipt §8.
10. **Headline policy (fixed in 00.6A.2):** no longer hard-coded on
    `TerminalLedger`. Continuity owns Episode-A deferred policy; matrix owns
    `pending_ratified_headline_rule` (no Episode-A language).

## 11. Negative-action confirmation

Confirmed for RUN 00.6A:

- no models invoked for scientific work
- no matrix scientific run
- no M0 run
- no Adaptive Riverbed / RUN 01 work
- no prompt, task corpus, scorer formula, control contract, or threshold changes
- no persistence-layer redesign
- no commit created
- no push attempted
- no pre-existing test deleted or weakened

## 12. Materials read (controlling)

- `AGENTS.md`, `COSMIC.md`, `README.md`
- `docs/EXPERIMENT_PROTOCOL.md`, `docs/EDGE_SPEC.md`
- All RUN 00 and RUN 00.5 adaptive docs listed in the task brief
- `generate.py`, `pipeline.py`, `score.py`, `run_matrix.py`, `run_continuity.py`
- Existing tests under `tests/`

## 13. Ready for independent adversarial review?

**Yes — for RUN 00.6A + 00.6A.1 + 00.6A.2 final re-review.**

Reviewers should verify:

1. product path never calls `generate()` for scored turns;
2. matrix never rebuilds status from exception substrings;
3. dry cannot enter `scientific_completion` or M1/M2;
4. ledger bijection (no missing/duplicate planned cells);
5. `NO_FINAL_RESPONSE` stays distinct from `TIMEOUT` and empty `COMPLETED`;
6. no scientific threshold or scorer change landed with this lane;
7. **00.6A.1:** all `required_section:*` → SCHEMA_FAILED; unknown violations fail closed;
8. **00.6A.1:** continuity events expose diagnostic counts without implying science;
9. **00.6A.1:** empty manifest → `EMPTY_MANIFEST` before generation;
10. **00.6A.1:** no compute-discard-recompute on matrix bare/budget/ck_strict raw paths.

M0 remains `NO-GO` until remaining RUN 00.5 gates (Episode A lifecycle,
control matching, scorer repair, provenance, Anthony authorization) pass.

Full amendment detail: `docs/adaptive/RUN_00_6A_1_AMENDMENT_RECEIPT.md`.
