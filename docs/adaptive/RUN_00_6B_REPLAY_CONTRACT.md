# RUN 00.6B / 00.6B.1 — Replay Contract

## Inputs

- `genesis.json` — frozen genesis snapshot
- `universe.json` — closed-set universe (used to validate batch assertions on replay)
- `events/{NNNNNN}_{event_id}.json` — complete accepted **candidate-batch** events only

## Algorithm (v2)

```
current_hash = hash(materialize(genesis, []))
seen_ids = {}
for event in ordered_events:
    fail if event.schema_version != ck.continuity_event.v2
    fail if event_id duplicate
    fail if event.parent_state_hash != current_hash
    fail if assertions empty / missing
    fail if duplicate triples inside assertions
    fail if assertions not canonically sorted
    fail if any assertion fails closed-set / combination checks (universe)
    append entire event (batch) to applied
    expected = hash(materialize(genesis, applied))
    fail if event.resulting_state_hash != expected
    current_hash = expected
return materialized state + current_hash
```

No model is invoked. Partial application of a batch is impossible: the event is
all-or-nothing.

## Fail-closed conditions

| Condition | Error class |
|---|---|
| Unknown `schema_version` (incl. v1) | `ReplayError` |
| Duplicate `event_id` | `ReplayError` |
| Parent hash ≠ current | `ReplayError` |
| Claimed resulting hash ≠ recomputed | `ReplayError` |
| Duplicate assertions inside event | `ReplayError` |
| Non-canonical assertion order | `ReplayError` |
| Invalid subject/object/relation/combo | `ReplayError` |
| Unknown event fields | `ReplayError` |
| Partial `.tmp` files | Ignored; quarantined |

## Atomic write method

Unchanged from 00.6B:

1. Serialize complete JSON payload.
2. Write temp file; `fsync`; readback equality.
3. `os.replace` → `events/{seq:06d}_{event_id}.json`.
4. Same for the single terminal receipt.

## Candidate cardinality

| Input | Events | Terminal receipts |
|---|---|---|
| Accepted candidate (N unique assertions) | 1 | 1 |
| Rejected candidate | 0 | 1 |

Event count tracks **accepted candidates**, not assertion count.

## Fresh-process requirement

Unchanged: open store from disk, `replay_store`, compile Episode B relations
from reconstructed `accepted_relations` only.

## Dry-run isolation

Unchanged: dry writes only to isolated store; `scientific_completion=false`.
