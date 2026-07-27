# RUN 00.9A / 00.9A.1 — Negative-Control Spec

Amended by **RUN 00.9A.1** with numeric invalidation thresholds.

## Primary: scrambled_state

Same structure and mass as C3 (candidate items, entity/relation vocabulary,
representation structure, candidate count, status-symbol mass, packet depth,
byte target where enforceable), but accepted-state labels are **deterministically
permuted** so they do **not** correspond to Episode A.

**Diagnoses:** format/structure benefit independent of true accepted state.

## Secondary integrity: A/A serialization

Two independently compiled but semantically identical controls.

**Diagnoses:** unexplained pipeline/runtime asymmetry.
Any exact-match discrepancy invalidates interpretation.

## Numeric decision integration (frozen)

```text
D_NC_i = Y_i(scrambled_state) - Y_i(C1)
mean_D_NC = mean_i(D_NC_i)
delta_m0 = 0.25
```

| Condition | Result |
|---|---|
| mean_D_NC ≥ +0.25 | pipeline_artifact; interpretation fails |
| mean_D_NC ≥ mean_D_C3 | pipeline_artifact; interpretation fails |
| A/A discrepancy count > 0 | pipeline_artifact; interpretation fails |
| Missing NC cells | package rejected (`MISSING_NEGATIVE_CONTROL`) |

Continuation is **not** licensed when NC reproduces C3-scale gains.
