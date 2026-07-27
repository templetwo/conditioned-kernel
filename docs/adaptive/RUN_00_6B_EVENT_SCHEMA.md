# RUN 00.6B / 00.6B.1 — Continuity Event Schema

**Schema version:** `ck.continuity_event.v2`  
**Receipt schema:** `ck.continuity_receipt.v1`  
**Validator version:** `ck.continuity_validator.v1`  
**Authority:** append-only events are durable truth; materialized state is derived  
**Atomic unit:** the **candidate** (not the individual assertion)

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
- Free-form prose may exist on the raw candidate but is **never** written into
  authoritative continuity state.
- Unknown assertion fields fail closed (`SCHEMA_FAILED:unknown_fields`).
- **Intra-candidate duplicate triples** fail closed (`DUPLICATE_ASSERTION`) —
  no silent dedupe.

## Closed relation vocabulary

Global allowlist (`ALLOWED_RELATIONS`):

- `remains_open`
- `is_answered`
- `depends_on`
- `blocked_by`
- `references`

A task universe may further restrict relations and valid
`(subject_id, relation, object_id)` combinations.

## Accepted event object (v2 — one per candidate)

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Must be `ck.continuity_event.v2` |
| `event_id` | string | Unique id (`cevt_…`) |
| `sequence` | int | Monotonic per store, starting at 1 |
| `parent_state_hash` | hex sha256 | Hash before this candidate event |
| `resulting_state_hash` | hex sha256 | Hash after applying **entire** assertion batch |
| `episode_id` | string | e.g. `episode_a` |
| `assertions` | array | Canonical ordered unique triples |
| `source_candidate_hash` | hex sha256 | SHA-256 of raw candidate UTF-8 bytes |
| `validator_version` | string | `ck.continuity_validator.v1` |
| `acceptance_reason_code` | string | e.g. `ACCEPTED` |
| `timestamp` | ISO-8601 UTC | Not used for hash chain |
| `repo_commit` | string\|null | Short git hash when available |
| `provenance` | object | Optional model/runtime metadata |

**Unsupported:** v1 single-triple top-level `subject_id`/`relation`/`object_id`
without `assertions`. Replay fails closed on unknown schema versions.

### Assertion batch rules

- Unique triples only (duplicates fail accept and fail replay).
- Sorted by `(subject_id, relation, object_id)` before hashing and persistence.
- Input order must not affect canonical payload bytes (apart from event_id,
  timestamp, candidate hash).

## Terminal receipt (exactly one per candidate)

### Accepted

| Field | Notes |
|---|---|
| `receipt_schema_version` | `ck.continuity_receipt.v1` |
| `terminal` | `true` |
| `decision` | `accepted` |
| `source_candidate_hash` | candidate hash |
| `event_id` | single event id |
| `accepted_assertion_count` | batch size |
| `accepted_assertions` | canonical triples |
| `parent_state_hash` / `resulting_state_hash` | batch boundary hashes |
| `reason_codes` | e.g. `["ACCEPTED"]` |

### Rejected

| Field | Notes |
|---|---|
| `terminal` | `true` |
| `decision` | `rejected` |
| `source_candidate_hash` | candidate hash |
| `event_id` | `null` |
| `event_ids` | `[]` |
| `accepted_assertion_count` | `0` |
| `parent_state_hash` / `resulting_state_hash` | **unchanged** (same value) |
| `reason_codes` | all failure codes |
| `duplicate_triple` | optional diagnostic for intra-candidate dupes |

## State hash method

1. Materialize:

```json
{
  "schema_version": "ck.materialized_state.v1",
  "genesis_hash": "<sha256 of canonical genesis JSON>",
  "accepted_relations": [ /* sorted unique triples from seed + all event batches */ ]
}
```

2. Canonical JSON: UTF-8, `sort_keys=True`, separators `(',', ':')`.
3. State hash = lowercase hex SHA-256 of those bytes.

Each v2 event contributes its full `assertions` batch atomically to the relation set.
