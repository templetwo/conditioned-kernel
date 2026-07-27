# RUN 00.9A — Static Adversarial Fixtures

All static. No model invocation.

## Failing cases (must reject)

| # | Case | Reason codes (examples) |
|---|---|---|
| 1 | Gold = full universe | `GOLD_SATURATES_PERMITTED_UNIVERSE` |
| 2 | Gold verbatim in C1 | `GOLD_VISIBLE_IN_CONTROL` |
| 3 | Gold mechanically only recipe in C1 | `GOLD_DERIVABLE_FROM_CONTROL` |
| 4 | C3 exact output-ready triples | `GOLD_OUTPUT_READY_IN_TREATMENT` |
| 5 | State query vs unrelated static gold | `STATE_GOLD_MISMATCH` |
| 6 | Missing distractors | `NO_INFORMATIONAL_DISTRACTORS` |
| 7 | Condition label in body | `CONDITION_IDENTITY_MODEL_VISIBLE` |
| 8 | C1/C3 candidate count differ | `INFORMATION_MATCHING_FAILED` |
| 9 | Missing NC | `MISSING_NEGATIVE_CONTROL` |
| 10 | Deciding metric unspecified | `MISSING_PRIMARY_METRIC` |
| 11 | One-task corpus | `ONE_TASK_CORPUS` |
| 12 | Post-performance selection | `POST_PERFORMANCE_TASK_SELECTION` |
| 13 | Same cell_id, two states | `CELL_ID_MULTIPLE_STATES` |
| 14 | Missing model digest | `MISSING_MODEL_DIGEST` |
| 15 | Null result has licensed language | (claim table documents explicit null claim) |
| 16 | Omitted/None permitted universe | `PERMITTED_COMBINATIONS_REQUIRED` (fail-closed) |
| 17 | Empty permitted universe | `PERMITTED_COMBINATIONS_EMPTY` |
| 18 | Median offered as primary estimand | `MEDIAN_NOT_PRIMARY_ESTIMAND` |
| 19 | mean_D_NC ≥ δ_m0 | pipeline_artifact |
| 20 | Unqualified runtime | `RUNTIME_CONTRACT_UNQUALIFIED` |

## Passing toy contracts

`tests/fixtures/m0_v2_static_cases.json` — `m0v2_toy_pass_01`, `m0v2_toy_pass_02`.

Implemented in `tests/test_run_00_9a_scientific_contract.py`.
