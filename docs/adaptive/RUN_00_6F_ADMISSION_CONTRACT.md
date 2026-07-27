# RUN 00.6F — Admission Contract

**Module:** `src/conditioned_kernel/m0_admission.py`  
**Schema:** `ck.m0_admission_report.v1`

Admission is **separate** from TerminalLedger facts. It consumes only the frozen
manifest and completed terminal records.

## Coverage formulas

```text
terminalization_coverage = terminal_cells_n / planned_cells_n
observed_score_coverage  = SCORED cells with non-null score / planned_cells_n
primary_pair_coverage    = valid C1/C3 scored pairs / planned C1/C3 pairs
```

Valid ledger requires `terminalization_coverage == 1.0` (every planned cell has
a terminal factual record — not every model response observed).

## Valid primary pair

A C1/C3 pair is valid only if both terminals:

- exist
- are `SCORED` with non-null `primary_score`
- passed control verification (`pass`)
- passed packet verification (`pass`)
- have complete provenance
- match frozen model tag and generation parameters
- are free of task-contract and scorer-internal errors

## Primary headline admission (C3 vs C1)

Eligible **only if all** are true:

1. Authorization receipt present and matches manifest id + SHA-256  
2. `terminalization_coverage == 1.0`  
3. `primary_pair_coverage == 1.0`  
4. Every primary pair passed control contract  
5. Every primary pair has complete required provenance  
6. Frozen model and generation parameters used  
7. No duplicate terminal records  
8. No unplanned terminal records  
9. No task-contract error in planned primary cells  
10. No scorer-internal error in planned primary cells  
11. Ledger integrity verification passes  
12. Manifest integrity verification passes  

When `primary_pair_coverage < 1.0`:

- primary headline = null  
- `primary_headline_eligible = false`  
- partial observed values may appear only as **descriptive**  
- missing/invalid pair reasons enumerated  

No imputation. No replacement of failed cells.

The 100% rule is a **structural admission gate** for this bounded prototype, not
an efficacy threshold.

## Scientific stamps and report-policy invariant (00.6F.1)

```text
headline_eligible == true  ⇒  scientific_completion == true
```

A report may be scientifically complete but headline-ineligible.  
A report may **never** be headline-eligible while scientifically incomplete.

During RUN 00.6F / 00.6F.1 both remain false. Structural pair readiness is
exposed as `primary_headline_structurally_ready` and does **not** flip
report-level `headline_eligible`.

RUN 00.6F never mints `experiment_contract_id`.
