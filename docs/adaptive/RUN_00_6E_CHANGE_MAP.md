# RUN 00.6E — Change Map

**Base:** `02a0027`  
**Branch:** `grok/ck-run-00-6e-relational-scorer`

## Added

| Path | Role |
|---|---|
| `src/conditioned_kernel/relational_scorer.py` | Closed-set relational scorer (`ck.relational_score.v1`) |
| `tests/fixtures/relational_scorer_cases.json` | 30 frozen adversarial fixtures + property universe |
| `tests/test_run_00_6e_relational_scorer.py` | 51 offline tests incl. monotonicity property proof |
| `docs/adaptive/RUN_00_6E_RELATIONAL_SCORER_SPEC.md` | Spec |
| `docs/adaptive/RUN_00_6E_SCORING_SCHEMA.md` | Schema / formula / hashing |
| `docs/adaptive/RUN_00_6E_ADVERSARIAL_FIXTURES.md` | Fixture catalog |
| `docs/adaptive/RUN_00_6E_IMPLEMENTATION_RECEIPT.md` | Receipt |
| `docs/adaptive/RUN_00_6E_CHANGE_MAP.md` | This file |

## Modified

None (greenfield module + tests + docs only).

## Deliberately untouched

| Area | Paths / notes |
|---|---|
| Control contracts C0–C3 | `control_contract.py` |
| Continuity events / store / replay / gate / live | `continuity_*.py` |
| Outcomes / ledger | `outcomes.py` (consumer-ready via status strings only) |
| Product generate / Ollama | `generate.py` |
| Prior lexical scorer | `score.py` |
| Pipeline | `pipeline.py` |
| Prompts / matrix / M0 | no activation |
| Execution scopes | no `SCIENTIFIC_EXPERIMENT` |
| Adaptive riverbed | HOLD |

## Integration surface (narrow)

```text
score_cell(...)
score_planned_cells([...])  →  list[ck.relational_score.v1 records]
```

Inputs: gold contract, parsed assertions, inference_status, provenance.  
Outputs: one terminal score record per planned cell.

## Verification delta

| Suite | Count |
|---|---|
| Pre-00.6E (at base) | 251 passed |
| 00.6E new | +51 |
| Full suite | **302 passed** |

## Policy stamps on all 00.6E artifacts

```text
scientific_status = scorer_validation_only
scientific_completion = false
headline_eligible = false
headline_ineligible_reason = m0_manifest_and_admission_contract_not_yet_ratified
```
