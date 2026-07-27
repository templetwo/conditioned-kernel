# RUN 00.9A — Claim Ladder and Falsification Contract

## Claim ladder

| Level | Claim | M0-v2 |
|---|---|---|
| **A** Instrument | Pipeline runs; evidence truthful | Already established (commissioning); not re-tested |
| **B** Cell observation | One C3 cell ≠ paired control | Diagnostic only |
| **C** Task pair | Structured replay changed one frozen task pair under one model snapshot | Yes |
| **D** Corpus M0 | Across preregistered corpus, paired outcome moves as predicted under frozen contract | **Maximum licensed** |
| **E** General thesis | Substrate-owned continuity as general mechanism | **Not licensed** |

**Level E requires:** multi-model, multi-host, multi-corpus, preregistered
cross-lab replications beyond D.

## Primary estimand (frozen)

```text
D_i = Y_i(C3) - Y_i(C1)
Y = exact_relation_set_match  ∈ {0,1}
primary corpus estimand = median_i D_i
predicted direction: C3 > C1  (median D_i > 0)
```

**Unit:** eligible task.  
**Missing pairs:** exclude from median; block claim if coverage < 1.0.  
**Failures:** non-SCORED → null Y; task out of primary median.  
**Uncertainty:** descriptive task table; no asymptotic p-values as primary.

Mean is **not** interchangeable with median.

## Single deciding metric (frozen)

| Role | Metric |
|---|---|
| **Primary** | `exact_relation_set_match` |
| Secondary / diagnostic | `primary_score` |

No post-run switching.

## Falsification / decision classes

| Outcome | Class |
|---|---|
| C3 systematically below C1 | weaken_hypothesis |
| C3 ≈ C1 | inconclusive |
| Negative control same gain as C3 | pipeline_artifact |
| A/A unexplained asymmetry | pipeline_artifact |
| Parser/provenance condition failures | invalidate_experiment |
| Leakage after freeze | invalidate_experiment |
| Incomplete primary-pair coverage | invalidate_experiment |
| Runtime provenance failure | invalidate_experiment |
| Gold / scorer contract failure | invalidate_experiment |

Not every outcome is compatible with the thesis.

## Licensed language (examples)

**Positive (max D):**  
“Under the frozen M0-v2 task corpus, model snapshot, runtime contract, and
paired control design, structured replay produced a larger preregistered
task-level outcome than the flat control according to the frozen decision rule.”

**Forbidden:** “Conditioned Kernel works.”
