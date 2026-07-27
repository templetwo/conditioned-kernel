# RUN 00.6D — Change Map

**Branch:** `grok/ck-run-00-6d-controls`  
**Starting commit:** `b67fa2b` / control commit `3abd15e`  
**Scope:** packet sufficiency + mechanical control contracts (no model runs)  
**Amendment:** RUN 00.6D.1 — C1 target mandatory at construction; dead pad removed

## Production

| File | Role |
|---|---|
| `src/conditioned_kernel/control_contract.py` | **created** — annotations, compile C0–C3, padding, verifier; **00.6D.1:** C1 target mandatory |

## Tests / fixtures

| File | Role |
|---|---|
| `tests/fixtures/control_task_live_plumbing_01.json` | frozen task-dependency annotation |
| `tests/test_run_00_6d_controls.py` | offline control suite |
| `tests/test_run_00_6d_1_c1_integrity.py` | **00.6D.1** — C1 construction integrity |

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
