# RUN 00.6C — Packet Contract

## Episode A packet (`packet_kind: episode_a_continuity`)

### Allowed fields

| Field | Purpose |
|---|---|
| `objective` | Bounded task objective / prompt |
| `subject_ids` | Closed-set subject identifiers |
| `object_ids` | Closed-set object identifiers |
| `allowed_relations` | Closed-set relations (subset of global allowlist) |
| `task_facts` | Facts needed to choose a valid relation |
| `output_schema` | Exact `continuity_assertions` JSON schema |
| `instructions` | Closed-set-only return rules; empty list rejected as incomplete |

### Forbidden in Episode A packet

- expected / gold assertion labeled as answer
- complete archive or unrelated corpus threads
- adaptive dials / retrieval / tool instructions
- prior free-form model prose as authority
- large-model fallback text
- hidden fallback behavior

### Model surface

- System: continuity aperture; JSON `continuity_assertions` only
- `format=`: `CONTINUITY_ASSERTIONS_FORMAT`
- Final-response channel only enters the gate (thinking never accepted)

## Episode B packet (`packet_kind: episode_b_continuity`)

### Sources (only)

1. Verified `replay_store` of genesis + append-only events
2. Frozen genesis goal / seed_facts / task_id
3. Task Episode B prompt string

### Fields

| Field | Source |
|---|---|
| `accepted_relations` | `episode_b_packet_relations(store)` after replay |
| `state_hash` | reconstructed hash |
| `seed_facts` / `goal` | genesis |
| `prompt` | task episode_b.prompt |

### Forbidden inheritance

Episode B must **not** receive:

- Episode A in-memory Python objects
- raw Episode A candidate prose as authoritative state
- temporary variables from Episode A process
- unverified disk reads that skip hash-chain replay

## Hashing

Packet hash = SHA-256 of canonical JSON (`sort_keys=True`, compact separators).
