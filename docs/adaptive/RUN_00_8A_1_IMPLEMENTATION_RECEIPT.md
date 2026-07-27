# RUN 00.8A.1 — Implementation Receipt

**Base:** `7827e8cea5cc9cdcaed6f7672a21d9e224032dd8`  
**Branch:** `grok/ck-run-00-8a-1-mandatory-receipts`  
**M0:** NO-GO · Adaptive: HOLD · No models

## Pre-fix reproduction

At `7827e8c`, with `require_evidence_receipts` defaulting to `False`:

```text
M0LedgerSession.terminalize(
  IntegrationInputs(
    planned_cell=...,
    classification=SCORED,
    score_record=...,
    packet_verification_status="pass",   # caller claim
    control_verification_status="pass",  # caller claim
    # packet_receipt omitted
    # control_receipt omitted
  )
)
→ accepted path progress; packet/control status taken from caller strings
```

Recorded offline before the fix: `BYPASS_ACCEPTED` with
`packet_verification_status=pass` / `control_verification_status=pass` without
receipt artifacts.

## Disposition of bypass field

**Removed completely** from `IntegrationInputs` and all production call sites.
Not deprecated-with-false-path.

Integration surface version note: **ck.terminal_integration.v2**
(v1 optional-receipt semantics superseded; not silent under same version name).

## Lowest enforced authority boundary

`M0LedgerSession.terminalize` — always requires and verifies
`packet_receipt` + `control_receipt`.

## Missing-evidence classifications

- `PACKET_RECEIPT_REQUIRED`
- `CONTROL_RECEIPT_REQUIRED`
- `EVIDENCE_RECEIPT_UNVERIFIED`
- `EVIDENCE_RECEIPT_CELL_MISMATCH`

## Commands

```text
pytest -q tests/test_run_00_8a_1_mandatory_receipts.py
16 passed

pytest -q
440 passed
# 424 at 7827e8c + 16 from 00.8A.1
```

## Retired manifest

`ck.m0.candidate.v1` / `9ec3d37a…` byte-identical and not regenerated.

## Files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/m0_ledger_integration.py` | mandatory receipts; remove flag |
| `src/conditioned_kernel/commissioning_executor.py` | drop require flag |
| `tests/test_run_00_6f_ledger_integration.py` | IntegrationInputs receipts |
| `tests/test_run_00_8a_commissioning_safety.py` | IntegrationInputs receipts |
| `tests/test_run_00_8a_1_mandatory_receipts.py` | created |
| `docs/adaptive/RUN_00_8A_1_*.md` | created |

## Remaining limitations

- dry_planning_only does not yet hard-block `terminalize` by scope enum on
  IntegrationInputs (receipts still mandatory for any terminalize call).
- Control receipt required for all cells including C0; acceptable for
  commissioning honesty, may be refined if C0 is later defined as non-paired.

## Ready for independent review?

**Yes.**
