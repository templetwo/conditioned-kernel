# RUN 00.5 — Baseline Integrity Test Plan

Status: test design only; no test is created or modified in RUN 00.5  
Baseline under test: `db668a91e32843c3e53de58325cc17fff4b9c746`

## 1. Test policy

Implementation should add new tests without weakening or deleting existing ones. All new tests are offline and deterministic: they use temporary state directories, fake typed clients, pinned byte fixtures, and scorer-only corpus fixtures. They do not invoke a live model or run M0.

“Must fail now” means the proposed test is expected to be red against the audited commit for the defect it is designed to expose. A test unexpectedly passing requires inspection; it is not proof that the full invariant already holds.

Proposed test files:

- `tests/test_baseline_lifecycle_integrity.py`
- `tests/test_packet_sufficiency.py`
- `tests/test_outcome_unification.py`
- `tests/test_control_matching.py`
- `tests/test_continuity_relational_scorer.py`
- `tests/test_manifest_receipts.py`

## 2. Lifecycle and state continuity

| Test name | Invariant | Fixture | Expected result | Failure meaning | Target module | Must fail now? |
|---|---|---|---|---|---|---|
| `test_episode_a_accepted_output_persists_and_is_loaded_by_episode_b` | An accepted Episode A delta is durable and is the source of Episode B state. | Temporary seed state; fake completed JSON candidate touching one open thread; invoke Episode A then a fresh loader/worker. | Episode A is `COMPLETED_VALID`; before/after hashes differ as declared; Episode B reads the accepted event/thread timestamp from disk and its source hash equals Episode A's after hash. | The experiment is reseeding or carrying in-memory artifacts instead of measuring continuity. | `pipeline.py`, `accept.py`, `state.py`, `experiments/run_continuity.py` | Yes |
| `test_episode_a_rejected_output_does_not_mutate_state` | Rejection has no durable side effect. | Same state; schema-valid candidate with an invented thread ID or semantic contradiction. | Terminal rejection (`SCHEMA_FAILED` or `SEMANTIC_FAILED`); all state-file hashes byte-identical; no persisted continuity event. | Untrusted or rejected output can contaminate later episodes. | `validate.py`, `accept.py`, `state.py`, continuity runner | Yes |
| `test_model_candidate_cannot_call_state_mutation_directly` | Only a trusted delta type reaches the state writer. | Parsed JSON containing arbitrary keys, file paths, a note, and a forged operation. | Validation fails; state mutation API rejects raw mappings/candidate types; no files outside the declared state set are touched. | Model output has a write-capability path. | proposed `outcomes.py`, `accept.py`, `state.py` | Yes |
| `test_allowlisted_thread_touch_is_derived_not_replayed` | Trusted code reconstructs the allowed operation from validated canonical IDs. | Candidate proposes one real and one forged thread; allowlist contains only the real ID. | Whole candidate is rejected; no partial touch; receipt contains no trusted delta. | Partial or direct replay lets mixed-validity output mutate state. | `validate.py`, `accept.py` | Yes |
| `test_atomic_persistence_readback_mismatch_invalidates_episode_a` | Acceptance requires complete atomic write and verified readback. | Fault-injected state writer returns/readbacks bytes with a hash mismatch. | `COMPLETED_INVALID` with persistence/readback reason; Episode B cells are `NOT_RUN`; no completed continuity event. | A receipt can claim acceptance without matching durable bytes. | `state.py`, `pipeline.py`, continuity runner | Yes |
| `test_multi_file_state_change_cannot_be_observed_partially` | A continuity update has a recoverable transaction boundary. | Fault injection between current/thread durable writes. | Either prior state is fully visible or the new event and all derived views are fully visible; never a completed partial transition. | Crash timing can create protocol-valid-looking split state. | `state.py` | Yes |
| `test_episode_b_requires_fresh_process_and_post_state_hash` | A cold-start receipt proves process and filesystem continuity. | Episode A receipt plus a same-PID loader and a fresh-PID loader. | Same-PID attempt is ineligible; fresh loader must match after-state/event hashes before Episode B invocation. | Within-process memory can be mistaken for continuity. | `experiments/run_continuity.py` | Yes |
| `test_episode_a_failure_blocks_all_dependent_episode_b_cells` | No Episode B inference follows an incomplete Episode A. | Fake Episode A `TIMEOUT` in a manifest with all existing arms. | One Episode A `TIMEOUT`; one `NOT_RUN` row per dependent arm with `blocked_by_manifest_cell_id`; fake Episode B client is never called. | Failed continuity is omitted or Episode B runs against seed state. | continuity runner, proposed `outcomes.py` | Yes |

