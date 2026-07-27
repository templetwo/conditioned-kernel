# RUN 00.5 — Baseline Integrity Repair Specification

Status: specification only; implementation and M0 execution are not authorized  
Audited commit: `db668a91e32843c3e53de58325cc17fff4b9c746`  
Branch: `codex/ck-run-00-5-spec`  
Scope: the existing static Conditioned Kernel experiment only

## 1. Governing constraint

The M0 scientific question is unchanged:

> Can a persistent local substrate make a small model more coherent, state-faithful, continuous, and repairable than the same model bare?

RUN 00.5 specifies only the repairs needed to make that question measurable. It does not introduce the Adaptive Riverbed, a new treatment, a new task, a new model condition, or a new scientific threshold.

The current audited commit cannot validly execute M0. In the continuity path, Episode A invokes a model but does not parse, validate, accept, or persist its output; Episode B is then seeded from the original task state. The treatment packet also omits the task seed facts and all corpus threads. A successful current run would therefore demonstrate static seed-context retrieval, not accepted cross-episode continuity.

## 2. Minimal repair set

The minimum protocol-valid implementation is:

1. Establish one canonical typed terminal-outcome object and require product, matrix, continuity, experiment, and dry-run callers to use it.
2. Route Episode A through the canonical compile → typed inference → parse → validate → assess → accept/reject path.
3. Derive an allowlisted state delta inside trusted substrate code; never give model output a write capability.
4. Persist an accepted delta atomically, read it back from a fresh `SubstrateState`, and bind the before/after hashes to the receipt.
5. Compile Episode B from the reloaded post-accept state, not from the original corpus seed or an in-memory artifact copy.
6. Correct task-state ingestion so every declared required fact and thread is available to the compiler, with explicit insufficiency instead of required-field truncation.
7. Build a manifest before execution and emit exactly one terminal row for every planned task/condition/episode cell, including operational failures and dry runs.
8. Replace the substring continuity headline with deterministic closed-set relational assessment and keep any semantic paraphrase judgment separate.
9. Enforce the control-matching contract mechanically and record its byte and information-set receipts.
10. Add the integrity tests in `RUN_00_5_TEST_PLAN.md`; make their passage, the existing green suite, clean provenance, and Anthony's explicit authorization mandatory M0 gates.

No other refactor is needed for the pre-M0 lane.

## 3. Canonical Episode A lifecycle

The names below identify the current owning module or the minimal proposed shared module. `ExecutionOutcome` is a new static-baseline type, not an adaptive component.

