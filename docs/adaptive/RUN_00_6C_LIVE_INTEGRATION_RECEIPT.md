# RUN 00.6C — Live Integration Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6c-live-continuity`  
**Starting commit:** `e1d6730f5ec3ef64a3ff2171f1a0038aad98756e`  
**Disposition:** live plumbing wired; amended by **RUN 00.6C.1** (durable receipt
truth). M0 remains `NO-GO`

## 1. Mission

Wire the verified 00.6B / 00.6B.1 candidate-atomic continuity subsystem into
`run_continuity.py` so Episode A can accept/reject structured assertions to an
append-only store, and Episode B can start in a **fresh process** and compile
only from **verified replay**.

## 2. Architecture (live path)

```
run_continuity.py --live-plumbing
  ├─ Episode A subprocess (a-live)
  │    compile_episode_a_packet (closed sets only)
  │    OllamaClient.run  (typed inference)
  │    process_episode_a_candidate  (gate exactly once)
  │    ContinuityStore append (1 event or 0 + 1 reject receipt)
  ├─ parent reaps Episode A (no in-memory handoff)
  └─ Episode B subprocess (b-live)
       ContinuityStore.open(store_path only)
       replay_store (hash chain)
       compile_episode_b_packet(accepted_relations)
       optional single model invoke (smoke)
```

Policy on every live-plumbing report/event:

```text
scientific_status = live_plumbing_only
headline_eligible = false
headline_ineligible_reason = controls_and_scoring_not_yet_ratified
scientific_completion_n = 0
```

## 3. Test-first

Offline tests written first (`tests/test_run_00_6c_live_integration.py`).
Initial failure: `run_continuity` lacked `episode_a_live` exports — then wired.

## 4. Commands and results

### Offline suite

```text
pytest -q tests/test_run_00_6c_live_integration.py
20 passed

pytest -q
192 passed in 3.40s

ruff (touched files): All checks passed!
mypy --follow-imports=skip continuity_live.py: Success
```

### Offline inject e2e (no model required for gate)

```text
python experiments/run_continuity.py --live-plumbing \
  --tasks experiments/probes/live_plumbing_task.json --limit 1 \
  --inject-final-response '{"continuity_assertions":[...]}' \
  --out /tmp/ck-006c-offline.json

Episode A: completed / gate=accepted / events=1 / pid=97321
Episode B: replay=True / rels=1 / pid=97323
scientific_completion_n=0 headline_eligible=false
```

Distinct PIDs confirmed.

### Bounded live smoke (one model, one task)

```text
python experiments/run_continuity.py --live-plumbing \
  --tasks experiments/probes/live_plumbing_task.json --limit 1 \
  --out /tmp/ck-006c-live-smoke.json \
  --store-dir /tmp/ck-006c-live-stores \
  --invoke-episode-b-model
```

| Field | Value |
|---|---|
| Model | `qwen2.5:0.5b` (profile default `orin_nano_8gb`) |
| Runtime | local Ollama `http://127.0.0.1:11434` |
| Episode A inference | `completed` |
| Final response | `{"continuity_assertions":[{"subject_id":"thread_gamma_receipt","relation":"remains_open","object_id":"question_cold_start"}]}` |
| Gate | `accepted` |
| Events | 1 |
| Rejection receipts | 0 |
| Candidate hash | `5849d4aa1f79d8d96422da531793e26a072623aef83b3b3374d5f16f3da15a8a` |
| Episode A packet hash | `9e4348d67e4ad6754f2dc79ad8b964240529fac628766814f0ce3694790e9da0` |
| Episode A PID | 97397 |
| Episode B replay | `True` |
| State hash | `ede65adab87bf96a3b73861d7c9068869dcc572e3caf50125e1bce85e75b2872` |
| Relations | 1 (`thread_gamma_receipt` / `remains_open` / `question_cold_start`) |
| Episode B packet hash | `92fd437caa16f69bc823544c628bad94420482ce8f79e0b5999ff1c675d82d30` |
| Episode B inference | `completed` (smoke invoke) |
| Episode B PID | 97400 |
| used_episode_a_memory | `false` |
| scientific_completion_n | **0** |
| headline_eligible | **false** |
| scientific_status | **live_plumbing_only** |

**Prompt was not modified after observing the result.** Acceptance was a plumbing
outcome under the frozen packet contract, not a tuned scientific claim.

## 5. Fresh-process proof

1. Episode A writes store under `store-dir/<task_id>/` and exits (subprocess).
2. Episode B starts as a **new** subprocess with only `store_root` in payload.
3. `used_episode_a_memory=false` on B result.
4. Offline unit test `test_episode_b_fresh_process_reads_only_replay` uses a
   third interpreter via `python -c`.
5. Live smoke PIDs **97397 ≠ 97400**.

## 6. Files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/continuity_live.py` | created |
| `experiments/run_continuity.py` | live plumbing mode + workers |
| `experiments/probes/live_plumbing_task.json` | created |
| `tests/test_run_00_6c_live_integration.py` | created |
| `docs/adaptive/RUN_00_6C_*.md` | created (3 files) |

## 7. Negative-action confirmation

- no control / scorer / threshold changes
- no prompt tuning after observation
- no matrix / seed sweep / fallback model
- no adaptive dials / retrieval / tools
- no event schema v3
- no second event store
- no M0 headline eligibility
- no commit required by this receipt (working tree)

## 8. Remaining blockers to M0

1. Control matching still unrepaired (byte-budget / instruction identity).
2. Continuity scorer still void for cross-model claims (shotgunning).
3. Legacy three-arm path still confounds treatment information (RUN 00).
4. Full corpus integration of `continuity_universe` across all tasks.
5. Provenance completeness for scientific artifacts.
6. Anthony authorization after gate receipt.

## 9. Ready for independent review?

**Yes — for RUN 00.6C + 00.6C.1** (live plumbing + durable receipt truth).

See `RUN_00_6C_1_RECEIPT_TRUTH_AMENDMENT.md` for the disk-receipt defect fix.

M0 remains `NO-GO`.