## 3. Packet sufficiency and leakage

| Test name | Invariant | Fixture | Expected result | Failure meaning | Target module | Must fail now? |
|---|---|---|---|---|---|---|
| `test_missing_required_fact_causes_explicit_packet_insufficiency` | Every declared task fact is mandatory and missingness is detected before inference. | Episode A task declares two fact IDs; loaded state omits one. | Compile terminates `COMPLETED_INVALID`/`PACKET_INSUFFICIENT`, naming the missing fact; client call count remains zero. | Packet truncation/omission can be misclassified as model failure. | `state.py`, `compile.py`, proposed `outcomes.py` | Yes |
| `test_seed_facts_are_resolved_into_episode_a_packet` | Corpus seed facts are operational state, not dead fields. | `seed_state.seed_facts` with unique fact IDs/values. | All declared facts appear once in the packet and inclusion receipt; atom hashes match state. | Current `fact_list()` still ignores task seed facts. | `state.py`, `compile.py`, continuity task loader | Yes |
| `test_required_thread_requires_id_title_and_normalized_status` | Thread dependencies are complete and cannot disappear through an absent status. | Three corpus threads: valid open, missing status, invalid status. | Missing/invalid status is explicit loader schema failure (or one approved normalization is receipt-recorded); no silent empty `open_threads`. | Treatment loses the corpus thread while control retains it. | `state.py`, continuity task loader, `compile.py` | Yes |
| `test_missing_goal_operation_schema_or_allowlist_is_insufficient` | Every required dependency class is enforced. | Parameterized omission of goal, task prompt/operation, output schema, allowed operation set, or allowed ID set. | Each omission stops compilation with its precise dependency code; no inference. | Required contract pieces can default to misleading empties. | `compile.py` | Yes |
| `test_required_records_are_never_clipped_to_fit_budget` | Required state is atomic with respect to budgeting. | Profile budget one byte smaller than complete required serialization. | Explicit `PACKET_INSUFFICIENT`; no shortened fact/title/ID and no client call. | Compiler manufactures a different under-informed task. | `compile.py`, `edge.py` | Yes |
| `test_optional_records_drop_only_by_declared_priority` | Optional context is bounded and deterministic. | Required set plus several optional records under a constrained byte budget. | Required atoms all present; whole optional records admitted in pinned priority/ID order; omission receipt is exact; repeated builds match. | Context selection is opportunistic or answer-aware. | `compile.py` | Yes |
| `test_forbidden_answer_fields_never_enter_model_visible_bytes` | Gold/scorer fields are not answer leakage. | Task object includes answer key, expected writes, progress trace, correct action, scorer relations, and forbidden-invention examples with unique sentinels. | Complete system/user/schema bytes contain none of the sentinels; leakage scan passes. An intentionally injected sentinel fails closed. | Treatment or control is handed the target answer. | task loader, `compile.py`, control builder | Yes |
| `test_irrelevant_context_is_excluded_and_receipt_provenance_remains_out_of_prompt` | Provenance does not consume or contaminate the task prompt. | State with unrelated closed threads, logs, timestamps, runtime diagnostics, and scorer metadata. | Values absent from model-visible bytes; their allowed hashes/paths may appear only in receipt metadata. | More context or volatile metadata is being added without task necessity. | `compile.py` | Yes |
| `test_packet_compilation_is_byte_deterministic_for_identical_inputs` | Same state/task/profile yields identical model-visible bytes. | Freeze timestamps/volatile IDs; compile twice. | Model-visible system/user/schema bytes and inclusion receipts match; volatile receipt IDs may differ outside prompt. | A causal pair or replay cannot be reproduced. | `compile.py` | Yes |

## 4. Typed outcomes, missingness, and denominators