| Transition | Owning module | Exact input → output | Allowed status/decision | Fail-closed behavior | Receipt evidence | Required tests |
|---|---|---|---|---|---|---|
| State load | `state.py` | `StateLocation(state_dir: Path, logs_dir: Path)` → `LoadedState(snapshot: SubstrateState, source_hashes: Mapping[str, Sha256], loaded_at: UTCDateTime)` | `LOADED`; terminal `NOT_RUN` only before invocation | Missing, malformed, or unhashable required state stops compilation. No empty default may stand in for a required task field. | source paths, complete file SHA-256 values, schema version, load timestamp | required-state load; malformed state; missing task fact/thread |
| Packet compile | `compile.py` | `CompileRequest(state: LoadedState, task: EpisodeTask, profile: EdgeProfile)` → `CompileResult(packet: ArrivalPacket, model_input: ModelInput, sufficiency: PacketSufficiencyReceipt)` | `SUFFICIENT`; terminal `SCHEMA_FAILED` for malformed declared state; terminal `COMPLETED_INVALID` with reason `PACKET_INSUFFICIENT` for a well-formed state that cannot supply/fit dependencies | All declared required dependencies must be present before optional fields. Required data is never silently dropped. Gold fields are rejected if model-visible. | packet hash, model-input hash, included field/record IDs, omitted optional IDs and reasons, forbidden-field scan, byte count, task dependency manifest hash | required inclusion; omission insufficiency; leakage rejection; deterministic order; budget failure |
| Model invocation | `generate.py` through the shared executor | `ModelInput` → existing `InferenceResult` → canonical `ExecutionOutcome` projection | `COMPLETED_VALID` may not be assigned yet; transport layer yields provisional `INFERENCE_COMPLETED`, or terminal `TIMEOUT`, `TRANSPORT_ERROR`, `INVALID_RESPONSE`, `NO_FINAL_RESPONSE` | Use `OllamaClient.run`, never exception/string inference. A typed `NO_FINAL_RESPONSE` always has `output=null` and cannot be reconstructed as `""` by a caller. Thinking is telemetry only. Stop downstream mutation on non-completion. | request hash, model identity, mode, timeout, decoding options, elapsed time, channel character counts, typed inference status, error class/message | timeout and no-final preservation through every caller; thinking isolation |
| Candidate extraction | `pipeline.py` | `InferenceResult(status=COMPLETED, output: str)` → `CandidateEnvelope(raw_bytes: bytes, raw_sha256: Sha256, packet_id: PacketId, pass_index: int)` | provisional `CANDIDATE_OBSERVED` | Candidate bytes are immutable and hashed once. A genuinely observed empty final may proceed but cannot become valid JSON and therefore cannot become `COMPLETED_VALID`. No field is trusted or used as a state delta yet. | raw byte length/hash, packet ID, pass index, channel provenance | no-final not coerced to empty; observed empty fails parse; immutable candidate hash |
| Parse | `return_path/parse.py` | `CandidateEnvelope` → `ParsedCandidate | ParseFailure` | continue on parse success; terminal `PARSE_FAILED` on failure | Do not synthesize missing required fields, coerce a wrong type to an empty value, or recover an answer from the thinking channel. | parser version, parse status/error, parsed shape hash | malformed JSON; missing object; wrong root/type |
| Closed-set validation | `return_path/validate.py` | `ParsedCandidate + ArrivalPacket` → `ValidationReceipt` | continue on schema/state-policy success; terminal `SCHEMA_FAILED` on structural/schema violation | Require every schema member and nested type explicitly. Reject unknown state operations and identifiers. Do not normalize absent `next_state` to `{}`. | schema ID/hash, violations with field paths, allowed identifier set hash, evidence matches | missing `next_state`; non-array `thread_touch`; invented operation/ID |
| Semantic and continuity assessment | `return_path/assess.py` plus corrected `continuity.py` | `ParsedCandidate + ValidationReceipt + EpisodeTaskEvaluationContract` → `AssessmentReceipt` | `ACCEPT`, `REJECT`, or bounded `REPAIR`; terminal `SEMANTIC_FAILED` after final semantic/continuity rejection | Primary continuity is closed-set relational assessment. Prose semantic judgment is separately labeled and cannot silently control the headline. Repair never receives gold answers. | relation-set comparison, omissions, contradictions, unsupported additions, orphan identifiers, repair pass | relational fixtures; repair has no answer-key leakage |
| Acceptance or rejection | `return_path/accept.py` | `AssessmentReceipt + ParsedCandidate` → `AcceptanceDecision(accepted_candidate_id, trusted_delta | None)` | provisional `ACCEPTED` or terminal `COMPLETED_INVALID`/specific failure | Trusted code constructs `trusted_delta` only from allowlisted operations and validated identifiers. Rejection creates no delta and cannot mutate state. | decision, reason codes, candidate/packet hashes, exact allowlist version, derived-delta hash | rejected no-mutation; direct model write impossible; allowed delta derived |
| Allowlisted state mutation | `state.py` | `LoadedState + TrustedStateDelta` → `ProspectiveState(before_hashes, after_bytes, after_hashes)` | provisional `MUTATION_PREPARED` | Apply only declared static operations. No arbitrary key, note, file, path, or operation supplied by the model is writable. Failure leaves durable state unchanged. | normalized delta, before/after hashes, touched records | allowlist; unknown op; idempotence as declared |
| Atomic persistence | `state.py` | `ProspectiveState` → `PersistenceReceipt` | provisional `PERSISTED`; terminal `COMPLETED_INVALID` with persistence reason if commit/readback fails | Write complete temporary files, `fsync`, atomically replace, then read and hash complete bytes. Multi-file changes require a recoverable transaction boundary or one canonical event file plus derived views; partial success is not acceptance. | temp-to-final operation, filesystem paths, file hashes, fsync/readback status, continuity event ID | atomic failure; readback hash; no partial accepted state |
| Next-episode state load | `state.py`; orchestrated by `experiments/run_continuity.py` | `StateLocation + expected PersistenceReceipt` → fresh `LoadedState` | provisional `RELOAD_VERIFIED`; terminal `COMPLETED_INVALID` on mismatch | A new process must load from the persisted path. In-memory `artifacts`, original seed state, or parent-process objects cannot satisfy this step. Episode B cannot start on mismatch. | distinct process IDs/timestamps, source paths, expected/actual hashes, observed accepted event ID | accepted output loaded next episode; distinct PID; original seed cannot substitute |
| Receipt finalization | shared outcome serializer used by `pipeline.py` and experiment runners | all phase receipts → `ExecutionOutcome` and one manifest row | one terminal status from §6 | Receipt serialization failure invalidates completion. A planned row still exists with its terminal failure; it is never omitted. | all fields in §8 plus provenance and phase chain hashes | receipt completeness; exactly-one terminal record |

