# RUN 00.6C — Change Map

**Branch:** `grok/ck-run-00-6c-live-continuity`  
**Starting commit:** `e1d6730f5ec3ef64a3ff2171f1a0038aad98756e`  
**Scope:** Wire candidate-atomic continuity into live Episode A → fresh Episode B path

## New / modified production

| File | Role |
|---|---|
| `src/conditioned_kernel/continuity_live.py` | **created** — packet compile, Episode A/B live runners |
| `experiments/run_continuity.py` | `--live-plumbing`, `episode_a_live` / `episode_b_live`, orchestrator |
| `experiments/probes/live_plumbing_task.json` | **created** — closed-universe plumbing fixture |

## Tests

| File | Role |
|---|---|
| `tests/test_run_00_6c_live_integration.py` | **created** — 20 integration tests |

## Documentation

| File | Role |
|---|---|
| `docs/adaptive/RUN_00_6C_LIVE_INTEGRATION_RECEIPT.md` | Receipt |
| `docs/adaptive/RUN_00_6C_PACKET_CONTRACT.md` | Packet contract |
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