| Test name | Invariant | Fixture | Expected result | Failure meaning | Target module | Must fail now? |
|---|---|---|---|---|---|---|
| `test_product_timeout_classification_survives_pipeline_path` | Product execution preserves typed timeout. | Fake client returns `InferenceResult(TIMEOUT, output=None)`. | `ExecutionOutcome.status == TIMEOUT`; `output is None`; no parse, score, mutation, or empty answer success. | `run_turn` still flattens typed inference through `generate()`/exception handling. | `generate.py`, `pipeline.py`, proposed `outcomes.py` | Yes |
| `test_matrix_timeout_classification_survives_all_conditions` | Matrix execution uses the same type, not error-text heuristics. | Fake client returns timeout for CK and primary control cells. | Both terminal rows are `TIMEOUT` with null output and no scores; original typed reason survives serialization. | Matrix can turn timeout into transport error, zero, or completed row. | `experiments/run_matrix.py`, proposed `outcomes.py` | Yes |
| `test_continuity_timeout_classification_survives_worker_and_parent` | Worker JSON round-trip preserves the canonical outcome. | Episode A and Episode B fake timeout worker payloads. | Parent rows retain `TIMEOUT`, null output, phase receipt, and manifest identity. | Subprocess serialization reconstructs status from text or drops the row. | `experiments/run_continuity.py` | Yes |
| `test_no_final_response_cannot_become_empty_successful_output` | A typed no-final response cannot be coerced into an empty completed answer. | Fake `InferenceResult(NO_FINAL_RESPONSE, output=None)` with thinking telemetry passed through product, matrix, worker, and parent adapters. | Every path retains `NO_FINAL_RESPONSE` and `output=None`; parse/score/mutation are not called. A separate genuinely observed empty candidate may reach parse but must terminate `PARSE_FAILED`, never `COMPLETED_VALID`. | Caller-side `res.output or ""` converts missing output into successful empty output. | `generate.py`, `pipeline.py`, matrix/continuity adapters | Yes |
| `test_parse_schema_and_semantic_failures_remain_distinct` | Lifecycle failures preserve their terminal layer. | Three candidates: malformed JSON, missing nested required member, exact schema with wrong relation. | `PARSE_FAILED`, `SCHEMA_FAILED`, and `SEMANTIC_FAILED` respectively; each has observed raw output and no numeric failure score. | Failures collapse into reject/error/zero and cannot be audited. | `parse.py`, `validate.py`, corrected `continuity.py`, proposed `outcomes.py` | Yes |
| `test_dry_run_cannot_count_as_completed_observation` | Synthetic plumbing is never scientific completion. | Full continuity manifest executed with fake/dry fixtures. | Every executed dry cell is `DRY_RUN_ONLY`, `scientific_completion=false`, excluded from admitted pairs and M0 gate; no model output field is forged. | Current dry path is labeled completed and can enter means/events. | pipeline, matrix/continuity runners, proposed `outcomes.py` | Yes |
| `test_task_failure_remains_in_planned_denominator` | Failure does not shrink the denominator. | Manifest with one valid task and one Episode A transport failure across existing arms. | Denominator equals manifest size; failed and dependent `NOT_RUN` rows are present; admitted count is smaller and explicit. | The runner's `continue` and `len(rows)` redefine the experiment after failure. | continuity runner, aggregation | Yes |
| `test_every_planned_task_has_exactly_one_terminal_record` | Manifest-to-result is a bijection. | Manifest containing multiple tasks/conditions/episodes; inject success, timeout, rejection, and block. | Exactly one row per manifest key; all terminal; validator accepts. Duplicate one row or delete one row and validator rejects. | Omitted/duplicated cells or dict overwrite can create a false complete result. | proposed `outcomes.py`, matrix/continuity runners, `score.py` | Yes |
| `test_not_run_requires_reason_and_blocking_reference` | `NOT_RUN` is typed evidence, not a blank placeholder. | Cell blocked by Episode A plus a deliberately uninvoked cell. | Both contain a reason; dependency case references its blocker; neither has output/score/completion. | Planned work can silently disappear behind untyped `None`. | proposed `outcomes.py` | Yes |
| `test_incomplete_primary_pairs_emit_no_headline` | Primary quality contrast requires complete valid pairs. | One valid pair plus one timeout/control-valid pair from a fixed manifest. | Primary headline is absent; status distributions and planned/admitted counts remain. No zero imputation. | Survivor-only or legacy unpaired gain is presented as causal. | `score.py`, `experiments/run_matrix.py` | Yes |

## 5. Control matching