### 3.1 State-write authority

Model-visible output is an untrusted proposal. It has no filesystem object, file path, database handle, callback, tool, or mutation method. The only state-changing call accepts a trusted `TrustedStateDelta` type that cannot be constructed from arbitrary decoded JSON without successful validation and an acceptance decision.

For the existing static schema, the initially allowlisted operation remains thread touch by an existing canonical thread ID. `proposed_note` remains non-durable. Any broader operation requires a separate specification and Anthony's approval.

## 4. Canonical definitions

**Candidate**  
An immutable, hash-bound final-response byte sequence observed from a completed inference, plus packet ID, pass index, and channel provenance. Thinking text, transport errors, timeouts, typed no-final responses, and dry fixtures are not model candidates. A genuinely observed empty final may be a candidate but cannot satisfy the JSON schema or become a completed valid observation.

**Valid candidate**  
A candidate whose bytes parse without coercion, match the complete output schema including nested types, use only closed-set identifiers/operations, contain no forbidden leakage, and pass the deterministic semantic/continuity contract. Validity does not itself authorize persistence.

**Accepted candidate**  
A valid candidate for which trusted assessment returned `ACCEPT` and trusted substrate code derived an allowlisted state delta. It is accepted in memory but is not yet a completed continuity event.

**Persisted continuity event**  
An accepted candidate whose trusted delta was atomically committed, completely read back, hash-verified, and recorded with candidate, packet, before-state, and after-state hashes. A receipt log without matching durable state is not a persisted event.

**Completed Episode A observation**  
A `COMPLETED_VALID` Episode A row for which inference, parse, schema, semantic/continuity assessment, acceptance, atomic persistence, fresh-process reload, and receipt finalization all succeeded. Episode B may start only after this definition is satisfied. A rejected candidate, dry run, omitted row, or operational failure is not a completed Episode A observation.

## 5. Packet sufficiency contract

### 5.1 Classification

| Class | Episode A fields/elements | Rule |
|---|---|---|
| Required operational state | task ID and prompt; current goal; every task-declared seed fact dependency; every task-declared thread dependency with canonical `id`, `title`, and normalized `status`; applicable static constraints; requested operation; output schema/acceptance contract; allowed state-operation and identifier sets; profile fields that change the actual model envelope | Include all, in canonical order, or return explicit insufficiency before inference. |
| Optional supporting state | relevant accepted-history summaries; relevant method summaries; non-required open threads; non-target provenance labels; bounded explanatory text | Include only after required state fits, by a fixed priority/order. Record every omission and reason. |
| Forbidden answer leakage | Episode B `answer_key`; `correct_next_action.accept_any_of`; `progress_trace.accept_any_of`; scorer relation gold sets; expected state-write values that disclose the target; forbidden-invention examples that name the answer; labels identifying the correct arm; post-task outcome/score | Exclude from every model-visible field, system prompt, repair prompt, padding region, and cache key. A compiler leakage scan is mandatory. |
| Irrelevant context | unrelated closed threads; unrelated full logs; wall-clock timestamps and volatile IDs; receipt counters; environment diagnostics; scorer internals; model rankings; complete archived files | Exclude. Hash/provenance metadata may exist outside the prompt in the receipt. |

`seed_facts` must enter the canonical fact accessor or a task-specific fact projection; it may not be written to `current.json` and then ignored. Corpus threads without `status` must either be rejected as malformed or normalized by the corpus loader under one documented rule before compilation. The compiler itself must not silently infer that an unspecified thread is open.

### 5.2 Deterministic inclusion rule

