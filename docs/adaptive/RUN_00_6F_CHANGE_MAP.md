# RUN 00.6F — Change Map

**Base:** `5826b33`  
**Branch:** `grok/ck-run-00-6f-ledger-manifest`

## Added

| Path | Role |
|---|---|
| `src/conditioned_kernel/m0_manifest.py` | Candidate manifest, eligibility, planned cells, dry plan |
| `src/conditioned_kernel/m0_ledger_integration.py` | Planned → TerminalLedger + terminal_cell.v1 |
| `src/conditioned_kernel/m0_admission.py` | Coverage + primary headline admission |
| `tests/test_run_00_6f_manifest.py` | Manifest freeze tests |
| `tests/test_run_00_6f_ledger_integration.py` | Ledger integration tests |
| `tests/test_run_00_6f_admission.py` | Admission / headline gate tests |
| `experiments/manifests/m0_candidate_v1.json` | Frozen candidate manifest |
| `experiments/manifests/m0_candidate_v1_exclusions.json` | Exclusion ledger |
| `experiments/manifests/m0_candidate_v1_plan.json` | Dry plan |
| `docs/adaptive/RUN_00_6F_*.md` | Specs + receipt + change map |

## Modified (narrow)

| Path | Change |
|---|---|
| `src/conditioned_kernel/outcomes.py` | `ManifestCell.cell_id_override`; ledger reason prefixes `UNPLANNED_CELL` / `DUPLICATE_TERMINALIZATION` |

## Untouched (frozen components)

- `relational_scorer.py` (no formula/feature change)
- `control_contract.py` (no C0–C3 semantic change)
- `continuity_*.py` (persistence/replay/events)
- `generate.py` / prompts
- Adaptive / scientific scope activation

## Verification delta

| Suite | Count |
|---|---|
| At 5826b33 | 324 passed |
| 00.6F new | +50 |
| Full suite | **374 passed** |

## Manifest freeze fingerprint (00.6F.1)

```text
manifest_id     = ck.m0.candidate.v1
manifest_sha256 = 9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922
planned_cells   = 4
primary_pairs   = 1
included_tasks  = live_plumbing_01_m0_v1
excluded_tasks  = 17
discovered      = 18
```

## 00.6F.1 amendment adds

- gold semantics gate (`all_required` only)
- fail-closed `output_schema_id`
- Path A `live_plumbing_01_m0_v1` task contract
- full corpus eligibility table
- report-policy: headline ⇒ scientific_completion