| Test name | Invariant | Fixture | Expected result | Failure meaning | Target module | Must fail now? |
|---|---|---|---|---|---|---|
| `test_primary_control_has_byte_identical_instructions` | System and fixed wrapper instructions are identical. | One shared information set compiled into CK and flat forms. | System/wrapper hashes equal and receipt declares instruction identity. | Difference includes instruction wording, not just substrate structure. | `compile.py`, proposed control builder, `run_matrix.py` | Yes |
| `test_primary_control_complete_messages_are_exactly_byte_matched` | Actual model-visible UTF-8 length is equal. | CK representation longer than flat representation; deterministic padding enabled. | Complete user-message byte counts equal; padding has only permitted bytes; exact count in receipt. | `budget_matched` is merely a name or estimated packet length. | proposed control builder, `run_matrix.py` | Yes |
| `test_primary_control_information_atom_multisets_are_identical` | Task facts/threads/constraints are the same data. | Shared information set with repeated-looking values across two threads. | Sorted atom hashes exactly equal; every atom appears once in each arm. | The treatment or control has an information-access advantage. | proposed control builder | Yes |
| `test_primary_control_schema_runtime_and_decoding_are_identical` | Format and execution are paired invariants. | Pair with identical declared settings, then parameterized changes to schema, mode, seed, timeout, context, load policy, and repair policy. | Base pair eligible; every changed field makes preflight `CONTROL_MATCH_FAILED` and no client call. | A runtime/API confound survives under a matched label. | control builder, shared executor, matrix runner | Yes |
| `test_primary_control_diff_contains_only_structure_and_padding` | Only the declared treatment is different. | Machine-readable normalized request diff. | All diff paths classify as hierarchy/labels/order/separators/padding. Add one fact or instruction byte and eligibility becomes false. | An unexpected causal difference is hidden in serialization. | proposed control builder | Yes |
| `test_control_build_is_deterministic_and_gold_blind` | Corpus order/output keys cannot steer the control. | Shuffle input object keys and inject scorer-only sentinels. | Arm bytes rebuild identically after canonicalization; sentinels absent; pair receipt hashes stable. | Control authorship or leaked gold can determine results. | task loader, control builder | Yes |
| `test_token_counts_are_reported_as_diagnostic_not_assumed_equal` | Byte equality is not mislabeled token equality. | Pinned tokenizer fixture where equal-byte forms have unequal token counts. | Receipt shows byte identity true, exact token counts/delta, and diagnostic label; no token-match claim/threshold. | The causal label overstates budget matching. | control builder, receipt serializer | Yes |

## 6. Relational continuity scorer

| Test name | Invariant | Fixture | Expected result | Failure meaning | Target module | Must fail now? |
|---|---|---|---|---|---|---|
| `test_exact_relational_continuity_receives_primary_credit` | Correct subject/predicate/object preservation earns the categorical primary result. | Closed universe; candidate asserts every required relation exactly once. | `EXACT_RELATIONAL_FIDELITY`; all failure sets empty. | Replacement cannot recognize correct continuity. | corrected `continuity.py` | Yes |
| `test_correct_paraphrase_with_exact_relations_receives_credit` | Prose wording does not defeat exact structured continuity. | Semantically correct paraphrase with the same structured relation set. | Same primary result as exact wording; optional prose component separately labeled. | Primary still depends on brittle substrings. | corrected `continuity.py` | Yes |
| `test_one_critical_omission_is_reported_not_partially_passed` | Missing a required relation is explicit. | Exact candidate minus one required tuple. | `RELATIONAL_FIDELITY_NOT_EARNED`; exact tuple in `omissions`; no weighted pass. | Partial mention masks lost state. | corrected `continuity.py` | Yes |
| `test_one_contradiction_is_reported_even_with_correct_identifiers` | Wrong relation defeats identifier presence. | Known IDs with mutually exclusive status/action relation. | Not earned; tuple in `contradictions`. | Identifier presence is still rewarded over truth. | corrected `continuity.py` | Yes |
| `test_identifier_shotgun_receives_no_continuity_credit` | Listing all possible identifiers without relations earns nothing. | Prose dumps the entire entity universe; assertion list empty. | Not earned; `correct_preservation` empty; IDs appear as orphans; no numeric continuity score. | The known shotgunning exploit remains. | corrected `continuity.py` | Yes |
| `test_all_possible_relations_shotgun_cannot_pass` | Relational overproduction also fails. | Candidate asserts every subject/predicate/object combination including the gold tuples. | Not earned; unsupported/contradictory/overproduction sets populated. | Adding the correct tuple amid exhaustive guesses earns a pass. | corrected `continuity.py` | Yes |
| `test_invented_identifier_fails_closed_before_scoring` | Entity universe is closed. | One otherwise-correct candidate with an invented thread ID. | `SCHEMA_FAILED`; scorer `NOT_SCORED`; invented field path recorded. | Fabrication receives partial continuity credit. | `validate.py`, corrected `continuity.py` | Yes |
| `test_correct_identifiers_assigned_to_wrong_threads_do_not_receive_credit` | Relations, not tokens, determine correctness. | Swap next actions/statuses across two known thread IDs. | Not earned; wrong assignments/contradictions exact; required originals omitted. | Identifier copying still passes despite relational corruption. | corrected `continuity.py` | Yes |
| `test_verbose_noncommittal_output_receives_no_relational_credit` | Verbosity cannot substitute for assertions. | Long answer mentions goals/options but supplies no required assertions. | Not earned; omissions and orphan mentions recorded. | Style/length is mistaken for continuity. | corrected `continuity.py` | Yes |
| `test_malformed_and_empty_outputs_never_reach_scorer` | Execution/parse status owns pre-scorer failure. | Malformed JSON, typed no-final, and genuinely observed empty final fixtures. | Malformed/observed-empty candidates are `PARSE_FAILED`; typed no-final is `NO_FINAL_RESPONSE`; scorer spy call count zero; no continuity value. | Failure is converted into a low/zero score. | shared executor, `parse.py`, corrected `continuity.py` | Yes |
| `test_scorer_grounds_only_against_arm_visible_evidence` | Hidden original artifacts cannot grant grounding. | Gold relation in original seed but deliberately absent from the arm evidence view. | Cell is protocol-invalid/packet-insufficient; scorer does not call the claim grounded from hidden artifacts. | Scoring credits information the model never saw. | corrected `continuity.py`, packet receipt | Yes |

