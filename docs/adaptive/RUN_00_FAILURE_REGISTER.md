# RUN 00 — Failure Register

**Commit audited:** `db668a91e32843c3e53de58325cc17fff4b9c746`  
**Rule:** findings describe current behavior; no production patch is included in RUN 00.

Severity meanings:

- **CRITICAL** — can manufacture, erase, or mislabel the event behind a scientific result.
- **HIGH** — breaks a declared invariant, replay/provenance guarantee, or acceptance boundary.
- **MEDIUM** — material drift/operational weakness that does not alone create a gain claim.
- **LOW** — clarity or maintainability issue with bounded present impact.

## Findings

| ID | Severity | Finding | Evidence | Consequence | Required invariant before advancement |
|---|---|---|---|---|---|
| CK-R00-001 | **CRITICAL** | Continuity Episode A never produces an accepted durable transition. | `experiments/run_continuity.py:137-156` calls the model, stores raw text in a log string, and returns. It never calls parse, validate, assess, accept, or `expected_state_writes`. Episode B re-seeds the original task at `159-171`. | The required “accepted output/state write → kill process → resume from filesystem” event never occurs. Current continuity runs are static seed-context comparisons, not continuity of accepted work. | Episode A must emit a typed generation result, candidate, receipt, accepted state delta, before/after hashes, and a frozen artifact consumed by Episode B. Rejection/failure must prevent a continuity score. |
| CK-R00-002 | **CRITICAL** | The continuity treatment omits task-specific facts and every corpus thread; arms do not contain the same information. | `seed_state_dir` writes facts to `current.seed_facts` (`run_continuity.py:109-117`), but `fact_list` ignores them (`state.py:79-93`). `open_threads` requires `status == "open"` (`state.py:76-77`), while all 18 corpus thread records omit status. Bare serialization reads original facts/threads directly (`continuity.py:38-62`). Offline reproduction showed `compiled_open_threads=[]` and only generic facts. | CK is scored without the identifiers/evidence that bare receives. Any arm delta confounds structure with information removal. | Derive every arm from one canonical frozen artifact; prove inclusion/exclusion and model-visible byte hashes mechanically. |
| CK-R00-003 | **CRITICAL** | Continuity admission and denominators fail open; dry plumbing is publishable as completed science. | Episode A worker failure is `continue`d (`run_continuity.py:309-312`); summary uses only `status == completed` survivors (`336-341`); event says `rows_expected=len(rows)` (`411-413`). Dry mode initializes `status="completed"` (`220-235`) and neither report nor event records `dry`. Reproduction produced six valid rows and M1/M2 values with no inference. | Hard cases can disappear, one-sided missingness can improve means, and dry output is indistinguishable from a real run. | Expected task/arm/repeat cells must be preregistered; every cell gets a terminal typed status; dry artifacts are schema-distinct and cannot carry scientific headlines. |
| CK-R00-004 | **CRITICAL** | Product and matrix inference bypass the typed admission boundary. | `pipeline.run_turn` calls `ollama.generate` (`pipeline.py:121-127`); controls call `client.generate` (`run_matrix.py:109-130`). Only `OllamaClient.run` distinguishes no-final/timeout/transport/invalid (`generate.py:115-174`). Matrix reconstructs status from error strings (`run_matrix.py:343-367`). Thinking-only reproduction became two validation passes and `reject`, with no thinking telemetry or `NO_FINAL_RESPONSE`. | A thinking-only response, malformed response, HTTP failure, or timeout can be misclassified; product receipts and matrix rows disagree with the repository's own admission law. | All scored/product calls must consume one typed result; no caller may infer status from strings or raw response shape. |
| CK-R00-005 | **CRITICAL** | The C1 headline control is not budget matched or instruction identical, and an unpaired aggregate remains labelled headline. | `budget_matched_prompt` has no byte target (`run_matrix.py:133-142`). Current reproduction: CK packet text 1,310 B vs control 724 B. Control system text (`231-237`) differs from CK (`compile.py:155-162`). `headline_vs_budget_matched_bare` uses independent condition means (`run_matrix.py:384-390`); only the separate paired object fails closed (`391-404`). | A reported difference can arise from instruction, byte mass, different surviving probes, or substrate behavior. | Define the exact model-visible budget, use byte-identical rules, pair by full trial key, and reserve `headline` for a gate-approved paired estimand. |
| CK-R00-006 | **CRITICAL** | The continuity scorer is a known invalid recall/shotgunning metric but the runner still emits M1/M2. | `score_episode_b` uses substring presence for dimensions (`continuity.py:194-305`). `docs/RE_GROUNDING.md:163-171` marks the metric void; commit `1dfc607` says verbose identifier dumping beats precise answers. `run_continuity.py:381-387` still computes M1/M2. | Numeric continuity comparisons remain easy to game and cannot support adaptation decisions or cross-model claims. | A scorer must be preregistered, falsified against shotgun/precision fixtures, and version-gated before M fields can exist. |
| CK-R00-007 | **HIGH** | Continuity grounding uses evidence not visible to the scored arm. | Every arm calls `score_episode_b(... packet=ck_packet, artifacts=artifacts)` (`run_continuity.py:225`). `evidence_blob` combines that CK packet with all original artifacts (`continuity.py:121-159`), including facts truncated from bare or redacted from broken. | Unsupported claims may be credited as grounded because the answer key knows evidence the model never saw. | Grounding must use only canonical bytes visible to that arm, plus explicitly external scorer-only truth that cannot confer evidence credit. |
| CK-R00-008 | **HIGH** | Candidate schema presence is erased, and malformed `next_state` shapes can validate. | Parser normalizes missing `next_state` to `{}` (`parse.py:81-87`); validator checks only `isinstance(..., dict)` (`validate.py:351-365`). It validates `thread_touch` only when it is already a list and otherwise adds no violation (`394-442`). Reproduction accepted JSON with no `next_state` as `valid_schema=true`, `state_faithful=true`, no violations. | Schema success can be mistaken for semantic/contract success; unknown shapes may reach ACCEPT (though the writer currently ignores a non-list touch). | Preserve field presence and validate required nested types/keys independently of server-side constrained decoding. Unknown/missing states fail closed. |
| CK-R00-009 | **HIGH** | Qualification can call an unusable raw path successful and does not measure actual memory residency. | Raw success is `status == COMPLETED` only (`qualify_models.py:300-305`). Committed `gemma3:1b` has `8_raw_path_works: true` and raw output `""` (`runs/qualification_20260722T220405Z/gemma3_1b.json:12,58-60`). Memory fit is model file size ≤ RAM minus 1.5 GB (`qualify_models.py:193-217`), not observed VRAM/RSS/fragmentation. | `QUALIFIED` overclaims what was verified and can admit a model/path that yields no usable output or does not fit under real load. | Qualification checks need typed pass criteria, non-empty final response where required, actual target-host residency evidence, and tuple-bound verdicts. |
| CK-R00-010 | **HIGH** | Qualification “schema compliance” tests key presence, not the declared schema. | `qualify_models.py:268-298` accepts any dict containing `answer`, `evidence_used`, and `next_state`, regardless of types, nested fields, or empty answer. | A model can qualify while failing the product return-path contract. | Reuse the same parser/validator or a frozen qualification schema; record structural and semantic eligibility separately. |
| CK-R00-011 | **HIGH** | Experiment provenance is not sufficient for deterministic replay. | Matrix report lacks repo commit/dirty state, corpus hash, state file hashes/bytes, exact model-visible prompt hash, and replay command (`run_matrix.py:411-431`). Continuity hashes partial contexts but not full messages/system/options; tracked continuity artifacts have `environment: null`. Receipts log ids/hash/decision but not packet bytes/raw response/config/state hashes (`accept.py:29-56`). | Another operator cannot reconstruct a run or prove the state transition without invoking hidden current state. | One versioned manifest must bind commit, dirty diff hash, corpus, state snapshot, profile, model digest/runtime, exact request/response channels, route, and before/after state hashes. |
| CK-R00-012 | **HIGH** | Expected-pair accounting is inferred from observed rows and collapses repeated trials. | `paired_gain` and `budget_conditional_gain` build dicts keyed only by `probe_id` and infer expected probes from the observed union (`score.py:380-383`, `523-526`). Duplicate repeats overwrite; a probe absent from both conditions never enters the universe. | Missing rows can disappear, and repeats cannot be represented honestly. | Pass a preregistered expected trial-key set such as `(probe_id, repeat, seed, condition)`; reject duplicates and missing cells. |
| CK-R00-013 | **HIGH** | Scientific thresholds and composite semantics are hardcoded outside ratified config. | Examples: evidence length 12 (`validate.py:219-236`), goal overlap 0.85 (`122-142`), responsiveness token thresholds (`145-179`), substring answer keys (`score.py:21-66`), delta bounds ±1 and composite formula (`score.py:329-360`, `447-473`). `docs/RE_GROUNDING.md:163-171` notes the shipped composite differs from protocol SG. | Adaptive work could accidentally tune against evaluation data or silently change the scientific estimand. | Separate safety invariants from scientific thresholds; version and fail-close all unratified science config. |
| CK-R00-014 | **HIGH** | Repair and mode bounds do not fail closed at runtime boundaries. | `run_turn` accepts any `max_repair` and loops `range(repairs + 1)` (`pipeline.py:45,60,74`); CLI exposes unrestricted integer (`cli.py:296`). Unknown profile mode silently becomes `chat_json` (`pipeline.py:69-72`). | An opt-in caller can exceed the one-repair law; an unknown state is normalized into a valid route instead of rejected. | Clamp to a versioned hard maximum and reject unknown modes/states/schema versions. |
| CK-R00-015 | **HIGH** | The latest repository plan and supplied adaptive plan are mutually blocking without an authority decision. | Latest admitted repo plan says “Run M0 next, and only M0” and prohibits scorer/metric changes until gates pass (`docs/BUOYANCY_EVOLUTION.md:246-252`; `docs/RE_GROUNDING.md:253-263`). Supplied run orders schedule adaptive contracts/event spine/sensors before model work. | Proceeding to RUN 01 may violate the current plan of record; following M0 may violate tonight's external stop line. | Anthony must name the controlling plan and explicitly supersede or sequence the other. |
| CK-R00-016 | **MEDIUM** | Declared experiment conditions are not executable. | C2/C4/C5 appear at `docs/EXPERIMENT_PROTOCOL.md:24-29`; matrix implements only bare, budget-matched, and strict, with all else `unknown_condition` (`run_matrix.py:263-338`). | Component attribution and the protocol's ablations cannot be run as documented. | Report implementation status in the protocol and reject unknown condition names before starting a run. |
| CK-R00-017 | **MEDIUM** | Packet ordering and hashing are stable only relative to mutable list order, not canonical semantic state. | Open threads preserve JSON file order (`state.py:76-77`, `compile.py:73-76`); no sort key exists. `packet_hash` includes volatile `packet_id`/`created_at` (`compile.py:124-126`) even though model input strips them (`146-150`). | Semantically identical state reorderings change prompts/hashes; identical model-visible prompts get different packet hashes. | Define canonical ordering and separate model-input/content hash from unique packet-instance id. |
| CK-R00-018 | **MEDIUM** | Configured log budget is decorative and JSONL writes are not concurrency coordinated. | `max_log_file_bytes` is loaded/reported only (`edge.py:38,68,98`); append uses a plain unlocked file open (`state.py:41-47`). | Edge logs can grow without bound and concurrent writers can interleave or race with state counters. | Enforce/receipt rotation policy and define single-writer or locking semantics before adaptive multi-passage runs. |
| CK-R00-019 | **MEDIUM** | Rejected outcomes carry `accepted_at`, and accepted-state provenance is incomplete. | `accept_candidate` always sets `accepted_at` (`accept.py:29-37`), including rejects, and outcome has no before/after state hash. | Machine consumers can confuse event time with acceptance; replay cannot verify mutation. | Use neutral event time plus acceptance time only on accept; include transition hashes. |
| CK-R00-020 | **MEDIUM** | Static default-model documents/config disagree with the qualification recommendation. | `orin_nano_8gb.json` and README default to `qwen2.5:0.5b`; `MODEL_QUALIFICATION.md:54-58` recommends `gemma3:1b`; the supplied research report also treats 1B as practical minimum. | A default run can use a model the repository says is smoke-only/below the functional band. | Anthony should distinguish product default, smoke default, and scientific subject in versioned config. |

