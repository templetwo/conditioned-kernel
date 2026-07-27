# RUN 00.6C — Change Map

**Branch:** `grok/ck-run-00-6c-live-continuity`  
**Starting commit:** `e1d6730` / live commit `1cc4482`  
**Scope:** Wire candidate-atomic continuity into live Episode A → fresh Episode B path  
**Amendment:** RUN 00.6C.1 — durable receipt `execution_scope` + no post-persist science patch

## New / modified production

| File | Role |
|---|---|
| `src/conditioned_kernel/continuity_live.py` | **created** — packet compile, Episode A/B live runners; **00.6C.1:** scope before persist |
| `src/conditioned_kernel/continuity_gate.py` | **00.6C.1:** `ExecutionScope`, receipt v2, verify pair |
| `experiments/run_continuity.py` | `--live-plumbing`; **00.6C.1:** verify disk receipts |
| `experiments/probes/live_plumbing_task.json` | **created** — closed-universe plumbing fixture |

## Tests

| File | Role |
|---|---|
| `tests/test_run_00_6c_live_integration.py` | **created** — 20 integration tests |
| `tests/test_run_00_6c_1_receipt_truth.py` | **00.6C.1** — on-disk receipt truth |

## Documentation

| File | Role |
|---|---|
| `docs/adaptive/RUN_00_6C_LIVE_INTEGRATION_RECEIPT.md` | Receipt |
| `docs/adaptive/RUN_00_6C_PACKET_CONTRACT.md` | Packet contract |
| `docs/adaptive/RUN_00_6C_1_RECEIPT_TRUTH_AMENDMENT.md` | Receipt truth amendment |
| `docs/adaptive/RUN_00_6C_CHANGE_MAP.md` | This file |

## Explicit non-changes

| Surface | Status |
|---|---|
| Event schema (v2) | unchanged |
| Continuity gate / store / replay core | used, not redesigned |
| Control conditions / scorers / thresholds | untouched |
| M0 headline policy | still ineligible |
| Adaptive Riverbed | not started |
| Legacy three-arm continuity path | preserved (default without `--live-plumbing`) |