1. The corpus loader validates a task dependency manifest containing canonical state references, not answer text.
2. The loader resolves every reference against the loaded state and rejects duplicates, missing references, and ambiguous aliases.
3. The compiler emits, in this order: operation/output contract; task prompt; goal; constraints; required facts sorted by canonical ID; required threads sorted by canonical ID; allowed operations/IDs; optional records by declared priority then canonical ID.
4. Serialization is canonical UTF-8 with a pinned schema/version and no volatile model-visible fields.
5. Required content is budgeted first. If it does not fit intact, compilation returns `PACKET_INSUFFICIENT`; required elements are not clipped, summarized, or dropped.
6. Optional content is included whole until the next record would exceed the budget. The receipt records each included and omitted record with a reason.
7. A forbidden-field scan runs over the complete model-visible system and user bytes before invocation.

This rule supplies enough state to attempt the task while withholding the target answer. It does not increase context indiscriminately.

### 5.3 Packet-omission proof obligations

For each required dependency class, a counterfactual compiler fixture removes exactly that dependency while holding all other bytes constant. The expected outcome is explicit `PACKET_INSUFFICIENT` identifying the missing reference before model invocation. The minimum fixtures remove:

- the current goal;
- one required seed fact;
- one required thread ID/title/status record;
- the task prompt/requested operation;
- the output schema;
- the allowed state-operation/identifier set.

Optional-field removal must still compile and must appear in the omission receipt. Forbidden-answer insertion must fail the leakage scan. These are deterministic sufficiency tests, not model-quality tests, and require no model run.

## 6. One canonical typed outcome path

The implementation should introduce one immutable `ExecutionOutcome` in a shared static module (proposed: `src/conditioned_kernel/outcomes.py`). Product execution, `run_matrix.py`, `run_continuity.py`, experiment workers, and dry runs must consume or produce this type; no caller may reconstruct status from exceptions, strings, `decision`, empty output, or score presence.

Minimum shape:

```text
ExecutionOutcome(
  run_id, manifest_cell_id, task_id, condition_id, episode,
  status: TerminalStatus,
  output: str | None,
  candidate_id: str | None,
  decision: accept | reject | none,
  reason_codes: tuple[str, ...],
  inference: InferenceResult | None,
  phase_receipts: PhaseReceipts,
  dry_run: bool,
  quality_admitted: bool,
  scientific_completion: bool,
  started_at, ended_at, provenance
)
```

Exactly one of these terminal values is required:

| Status | Meaning | `output` | Scientific completion |
|---|---|---|---|
| `COMPLETED_VALID` | Full lifecycle, including required persistence/reload for Episode A, succeeded and the candidate was accepted | observed final string | yes |
| `COMPLETED_INVALID` | Inference completed and evaluation reached a terminal rejection not more specifically classified below, or trusted persistence/reload/receipt verification failed | observed string when one exists | no |
| `TIMEOUT` | Typed invocation timeout | `null` | no |
| `TRANSPORT_ERROR` | Request could not produce a response because of transport/runtime failure | `null` | no |
| `INVALID_RESPONSE` | Transport returned a response that cannot supply the expected response envelope/channel | `null` | no |
| `NO_FINAL_RESPONSE` | Reasoning/telemetry may exist, but no final response was observed | `null` | no |
| `PARSE_FAILED` | Final response was observed but candidate JSON could not be parsed without coercion | observed string | no |
| `SCHEMA_FAILED` | Parsed value violates candidate/state/packet schema or closed-set identifier/operation typing | observed string where applicable | no |
| `SEMANTIC_FAILED` | Parsed, schema-valid candidate failed deterministic semantic or continuity assessment | observed string | no |
| `NOT_RUN` | Planned manifest cell was never invoked, with a reason such as blocked dependency or authorization | `null` | no |
| `DRY_RUN_ONLY` | Plumbing used synthetic/no-inference data | synthetic data only in a separate fixture field; `output` is `null` | no |

Precedence is lifecycle order: invocation failures precede parse; parse precedes schema; schema precedes semantic; persistence/reload/receipt failure becomes `COMPLETED_INVALID` with a precise reason code. `COMPLETED_VALID` is assigned only during receipt finalization.

### 6.1 Denominator and reporting rules

