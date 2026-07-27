# RUN 00.6F — Ledger Integration Spec

## Boundary

`TerminalLedger` remains a **factual** record. It does not decide scientific
headlines. Episode A policy is not reintroduced.

Integration adapter: `src/conditioned_kernel/m0_ledger_integration.py`

```text
planned cell
  + packet/control verification
  + typed inference outcome
  + ck.relational_score.v1 | null
  + provenance
  → exactly one terminal_cell.v1
  → exactly one TerminalLedger row
```

## Existing ledger reuse

- `TerminalLedger` enforces one row per planned `ManifestCell`
- Fail closed:
  - `UNPLANNED_CELL`
  - `DUPLICATE_TERMINALIZATION`
- Optional `ManifestCell.cell_id_override` carries SHA-256 planned-cell IDs
  without changing default colon-joined identity for other callers

## Terminal classification mapping

| M0 classification | TerminalStatus | primary_score |
|---|---|---|
| SCORED | COMPLETED_VALID | numeric (from scorer) |
| TIMEOUT | TIMEOUT | null |
| TRANSPORT_ERROR | TRANSPORT_ERROR | null |
| INVALID_RESPONSE | INVALID_RESPONSE | null |
| NO_FINAL_RESPONSE | NO_FINAL_RESPONSE | null |
| MALFORMED_ASSERTIONS | PARSE_FAILED | null |
| PACKET_CONTRACT_FAILED | SCHEMA_FAILED | null |
| CONTROL_CONTRACT_FAILED | COMPLETED_INVALID | null |
| TASK_CONTRACT_ERROR | SEMANTIC_FAILED | null |
| SCORER_INTERNAL_ERROR | COMPLETED_INVALID | null |
| UPSTREAM_STATE_UNAVAILABLE | NOT_RUN | null |
| PROVENANCE_INCOMPLETE | COMPLETED_INVALID | null |
| INTERNAL_EXECUTION_ERROR | COMPLETED_INVALID | null |

All M0 terminal records force:

```text
scientific_completion = false
headline_eligible = false
quality_admitted = false
```

Incomplete provenance on an otherwise SCORED input reclassifies to
`PROVENANCE_INCOMPLETE` with null score.

## Append-only

A finalized cell may not be overwritten. Retries are not replacement: they
require a separately planned cell ID (none in this candidate manifest).

## Schema

`ck.terminal_cell.v1` fields include classification, reason codes, packet/control
status, inference/scorer status, scores (nullable), hashes, model/provenance,
timestamps, and scientific/headline stamps.
