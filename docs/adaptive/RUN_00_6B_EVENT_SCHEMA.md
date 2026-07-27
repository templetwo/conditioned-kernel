# RUN 00.6B — Continuity Event Schema

**Schema version:** `ck.continuity_event.v1`  
**Validator version:** `ck.continuity_validator.v1`  
**Authority:** append-only events are durable truth; materialized state is derived

## Candidate shape (model-visible proposal)

```json
{
  "continuity_assertions": [
    {
      "subject_id": "thread_2",
      "relation": "remains_open",
      "object_id": "question_4"
    }
  ]
}
```

Rules:

- Root must be a JSON object.
- `continuity_assertions` is a non-empty list of objects.
- Each assertion has **exactly** `subject_id`, `relation`, `object_id` (non-empty strings).
- No confidence fields.
- Free-form prose (`answer`, notes, etc.) may exist on the raw candidate for
  product paths but is **never** written into authoritative continuity state.
- Unknown assertion fields fail closed (`SCHEMA_FAILED:unknown_fields`).

## Closed relation vocabulary

Global allowlist (`ALLOWED_RELATIONS`):

- `remains_open`
- `is_answered`
- `depends_on`
- `blocked_by`
- `references`

A task universe may further restrict relations and valid
`(subject_id, relation, object_id)` combinations. Unknown relations fail closed.

## Accepted event object

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Must be `ck.continuity_event.v1` |
| `event_id` | string | Unique id (`cevt_…`) |
| `sequence` | int | Monotonic per store, starting at 1 |
| `parent_state_hash` | hex sha256 | Hash before this event |
| `resulting_state_hash` | hex sha256 | Hash after applying this event |
| `episode_id` | string | e.g. `episode_a` |
| `subject_id` | string | Closed-set subject |
| `relation` | string | Closed-set relation |
| `object_id` | string | Closed-set object |
| `source_candidate_hash` | hex sha256 | SHA-256 of raw candidate UTF-8 bytes |
| `validator_version` | string | `ck.continuity_validator.v1` |
| `acceptance_reason_code` | string | e.g. `ACCEPTED` |
| `timestamp` | ISO-8601 UTC | Event time (not used for hash chain) |
| `repo_commit` | string\|null | Short git hash when available |
| `provenance` | object | Optional model/runtime metadata |

Unknown event fields fail closed on replay.

## State hash method

1. Materialize:

```json
{
  "schema_version": "ck.materialized_state.v1",
  "genesis_hash": "<sha256 of canonical genesis JSON>",
  "accepted_relations": [
    {"object_id":"…","relation":"…","subject_id":"…"}
  ]
}
```

2. `accepted_relations` are unique triples sorted by
   `(subject_id, relation, object_id)`.
3. Canonical JSON: UTF-8, `sort_keys=True`, separators `(',', ':')`.
4. State hash = lowercase hex SHA-256 of those bytes.

Genesis seed relations (if any) are included before event-derived atoms.

## Rejection receipt

Rejected candidates write a receipt under `receipts/reject_*.json` with:

- `decision: rejected`
- `reason_codes` (e.g. `UNKNOWN_SUBJECT`, `PARSE_FAILED:…`, `DUPLICATE_ASSERTION:…`)
- `source_candidate_hash`
- `scientific_completion: false`

No continuity event file is created on rejection.
