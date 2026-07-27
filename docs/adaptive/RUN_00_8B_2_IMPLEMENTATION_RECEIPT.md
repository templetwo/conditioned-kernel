# RUN 00.8B.2 — Implementation Receipt

**Base HEAD:** `bf6eb9583615a256a4fbcc67fa4067d5f6b45d70`  
**Branch:** `grok/ck-run-00-8b-2-publication-gate-wiring`  
**M0:** NO-GO · Adaptive: HOLD · No models

## Pre-wiring defect

`verify_artifact_publication` was only imported by tests. A new governed run
could finalize reports, be gitignored, committed, and never call the verifier.

## Wiring

| Component | Role |
|---|---|
| `governed_run_finalization.py` | `finalize_governed_run` / `verify_publication_only` |
| `cli.py` | `ck verify-publication`, `ck finalize-governed-run` |
| `artifact_publication.main` | module CLI parity |
| `ollama_commissioning.execute_commissioning_run` | always calls finalizer after manifest write |

## Commands

```text
pytest -q tests/test_run_00_8b_2_publication_gate_wiring.py
11 passed

pytest -q
465 passed

PYTHONPATH=src python -m conditioned_kernel.cli verify-publication \
  --run-dir experiments/runs/commissioning_00_8b \
  --commit-ref 39dc0ec3603a3a4a2f63a292a91a598503558d79
publication_complete=True declared=63 reasons=[]
# exit 0
```

## Files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/governed_run_finalization.py` | created |
| `src/conditioned_kernel/cli.py` | publication commands |
| `src/conditioned_kernel/artifact_publication.py` | module CLI |
| `src/conditioned_kernel/ollama_commissioning.py` | finalizer call |
| `tests/test_run_00_8b_2_publication_gate_wiring.py` | created |
| `docs/adaptive/RUN_00_8B_2_*.md` | created |

## Untouched

Verifier core logic; scorer; scientific tasks; retired manifest; no model runs.

## Ready for independent review?

**Yes.**
