# RUN 00 — Current System Audit

**Inspected commit:** `db668a91e32843c3e53de58325cc17fff4b9c746`  
**Audit branch:** `codex/ck-run-00-audit`  
**Audit date:** 2026-07-26/27 EDT  
**Scope:** read-only architecture and falsification audit; documentation is the only repository output

## Verdict

The static Conditioned Kernel runtime is compact, bounded, and substantially easier to reason about than the surrounding experiment harness. Its compile/validate/repair/accept circuit is real, and accepted model output reaches durable state only through a narrow, allowlisted update path.

The current scientific harness is not ready to support an adaptive layer or a substrate-gain claim. Five blockers dominate:

1. The continuity runner does not qualify or persist Episode A model output, then reconstructs Episode B from the original seed rather than from accepted Episode A state.
2. The continuity treatment packet drops all task-specific facts and all corpus threads, so its three arms are not derived from the same information.
3. Continuity failures can disappear from the denominator, and `--dry` emits apparently valid completed rows and M1/M2 values without marking the artifact dry.
4. The product pipeline and matrix runner bypass the typed inference result that distinguishes timeout, transport error, invalid response, and thinking without a final response.
5. The named C1 headline control is neither byte-budget matched nor instruction-identical, while an unpaired aggregate remains labelled `headline_vs_budget_matched_bare`.

The repository already records that the continuity scorer is void for cross-model inference because substring recall rewards identifier shotgunning (`docs/RE_GROUNDING.md:163-171`, commit `1dfc607`). The current code still calculates and publishes M1/M2 from that scorer.

No adaptive implementation should start until Anthony resolves the plan-of-record conflict and the event-admission issues above. The detailed findings are in [RUN_00_FAILURE_REGISTER.md](RUN_00_FAILURE_REGISTER.md).

## Executable path

| Transition | Owner | Input → output | Control | Explicit failures | Implicit failures / audit result | Tests / artifacts |
|---|---|---|---|---|---|---|
| CLI input | `cli._cmd_ask` (`src/conditioned_kernel/cli.py:141-181`) | prompt + runtime flags → `TurnResult` rendering | deterministic | missing prompt; non-accept exit codes | CLI accepts arbitrary `--max-repair`; no CLI receipt for typed generation status | `tests/test_pipeline_dry.py` covers accept/reject, not CLI error/status rendering |
| State load | `SubstrateState.load` (`state.py:60-74`) | JSON files → in-memory dict/list snapshot | deterministic filesystem read | JSON/file exceptions propagate | no schema/version validation; missing files silently become empty state | indirectly exercised by compile/pipeline tests |
| State projection | `fact_list`, `open_threads` (`state.py:76-93`) | state snapshot → facts/open threads | deterministic | none | `seed_facts` is ignored; threads lacking `status: open` disappear | corpus tests validate corpus shape but do not compile corpus seed state |
| Packet compile | `compile_turn` / `build_arrival_packet` (`compile.py:54-121`, `218-252`) | state + user input + optional repair plan → packet + Ollama payload | deterministic except receipt ids/timestamps; volatile fields stripped from model input | `BudgetError` | insertion order is preserved, not canonicalized; packet hash includes volatile fields; contract fields exceed implemented semantics | `test_compile.py`, `test_edge.py` |
| Edge budget | `enforce_packet_budget` (`edge.py:145-222`) | packet + profile → bounded packet | deterministic | strict oversize raises | trims by fixed order, not provenance/relevance; `_edge.packet_bytes` describes pre-`_edge` bytes; log budget is unused | `test_edge.py` |
| Model invocation — product | `run_turn` → `OllamaClient.generate` (`pipeline.py:113-148`) | model input → raw response dict/string | model-controlled | all operational failures become `OllamaError` / `decision=error` | bypasses `OllamaClient.run`; no `NO_FINAL_RESPONSE`, `INVALID_RESPONSE`, elapsed time, or channel counts | no test exercises typed status through `run_turn` |
| Model invocation — controls | `fair_generate` (`experiments/run_matrix.py:109-130`) | prompt → string | model-controlled | exception | same typed-status bypass as product path | no control-path inference fixture |
| Typed inference boundary | `OllamaClient.run` (`generate.py:115-174`) | response/exception → `InferenceResult` | deterministic classification around model call | typed completed/no-final/timeout/transport/invalid | good implementation, but not used by product or matrix paths | `test_measurement_validity.py:34-243`; qualification and continuity workers use it |
| Raw channel extraction | `extract_text` (`generate.py:176-182`) | response dict → final-response text | deterministic | missing shapes collapse to empty text | never merges thinking into final response (good); callers using `generate` cannot distinguish absent final from true empty | channel-separation tests are strong but scoped to `.run()` |
| Parse | `parse_candidate` (`return_path/parse.py:31-96`) | raw text → candidate dict | deterministic | parse error stored in candidate | missing `next_state` normalizes to `{}`, erasing presence information | `test_parse.py` |
| Schema/semantic validation | `validate_candidate` (`return_path/validate.py:301-457`) | candidate + packet → validation receipt | deterministic closed-set checks | violations list | missing `next_state` and non-list `thread_touch` can be schema-valid; hardcoded heuristic thresholds are outside frozen config | `test_validate.py`; no missing-next-state/thread-touch-type test |
| Decision | `assess` (`return_path/assess.py:10-25`) | receipt + pass index/bound → accept/repair/reject | deterministic | three decisions only | external `max_repair` is not clamped; every first-pass failure is marked repairable | covered indirectly |
| Repair | `build_repair_plan` (`return_path/repair.py:106-163`) | violations + candidate + packet → diagnostic packet fields | deterministic | none | adds concrete new information (good), but can copy goal/evidence samples and needs leak accounting | `test_repair.py` |
| Acceptance / rejection logging | `accept_candidate` (`return_path/accept.py:11-57`) | state + packet + candidate + receipt → outcome/logs | deterministic gate after model | non-accept is logged | field `accepted_at` is populated for rejects; receipt lacks full packet/raw response/config/state hashes | pipeline tests verify receipt existence only |
| Durable state mutation | `apply_state_updates` (`state.py:115-135`) | accepted `next_state` → thread timestamps/counter | deterministic allowlist | unknown touches produce no update | model can propose only `thread_touch`; validator qualifies it first. Fuzzy validator matches can later be silently unapplied by exact writer | `test_repair.py`; no end-to-end mismatch receipt test |
| Matrix scoring | `score_output`, aggregation (`score.py`, `run_matrix.py:384-430`) | rows → aggregates/gains | deterministic | paired path nulls incomplete pairs | legacy unpaired object still named headline; expected probe universe inferred from observed union; duplicate probe ids overwrite | score/measurement tests cover simple unique probe ids only |
| Continuity construction | `episode_a`, `episode_b` (`run_continuity.py:137-236`) | task seed/model output → three arm rows | mixed | worker error dict | Episode A is not accepted/persisted; treatment rebuilt from seed; task facts/threads absent; score uses CK packet/original artifacts for every arm | arm/scorer unit tests use idealized fixtures, not runner-produced packets |
| Continuity aggregation | `run_continuity.main` (`run_continuity.py:305-417`) | arm rows → means/M1/M2/event | deterministic | none fail closed | Episode A failures are skipped; means use completed survivors; `rows_expected=len(rows)`; dry rows are completed; no paired/missingness gate | no runner integration test |