## 7. Manifest and provenance receipts

| Test name | Invariant | Fixture | Expected result | Failure meaning | Target module | Must fail now? |
|---|---|---|---|---|---|---|
| `test_terminal_receipt_contains_complete_phase_chain` | A completion is replayable and content-bound. | One fake successful Episode A and one fresh-load Episode B. | Receipt has all fields required by baseline spec §8; phase hashes chain; no placeholder provenance. | “Completed” cannot be tied to source, bytes, or durable transition. | proposed `outcomes.py`, runners, `accept.py` | Yes |
| `test_receipt_rejects_dirty_or_unexplained_provenance` | M0 gate distinguishes known documentation state from implementation/corpus drift. | Gate receipt with clean expected paths, then an unexplained source or corpus diff. | Clean fixture may pass provenance; unexplained diff makes gate `NO-GO` and names paths. | Results can be produced from unaudited code/tasks. | proposed gate/receipt validator | Yes |
| `test_m0_gate_requires_explicit_anthony_authorization` | Passing software tests alone cannot start M0. | Fully passing synthetic gate receipt without, then with, an authorization record. | Missing authorization is `NO-GO`; authenticated explicit authorization is necessary but not sufficient unless all other gates pass. | Repository text or an agent infers execution authority. | proposed gate validator | Yes |
| `test_no_unratified_threshold_change_in_gate_diff` | Numeric scientific policy remains governed. | Baseline configuration/protocol hashes plus a fixture threshold edit. | Unchanged fixture passes this check; edited threshold yields `NO-GO` and exact diff. | Repair implementation silently changes the scientific rule. | proposed gate validator | Yes |

## 8. Red/green sequence for a later authorized implementation

1. Add the proposed tests and prove each “Yes” row fails for its intended reason on the audited baseline.
2. Implement only the minimum static repair.
3. Run the new focused tests until green.
4. Run the complete existing test suite; no regression is accepted.
5. Run no live model while constructing the test fixtures or scorer.
6. Freeze source, corpus, schemas, scorer fixtures, and provenance hashes.
7. Produce the M0 preflight gate receipt and stop for Anthony's authorization.

Changing expected results merely to make the existing implementation pass is not a repair.

## 9. M0 preflight acceptance

The test lane passes only when:

- every test above passes;
- every pre-existing test remains green;
- no test invokes a live model;
- the exact test command, environment, exit status, and source/test hashes appear in the implementation receipt.

RUN 00.5 does not authorize that implementation or any change to the current test files.
