# RUN 00.6B — Change Map

**Branch:** `grok/ck-run-00-6b-episode-a`  
**Starting commit:** `db668a91e32843c3e53de58325cc17fff4b9c746`  
**Scope:** Episode A external continuity lifecycle only

## New production modules

| File | Role |
|---|---|
| `src/conditioned_kernel/continuity_events.py` | Event schema constants, relation atoms, canonical state hash |
| `src/conditioned_kernel/continuity_store.py` | Genesis/universe load, atomic event+receipt append, quarantine |
| `src/conditioned_kernel/continuity_replay.py` | Deterministic replay, fail-closed integrity |
| `src/conditioned_kernel/continuity_gate.py` | Parse → validate → accept/reject → persist; Episode B relations |

## Tests

| File | Role |
|---|---|
| `tests/test_run_00_6b_episode_a.py` | Accept, reject, fail-closed, replay, tamper, fresh process, dry-run |

## Documentation

| File | Role |
|---|---|
| `docs/adaptive/RUN_00_6B_EVENT_SCHEMA.md` | Candidate + event schema |
| `docs/adaptive/RUN_00_6B_REPLAY_CONTRACT.md` | Replay + atomic write contract |
| `docs/adaptive/RUN_00_6B_IMPLEMENTATION_RECEIPT.md` | Implementation receipt |
| `docs/adaptive/RUN_00_6B_CHANGE_MAP.md` | This file |

## Explicit non-changes

| Surface | Status |
|---|---|
| Adaptive Riverbed / dials | untouched |
| Control matching / budgets | untouched |
| Continuity scorer (`continuity.py` score path) | untouched |
| Scientific thresholds | untouched |
| Prompts / task corpus | untouched |
| Model matrix / M0 | not run |
| TerminalStatus taxonomy split | not done |
| Sovereign Stack import | not done |
| Product pipeline default path | not rewritten to force continuity_assertions |

## Interaction with RUN 00.6A

00.6A typed outcomes and ledger remain available. Episode A continuity events
are a separate append-only store. Experiment headline policy remains on
runners (00.6A.2); this run does not mark M0 headline eligible.
