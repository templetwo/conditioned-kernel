# RUN 00.8A — Evidence Binding Contract

## Manifest integrity

Admission **always** recomputes:

```text
SHA256(canonical_json(manifest without manifest_sha256 field))
```

Compare to claimed hash. Reasons: `MANIFEST_HASH_MISMATCH`,
`MANIFEST_CANONICALIZATION_FAILED`, `MANIFEST_INTEGRITY_UNVERIFIED`.

Never set `authorization_status=ratified_receipt_present` when integrity fails.

## Authorization receipt binding

Required fields:

- manifest_id, manifest_sha256 (exact computed)
- authorized_model (= manifest model_tag)
- resolved_model_digest
- authorized_planned_cell_count
- authorized_condition_set
- authorizing_principal, authorization_timestamp
- experiment_contract_id

## Score-to-cell binding

Reject:

- task_id / condition_id mismatch → `SCORE_CELL_MISMATCH`
- expected_relation_hash mismatch → `SCORE_EXPECTED_HASH_MISMATCH`
- scorer schema mismatch → `SCORE_SCHEMA_MISMATCH`
- SCORED without score_record → `SCORED_WITHOUT_SCORE_RECORD`

Planned `expected_relation_hash` is never overwritten by score data.

## Packet/control status

Derived only from `ck.packet_receipt.v1` / `ck.control_receipt.v1` artifacts.
Caller strings `"pass"` are ignored when receipts are present.
Failed control receipt cannot be admitted as PASS.

## Provenance completeness

Computed from required fields via `compute_provenance_completeness`.
Caller `provenance_complete=true` is not authoritative under
`require_evidence_receipts`.