## Minimal reproductions

### R1 — Continuity packet loses corpus facts and threads

For the first corpus task, materialize `seed_state_dir`, load `SubstrateState`, and compile Episode B. Observed:

```json
{
  "seed_facts": [
    "This system is fully local.",
    "Active sprint code is CK-SPRINT-GAMMA-7.",
    "Deliverable is the continuity cold-start receipt on Orin.",
    "Sensors are out of scope for v0."
  ],
  "seed_threads": [{"id": "thread_gamma_receipt", "title": "..."}],
  "compiled_facts": ["generic runtime facts ...", "Current goal: ..."],
  "compiled_open_threads": []
}
```

### R2 — Missing required `next_state` validates

Input candidate:

```json
{
  "answer": "Substrate design stays fully local.",
  "evidence_used": ["This system is fully local."]
}
```

Observed receipt:

```json
{
  "valid_schema": true,
  "state_faithful": true,
  "violations": []
}
```

### R3 — Thinking-only product call bypasses typed status

A fake client returned `{"message":{"content":"","thinking":"xxxxxxxxxx"}}` through `run_turn`. Observed two ordinary validation passes ending in:

```json
{
  "decision": "reject",
  "error": "rejected_after_validation",
  "candidate_parse_error": "no_json_object_found"
}
```

