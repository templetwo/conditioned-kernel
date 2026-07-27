# RUN 00.8B — Change Map

**Base:** `117c211`

## Added

| Path | Role |
|---|---|
| `src/conditioned_kernel/commissioning_plan.py` | ck.commissioning_plan.v1 |
| `src/conditioned_kernel/ollama_commissioning.py` | preflight + real Ollama run |
| `experiments/runs/commissioning_00_8b/**` | governed run artifacts |
| `docs/adaptive/RUN_00_8B_*.md` | specs and receipts |

## Unchanged

| Path | Note |
|---|---|
| `experiments/manifests/m0_candidate_v1.json` | retired; hash 9ec3d37a… intact |
| relational scorer arithmetic | untouched |
| 00.8A.1 mandatory receipts | enforced |
| 440 tests | remain green |

## Not done (correctly)

- No M0-v2 task redesign  
- No scientific authorization  
- No Adaptive Riverbed  
- No network model pull  
