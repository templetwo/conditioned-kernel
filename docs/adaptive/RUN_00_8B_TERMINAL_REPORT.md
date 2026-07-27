# RUN 00.8B — Terminal Report (Commissioning)

Full machine-readable report:

`experiments/runs/commissioning_00_8b/terminal_report.json`

## Summary

| Field | Value |
|---|---|
| result_class | COMMISSIONING_COMPLETE_WITH_PROVENANCE_LIMITATIONS |
| invocations | 4 / 4 max |
| terminal records | 4 |
| scientific_completion | false |
| headline_eligible | false |
| m0_authorized | false |
| efficacy_claim_permitted | false |

## Request / response hash pairs (prefix)

| Cond | request_sha256 (16) | response_sha256 (16) |
|---|---|---|
| C0 | 2b9562a149612736 | 3ed7cf4e1c21a161 |
| C1 | c8d06add326b2f7d | e0e868bb2f6dbab7 |
| C2 | 0cb9d7b9e66a7065 | 235d134e5288586d |
| C3 | 3b7d28c7e1673acf | d330858dc9625c19 |

## What this means

The governed execution instrument completed the declared end-to-end path and
retained internally consistent evidence.

It does **not** mean C3 worked scientifically, beat C1, or that the thesis was
supported. M0 is not complete.
