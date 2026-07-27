# RUN 00.5 — Authority Note

Recorded: 2026-07-26  
Authority: Anthony J. Vasquez Sr.  
Lane: bounded pre-M0 baseline integrity-repair specification

## Authorized

Anthony J. Vasquez Sr. authorized documentation and test design necessary to specify repairs required before the existing static Conditioned Kernel M0 can validly run.

This authorization supersedes the repository instruction “Run M0 next, and only M0” only to the minimum extent necessary to perform RUN 00.5 specification work.

The authorized outputs are limited to:

1. `docs/adaptive/RUN_00_5_BASELINE_REPAIR_SPEC.md`
2. `docs/adaptive/RUN_00_5_CONTROL_MATCHING_SPEC.md`
3. `docs/adaptive/RUN_00_5_SCORER_REPAIR_SPEC.md`
4. `docs/adaptive/RUN_00_5_TEST_PLAN.md`
5. `docs/adaptive/RUN_00_5_AUTHORITY_NOTE.md`
6. `docs/adaptive/RUN_00_5_RECEIPT.md`

## Not authorized

- M0 execution;
- any model invocation or model matrix;
- Adaptive RUN 01;
- Adaptive Riverbed implementation;
- production-code changes;
- existing-test changes or new-test implementation;
- configuration or corpus changes;
- new experimental conditions or task content;
- scientific threshold, weight, cutoff, utility, or acceptance-rule changes;
- implementation of any repair specified in RUN 00.5;
- commit or push.

No repository text, passing test, prepared command, or agent inference can expand this authority.

## Scientific boundary

The existing M0 scientific question remains unchanged. RUN 00.5 may identify a defect that changes how an existing or future result must be interpreted, but it may not tune the experiment, select a favorable threshold, or add a treatment.

The specification may propose static data types, fields, validators, tests, and receipt requirements. A proposal is not permission to implement it.

## Next approvals required

Anthony's next explicit approval is required before:

1. production or test implementation begins;
2. any task/corpus/output-schema annotation changes;
3. any control contract beyond the existing condition set is adopted;
4. any numeric scientific rule is ratified;
5. M0 is executed after all go/no-go gates pass;
6. any commit or push;
7. Adaptive RUN 01 or any adaptive architecture work.

Until those approvals exist, the M0 gate is `NO-GO` and the adaptive lane is closed.
