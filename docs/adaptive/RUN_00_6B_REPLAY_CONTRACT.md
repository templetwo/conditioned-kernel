# RUN 00.6B — Replay Contract

## Inputs

- `genesis.json` — frozen genesis snapshot
- `universe.json` — closed-set universe (for new accepts; not required for pure replay of events)
- `events/{NNNNNN}_{event_id}.json` — complete accepted events only

## Algorithm

```
current_hash = hash(materialize(genesis, []))
seen_ids = {}
for event in ordered_events:
    fail if event.schema_version != ck.continuity_event.v1
    fail if event_id duplicate
    fail if event.parent_state_hash != current_hash
    append event relation atom to applied list
    expected = hash(materialize(genesis, applied))
    fail if event.resulting_state_hash != expected
    current_hash = expected
return materialized state + current_hash
```

No model is invoked.

## Fail-closed conditions

| Condition | Error class |
|---|---|
| Unknown `schema_version` | `ReplayError` |
| Duplicate `event_id` | `ReplayError` |
| Parent hash ≠ current | `ReplayError` (broken chain) |
| Claimed resulting hash ≠ recomputed | `ReplayError` (tamper / mutation) |
| Unknown event fields | `ReplayError` |
| Partial `.tmp` files | Ignored by listing; moved to `quarantine/` |

## Atomic write method

For each accepted event + receipt:

1. Serialize complete JSON payload.
2. Write to a unique temp file in the target directory.
3. `fsync` the temp file.
4. Read back and require byte equality.
5. `os.replace` temp → final path (`events/{seq:06d}_{event_id}.json`).
6. Same protocol for the paired receipt under `receipts/`.

Crash leaving only `.tmp` files cannot produce a listable accepted event.

## Fresh-process requirement

A consumer must:

1. Open the store path from disk.
2. Call `replay_store` (or equivalent) with no in-memory Episode A objects.
3. Compile Episode B packet relations exclusively from reconstructed
   `accepted_relations`.

Process identity of Episode A is irrelevant; only genesis + events matter.

## Idempotence / duplicates

- Replaying the same event stream twice yields the same state hash (byte-
  deterministic materialization).
- Attempting to **accept** the same relation triple again yields
  `DUPLICATE_ASSERTION` and appends no event.

## Dry-run isolation

`process_episode_a_candidate(..., dry_run=True, dry_store_root=…)` writes only
to the dry store. The primary store is unchanged.
`scientific_completion` is always false for dry runs.