## Actual durable authority path

The model does not have an unrestricted state-write path:

```text
model JSON
  → parse_candidate
  → validate_candidate
  → assess == accept
  → accept_candidate
  → SubstrateState.apply_state_updates
  → exact existing thread id/title timestamp only
```

`proposed_note` remains in the output schema but is intentionally not persisted (`state.py:129-130`). The accepted candidate can increase `receipt_count_24h` and touch an existing thread; it cannot create a thread, change the goal, change flags, or write arbitrary keys. This is one of the strongest existing boundaries and should be preserved.

## Experiment reality

### Matrix

- `bare`, `budget_matched_bare`, and `ck_strict` exist.
- Protocol conditions C2 `prompted_persona`, C4 `ck_ablated_compile`, and C5 `ck_ablated_validation` are declared but unimplemented (`docs/EXPERIMENT_PROTOCOL.md:24-29`; unknown conditions fall through at `run_matrix.py:336-338`).
- C1 is not byte matched. On the current state and probe text, the compiled model packet was 1,310 bytes and `budget_matched_prompt` was 724 bytes.
- The matrix control system text differs from the CK system text (`run_matrix.py:231-237` versus `compile.py:155-162`).
- `headline_paired_vs_budget_matched_bare` is the safer object, but `headline_vs_budget_matched_bare` is still emitted from unpaired condition means and labelled as the headline (`run_matrix.py:384-404`).
- Product and control inference status is reconstructed after the fact from exception strings (`run_matrix.py:343-367`), not taken from `InferenceResult`.

### Continuity

The runner's comments claim Episode A “does work, writes state,” but `episode_a` only generates text and returns it in `episode_a_log`; it never parses, validates, accepts, or applies `expected_state_writes` (`run_continuity.py:137-156`). Episode B calls `seed_state_dir` again and builds a new packet from the original seed (`run_continuity.py:159-171`).

The treatment is additionally starved of the corpus state:

