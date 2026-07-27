# RUN 00.6A — Change Map

**Lane:** baseline-integrity repair (typed outcomes + terminal ledger only)  
**Branch:** `grok/ck-run-00-6a-outcomes`  
**Starting commit:** `db668a91e32843c3e53de58325cc17fff4b9c746`  
**Scope boundary:** product / matrix / continuity / dry-run typed outcomes and
manifest ledger. Episode A persistence, scorer repair, control matching,
and scientific thresholds are out of scope.

**Amendments:**

- RUN 00.6A.1 (2026-07-27) — `RUN_00_6A_1_AMENDMENT_RECEIPT.md`
- RUN 00.6A.2 (2026-07-27) — `RUN_00_6A_2_AMENDMENT_RECEIPT.md` (ledger facts
  vs experiment headline policy)

## New module

| File | Role |
|---|---|
| `src/conditioned_kernel/outcomes.py` | Canonical `TerminalStatus`, `ExecutionOutcome`, `ManifestCell`, `TerminalLedger`, classifiers, dry-run factory, scientific-completion gate; **00.6A.1:** structured violation map, `EmptyManifestError`, `diagnostic_counts()`; **00.6A.2:** `diagnostic_counts()` is facts-only (no headline policy) |

## Production / experiment wiring

| File | Change | Why |
|---|---|---|
| `src/conditioned_kernel/pipeline.py` | Product path calls `OllamaClient.run` instead of `generate`; attaches `TurnResult.execution_outcome`; dry_candidate_text → `DRY_RUN_ONLY` with `scientific_completion=false` | CK-R00-004: typed inference at product boundary; CK-R00-003 dry admission |
| `experiments/run_matrix.py` | `fair_generate` returns `InferenceResult` via `.run()`; status never reconstructed from exception strings; planned manifest + `TerminalLedger` for every probe×condition; **00.6A.1:** single-compute branches; `EMPTY_MANIFEST` preflight; **00.6A.2:** `matrix_headline_policy()` | CK-R00-004 matrix bypass; exactly-one terminal row |
| `experiments/run_continuity.py` | Dry → `DRY_RUN_ONLY`; no `output or ""` coercion for non-observed; Episode A failure emits `NOT_RUN` arm rows; ledger + report/event dry markers; **00.6A.1:** explicit diagnostic counts; `EMPTY_MANIFEST` preflight; **00.6A.2:** `continuity_headline_policy()` | CK-R00-003 missing cells and dry-as-completed |

## Tests

| File | Role |
|---|---|
| `tests/test_outcome_unification.py` | Ten required invariants plus pipeline/matrix classifier path checks |
| `tests/test_run_00_6a_1_amendment.py` | **00.6A.1** — structured violations, diagnostic counts, empty manifest, single-compute |
| `tests/test_run_00_6a_2_policy_separation.py` | **00.6A.2** — ledger facts vs continuity/matrix headline policy |

## Documentation deliverables

| File | Role |
|---|---|
| `docs/adaptive/RUN_00_6A_IMPLEMENTATION_RECEIPT.md` | Original 00.6A receipt (amended notes) |
| `docs/adaptive/RUN_00_6A_CHANGE_MAP.md` | This file |
| `docs/adaptive/RUN_00_6A_1_AMENDMENT_RECEIPT.md` | Four-finding corrective receipt |
| `docs/adaptive/RUN_00_6A_2_AMENDMENT_RECEIPT.md` | Policy/fact separation receipt |

## Design debt (record only — later bounded run)

`TerminalStatus` conflates execution outcome, candidate validity, lifecycle
acceptance, and scientific completion. Do **not** migrate the taxonomy in
00.6A.1. Split orthogonally in a future run.

## Explicit non-changes

| Surface | Status |
|---|---|
| Prompts / system text | unchanged |
| Task corpus | unchanged |
| Scorers (`score.py`, `continuity.score_episode_b`) | unchanged formulas/thresholds |
| Control budget matching | unchanged (still not byte-matched; out of scope) |
| Episode A accept/persist | unchanged (still diagnostic; out of scope) |
| Persistence / append-only continuity events | out of scope |
| Scientific thresholds | frozen / unchanged |
| Model invocation in tests | none |
| M0 | still NO-GO |
| Commit / push | not performed |

## Terminal-state mapping

| TerminalStatus | Source | `output` | scientific_completion |
|---|---|---|---|
| `COMPLETED_VALID` | Product accept only (non-dry) | observed string | yes |
| `COMPLETED_INVALID` | Provisional completed inference; matrix control observed answer (no accept gate); continuity Episode B observed (lifecycle incomplete); generic terminal reject | string or null | no |
| `TIMEOUT` | `RunStatus.TIMEOUT` via `OllamaClient.run` | null | no |
| `TRANSPORT_ERROR` | `RunStatus.TRANSPORT_ERROR` | null | no |
| `INVALID_RESPONSE` | `RunStatus.INVALID_RESPONSE` | null | no |
| `NO_FINAL_RESPONSE` | `RunStatus.NO_FINAL_RESPONSE` | null | no |
| `PARSE_FAILED` | Product reject with parse failure | observed string | no |
| `SCHEMA_FAILED` | Product reject with schema markers | observed string | no |
| `SEMANTIC_FAILED` | Product reject with semantic violations | observed string | no |
| `NOT_RUN` | Planned cell blocked (e.g. Episode A failure) | null | no |
| `DRY_RUN_ONLY` | Dry plumbing / dry_candidate_text | null | no |

Inference-layer `RunStatus` remains the transport taxonomy. `TerminalStatus`
is the lifecycle terminal taxonomy; they are not competing labels for the
same event.

## Caller path summary

```text
product:   compile → OllamaClient.run → ExecutionOutcome projection
           → parse/validate/assess/accept → COMPLETED_VALID | lifecycle fail
           dry_candidate_text → DRY_RUN_ONLY (plumbing may still accept)

matrix:    fair_generate → OllamaClient.run → InferenceResult
           ck_strict → run_turn.execution_outcome
           manifest(probe × condition) → TerminalLedger (1:1)

continuity: Episode B worker → typed status / DRY_RUN_ONLY
            orchestrator manifest(task × arm) → TerminalLedger (1:1)
            Episode A fail → NOT_RUN rows for all arms (no cell drop)
```