- Construct an immutable manifest before execution. Its cell key is `(run_id, task_id, condition_id, episode, replicate_id)`.
- The result artifact contains exactly one terminal row for every manifest key. Duplicate or missing keys invalidate the artifact.
- The planned denominator is the manifest cell count, never `len(completed_rows)` or the union of observed IDs.
- Status counts use the full planned denominator.
- Quality-conditional summaries may use only explicitly admitted `COMPLETED_VALID` paired cells and must report planned, admitted, and excluded counts plus exclusions by status. An incomplete primary pair produces no primary headline.
- Operational and candidate failures remain categorical outcomes. They are never silently converted to a numeric zero, empty string, untyped `None`, or omitted row.
- A budget-conditional estimand may treat a failure as failure only through a separately named, preregistered categorical success rule or an Anthony-ratified utility mapping. The original status remains present; no implicit zero imputation is permitted.
- `DRY_RUN_ONLY` and `NOT_RUN` remain in the planned artifact but never count as scientific completion, accepted output, valid pair, or M0 evidence.
- Episode A failure produces terminal Episode A and `NOT_RUN` Episode B rows for every dependent condition, with `blocked_by_manifest_cell_id` recorded.

## 7. Scientific interpretation after repair

The repair does not change the M0 question, but it constrains what M0 can establish. A single accepted, persisted, freshly reloaded local round trip is an instrumentation and protocol-admission milestone. It is not evidence of substrate gain, model improvement, or an Adaptive Riverbed effect. Any causal gain claim requires a later authorized run with a mechanically valid primary control, complete paired outcomes, and the corrected scorer.

Pre-repair continuity scores cannot be reinterpreted as cross-episode continuity because the current Episode A output was not persisted, Episode B was reseeded, required task state was absent from the CK packet, and the current scorer rewards identifier enumeration. Those artifacts are diagnostic only.

## 8. Required receipt fields

Every terminal row must carry, directly or by content-addressed reference:

- run, manifest-cell, task, condition, episode, and replicate IDs;
- audited commit, branch, dirty-state inventory, corpus path and complete SHA-256, and schema/scorer/compiler versions;
- model name/digest, runtime version, device/load state, profile, mode, timeout, decoding parameters, and declared budgets;
- state source paths and complete before-load hashes;
- packet/model-input hashes, exact byte counts, included/omitted dependency IDs and reasons, forbidden-leakage scan result;
- typed inference status, output nullability, error class/message, elapsed time, and thinking/final channel counts;
- raw candidate byte count/hash, parse status/error, schema violations, semantic/continuity assessment sets, and decision;
- trusted allowlist version, normalized delta and hash, before/after state hashes, atomic-write/readback result;
- fresh-load process ID/path/hash and expected-versus-observed continuity event ID;
- final terminal status, reason codes, scientific-completion flag, dry-run flag, and start/end timestamps.

Secrets, hidden reasoning content, and unrestricted raw environment dumps are not receipt fields.

## 9. M0 go/no-go gate

M0 is `NO-GO` unless every item below is evidenced in one preflight gate receipt:

- one canonical typed inference/outcome path is used everywhere;
- Episode A parses, validates, accepts, and atomically persists an allowlisted delta;
- a fresh Episode B process demonstrably loads the accepted post-state and matching continuity event;
- every planned manifest cell has exactly one terminal row;
- dry runs cannot count as scientific completion;
- the primary control contrast and matching contract are explicit and mechanically verified;
- the corrected scorer passes every adversarial fixture in `RUN_00_5_SCORER_REPAIR_SPEC.md`;
- all pre-existing tests remain green;
- every new integrity test in `RUN_00_5_TEST_PLAN.md` passes;
- no scientific threshold changed without ratification;
- source, corpus, model/runtime, packet, state transition, and result provenance is complete and clean;
- the worktree contains no unexplained implementation or corpus change;
- Anthony J. Vasquez Sr. explicitly authorizes M0 after reviewing the implementation receipt.

Any false, missing, ambiguous, or unverifiable gate item is `NO-GO`. Passing RUN 00.5 documentation alone does not open M0.

## 10. Decisions reserved for Anthony

Implementation cannot begin until Anthony decides or approves:

1. whether byte equality is the binding primary budget contract and token counts remain diagnostic, as recommended in the control specification;
2. whether the canonical task corpus may add dependency references and closed-set relational gold fields without changing the underlying task content;
3. whether accepted Episode A continuity is represented by a canonical append-only event plus derived current views, or by a recoverable multi-file transaction;
4. whether structured relational assertions become a required output field for continuity tasks;
5. whether any separately labeled semantic-paraphrase judge is allowed; deterministic primary scoring does not require one;
6. the later implementation authorization;
7. M0 execution authorization after the gate is satisfied;
8. any numeric threshold or utility mapping, none of which is selected here.
