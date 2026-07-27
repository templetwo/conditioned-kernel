# RUN 00.8A.1 — Mandatory Evidence-Receipt Invariant

## Invariant

For every planned commissioning or scientific cell:

1. Terminalization **requires** a verified packet receipt.
2. Terminalization **requires** a verified control receipt.
3. Packet/control status and receipt hashes are derived **only** from those
   artifacts.
4. There is **no** production API flag that disables this.

## Authority boundary

Lowest enforceable public boundary:

```text
M0LedgerSession.terminalize(IntegrationInputs)
```

`IntegrationInputs` (integration surface **ck.terminal_integration.v2**):

- requires `packet_receipt: Mapping`
- requires `control_receipt: Mapping`
- no `require_evidence_receipts`
- no authoritative `packet_verification_status` / `control_verification_status`
- optional diagnostic fields only (never decide validity)

## Missing evidence

| Absence | Reason code |
|---|---|
| packet_receipt is None | `PACKET_RECEIPT_REQUIRED` |
| control_receipt is None | `CONTROL_RECEIPT_REQUIRED` |
| receipt fails verify | `EVIDENCE_RECEIPT_UNVERIFIED` (+ verify reasons) |
| cell/task/condition mismatch | `EVIDENCE_RECEIPT_CELL_MISMATCH` |

No completed-valid record is created from missing evidence.

## Scopes

| Scope | Behavior |
|---|---|
| commissioning_validation | receipts mandatory |
| scientific_experiment | receipts mandatory + authorization |
| dry_planning_only | must not terminalize live model cells |

Synthetic tests construct canonical synthetic receipts via
`synthetic_pass_receipts` / `make_*_receipt` — never bare PASS strings.

## Removed

`require_evidence_receipts` — complete removal from production API.
