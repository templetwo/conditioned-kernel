# RUN 00.9A / 00.9A.1 — Claim Ladder and Falsification Contract

Amended by **RUN 00.9A.1** (mean estimand, δ_m0, fail-closed NC rules).

## Claim ladder

| Level | Claim | M0-v2 |
|---|---|---|
| **A** Instrument | Pipeline runs; evidence truthful | Already established (commissioning); not re-tested |
| **B** Cell observation | One C3 cell ≠ paired control | Diagnostic only |
| **C** Task pair | Structured replay changed one frozen task pair under one model snapshot | Yes |
| **D** Corpus M0 | Mean paired exact-set-match difference meets continuation threshold under frozen contract + validity gates | **Maximum licensed** |
| **E** General thesis | Substrate-owned continuity as general mechanism | **Not licensed** |

**Level E requires:** multi-model, multi-host, multi-corpus, preregistered
cross-lab replications beyond D.

## Primary estimand (frozen — 00.9A.1)

```text
Y_i(c) = exact_relation_set_match ∈ {0,1}
D_i = Y_i(C3) - Y_i(C1)            ∈ {-1, 0, 1}
primary corpus estimand = mean_i(D_i)
```

Descriptive paired corpus estimand (net fraction of task-pair wins).
**Not** an asymptotic estimate. **Median is not primary.**

## Minimally relevant effect

```text
delta_m0 = 0.25
```

At N=12, δ=0.25 ⇔ three net task-pair wins.

| mean_D_C3 | Class |
|---|---|
| ≥ +0.25 | continuation (subject to NC/AA/validity) |
| (−0.25, +0.25) | inconclusive — **any positive below δ is not support** |
| ≤ −0.25 | materially weakens M0-v2 hypothesis |

## Single deciding metric (frozen)

| Role | Metric |
|---|---|
| **Primary** | `exact_relation_set_match` |
| Secondary / diagnostic | `primary_score` |

No post-run switching.

## Negative-control decision rule

Primary NC: **scrambled_state**. Secondary integrity: **A/A serialization**.

```text
D_NC_i = Y_i(scrambled_state) - Y_i(C1)
mean_D_NC = mean_i(D_NC_i)
```

Interpretation fails (`pipeline_artifact`) when:

- `mean_D_NC >= +0.25`, or
- `mean_D_NC >= mean_D_C3`, or
- any A/A exact-match discrepancy

Continuation requires:

```text
mean_D_C3 >= +0.25
mean_D_NC < +0.25
mean_D_C3 > mean_D_NC
aa_discrepancy_count == 0
primary_pair_coverage == 1.0
negative_control_coverage == 1.0
all scientific validity gates pass
```

## Falsification / decision classes

| Outcome | Class |
|---|---|
| mean_D_C3 ≤ −0.25 | weaken_hypothesis |
| −0.25 < mean_D_C3 < +0.25 | inconclusive |
| mean_D_NC ≥ +0.25 or ≥ mean_D_C3 | pipeline_artifact |
| A/A discrepancy > 0 | pipeline_artifact |
| Parser/provenance / leakage / incomplete coverage | invalidate_experiment |

Not every outcome is compatible with the thesis.

## Licensed language

**Positive (continuation only, max D):**  
“Under the frozen M0-v2 corpus, model snapshot, runtime contract, and paired
control design, the mean paired exact-set-match difference for structured
replay versus the flat control met the preregistered continuation threshold,
while the scrambled-state and A/A validity gates passed.”

**Forbidden:** “Conditioned Kernel works.”