- task facts are stored as `current.seed_facts` (`run_continuity.py:109-117`), but `SubstrateState.fact_list` never reads that field (`state.py:79-93`);
- all 18 corpus thread records lack `status`, while `open_threads` admits only `status == "open"` (`state.py:76-77`), so every compiled treatment packet has `open_threads=[]`;
- the bare arm is built directly from the task's original facts and threads (`continuity.py:38-62`).

The current three arms therefore do not receive the same information under different structure. This invalidates both the continuity treatment and its budget-matched comparison before scorer quality is considered.

The dry reproduction is also scientifically unsafe:

```text
python experiments/run_continuity.py --limit 2 --dry --out /tmp/ck-run00-continuity-dry.json
→ six rows status=completed
→ rows_valid=6, rows_expected=6
→ M1=0.0, M2=0.0
→ no dry marker in report/event
```

### Qualification

The qualification gate is useful preflight plumbing but overstates some checks:

- memory fit is inferred from model file bytes and a 1.5 GB subtraction, not observed board residency/fragmentation (`qualify_models.py:193-217`);
- schema compliance checks only presence of three top-level keys, not types/non-empty values (`qualify_models.py:268-298`);
- raw path “works” for any `COMPLETED` result, including empty output (`qualify_models.py:300-305`). The committed `gemma3:1b` artifact says `8_raw_path_works: true` while its raw output is `""` (`runs/qualification_20260722T220405Z/gemma3_1b.json:12,58-60`);
- determinism can classify repeated null/failure hashes as stable because status is not part of equality (`qualify_models.py:307-359`).

## Documentation/code contradictions

| Claim | Executable reality |
|---|---|
| Continuity Episode A writes and freezes accepted state | no parse, validation, acceptance, or state update occurs |
| Three continuity arms derive from one frozen artifact set | CK arm is rebuilt from seed; task facts/threads are omitted, bare receives them |
| Dry run exercises plumbing only | dry rows are marked completed and included in scientific means/events |
| RunStatus is classified at the Ollama boundary | true in `.run()`, false in product and matrix paths |
| C1 is budget matched and is the headline control | no byte matching; system instructions differ; an unpaired headline remains |
| C0–C5 are defined experiment conditions | C2/C4/C5 have no implementation |
| `max_log_file_bytes` is an edge bound | field is loaded/reported but never enforced |
| Current default should be the smallest qualified practical model | profile/README default remains `qwen2.5:0.5b`; qualification recommends `gemma3:1b` |
| Latest admitted repo plan says “Run M0 next, and only M0” | supplied Adaptive Riverbed run orders say RUN 00 → RUN 01 docs → RUN 02 code before any model work |

## Strongest design choices to preserve

1. **Typed inference outcomes and channel separation.** `InferenceResult` distinguishes completed, no-final-response, timeout, transport error, and invalid response; thinking is telemetry, never an answer.
2. **Two estimands.** Paired quality and budget-conditional utility answer different questions, and missingness bounds/dropout symmetry are explicit.
3. **Narrow durable authority.** Accepted model output reaches only allowlisted existing-thread touches; `proposed_note` is not persisted.
4. **Deterministic, edge-bounded compilation.** Volatile ids/timestamps are stripped from model input; packets, context, seed, temperature, and repair count are profile controlled.
5. **Closed-set validation with adversarial history.** Goal echo, responsiveness, evidence membership/length, fact contradictions, forbidden strings, and thread ids are mechanically checked and regression tested.
6. **Atomic state replacement and append-only evidence.** JSON state uses temp-file replacement/fsync; candidates, receipts, history, and errors are separate JSONL streams.

## Verification performed

- Full offline suite: **85 passed in 2.42s** using Python 3.13 pytest.
- Isolated `ck smoke --dry`: **accepted**, one pass, packet 1,444 bytes; state/log writes were redirected to `/tmp`.
- Isolated continuity dry smoke: **2 tasks × 3 arms**, all boundaries distinct; exposed dry-admission defect above.
- Repository experiment artifacts, correction manifests, qualification rows, recent 12-commit history, all package modules, experiment runners, tests, configs, state templates, and all files under `docs/` were inspected.
- No live Ollama run or scientific model matrix was started.

## Safe preservation boundary before adaptation

Preserve the existing static runtime as an unchanged control, but do not treat current experiment reports as a stable interface. Before RUN 01, freeze and test these boundaries explicitly:

1. typed generation outcome reaches every caller;
2. an expected trial manifest exists independently of observed rows;
3. dry runs are structurally non-admissible;
4. Episode A acceptance and state transition are real and replayable;
5. each arm's exact model-visible bytes are hashed and information-accounted;
6. unknown schema/state/condition values fail closed;
7. no M1/M2/headline field can be emitted when its scorer or coverage gate is void.

