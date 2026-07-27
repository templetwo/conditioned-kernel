# RUN 00.8A — Change Map

**Base:** `36e889e`

## Added

| Path | Role |
|---|---|
| `src/conditioned_kernel/commissioning_executor.py` | Synthetic end-to-end executor |
| `src/conditioned_kernel/persistent_terminal_ledger.py` | Durable append-only ledger |
| `src/conditioned_kernel/response_scoring_adapter.py` | ck.response_scoring_adapter.v1 |
| `src/conditioned_kernel/evidence_verification.py` | Packet/control receipt derivation |
| `src/conditioned_kernel/runtime_provenance.py` | Digest + completeness |
| `tests/test_run_00_8a_commissioning_safety.py` | Trust-boundary tests |
| `docs/adaptive/RUN_00_8A_*.md` | Specs + receipt + supersession |

## Modified

| Path | Change |
|---|---|
| `edge.py` | Preserve temperature=0, seed=0 |
| `control_contract.py` | Neutral pad; no condition in body; control headline always false |
| `m0_admission.py` | Independent hash; stronger auth; per-condition counts |
| `m0_ledger_integration.py` | Score binding; receipts; RUNTIME_PROVENANCE_FAILURE |
| `m0_manifest.py` | Frozen overwrite refusal; retired hash constant |

## Untouched

`relational_scorer.py` formula, continuity store/replay, scientific task redesign, M0 live run.
