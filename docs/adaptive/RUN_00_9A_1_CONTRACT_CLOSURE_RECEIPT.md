# RUN 00.9A.1 — Contract Closure Receipt

## Identity

| Field | Value |
|---|---|
| **Starting commit (pushed HEAD)** | `862429c4e181fed2c31fb2aa57bc8010a4b28265` |
| Starting message | `RUN 00.9A: M0-v2 scientific contract and task-design freeze` |
| Base branch | `grok/ck-run-00-9a-scientific-contract-freeze` |
| Working branch | `grok/ck-run-00-9a-1-contract-closure` |
| M0 | NO-GO |
| Adaptive Riverbed | HOLD |
| Corpus construction | NOT AUTHORIZED |
| Model execution | NOT AUTHORIZED |

## Fail-open reproduction (pre-fix)

Against real RUN 00.8B C1 packet
`experiments/runs/commissioning_00_8b/cells/C1_budget_matched_bare/packet_body.json`
and saturated gold (= complete permitted universe of two triples):

| Call | Result |
|---|---|
| `permitted_combinations=REAL_PERMITTED` | `GOLD_DERIVABLE_FROM_CONTROL`, `leakage_detected=True` |
| `permitted_combinations=None` (old API) | **`leakage_detected=False`** (fail-open false negative) |

Additional pre-fix defects recorded:

1. Median of ternary paired differences discards net-positive configs
   (e.g. four C3 wins, one C1 win, seven ties → median 0, mean +0.25).
2. Old `> 0` rule would treat one net win of twelve as support
   (1/12 < 0.25 → now inconclusive).
3. Scrambled-state gain matching C3 lacked a numeric invalidation rule.

## API / type correction

- `permitted_combinations` is a **required** keyword (no default).
- `None` → `LeakageAnalysisError(PERMITTED_COMBINATIONS_REQUIRED)` or incomplete
  analysis result with `leakage_detected=True`.
- Empty → `PERMITTED_COMBINATIONS_EMPTY`.
- Incomplete analysis never returns `leakage_detected=false`.
- Stable reasons: `PERMITTED_COMBINATIONS_REQUIRED`, `PERMITTED_COMBINATIONS_EMPTY`,
  `LEAKAGE_ANALYSIS_INCOMPLETE`, `CONTROL_DERIVABILITY_UNRESOLVED`.

## Frozen scientific choices

| Axis | Value |
|---|---|
| Primary metric | `exact_relation_set_match` |
| Secondary metric | `primary_score` |
| Primary estimand | `mean_paired_difference` |
| δ_m0 | **0.25** |
| Primary NC | `scrambled_state` |
| Secondary integrity | `aa_serialization` |
| C3 representation | `structured_state_v1` (hard non-output-ready) |
| N_candidate | 24 |
| N_min_eligible | 12 |
| Replicates / retries | 1 / 0 |

### δ_m0 justification

Descriptive threshold: at N=12, 0.25 equals three net task-pair wins.
Any positive mean below 0.25 is **inconclusive**, not support.

### Negative-control numeric rule

- `mean_D_NC >= +0.25` → pipeline_artifact  
- `mean_D_NC >= mean_D_C3` → pipeline_artifact  
- Any A/A exact-match discrepancy → pipeline_artifact  

### Non-output-ready C3 invariant

Mandatory exclusion `GOLD_OUTPUT_READY_IN_TREATMENT` when C3 is byte-identical,
schema-equivalent, or a complete scorer-triple rendering of gold.

## Exact files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/m0_leakage_analysis.py` | fail-closed rewrite |
| `src/conditioned_kernel/m0_scientific_contract.py` | mean/δ_m0/NC/order |
| `src/conditioned_kernel/m0_task_eligibility_v2.py` | N_candidate=24, manifest gate |
| `src/conditioned_kernel/m0_preregistration_v2.py` | template amendment |
| `tests/test_run_00_9a_1_contract_closure.py` | new (required cases) |
| `tests/test_run_00_9a_scientific_contract.py` | API + claim language |
| `docs/adaptive/RUN_00_9A_*.md` | amended consistently |
| `docs/adaptive/RUN_00_9A_1_CONTRACT_CLOSURE_RECEIPT.md` | this receipt |

## Verification

```text
PYTHONPATH=src pytest tests/test_run_00_9a_scientific_contract.py \
  tests/test_run_00_9a_1_contract_closure.py -q
# 68 passed

PYTHONPATH=src pytest -q
# 533 passed

ruff check on amended modules
# All checks passed

# Staging publication (pre-commit):
finalize_governed_run(... staging_mode=True) → publication_complete=True
```

## Proof no model invoked

- No Ollama client calls in this round.
- No generation of model outputs.
- Tests are static pure-Python contract checks plus on-disk commissioning packet
  bytes (instrument evidence only).


## Publication discipline

| Step | Result |
|---|---|
| Staging `finalize_governed_run(staging_mode=True)` | `publication_complete=True` |
| Commit | `db5186ba6a5ba62ba941986715ee50cfae563215` |
| Committed verification against that commit | `publication_complete=True`, 3/3 declared hashes verified and present in commit |
| Governed design packet | `experiments/runs/scientific_contract_00_9a_1/` |
| Silently ignored governed artifacts | **none** |

No push in this round (independent review gate first).

## Remaining limitations

1. Leakage derivability still requires an explicit permitted universe argument
   (now mandatory); packet-local universe extraction is not yet automatic.
2. Counterbalance planner is a seed-pinned plan generator; execution wiring is
   out of scope until a future scientific run is authorized.
3. Replicate count remains 1 — no independent-replication claim.
4. No M0-v2 corpus, execution manifest, or authorization receipt exists.
5. Commissioning 00.8B evidence remains non-scientific instrument evidence only.

## Review readiness

**Yes for independent design-review of the contract closure** — not for
execution authorization, corpus construction, or scientific completion.