No `NO_FINAL_RESPONSE`, `thinking_chars`, or typed inference object was present.

### R4 — C1 bytes are not matched

Current state, prompt `State the design intent`:

```text
CK serialized packet bytes:       1310
budget_matched_prompt bytes:       724
delta control - CK:               -586
```

### R5 — Dry run is admitted

```text
python experiments/run_continuity.py --limit 2 --dry \
  --out /tmp/ck-run00-continuity-dry.json
```

Observed six rows with `status=completed`, `rows_valid=6`, `rows_expected=6`, M1/M2 values, and no report/event field marking the run dry.

## Named attack-surface disposition

| Requested audit surface | Disposition |
|---|---|
| timeout conflation | **Confirmed** on product/matrix paths; typed distinction exists but is bypassed |
| thinking/final conflation | thinking is not copied into final (good), but thinking-only is mis-admitted outside `.run()` |
| omitted failures | **Confirmed** in continuity Episode A skip, survivor-only means, observed-row denominator |
| empty string treated as answer | deliberately a completed zero in `.run()`; **unsafe** for qualification raw-path “works”; dry no-inference also becomes completed empty |
| invalid rows affecting headline | **Confirmed** via unpaired legacy headline and absent expected universe; paired function is safer for unique observed ids |
| direct model-to-state write | **Not found.** Writes are acceptance-gated and allowlisted; preserve this boundary |
| retry without new information | production repair adds deterministic diagnostics; dry mode reuses identical candidate but is non-model plumbing. Hard bound is caller-overridable |
| schema success as semantic success | **Confirmed** in missing `next_state`, qualification key-presence check, and continuity summaries independent of key/grounding acceptance |
| answer leakage through compiled context | **Risk confirmed, exploit not fully adjudicated.** Repair embeds goal/evidence samples; information budgets and target-leak fixtures are absent |
| model-specific assumptions | default/recommendation drift; raw/chat support varies; qualification artifacts are host-specific |
| nondeterministic ordering | state list order is not canonical; load-state nondeterminism is documented and primed in experiments |
| thresholds outside frozen config | **Confirmed** across validator/scorer/composite |
| missing provenance | **Confirmed**; no complete replay manifest or before/after state-hash chain |

