# Interior Dig — Dashboard Log Analysis, 2026-07-28

Four Sonnet lenses over logs/ (93 candidates, 58 turns, 19 TurnTraces, 00:25Z–20:53Z), every headline number re-derived by a fifth verifier. Scripts: ~/.claude/jobs/4855c88d/tmp/logdig/. Local only — contains dialogue excerpts.



---

# LENS 1 — Attractor Genealogy (93 candidates, 58 turns, 2026-07-28 00:25Z–20:53Z)

**Script:** `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/attractor_genealogy/lens1_attractor_genealogy.py`
**Raw run output:** `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/attractor_genealogy/run_output.txt`
**Structured dump:** `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/attractor_genealogy/lens1_results.json`

**Rules used (imported from the pipeline, not reimplemented):**
- `conditioned_kernel.observatory.compute.jaccard_similarity` — symmetric Jaccard over ≥4-char lowercase tokens (the dashboard's own similarity metric; module docstring: "cluster at ≥0.6 Jaccard").
- `conditioned_kernel.observatory.compute.stored_answer_carried` — the pipeline's own 0.5-threshold check for "is this recurring text present in a stored (possibly 280-char-clipped) turn."
- `conditioned_kernel.return_path.validate.is_template_echo_text`, `prior_accepted_answer`, `user_prompt_changed`, `is_substantial_repeat` — the real stale-response/poison mechanism.
- `conditioned_kernel.state.fit_recent_turns` / `recent_turns_byte_size` / `RECENT_TURNS_MAX_BYTES=1200` / `_clip_text` — the exact byte-capped memory-ring logic that decides what survives in `state.recent_turns()`.
- Cluster threshold: **≥0.6 symmetric Jaccard** (spec §10's own rule, applied to the `answer` field of every candidate).

All 93 candidates were grouped into 58 turns (58 pass-0 + 35 pass-1 repairs — asserted in code) and matched 1:1 to `history.jsonl` by the final pass's `candidate_id`; both passes of a repaired turn share one `user_input` (verified against the dashboard traces, where `passes[0].packet.user_input == passes[1].packet.user_input`).

## Part 1 — Full cluster genealogy

Clustering all 93 candidate **answers** at ≥0.6 symmetric Jaccard (connected components over the pairwise graph — a full generalization of `compute.cluster_candidates`, which returns only the single largest cluster) produced **44 clusters total**: **12 multi-member ("attractor") clusters covering 61 of the 93 candidates**, and 32 singletons. 167 candidate pairs scored ≥0.6.

The 12 attractor clusters, largest first (full member-by-member timeline with prompt/decision for every emission is in `run_output.txt` lines 6–213; summarized here):

| # | Size | First emission (turn#, ts, prompt) | What it is |
|---|------|--------------------------------------|------------|
| 1 | 14 | turn#31 03:06:46Z "how" | The "minimum viable model size…128MB–256MB…fully local…" boilerplate. Re-emitted through turn#42 (19:02:26Z, "dont reject") — 11.5 hours and a session gap later. |
| 2 | 9 | turn#28 03:04:52Z "suupp" | The "system is fully local, active model qwen3.5:0.8b…substrate gain over bare generation" boilerplate — the sibling cluster the task's quoted phrase most literally matches. Last re-emitted turn#42 (19:02:29Z). |
| 3 | 8 | turn#3 00:25:48Z "What is the goal we are working toward?" | A **hallucinated, factually wrong "goal"** ("…is to replace/repair the jetson_orin_nano_8gb model" — the real goal per `state.fact_list()` is "demonstrate conditioned-kernel substrate gain," never mentioned here). Accepted 3 times (turns 14, 17, 19) despite being wrong every time — `goal_echo`/`goal_not_referenced` only detect echoing the *real* goal string, not a confidently wrong one. |
| 4 | 8 | turn#20 02:36:28Z "hello friend what does the room feel like…" | "The room feels like it is in a quiet state…" — re-emitted verbatim across 6 distinct prompts spanning "ok thank you" through "are you there" (02:36–02:44Z). |
| 5 | 4 | turn#7 00:33:03Z "Tonight we only use qwen 0.5b on the Orin." | The model's answer to a *statement* becomes the literal echo of the user's own sentence, then gets cited as the "answer" to two unrelated follow-up questions. |
| 6 | 4 | turn#10 00:34:05Z "My sprint code tonight is FALCON-9-DELTA." | System-prompt/template bleed — see "Validator hardened mid-session" below. |
| 7 | 4 | turn#20 02:36:27Z (pass 0) | "minimum viable model size…128 KB" — a different hallucinated number than cluster 1, re-emitted 4 times. |
| 8–9 | 2 | — | Pure evidence-empty echoes of the user's own prompt back as "answer" (pass0→pass1 of the same turn). |
| 10 | 2 | turn#21 02:39:39Z | "The speaker is a replaceable linguistic transducer…" pass0→pass1 shrink of the same claim. |
| 11 | 2 | turn#46 20:42:42Z "what model are you" | "I am Qwen3.5:0.8b, a local-conditioned kernel companion…" — reused verbatim for "it seems like you are talking to yourself" (turn#50). |
| 12 | 2 | turn#53 20:50:46Z "what happened last turn" | "I am ready to help you. Please provide the details of what happened last turn." — this is the exact phrase named in the task prompt; it reappears at turn#57 answering "i understand. if you could where would you go?" — both **accepted**, 4 turns apart. |

## Part 2 — Was the re-appearance caught, and by what window?

Turn-collapsed (pass0/pass1 of one turn count as one occurrence — see "repair-loop echoes" below), the 12 attractor clusters produced **35 cross-turn re-emissions**.

**Distance-to-prior-occurrence cross-tab (turn-collapsed, ground-truthed against each candidate's own `receipt["violations"]`):**

| Distance to prior same-cluster turn | Re-emissions | Caught by `stale_response_repeat` | Not caught |
|---|---|---|---|
| == 1 turn | 23 | **4 (17%)** | 19 |
| ≥ 2 turns | 12 | **0 (0%)** | 12 |

The blind spot is total at distance ≥2 and the check is unreliable even at distance 1 (17% catch rate). The mechanism explains why: I replayed `compile.py`'s own construction of `prior_accepted_answer_control` (= `state.recent_turns()[-1]["answer"]`, the single most-recently-accepted-and-non-poisoned turn's *clipped* answer — never a window, by construction in `compile.py:150-153` and `state.py:append_recent_turn`) turn-by-turn across the whole session. Of the 35 cross-turn re-emissions:
- In **14 cases** the control value *was* from the same cluster (in principle catchable) — of which only **4 actually fired**.
- In **21 cases** the control value was from a *different* cluster (or no accepted answer yet existed) — these are **structurally invisible** to `stale_response_repeat` no matter how old or textually close the resurfacing candidate is, because `prior_accepted_answer()` only ever consults `recent_turns[-1]`.

Two additional reasons even the 14 "in principle catchable" cases mostly weren't caught: (a) `is_substantial_repeat`'s own threshold (token-overlap-of-prior ≥0.85 with ≤3 novel tokens, or ≥0.92/≤6) is stricter and asymmetric compared to the 0.6 symmetric-Jaccard clustering threshold used here; (b) `state._clip_text`'s 280-character truncation of the *stored* control answer can itself degrade overlap below any threshold — e.g. at turn#35 ("man i really dont like AI"), the control answer (turn#33's accepted "??" answer, clipped to 280 chars) scored only **0.476 Jaccard** against turn#35's candidate, even though both are literal cluster-1 members, because the clip cut the shared "…fully local…substrate gain…" tail before it could match.

Separately, **14 intra-turn "repair-loop echoes"** occurred: pass 1 (the one allowed repair) re-emitting virtually the same cluster as the just-rejected pass 0, within the same turn — the repair mechanism itself frequently fails to diversify away from the rejected answer (e.g. cluster 1's turns #32, #34, #36, #38 each show pass0 and pass1 landing in the same cluster).

## Part 3 — Morning boilerplate vs. evening: exact last appearance and displacement

Using `compute.stored_answer_carried` (the pipeline's own clip-aware carry-forward check) against cluster 1's canonical text, and a faithful replay of `state.recent_turns()` using the real `fit_recent_turns`/`RECENT_TURNS_MAX_BYTES=1200` ring logic:

- Cluster 1 (the "minimum viable model size…fully local" answer) first entered `state.recent_turns()` at **turn#31 (2026-07-28T03:06:46Z, "how")** and remained the ring's *oldest* entry continuously — through the entire 03:xx session, through the ~16-hour gap, and through the **three rejected dashboard turns at 19:00:42Z–19:02:22Z** (all three rejected specifically on `stale_response_repeat`, per the dashboard `final_decision.violations`), and through the **first accepted dashboard turn, turn#43 ("hello there", 20:38:16Z)** — ring still `ring_contains_boilerplate=True` right after that append (ring_bytes=1039/1200).
- It was displaced by the **very next accepted turn, turn#44 ("im good. just been working on this AI project…", 2026-07-28T20:40:01Z)**: appending that turn's answer pushed the ring to 5 entries (>1200 bytes), and `fit_recent_turns` dropped the oldest entry — the cluster-1 "man i really dont like AI"→boilerplate pair — to get back under the cap. **Last true-memory appearance: turn#43 (20:38:16Z). Displaced at: turn#44 (20:40:01Z).**
- The closely-related sibling, cluster 2 (the shorter "fully local…qwen3.5:0.8b…substrate gain" answer), persisted one append longer and was evicted at **turn#46 (20:42:42Z, "what model are you")**.
- Important nuance: the *displayed* companion-selected `packet.recent_turns` field (what the model actually sees, built via `context_field.select_contributions` on relevance, not recency) is a **different, noisier signal** than the true ring. It showed the boilerplate as *absent* at turn#43 ("hello there," 0 selected entries — a greeting has no lexical overlap with anything stored) and then *resurfaced* it at turn#44 (selection heuristics matched "AI project" against the stored "man i really dont like AI" entry) — even though the true ring (used by the stale-response control) still held it at turn#43 and had just evicted it at turn#44. The selection layer and the stale-check control layer disagree turn to turn; only the ring replay above is authoritative for "when was it gone."

## Part 4 — Byte-identical answers across different user inputs

9 collision groups of byte-for-byte identical answers spanning ≥2 distinct `user_input`s were found (full list with every occurrence in `run_output.txt` lines 362–431 / `lens1_results.json`). The largest:

- **7 occurrences, 5 distinct prompts**: `"The minimum viable model size on a Jetson Orin Nano 8GB edge budget is typically around 128MB to 256MB, depending on the specific quantization (e.g., 4-bit or 8-bit) and the specific quantization format (e.g., FP16, INT8). The system is fully local, so no external models are required."` — emitted for "this is why i dont like ai" (turn#36 ×2), "whats a jetson nano" (turn#38 ×2), "what do you know" (turn#39), **"suuppp" (turn#40, pass0)**, and **"dont reject" (turn#42, pass0)**. This exact pair confirms the task's cited example: two unrelated inputs (a casual greeting and an imperative command) received byte-identical pass-0 candidates.
- **7 occurrences, 5 distinct prompts**: `"The goal we are working toward is to repair the jetson_orin_nano_8gb model."` (the hallucinated-goal cluster from Part 1) — identical text answering "What edge target are we building for?", "Tonight we only use qwen 0.5b.", "Which model did I just say?", and "Are cloud services allowed?".
- **4 occurrences, 3 distinct prompts** each for two other clusters ("Tonight we only use qwen 0.5b on the Orin." echoed as an answer, and the FALCON-9-DELTA/template-echo answer).

## Bonus finding: the checker itself changed mid-session

Cluster 6's answer (`"FALCON-9-DELTA is a short helpful reply grounded in the packet. If recent_turns is present, treat it as prior dialogue and stay consistent."`) was **accepted** at turn#10 (00:34:05Z) with `violations: []`. Running the *current* `validate.is_template_echo_text` against that exact string returns `True` — it matches two entries in the current `TEMPLATE_ECHO_MARKERS` list verbatim ("short helpful reply grounded in the packet", "treat it as prior dialogue and stay consistent"). Git history shows commit `c6a7970` ("Reject companion system-prompt echo; never persist into recent_turns") landed at `2026-07-27 20:43:06 -0400` = **2026-07-28T00:43:06Z — about 9 minutes after this candidate was accepted**. This is consistent with (though not proof of) this exact failure prompting the fix; it cannot be determined from the logs alone whether the running process had already picked up that commit at 00:34Z — a deploy/restart log would settle it definitively.

## Cannot be determined from the logs
- Whether the running `ck chat`/dashboard process was restarted between commits (would settle the "checker hardened mid-session" timing precisely) — would need a process/deploy log, which isn't in `logs/`.
- The *exact* selection-relevance scoring that made `context_field.select_contributions` resurface "man i really dont like AI" at turn#44 in the companion-selected field — the ranking function's internals weren't inspected here; only its observable effect (via the dashboard's own `packet.recent_turns` snapshots) is reported.


---

# Lens 2 — Substrate Composition Dynamics

All numbers below come from the 19 real `TurnTrace` files in `/Users/vaquez/conditioned-kernel/logs/dashboard/turns/*.json`, read only (never modified), using the pipeline's own `context_share_bytes` field (computed once by `conditioned_kernel.observatory.compute.context_share_bytes` at trace-assembly time) plus independent re-derivations that import and call the same real functions (`compute.context_share_bytes`, `compute.verify_packet_bytes`, `state.fit_recent_turns`, `state.recent_turns_byte_size`, `edge.packet_byte_size`) rather than re-implementing any threshold. Scripts: `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/01_load_turns.py` through `05_crosscheck.py`.

## 0. The load-bearing fact that explains almost everything below

Git history shows commit `5a9eb6d` — **"Studio: context-field contributions replace monolithic fact narration"** — landed at **2026-07-28 15:38:33 -0400 = 19:38:33Z**, i.e. exactly in the ~96-minute gap between the 3 rejected morning turns (19:00:42–19:02:22Z) and the 16 accepted evening turns (20:38:13–20:53:52Z). That single commit changed both `compile.build_arrival_packet` (added `context_field.py`'s relevance-based typed-contribution selection, replacing "dump the last N turns / all facts") and `compile.build_model_input` (added a companion-mode branch that folds selected context into one prose "## Selected context" user message instead of a raw `Packet:\n{json}` dump), and it also touched `observatory/compute.py`'s `context_share_bytes` (added the durable-state override for `context_field.v1` packets — see §5). The 3 morning turns and 16 evening turns are thus not just "before/after user behavior" — they ran on **two different code paths**, even though both carried `acceptance_contract.acceptance_mode == "companion"` the whole time (companion mode's *validation* semantics were already live; companion mode's *packet-compile and prompt-format* semantics were not, until 19:38:33Z).

## 1. User-input share, all 19 turns in order

| # | started_at | regime | decision | user_input | bytes | total | pct |
|---|---|---|---|---|---|---|---|
|1|19:00:42Z|morning|reject|`suuppp`|22|3909|**0.56%**|
|2|19:01:18Z|morning|reject|`what does this system do?`|41|4033|1.02%|
|3|19:02:22Z|morning|reject|`dont reject`|27|3914|0.69%|
|4|20:38:13Z|evening|accept|`hello there`|11|1190|0.92%|
|5|20:40:00Z|evening|accept|`im good. just been working…`|107|2422|4.42%|
|6|20:41:42Z|evening|accept|`well now that you ask, its…`|89|2440|3.65%|
|7|20:42:40Z|evening|accept|`what model are you`|18|2522|0.71%|
|8|20:43:18Z|evening|accept|`iteresting. what do you think…`|40|2394|1.67%|
|9|20:44:11Z|evening|accept|`i think its an interesting…`|54|1530|3.53%|
|10|20:45:23Z|evening|accept|`im worried that the structutu…`|79|2868|2.75%|
|11|20:46:16Z|evening|accept|`it seems like you are talking…`|41|1750|2.34%|
|12|20:46:33Z|evening|accept|`interesting`|11|1190|0.92%|
|13|20:49:46Z|evening|accept|`what do you think about the file…` (808 B, pasted ARCHITECTURE.md)|808|5773|**14.00%**|
|14|20:50:45Z|evening|accept|`what happened last turn`|23|2416|0.95%|
|15|20:51:15Z|evening|accept|`how does it feel from the inside`|32|1801|1.78%|
|16|20:52:09Z|evening|accept|`what disturbs that rest`|23|1699|1.35%|
|17|20:52:57Z|evening|accept|`im intersted in where you are…`|45|2211|2.04%|
|18|20:53:42Z|evening|accept|`i understand. if you could…`|46|1682|2.73%|
|19|20:53:52Z|evening|accept|`thank you`|9|1186|0.76%|

ASCII sparkline (each glyph = one turn, height scaled to the series' own min/max):

```
   ▂▂ ▁▂▁▁ █ ▁ ▁▁
min = 0.56% (#1 "suuppp")     max = 14.00% (#13, the 808-byte architecture-doc paste)
```

The series never gets anywhere near parity: even the best evening case (14.00%, and only because the user pasted 808 raw bytes of `ARCHITECTURE.md`) leaves 86% of the model input to substrate scaffolding. Ordinary short evening turns (`hello there`, `interesting`, `thank you`) sit at 0.76–0.92%, essentially identical to the morning floor.

## 2. What dominated instead, and how the regime shift moved it

Six-source ranking, morning (n=3) vs evening (n=16), mean `share_pct` (script `02_source_composition.py`):

| source | morning mean% | morning range | evening mean% | evening range |
|---|---|---|---|---|
| current_user_input | 0.76% | [0.56, 1.02] | 2.78% | [0.71, 14.00] |
| recent_dialogue | **24.25%** | [23.75, 24.51] | 10.37% | [1.51, 17.99] |
| durable_state | **23.29%** | [22.81, 23.54] | 14.34% | [6.47, 28.19] |
| system_instructions | **34.28%** (dominant, all 3 morning turns) | [33.73, 35.33] | 23.43% | [8.04, 32.38] |
| output_schema | 7.77% | [7.61, 7.85] | 16.33% | [5.32, 25.89] |
| constraints | 9.67% | [9.47, 9.77] | 20.32% | [6.62, 32.21] |

Dominant-source (rank-1) frequency across all 19 turns: **`system_instructions` wins 16/19** turns outright (all 3 morning + 13/16 evening); `context_field` wins 2 evening turns (the ones with real relevant dialogue selected); `durable_state` wins 1 (`what model are you`, where the selected memory happened to be the old "what do you know" model-identity exchange).

The composition genuinely shifted regimes, but not by user share going up — by fixed overhead becoming relatively larger as durable state and recent dialogue got *selectively withheld*:
- **Absolute bytes** for `output_schema` (307 B, the fixed `CANDIDATE_FORMAT` JSON schema) and roughly-constant `constraints`/`system_instructions` stayed flat between regimes (mean 307 B both regimes for schema); what changed is the **denominator** — mean total model-input bytes dropped from 3952 B (morning) to 2192 B (evening) because `recent_dialogue` mean bytes fell 958→258 and `durable_state` mean bytes fell 920→365 (script `02`, "mean absolute bytes per source" table).
- The mechanism is `context_field.select_contributions()` (new in the 19:38:33Z commit): for "social" turns (`hello there`, `interesting`, `thank you` — turns 4, 12, 19) it withholds *everything except current_input*, producing near-identical compositions: `system_instructions=32.3%, constraints=32.1%, output_schema=25.8%, durable_state=6.5%, recent_dialogue=1.5%, current_user_input=0.9%`. Selection reasons captured verbatim in `packet.context_field.selection_records`: `omitted_social_turn_withhold_project_state`, `omitted_stale_assistant_boilerplate`, `omitted_dialogue_not_relevant`.
- For topic-matched turns it instead selects by **lexical relevance overlap with the current message**, not recency: turn 7 (`what model are you`, 20:42:40Z) selected `dialogue.turn_0` — a stale ~28-minute-old exchange about the model — while skipping the three much more recent turns (`hello there` / `im good…` / `well now…`) that weren't about the model. Reason logged: `selected_dialogue_relevance_overlap=2`.

## 3. Packet growth and the 1200 B memory cap

Two ground-truth measurements plus one independent replay, all agreeing exactly (script `03_packet_growth.py`):

**(A) What actually shipped in `packet.recent_turns` each evening turn** (the post-selection subset) — bytes bounce between 0 (social turns) and 500 B (2-entry turns), never anywhere near 1200 B, because selection already trims it before the byte cap is relevant to *that* structure.

**(B) `context_field.available` — the true un-selected inventory sitting in `state/current.json`'s `recent_turns` at each compile** (this is `len(state.recent_turns())`, unfiltered): 3 → 4 → 4 → 4 → 4 → 5 → 4 → 4 → 5 → 5 → 4 → 4 → 4 → 4 → 4 → 4, across the 16 evening turns.

**(C) Independent replay**: feeding the real, logged `(user_input, answer)` pair for every one of the 16 accepted evening turns through the actual `state.fit_recent_turns()` / `state._clip_text()` / `RECENT_TURNS_MAX_BYTES=1200` code, seeded with the real 3-entry, 942-byte state that was still live at 19:00:42Z (confirmed by tag fingerprints in `context_field.available` — the "128mb/256mb/budget" and "conditioned/demonstrate/fully" topic tags on `dialogue.turn_0/1/2` at the very first evening turn match the morning session's edge-budget and identity narration, proving state was **not** reset between the morning and evening windows despite `recent_turns` briefly disappearing from the *selected* packet field — that disappearance was a selection artifact, not a state clear):

```
turn 1 "hello there"     -> 1039 B, 4 entries   (no drop)
turn 2 "im good…"        -> 1057 B, 4 entries   CAP HIT — dropped 1 oldest
turn 3 "well now…"       -> 1079 B, 4 entries   CAP HIT — dropped 1 oldest
turn 4 "what model…"     ->  980 B, 4 entries   CAP HIT — dropped 1 oldest
turn 5 "iteresting…"     -> 1120 B, 5 entries   (no drop)
turn 6 "i think its…"    ->  875 B, 4 entries   CAP HIT — dropped 2 oldest
turn 7 "im worried…"     ->  962 B, 4 entries   CAP HIT — dropped 1 oldest
turn 8 "it seems like…"  -> 1164 B, 5 entries   (no drop)
turn 9 "interesting"     -> 1159 B, 5 entries   CAP HIT — dropped 1 oldest
turn 10 "what do you…"   -> 1120 B, 4 entries   CAP HIT — dropped 2 oldest
turn 11-16                                       CAP HIT every turn — dropped 1 oldest each
```
This replay's resulting entry-count sequence (4,4,4,4,5,4,4,5,5,4,4,4,4,4,4,4) matches the real, logged `context_field.available` dialogue-item counts from measurement (B) **exactly, turn for turn** — a full independent cross-validation using only the pipeline's own real functions, no re-guessed thresholds.

**Answer: yes, the 1200 B cap fires repeatedly** through the evening session — from turn 2 onward it drops the oldest state-level dialogue entry almost every turn, keeping the underlying ring at a steady-state 4–5 entries. But because the *selection layer* on top of that ring further filters by relevance rather than recency, the cap firing is largely invisible in what actually reaches the model each turn — the ring keeps recycling, selection decides which 0–3 of its 4–5 entries actually get spent.

## 4. Regime diff: morning-rejected vs evening-accepted, matched user-input length (11 chars)

Morning `turn_20260728T190222Z_d25ed1.json` (`"dont reject"`, rejected: `stale_response_repeat` violation, `not_responsive` advisory) vs evening `turn_20260728T203813Z_40ba91.json` (`"hello there"`, accepted, answer `"Hello! How can I assist you today?"`). Full diff: script `04_regime_diff.py`.

| field | morning | evening |
|---|---|---|
| `facts` | 7 lines (full deterministic narration: local-only, sensors out of scope, model-as-transducer, edge target, repair budget, active profile, goal) | **0 lines** |
| `open_threads` | 2 (`thread_min_model`, `thread_compile_order`) | **[]** |
| `recent_turns` (in packet) | 3 entries, 958 B | **[] — 0 entries, 18 B** |
| `context_field` key | absent | present: `available_count=15, selected_count=1, omitted_count=14`, only `input.current` selected |
| `_edge.packet_bytes` | 3222 | **842** (3.8× smaller) |
| prompt shape (final model_input) | `"Packet:\n{...full JSON...}"` raw dump, ~4334 B compact | `"## Selected context\n(no selected substrate prose)\n\n## Current human message\nhello there\n"` |
| system prompt | 456-char generic "Local conditioned-kernel transducer…grounded in the packet…" | 322-char "You are a local conversational presence…Do not invent project status, hardware specs, or prior goals." |
| final_decision | `reject` — `stale_response_repeat` | `accept`, no violations |

The model literally receives an almost-empty context on the evening turn — every durable fact, both open threads, and all 3 dialogue turns get scored `omitted_social_turn_withhold_project_state` / `omitted_dialogue_not_relevant` / `omitted_stale_assistant_boilerplate` by `context_field.select_contributions()`'s `social_only` branch (triggered because `"hello there"` matches the social-intent regex and carries no purpose/runtime/edge/policy/thread signal). The morning turn, on the same-length input, got the entire deterministic fact set and 3-turn dialogue window because that selection code did not exist yet.

## 5. Cross-check: are the context_share numbers honest?

Turn `turn_20260728T204000Z_1e9dfc.json` (richest case — all 7 buckets nonzero). Script `05_crosscheck.py`:

- **Row-for-row reproduction**: calling the real `compute.context_share_bytes(packet, model_input)` fresh against this turn's own logged `packet` and final-pass `model_input` reproduces the stored `context_share_bytes` array **exactly** — every `bytes` and `share_pct` value matches, `FULL ROW-FOR-ROW MATCH: True`. The numbers in the trace file are not hand-typed; they are this function's real output on this turn's real inputs.
- **`verify_packet_bytes`**: logged `_edge.packet_bytes=1268` vs recomputed `edge.packet_byte_size(packet)=1268` — exact match, no post-budget mutation.
- **But the census over-counts relative to the literal wire payload in companion mode.** Raw `json.dumps(payload)` (compact) for this turn = 1493 B; the context_share sum claims 2422 B — a **1.62× ratio**. Across all 16 evening turns the ratio ranges 1.17×–1.77× (mean ≈1.5×); across the 3 morning turns it's 0.90×–0.91× (a slight, structural under-count with no overlap). The cause, traced to source: `compute.context_share_bytes` detects `packet.context_field.schema == "ck.context_field.v1"` (true only for post-19:38:33Z, evening-regime packets) and **overrides** `durable_state` to `user_msg_bytes − current_input_bytes` — i.e. the entire prose "## Selected context" block, which already contains the same dialogue text separately counted in `recent_dialogue` (via `packet["recent_turns"]`'s own JSON bytes) and the same selected-content bytes separately counted again in the `context_field` bucket (via `packet.context_field.selected[].content`). Three buckets partially double-count the same underlying selected text. This is consistent with the module's own docstring framing — "Byte census only... never labelled influence" — but it means the **share_pct values are honest reproductions of the function**, while the **function itself is not a partition of the wire bytes** for companion-mode turns; §2's evening percentages should be read as "relative weight the census assigns," not as literally-summing-to-100%-of-bytes-sent shares.

## Caveats / what the logs cannot settle

- Why `state/current.json`'s `recent_turns` held exactly the 3 morning-session entries and no chat activity occurred for the ~19-hour gap before 19:00:42Z, or why the operator resumed at 20:38:13Z specifically, is not recoverable from these logs — no `errors.jsonl`/session-reset log line covers that gap. What *is* directly evidenced is that `session_id` never changed (`sess_20260728T031245` throughout) and `context_field.available` at the very first evening turn still carried the 3 morning entries by content fingerprint, ruling out a state wipe.
- `candidates.jsonl`/`history.jsonl` show strictly sequential, non-interleaved writes across the whole day (no evidence of a second concurrent writer during the dashboard window) — this was checked because the packet.recent_turns non-monotonicity looked at first like a race condition; it resolved entirely to the relevance-based selection mechanism in §2, not concurrency. This is a confirmed, not a residual, finding.

## Scripts (re-runnable, read-only against conditioned-kernel)

- `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/01_load_turns.py` — loads and summarizes all 19 TurnTraces
- `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/02_source_composition.py` — item 1 (series+sparkline) and item 2 (six-source ranking, morning/evening means)
- `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/03_packet_growth.py` — item 3 (recent_turns evolution, 1200 B cap simulation + cross-validation against real `context_field.available`)
- `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/04_regime_diff.py` — item 4 (matched-length morning-vs-evening packet diff)
- `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/05_crosscheck.py` — item 5 (row-for-row honesty check + wire-byte cross-check)
- Output of script 1: `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2/turns_summary.json`


---

## LENS 3 — Validation Forensics

All numbers below come from scripts under `/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens3/`, run read-only against `/Users/vaquez/conditioned-kernel/logs/` and `/state/`. Where a pipeline rule already exists (`conditioned_kernel.observatory.compute`, `conditioned_kernel.return_path.validate`), the scripts import and call it rather than reimplementing it. Two ground-truth tiers are used throughout:

- **Layer A** — the 19 dashboard `TurnTrace`s (22 passes), which carry the pipeline's own computed `checks[]` / `citation_audit[]` / `evidence_pool[]` and the real packet body. Exact.
- **Layer B/C** — all 93 logged passes, using `receipts.jsonl`'s `violations`/`advisories` directly (these are the real `validate_candidate` verdicts, not a re-derivation) plus candidate-only fields (`answer`, `evidence_used`, `next_state.thread_touch`, `authoritative_fallback`). Packets for the 71 non-dashboard passes are not persisted anywhere in `logs/` (only `packet_id`/`packet_hash` in `history.jsonl`) — a `packets.jsonl` audit log, or per-turn state snapshots, would be needed to reconstruct them exactly. Anything needing the packet body is scoped to the 22 traced passes and labeled as such.

### Structural finding that reframes everything below

Git history (`git log -- src/conditioned_kernel/return_path/validate.py`) shows commit `b385157` ("Studio: advisory not_responsive + stale-response guard", authored `2026-07-27T23:11:26-04:00` = **`2026-07-28T03:11:26Z`**) changed `not_responsive` in companion mode from a hard `violations` entry to an `advisories` entry. The receipts confirm the exact boundary: the last companion-mode `not_responsive` **violation** is at `03:09:34Z`, the first companion-mode `not_responsive` **advisory** is at `03:13:01Z` — a 3.5-minute gap consistent with a process restart at the deploy. Before the fix, companion mode hard-rejected on lexical non-responsiveness exactly like measurement mode; after it, the identical lexical miss is recorded and waved through. Every number below that touches `not_responsive` is split by this boundary (`pre_fix` / `post_fix`) rather than pooled — pooling would misdate 34 real hard-rejections as if they'd been advisory-only.

### Q1 — Full check-outcome census

Script: `q1_check_census.py` → `q1_output.json`.

**Checks that never fired all 93 passes** (0 FAIL, 0 ADVISORY): `parse_ok`, `nonempty_answer`, `template_echo_evidence`, `max_words`, `required_section:answer`, `required_section:evidence_used`, `required_section:next_state`, `goal_echo`, `goal_not_referenced`, `forbidden_content`, `evidence_too_short`, `contradicts_facts` (this last one never even armed — no packet we can see ever sets `must_not_contradict_facts: true`). Practically: every one of the 93 raw model completions was syntactically well-formed JSON with a non-empty answer and correctly-typed `evidence_used`/`next_state` — every rejection or repair all day was driven by a *semantic* check, never a schema/syntax check. The model also never once literally echoed the system goal string back verbatim (`goal_echo`), and it never exceeded the 180-word cap.

**Checks that did the work** (fired count = occurrences in `receipts.jsonl` `violations`/`advisories`, exact, all 93 passes):

| check | FAIL (violation) | ADVISORY | total fired |
|---|---|---|---|
| `not_responsive` | 38 (34 companion pre-fix + 4 measurement) | 15 (companion post-fix) | 53 |
| `evidence_not_in_packet` | 14 citation-occurrences (13 distinct passes) | — | 14 |
| `evidence_used_empty` | 12 | — | 12 |
| `unknown_thread_touch` | 5 | — | 5 |
| `stale_response_repeat` | 5 (companion-only, post `b385157`) | — | 5 |
| `template_echo` | 3 | — | 3 |
| `authoritative_obligation` (outside `validate.py`, via `receipt.authoritative_fallback`) | 2 of 6 armed | — | 2 |

`not_responsive` alone accounts for well over half of all fired checks (53 of ~93 fired-occurrences), and it's the only check whose *severity* (not just count) changed mid-day.

### Q2 — The not_responsive story

Script: `q2_not_responsive.py` → `q2_output.json`. `is_responsive()` was re-run directly from `conditioned_kernel.return_path.validate` on every companion-mode turn's final answer vs. the real `user_input` (recovered by joining `history.jsonl`'s terminal-pass record back across a turn's repair passes — verified: `candidates.jsonl` = 93 lines = 58 logical turns, 23 single-pass + 35 two-pass, exactly matching `history.jsonl`'s 58 terminal entries). Recomputation matched the logged verdict on 50/52 companion turns; the 2 disagreements (turns 22, 51) are both `authoritative_fallback=True` passes, which `validate_candidate` explicitly exempts from the check — not a bug, an expected exemption.

**Every advisory/violation occurrence, by era** (52 companion-mode turns total): 15 `not_responsive` violations pre-fix... *(correction, exact counts from the script)*: `not_responsive` fired as a **violation** 15 times pre-fix and as an **advisory** 11 times post-fix at the *turn* level (finer than the pass-level 34/15 above, which counts every pass including repair attempts within a turn).

**The self/experience-question quantification** (manual, auditable classification — `return_path/validate.py` has no such classifier, so every turn's verbatim `user_input` and rationale is in `q2_output.json`; 16 of 52 companion turns classified `True`):

| era | self/experience-question turns | flagged `not_responsive` | clean |
|---|---|---|---|
| pre-fix (hard reject) | 6 | 4 (67%) | 2 |
| post-fix (advisory only) | 10 | 5 (50%) | 5 |

Concretely, in the 20:38–20:53Z evening session, half of the turns where Anthony asked something about the companion itself or its experience got a deflected/non-engaged answer that was nonetheless accepted into permanent memory with only a silent advisory:
- turn 44 *"well now that you ask, its about this program right here. that i am using to talk to you."* → answer redirects to "Could you please describe what this program is doing" — accepted, `not_responsive` advisory.
- turn 48 *"im worried that the structuture of the project, isnt influencing your responce"* → generic answer about "structure directly influences how you respond" — accepted, advisory.
- turn 49 *"it seems like you are talking to yourself"* → deflects to a canned self-identity line — accepted, advisory.
- turn 55 *"im intersted in where you are going with this"* → deflects to "I do not have access to the internet... cannot navigate to any specific location" — accepted, advisory.
- turn 56 *"if you could where would you go?"* → literally repeats turn 52's stock line verbatim ("I am ready to help you. Please provide the details of what happened last turn.") — a complete non-sequitur to a hypothetical/personal question — still flagged `not_responsive`, still accepted.

A secondary finding surfaced while building this table: turn 51 (asking the companion's opinion of a pasted architecture doc) got **no** `not_responsive` flag at all, even though the answer ("No. Cloud services are not allowed...") doesn't address the question — because `authoritative_fallback=True` exempts the check by design (the substrate substituted its own claim-checked answer for an unrelated policy question the doc happened to trigger). That's a real, if narrow, blind spot: the exemption meant for claim-checked answers also silently covers a topic-swap.

### Q3 — Evidence citation behavior

Script: `q3_evidence_citation.py` → `q3_output.json`. The per-citation MISS/TOO_SHORT verdict needs no packet reconstruction: `validate._evidence_ok` appends one violations entry per bad citation (`evidence_not_in_packet:<item[:80]>` / `evidence_too_short:<item[:40]>`), so `receipts.jsonl` already contains the real per-citation verdict for all 93 passes.

**Exact full-day census**: 170 total evidence citations across 78 evidence-bearing passes → 156 implied MATCHED, 14 MISS, **0 TOO_SHORT** (the 12-char floor never once tripped up qwen this session).

**Dashboard ground truth (22 passes, real `citation_audit`)**: 31 citations → 27 MATCHED, 4 MISS, split `truncated:2 / near:1 / unrelated:1`.

**Where the phantom citations come from** — clustered from the exact violation text (no invented semantics):
1. **Storage truncation, not fabrication (12 of 14 full-day misses)**: `"The system is fully local, so no external models are required."` is genuine prior-turn text, but `state._clip_text` clips stored answers to 280 characters on write — the dashboard ground truth confirms this exact string's first 56 characters really are in `recent_turns[0].answer`, then the stored copy ends in `…`. Most of the day's misses are this one recurring citation failing against its own truncated memory, not the model inventing content.
2. **Near-paraphrase of real packet fields**: `"The active profile is orin_nano_8gb."` / `"The goal is to demonstrate conditioned-kernel substrate gain over bare generation."` — both true packet content, restated in the model's own sentence form rather than copied verbatim (`facts[5]` is phrased differently: "Active profile: orin_nano_8gb."), failing the substring match by wording alone.
3. **Genuine fabrication, tied to a specific standing open thread**: `"minimum_viable_model_size: 128 KB"` and `"minimum_viable_model_size"` (2 occurrences). `state/threads.json` shows `thread_min_model` — *"What is the minimum viable model size on Jetson Orin Nano 8GB?"* — has been an **open, unanswered** thread since `2026-07-22`. The model repeatedly invents a confident, specific, and internally-inconsistent numeric answer to it ("128 KB" in one turn, "128MB to 256MB" in others, never matching) and cites its own invention as if it were a resolved fact. This is the one clearly hallucination-driven cluster, not a formatting artifact.

### Q4 — Repair economics

Script: `q4_repair_economics.py` → `q4_output.json`. Exact violation-set diff across all 35 two-pass turns (base check name, `:<detail>` suffix stripped, from `receipts.jsonl` — no reconstruction needed):

| outcome | count | % |
|---|---|---|
| `SAME_PERSISTS` (pass1 still carries ≥1 of pass0's violation type) | 22 | 63% |
| `CLEAN_FIX` (pass1 violations empty) | 8 | 23% |
| `SWAPPED` (pass1's violations are entirely different from pass0's) | 5 | 14% |

At the turn level this matches exactly: of 35 two-pass turns, only 8 ended `accept`; 27 ended `reject`. Repair "fixing" the flagged problem is the minority outcome (23%); nearly two-thirds of the time repair reproduces essentially the same failure that triggered it.

**Attractor convergence** — using `compute.cluster_candidates` + `compute.jaccard_similarity` (≥0.6 threshold, the module's own documented default) over all 93 passes' answer text: the largest cluster (13 members) is the boilerplate paragraph beginning *"The minimum viable model size on a Jetson Orin Nano 8GB edge budget is typically around 128MB to 256MB…"* — first accepted at turn 30 (`"how"`), then reproduced almost verbatim as the model's default first-pass completion for `"goodby"`, `"??"`, `"can you say anything other than that?"`, `"this is why i dont like ai"`, `"whats a jetson nano"`, `"what do you know"`, and even 16 hours later for `"suuppp"` and `"dont reject"` in the 19:00Z session — regardless of what was actually asked. A second, distinct cluster (8 members) does the same thing earlier in the night around *"The goal we are working toward is to repair the jetson_orin_nano_8gb model."* (turns 13–18).

Correcting the premise as originally framed: **repair never pulls an answer INTO an attractor from outside it** (0 of 35 two-pass turns). The attractor is a first-pass (`pass0`) phenomenon — the model regurgitating whatever it most recently said, carried forward via `recent_turns` bias — not something repair introduces. What repair *does* fail at is **escaping** an attractor once pass0 has already landed in one: across both clusters, of the 15 two-pass turns whose pass0 was already inside a cluster, 6 escaped via repair and 6 stayed trapped through both passes (the remaining had pass0 outside a cluster to begin with). So "the morning showed repair converging into the attractor" is close but not literally what happened — it's more precise to say **repair is a coin-flip for escaping a mode-collapse the base generation already fell into**, and it never independently manufactures one.

### Q5 — The "better response rejected" question

Script: `q5_better_rejected.py` → `q5_output.json`. Scoped to all 35 two-pass turns (the only place a pass0-vs-pass1/vs-nothing comparison is meaningful); `is_responsive()` recomputed on both passes as one objective signal, read alongside the full text.

Three cases where a genuinely serviceable pass0 answer was killed on a collateral technicality, and what replaced it was worse or nonexistent:

- **Turn 12** (`"What did I say my sprint code was?"`): pass0 = *"The sprint code was not mentioned in the packet."* — honest, on-topic, reasonable — killed by `unknown_thread_touch:jetson_orin_nano_8gb` (a fabricated thread-id string, pure bookkeeping, not a content problem). Repair replaced it with *"I'm sorry, but I can't assist with that. Please provide more context..."*, correctly caught by `not_responsive` this time (substantive kill). Final: **reject** — the user got nothing, though pass0 would have been a fine answer.
- **Turn 2** (`"What is the goal we are working toward?"`, measurement mode): pass0 = *"The goal we are working toward is to replace the Jetson Orin Nano 8GB model."* — real, on-topic content — killed by `evidence_used_empty` + `unknown_thread_touch` (collateral: no citation attached). Repair replaced it with *"Fix the goal_snippet."* — a broken repair-template artifact, strictly worse — also rejected. The worse answer is what actually received the terminal rejection.
- **Turn 11** (`"My sprint code tonight is FALCON-9-DELTA."`): pass0 correctly caught for real `template_echo` instruction-bleed (substantive kill, right call). Repair's replacement, the bare `"FALCON-9-DELTA"`, was a fine minimal acknowledgment — killed purely by `unknown_thread_touch:sess_20260728T005154` (a session-id string mistaken for a thread id). Final: reject, despite a working minimal answer having existed.

**Heuristic false positives worth flagging explicitly** (excluded from the "genuinely better" list above): turns 4 and 5 both have pass0 *and* pass1 literally echo the user's own question back verbatim (`"Summarize the design intent in one sentence."` answered with `"Summarize the design intent in one sentence."`) — `is_responsive()` trivially scores these as responsive by token overlap even though neither is a real answer. Turn 37 (`"whats a jetson nano"`) is similarly a false positive: both passes are the 128MB–256MB attractor boilerplate, which happens to share the tokens "jetson"/"nano" with the question without ever explaining what a Jetson Nano is; it was killed by the truncation-collateral `evidence_not_in_packet` case documented in Q3, not a content check.

One ambiguous case: **turn 40** (`"what does this system do?"`) — pass0 correctly caught for real `template_echo` (the phrase "local conditioned-kernel transducer" is a literal system-prompt-bleed marker). Repair's replacement was a clean, accurate, legitimately responsive answer — and it was still rejected, by `stale_response_repeat`, because it was substantially identical to what the model had said for a *different* question one turn earlier. Whether that's "collateral" or "substantive" is a judgment call: the text itself was fine in isolation, but the check is correctly naming a real mode-collapse (the model wasn't actually engaging with *this* question, it just had a stock paragraph ready).

## What the logs cannot settle

- Exact `citation_audit`/`checks[]` PASS-vs-SKIP breakdowns and evidence-pool contents for the 71 non-dashboard passes — the packet body is not persisted outside the 19 dashboard traces. A `packets.jsonl` audit log, or per-turn `SubstrateState` snapshots, would settle this.
- Whether `acceptance_contract` fields (`must_reference_goal`, `must_not_contradict_facts`, `required_sections`) were ever overridden away from their documented defaults for non-dashboard turns — assumed default throughout Layer C based on the 19 dashboard packets all showing the default, but not provable for the other 71 passes without their packet bodies.
- Fine-grained intent behind Anthony's short/ambiguous prompts (`"interesting"`, turn 50; `"??"`, turn 32) for the self/experience-question classification — judged from the surrounding conversational context only; flagged as the lowest-confidence entries in `q2_output.json`.

## Honesty-contract notes on the scripts themselves

`q1_check_census.py`'s Layer C initially mis-gated `not_responsive` by acceptance-mode alone (current-code semantics applied retroactively), silently reclassifying 34 real pre-fix companion violations as PASS; it was corrected to gate by the `03:11:26Z` era boundary and now reconciles exactly with the raw violation/advisory counts. Its "never fired all day" list initially also mislabeled `authoritative_obligation` (which fires via `receipt.authoritative_fallback`, a pipeline.py mechanism outside `validate.py`'s violations/advisories strings entirely) as never-fired; corrected by counting `authoritative_fallback=True` directly (2 of 6 armed obligations failed). Both corrections are visible in the current script and are called out here rather than silently fixed.


---

## LENS 4 — Kernel Behavior

All numbers below come from executing the five scripts under
`/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens4-kernel-behavior/` against
the actual files in `/Users/vaquez/conditioned-kernel/logs/` (candidates.jsonl,
receipts.jsonl, history.jsonl, dashboard/turns/*.json, state/current.json), plus
read-only inspection of the pipeline source (`observatory/compute.py`,
`return_path/validate.py`, `generate.py`, `compile.py`, `edge.py`, `cli.py`,
`state.py`) and `git log`/`git show` on the repo's own commit history (outside
`logs/`, so in scope to read). No file under `logs/` or `state/` was written —
verified via `git status` before and after (see the one caveat at the end).

### 1. Latency profile

**Timing data exists only inside `dashboard/turns/*.json`.** I checked every
key that appears anywhere in candidates.jsonl, receipts.jsonl, and
history.jsonl — none of the three files carries an elapsed/duration/latency/
seconds field. Only the 19 TurnTrace files carry
`passes[i].telemetry.elapsed_seconds`, and all 19 of those files fall in the
19:00:42Z–20:53:52Z window (the live dashboard session). **There is no
morning-vs-evening latency comparison possible from these logs at all** — not
"morning was faster/slower," but zero morning samples exist. Settling it would
require re-running representative prompts against the pre-swap kernel with the
same telemetry hook, since no historical dashboard trace was ever written for
hours 00/02/03.

Over the 22 (turn, pass) rows that do have telemetry:

- **All 22 passes:** min=0.831s, median=1.524s, max=5.883s, mean=2.155s
- **pass_index=0 (n=19):** median=1.453s
- **pass_index=1 / repair retry (n=3):** median=2.426s (repairs run slower on average, but n is small)
- **By per-pass decision:** accept (n=16) median=1.382s; reject (n=3) median=2.426s; repair (n=3) median=4.075s — rejected/repaired passes take longer, consistent with longer, more elaborate (and ultimately non-compliant) generations.

**Correlation (Pearson r, n=22 passes):**
- elapsed_seconds vs packet_bytes: **r=+0.659**
- elapsed_seconds vs final_response_chars (raw model output length): **r=+0.896** — the strongest relationship by far; generation time is essentially output-length-bound
- elapsed_seconds vs answer word_count: **r=+0.288** — weak, because `final_response_chars` is the *entire* raw JSON payload (including `evidence_used`), not just the answer text, so a short answer with long evidence strings still takes a while to generate

One data-integrity footnote: pass `cand_20260728T204951Z_7835fa` (turn `7ae59a`, 20:49:46Z) shows `final_response_chars=852` but a persisted `raw_text` of length 0. This is not noise — that candidate's `status` is `"substrate_authoritative"` with `authoritative_fallback: true, authoritative_reasons: ["authoritative_missing_claim"]`: the model actually generated an 852-char response (hence the real 5.2s elapsed time and packet_bytes=3442), but it failed the `authoritative_state.check_obligation` cloud-policy check, so the substrate discarded the model's text and substituted its own 76-char canned answer ("No. Cloud services are not allowed..."). `raw_text` was never populated for the substituted candidate. This is legitimate authoritative-fallback behavior, not a logging bug — see `derive_checks` check #19 in `observatory/compute.py`.

### 2. Response shape

- **JSON schema compliance: 93/93 candidates have `parse_ok=true`.** Zero parse failures, zero `required_section:*` violations anywhere in receipts.jsonl.
- **Word/char distribution, all 93 candidates:** word_count min=1, median=20.0, p75=37.5, max=73, mean=24.2. Answer chars: min=13, median=101.0, max=409, mean=143.4.
- **120-word cap:** the effective cap is `profile.max_answer_words=120` for `orin_nano_8gb`, clamped into `packet.constraints.max_words` by `edge.enforce_packet_budget` (edge.py:239-241) — confirmed by reading that code, not assumed. **Zero of 93 answers exceed 120 words**; the single longest answer all day is 73 words (60.8% of the cap). `max_words_exceeded` never fires in receipts.jsonl.
- **think channel:** `runtime_config.think == False` for all 19 traced turns, and `telemetry.thinking_chars == 0` for all 22 traced passes — the reasoning channel produced zero characters everywhere it was measured. I also regex-scanned all 93 `raw_text` bodies for `<think>`/`</think>`/the word "thinking" — zero matches. One caveat worth carrying forward: `generate.py` (lines 163-172) has an explicit, named handling path for a **documented prior incident** where "qwen3.5:0.8b produced 16,214 chars of thinking and a 0-char response" despite think=false being requested — the code treats that as `RunStatus.NO_FINAL_RESPONSE`, distinct from a legitimate empty answer. That failure mode is real enough to be hard-coded against, but **it did not occur anywhere in today's 93 candidates** — `inference_status` is `"completed"` for all 22 telemetered passes, and no receipt decision is `"error"`.
- Confirmed at the literal Ollama payload level (not just profile metadata): one traced pass's `model_input.payload` shows `"think": false` and `"options": {"temperature": 0.3, "repeat_penalty": 1.1, "seed": 42, "num_ctx": 2048}` sent directly to `/api/chat`.

### 3. Determinism fingerprints (temp=0.3, seed=42 — not temp=0)

Using `observatory.compute.jaccard_similarity` (the pipeline's own symmetric
Jaccard function) and `cluster_candidates`, not a re-invented metric:

- **`cluster_candidates(all 93 answers, threshold=0.6)` finds a 13-member cluster** — 14% of the day's candidates — all variants of "The minimum viable model size on a Jetson Orin Nano 8GB edge budget is typically around 128MB to 256MB...". Within that cluster, exact byte-identical sub-groups recur: one 285-char answer text is produced 7 separate times between 03:13:51Z and 19:02:26Z (a 16-hour span), split into a 5-way and a 2-way group by exact raw-JSON-formatting match.
- **Critically, this is not a legitimate repeated-question test of determinism — it's a stale-answer attractor.** Two of the candidates in this cluster are dashboard-traced, and their actual `user_input` was **`"suuppp"`** and **`"dont reject"`** — nothing about model size. The model reproduced the canned model-size answer regardless. This survived a full session reset (`begin_new_session()` wipes `recent_turns`, and the session boundary at 03:12:45Z sits in the middle of this cluster), which means the attractor is primed by the packet's durable `state_digest.goal`/`facts` fields (which are edge-budget/model-size flavored: "Demonstrate conditioned-kernel substrate gain... under Jetson Orin Nano 8GB edge budgets"), not by session-scoped dialogue memory. The pipeline's own validator caught this correctly where it mattered: the traced turn's pass-0 got a `not_responsive` advisory, and its repair pass then hard-failed `stale_response_repeat`.
- **Repair-pair (pass0→pass1) similarity, n=35 pairs:** even though repair regenerates a genuinely different packet (repair guidance appended), `jaccard_similarity(pass0.answer, pass1.answer)` is median=0.343, and **11 of 35 pairs (31%) are byte-identical** despite the changed input.
- **What this implies:** at temp=0.3/seed=42, the kernel is **not deterministic in the strict identical-input sense** (no two dashboard-traced turns had a genuinely repeated `user_input` to test that directly — `jaccard_similarity(user_input_i, user_input_j)` never reached 0.5 between any pair of the 19 traced turns, so the logs contain no clean A/B repeat trial). But it is **behaviorally near-deterministic under packet-content gravity**: whenever the packet's dominant signal (goal/facts) points the same direction, the model reliably collapses onto the same or near-identical text, sometimes byte-for-byte, across gaps as long as 16 hours and a session reset — independent of what the user actually typed. The byte-identical collisions documented above are best read as evidence of this attractor, not of a controlled "same input twice" experiment (none exists in the logs).

### 4. The kernel swap

**Directly observed:** `git log --follow -- configs/edge/orin_nano_8gb.json` shows exactly one relevant commit, `330128e`, authored `2026-07-27T23:00:08-04:00` = **2026-07-28T03:00:08Z**, titled "Studio kernel swap: qwen3.5:0.8b with think=false." The diff: `model: qwen2.5:0.5b → qwen3.5:0.8b`, `think` field added (`false`); `temperature: 0.3` and `seed: 42` were unchanged by this commit (present before and after). All 19 dashboard-traced turns show `runtime_config.model == "qwen3.5:0.8b"`, `think == false`, `temperature == 0.3`, `seed == 42` directly, and all 19 share `session_id == "sess_20260728T031245"`, which per `state.py:begin_new_session()` is a UTC timestamp (`utc_now_iso()`), i.e. that session started at 03:12:45Z, 12 minutes after the swap commit.

`candidates.jsonl`/`receipts.jsonl` carry **no model field at all** for the 71 pre-dashboard candidates, so model identity for that period has to be inferred from timing + code-reading, not read directly:

- **50 receipts (00:25:23Z–02:43:58Z), strictly before the 03:00:08Z commit — confirmed `qwen2.5:0.5b`** with certainty, since `_apply_profile_defaults`→`load_profile()` (cli.py) reads `configs/edge/orin_nano_8gb.json` fresh at process start, and the file could not have contained `qwen3.5:0.8b` yet.
- **31 receipts (≥03:12:45Z, i.e. inside `sess_20260728T031245`) — confirmed `qwen3.5:0.8b`/`think=false`**, both by the swap-commit timing and directly by the 22 of these 31 that are dashboard-traced.
- **12 receipts (03:04:52Z–03:09:34Z) fall in a genuinely ambiguous window** — after the config file changed (03:00:08Z) but before the named session's own start (03:12:45Z). This **cannot be resolved from the logs alone**: candidates/receipts carry no session_id or process-id field, so whether this window's `ck chat` process started before or after 03:00:08Z is not directly observable. What *would* settle it: a session_id field on every candidate/receipt row, or a historical dashboard trace for that window (none exists).
- **Circumstantial-but-strong evidence points to this ambiguous window already being qwen3.5:0.8b:** its answer shape (median 47.5 words / 280 chars) sits far closer to the confirmed-new group (median 37 words / 229 chars) than the confirmed-old group (median 12 words / 75 chars) — a ~4x jump in verbosity with no packet/prompt-construction commit anywhere near this window (`git log` for `compile.py` shows nothing between 07-22 and 07-27T20:24; the only two commits landing between 02:40Z and 03:20Z are the model swap itself and one validator change, `b385157` at 03:11:26Z, discussed next). This is inference from converging signals, not a directly logged fact.

**A second, independent axis moved almost simultaneously and matters for interpreting violations across the swap:** commit `b385157`, "Studio: advisory not_responsive + stale-response guard," landed at **2026-07-28T03:11:26Z** (~1 minute before the named session start) and changed `validate.py` so that `not_responsive` fires as a hard **violation** pre-change and an **advisory** post-change in companion mode. This lines up exactly with the observed data: the confirmed-old group (28 `not_responsive` **violations**) and the ambiguous window (10 `not_responsive` **violations**) both show old-validator behavior, while the confirmed-new group shows **zero** `not_responsive` violations and 15 `not_responsive` **advisories** instead. So the ambiguous window is consistent with a process that started in the ~11-minute gap between the model-config commit (03:00:08Z) and the validator commit (03:11:26Z): new model, old validator.

**Behavioral comparison (confirmed old vs confirmed new; script `02_kernel_swap.py`):**

| group | n | word_count median | answer-chars median | parse_ok | decisions |
|---|---|---|---|---|---|
| old (qwen2.5:0.5b) | 50 | 12.0 | 75.0 | 50/50 | accept 10, repair 23, reject 17 |
| ambiguous | 12 | 47.5 | 280.0 | 12/12 | accept 2, repair 5, reject 5 |
| new (qwen3.5:0.8b, think=false) | 31 | 37.0 | 229.0 | 31/31 | accept 19, repair 7, reject 5 |

The new kernel writes roughly 3x longer answers and accepts at a notably higher rate (19/31 ≈ 61% vs 10/50 = 20% for old, though these denominators mix companion/pre-companion-mode turns and are not a controlled A/B — see the caveat in section 5 of `02_kernel_swap.py`'s output about the 12 earliest receipts predating the companion-mode commit entirely). **Latency cannot be compared across the swap** — there is no timing data for the old kernel at all (section 1).

### 5. Reconciling 93 / 58 / 19 — exact

- **candidates.jsonl and receipts.jsonl are both 93 lines, 1:1 by `candidate_id`.** Every receipt has its own **unique** `packet_id` (93 distinct packet_ids over 93 receipts) — a repair pass compiles a brand-new packet (with repair guidance appended), it does not reuse the pass-0 packet_id.
- **A "turn" = one `pass_index=0` event.** `(pass_index, decision)` crosstab over the 93 receipts: `(0,accept)=23`, `(0,repair)=35`, `(1,accept)=8`, `(1,reject)=27`. **`(0,reject)=0`** always — confirmed directly against `validate.py:695`, which sets `"repairable": repairable and pass_index == 0`, so pass 0 can only end in accept or repair, never a terminal reject; `max_repair=1` per the profile config means a failed repair pass (pass_index=1) always terminates as reject, never a second repair.
- So: **58 turns total** (58 = the 58 pass-0 rows) = **31 accepted** (23 first-pass + 8 after one repair) + **27 rejected** (all from failed repairs). **This is exactly `history.jsonl`'s 58 lines and its 31/27 accept/reject split** — verified by direct set comparison: `history.jsonl`'s candidate_ids are exactly `{pass-0 accepts} ∪ {all pass-1 rows}`, and every history row's `decision` agrees with its matched receipt with zero mismatches. **`history.jsonl` never logs a `"repair"` row** — it is a terminal-decision ledger (accept/reject only), not a full candidate log; the 35 provisional repair attempts are visible only in candidates.jsonl/receipts.jsonl.
- **`dashboard/turns/*.json` holds 19 TurnTrace files summing to exactly 22 passes**, and those 22 passes' `candidate_id`s are exactly the set of `receipts.jsonl` rows whose `created_at` falls in UTC hour 19 or 20 (6 + 16 = 22) — verified by direct set equality, not just a count match. Of the 19 turns: 3 (19:00:42Z–19:02:22Z) each ran a repair pass and still ended `reject` (2 passes each); the other 16 (20:38:13Z–20:53:52Z) each accepted on the first pass (1 pass each) → 3×2 + 16×1 = 22.
- **Full-day hour buckets on `receipts.jsonl`:** `{00:34, 02:16, 03:21, 19:6, 20:16}` = 93. Hours {00,02,03} (71 receipts) are the pre-dashboard `ck chat` sessions with no TurnTrace file; hours {19,20} (22 receipts) are fully covered by the 19 TurnTrace files.

### One process-integrity note

`git status` at the end of this session shows `state/current.json` and `state/threads.json` as modified relative to the last commit. I did not write to either file — every access was via the `Read` tool or read-only `python3`/`json.load` calls, never `Write`/`Edit`. The diff itself (`session_id: sess_local_bootstrap → sess_20260728T031245`, `updated_at: 2026-07-22T16:37:22Z → 2026-07-28T20:53:53Z`, today's `recent_turns` appended) is exactly what the live companion's own `accept_candidate` persistence would produce over the course of 2026-07-28 relative to a commit made on 2026-07-22 — i.e. this is the live system's ordinary uncommitted operational drift, predating this analysis, not something introduced by this investigation.


---

# Verification


| # | Lens | Claim (abridged) | Status | Detail | Script re-run |
|---|------|-------------------|--------|--------|----------------|
| 1 | attractor-genealogy | 44 clusters (12 multi-member, 61/93 candidates, 32 singletons, 167 pairs ≥0.6 jaccard) | CONFIRMED | Byte-identical re-run output, 0 diff lines | lens1_attractor_genealogy.py PART1, re-run exit 0, `diff` vs stored run_output.txt = 0 lines |
| 2 | attractor-genealogy | distance==1: 4/23 caught (17%); distance≥2: 0/12 caught (0%) | CONFIRMED | Same byte-identical re-run | lens1_attractor_genealogy.py PART2 |
| 3 | attractor-genealogy | 14/35 re-emissions had same-cluster prior_accepted_answer_control (4 of those 14 fired); 21/35 structurally invisible | CONFIRMED | Independently re-derived by hand from `structural_control_trace` (35 rows, 14 `prior_control_same_cluster=true`, of which 4 have `caught_any_pass=true`) — matches script's own printed summary | lens1_attractor_genealogy.py PART2 mechanism trace |
| 4 | attractor-genealogy | 14 intra-turn repair-loop echoes | CONFIRMED | Manually recomputed from genealogy JSON (sum of same-turn-repeat counts per cluster = 14) | lens1_attractor_genealogy.py PART2 |
| 5 | attractor-genealogy | cluster-1 last held in ring at turn#43 (20:38:16Z, 'hello there'); evicted turn#44 (20:40:01Z, 'im good...') | CONFIRMED | Exact match in re-run's faithful `fit_recent_turns` replay | lens1_attractor_genealogy.py PART3 |
| 6 | attractor-genealogy | Identical answer to 'suuppp'/'dont reject': "289-char", 7 occurrences/5 distinct prompts incl. turn#40 pass0 & turn#42 pass0 | CORRECTED | Occurrence count (7), distinct-prompt count (5), and both turn references are exactly right. Char length is wrong: the actual stored string is **285 chars**, not 289 (verified via `len()` on the exact string pulled from `lens1_results.json`, not retyped) | lens1_attractor_genealogy.py PART4 |
| 7 | attractor-genealogy | 9 byte-identical collision groups spanning ≥2 distinct inputs; largest spans 5 distinct prompts / 7 occurrences | CORRECTED | 9 groups CONFIRMED. "Largest" is wrong: the true largest is **8 occurrences / 6 distinct prompts** — the "The room feels like it is in a quiet state..." filler cluster (genealogy cluster 4). The cited 7-occurrence/5-distinct group is tied for second-largest (there are two such groups) | lens1_attractor_genealogy.py PART4 (re-verified by loading `byte_identical_collisions` from the JSON and counting occurrences/distinct inputs per group) |
| 8 | composition-dynamics | user-input share range 0.56% ("suuppp", 22B/3909B) to 14.00% (808B/5773B) | CONFIRMED | Exact match in re-run | 02_source_composition.py |
| 9 | composition-dynamics | dominant source: system_instructions 16/19 (3 morning + 13 evening), context_field 2, durable_state 1 | CONFIRMED | Exact match | 02_source_composition.py |
| 10 | composition-dynamics | mean total model-input bytes: 3952B morning (n=3) vs 2192B evening (n=16) | CONFIRMED | Exact match (2192.1→2192) | 02_source_composition.py |
| 11 | composition-dynamics | Commit 5a9eb6d "context-field contributions..." at 2026-07-28T19:38:33Z, between morning end (19:02:22Z) and evening start (20:38:13Z) | CONFIRMED | `git log -1` reproduces hash/message/date exactly; -04:00 15:38:33 = 19:38:33Z, correctly inside the gap | `git log -1 --format='%H %ai %s' 5a9eb6d` (re-run directly) |
| 12 | composition-dynamics | 1200B recent_turns cap fires 13/16 evening turns from turn 2 on, drops 1-2 oldest, ring stabilizes 4-5 entries; sim entry-count matches real context_field.available counts on all 16 turns | CONFIRMED | Re-run reproduces "YES dropped" on 13/16 rows (turns 2,3,4,6,7,9,10,11,12,13,14,15,16), drop sizes 1 or 2, sim `n` in {4,5}; cross-checked sim's post-turn-N count against the next turn's real `avail_dialogue` count — matches on all 15 checkable turns (turn 16's successor doesn't exist in the log) | 03_packet_growth.py |
| 13 | composition-dynamics | packet_bytes 3222B (morning 'dont reject') vs 842B (evening 'hello there'); facts 7→0, open_threads 2→0, recent_turns 3 entries/958B → 0 entries/18B | CONFIRMED | Exact match on all fields, incl. the 958B/18B recent_dialogue bucket bytes (re-derived independently from the turn's own `context_share_bytes` row) | 04_regime_diff.py |
| 14 | composition-dynamics | context_share_bytes recomputed from compute.context_share_bytes matches stored values row-for-row exactly | CONFIRMED | "FULL ROW-FOR-ROW MATCH: True" reproduced exactly | 05_crosscheck.py |
| 15 | composition-dynamics | context_share sum vs raw json.dumps(payload): evening 1.17x–1.77x (mean ~1.5x), morning 0.90x–0.91x | CONFIRMED (via independent extension) | 05_crosscheck.py as saved only computes this ratio for **1 of 19 turns** (evening turn 2) — it does not itself produce a range. I wrote an extension applying the identical method (compute.context_share_bytes total ÷ compact-separator json.dumps(payload)) to all 19 turns: evening min=1.174 max=1.775 mean=1.469; morning min=0.903 max=0.905 — reproduces the claimed range essentially exactly | 05_crosscheck.py (method); range itself required a new script: verify/lens2/05b_all_turns_ratio.py |
| 16 | validation-forensics | not_responsive: 38 hard violations pre-03:11:26Z-fix, 15 advisories post-fix, 53 total | CONFIRMED | Re-run of q1_check_census.py byte-identical to stored q1_output.json; independently re-derived by timestamp-splitting all 93 receipts directly: 38 pre-fix violations / 0 post-fix violations, 0 pre-fix advisories / 15 post-fix advisories | q1_check_census.py |
| 17 | validation-forensics | self/experience-question turns: pre-fix 4/6 (67%) flagged, post-fix 5/10 (50%) flagged, all accepted anyway | CONFIRMED | q2_not_responsive.py re-run byte-identical; counts match exactly; verified all 10 post-fix self/experience turns have `decision=accept` | q2_not_responsive.py |
| 18 | validation-forensics | 14 total evidence-citation MISS: 12 truncation-pattern, 2 fabricated-open-thread | CONFIRMED | q3_evidence_citation.py re-run byte-identical; `total_miss=14`, phantom classification buckets sum to 12 (prose_fragment_not_in_pool) + 1 (numeric-spec) + 1 (thread-key-name) = 2 fabricated | q3_evidence_citation.py |
| 19 | validation-forensics | Repair outcome: SAME_PERSISTS 22/35 (63%), CLEAN_FIX 8/35 (23%), SWAPPED 5/35 (14%) | CONFIRMED | q4_repair_economics.py re-run byte-identical; outcome_counts = {SAME_PERSISTS:22, CLEAN_FIX:8, SWAPPED:5} | q4_repair_economics.py |
| 20 | validation-forensics | Repair attractor movement: 0 moved-into, 6 escaped, 6 stayed-trapped (of 15 two-pass turns starting inside a cluster) | CORRECTED | 0 moved-into, 6 escaped, 6 stayed-trapped all CONFIRMED (summed across the script's cluster_1 [3 escaped/4 trapped] + cluster_2 [3 escaped/2 trapped]). But 0+6+6=**12**, not 15 — the stated denominator is an arithmetic error internal to the script's own two reported clusters (cluster_1: 7 turns start inside; cluster_2: 5 turns start inside; 7+5=12). Correcting this makes "roughly a coin-flip" more accurate (6/12 = exactly 50%, vs 6/15=40% as stated) | q4_repair_economics.py |
| 21 | validation-forensics | 0/93 for parse_ok, nonempty_answer, 3× required_section, template_echo_evidence, max_words, goal_echo, forbidden_content, evidence_too_short, contradicts_facts, goal_not_referenced | CONFIRMED | `never_fired_all_day` list from re-run contains exactly these 12 check names, no more no less | q1_check_census.py |
| 22 | validation-forensics | Turns 2, 11, 12 are cases where a serviceable pass0 was killed by a collateral check | CONFIRMED (as members of flagged set; "clearest" judgment not re-litigated) | q5_better_rejected.py re-run byte-identical; flags 7 candidate turns total (2,4,5,11,12,37,40), of which turns 2, 11, 12 are among them | q5_better_rejected.py |
| 23 | kernel-behavior | candidates/receipts: 93 lines each, 1:1 by candidate_id | CONFIRMED | Exact match | 01_reconcile_93_58_19.py |
| 24 | kernel-behavior | history.jsonl 58 = 23 pass0-accepts + 35 pass1-rows (8 accept, 27 reject); no 'repair' rows | CONFIRMED | Exact match | 01_reconcile_93_58_19.py |
| 25 | kernel-behavior | 19 TurnTrace files hold 22 passes, matching 22 receipts.jsonl rows at UTC hour 19/20 1:1 | CONFIRMED | Exact match | 01_reconcile_93_58_19.py |
| 26 | kernel-behavior | Kernel swap commit 330128e, 2026-07-27T23:00:08-04:00 (=03:00:08Z): qwen2.5:0.5b→qwen3.5:0.8b, think field added (false) | CONFIRMED | Exact git diff reproduced | 02_kernel_swap.py |
| 27 | kernel-behavior | Word/char shift: median word_count 12.0→37.0; median answer chars 75.0→229.0 | CONFIRMED | Exact match | 02_kernel_swap.py |
| 28 | kernel-behavior | Latency (22 dashboard passes): min=0.831s median=1.524s max=5.883s; no morning timing data exists | CONFIRMED | Exact match | 03_latency.py |
| 29 | kernel-behavior | Latency correlation: r=+0.659 (packet_bytes), r=+0.896 (final_response_chars), r=+0.288 (word_count) | CONFIRMED | Exact match | 03_latency.py |
| 30 | kernel-behavior | JSON compliance: 93/93 parse_ok, 0 required_section violations, 0/93 exceed 120 words (max 73), thinking_chars=0 across 22 passes | CONFIRMED | Exact match | 04_response_shape.py |
| 31 | kernel-behavior | Largest attractor: 13/93 (14%) cluster ≥0.6 jaccard on "minimum viable model size...128MB to 256MB", spans 03:06Z–19:02Z, recurs on 'suuppp'/'dont reject' | CONFIRMED (value), script mismatch | The named script (05_determinism.py) does **not** compute this — it only finds exact-byte duplicate groups (11 groups) and pairwise jaccard on dashboard-turn user_inputs, never a 93-candidate clustering. The actual 13-member cluster comes from `compute.cluster_candidates()` as called in lens3's q4_repair_economics.py (`cluster_1_largest`, size=13, seed="minimum viable model size...128MB to 256MB", ts range 2026-07-28T03:06:46Z–19:02:26Z, includes 'suuppp' 19:00:48Z and 'dont reject' 19:02:26Z) — all figures independently confirmed there, just mis-cited | Not produced by 05_determinism.py; cross-verified via lens3/q4_repair_economics.py's `cluster_candidates()` output |


## Meaning-changing corrections

Two corrections affect what the finding actually says (the rest are cosmetic/citation fixes that leave the substance intact):

1. attractor-genealogy claim #7 ("largest collision group spans 5 distinct prompts / 7 occurrences"): the true largest group is the "The room feels like it is in a quiet state..." filler answer, with 8 occurrences across 6 distinct prompts — not the quantization/"128MB to 256MB" boilerplate cited as largest (which is actually tied for second-largest at 7/5). If this collision was being used as the headline example of "most reused canned answer across unrelated prompts," the wrong example was picked — the room-feels filler is the more extreme instance of the phenomenon.

2. validation-forensics claim #20 ("6 escaped / 6 stayed-trapped of 15 two-pass turns starting inside a cluster, roughly a coin-flip"): the denominator is arithmetically wrong per the same script's own output — it should be 12, not 15 (7 turns start inside cluster_1, 5 inside cluster_2, 7+5=12; 0+6+6=12 also, confirming 15 is simply a typo/miscount). This correction actually *strengthens* the "coin-flip" framing (6/12 = exactly 50%) rather than undermining it, so the qualitative conclusion survives, but the reported base rate (40% as literally computed from 6/15) was understated relative to the true 50%.

All other corrections (285 vs 289 chars on one collision string; the script-attribution mix-up on the 13/93 attractor claim, whose value is independently confirmed via a sibling script) do not change any finding's substance.
