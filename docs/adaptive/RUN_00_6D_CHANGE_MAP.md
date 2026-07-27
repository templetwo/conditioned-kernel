# RUN 00.6D — Change Map

**Branch:** `grok/ck-run-00-6d-controls`  
**Starting commit:** `b67fa2b0879830559dc9c19942f5647549763f78`  
**Scope:** packet sufficiency + mechanical control contracts (no model runs)

## Production

| File | Role |
|---|---|
| `src/conditioned_kernel/control_contract.py` | **created** — annotations, compile C0–C3, padding, verifier, science guard |

## Tests / fixtures

| File | Role |
|---|---|
| `tests/fixtures/control_task_live_plumbing_01.json` | frozen task-dependency annotation |
| `tests/test_run_00_6d_controls.py` | **created** — 31 offline tests |

## Documentation

| File | Role |
|---|---|
| `docs/adaptive/RUN_00_6D_PACKET_SUFFICIENCY_SPEC.md` | sufficiency + classification |
| `docs/adaptive/RUN_00_6D_CONTROL_CONTRACT.md` | byte match + verifier |
| `docs/adaptive/RUN_00_6D_CONTROL_MATRIX.md` | C0–C3 contrasts |
| `docs/adaptive/RUN_00_6D_IMPLEMENTATION_RECEIPT.md` | receipt |
| `docs/adaptive/RUN_00_6D_CHANGE_MAP.md` | this file |

## Explicit non-changes

| Surface | Status |
|---|---|
| Continuity event/receipt schemas | untouched |
| Continuity scorer | untouched |
| Live plumbing prompts | untouched |
| M0 / model matrix | not run |
| Adaptive Riverbed | not started |
| TerminalStatus taxonomy | not redesigned |
| Scientific thresholds | untouched |
