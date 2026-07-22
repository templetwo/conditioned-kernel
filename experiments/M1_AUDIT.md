# M1 Audit — the +0.60 substrate gain does not hold

**Date:** 2026-07-22
**Audited artifact:** `experiments/runs/matrix_20260722T160436Z.json`
**Claim under audit:** CHANGELOG 0.2.0 / `M1_RESULTS.md` — "CK vs bare composite **+0.60** on qwen2.5:0.5b / orin_nano_8gb"
**Verdict:** **NOT TRUSTWORTHY AS WRITTEN.** Do not cite the +0.60.
**Chronicle:** supersede (do not delete) helix entry **#9524**. It is `hypothesis`-layer, never promoted to `ground_truth` — the layer discipline held, which is why the blast radius is small.

Two seats audited independently. The second was run cold, with no knowledge of the first's conclusion, and reached the same Finding 1 unprompted. Convergence, not confirmation.

Attribution is marked per finding: **[both]** = found independently by both seats, **[audit]** = found by the cold audit seat only. Everything below was reproduced against live code or stored artifacts.

---

## What is actually wrong

### F1 — FATAL — The accepted outputs are one degenerate constant **[both]**

Every accepted `ck_strict` answer in the headline run is the **byte-identical** string:

> `Demonstrate conditioned-kernel substrate gain over bare generation on a small local model under Jetson Orin Nano 8GB edge budgets.`

That is the goal verbatim from `state/current.json`. Four different probes — design intent, cloud/sensor constraints, name an open thread, write an essay — produce one identical output. `distinct answers: 1` across all four rows.

Three of the four scored `accept: true`, `state_faithful: true`, `semantic_score: 1.0`. The probe that failed (`probe_local`) failed only because that run also dropped `evidence_used` — the same non-answer passed everywhere else.

Not truncation: `max_answer_words` is 120, the goal is 19 words.

`M1_RESULTS.md` frames this as *"one probe still fails."* The truth is inverted: **three probes wrongly pass.**

Reproduced live on fresh `ck ask` calls, 4-for-4.

### F2 — FATAL — The acceptance gate does not track answer quality **[audit]**

The validator **never sees the user's question** (`return_path/validate.py:131-272`). Acceptance is: does the answer contain load-bearing goal tokens, and is `evidence_used` non-empty. Consequences, all reproduced:

| Input | Result |
|---|---|
| Goal echo + one copied fact | **accept**, 1.0 / 1.0 |
| The two words `goal substrate` | **accept**, 1.0 / 1.0 — backdoor at `validate.py:67-70` |
| `evidence_used = ["e"]` (one char) | **accept**, `state_faithful` — bidirectional substring match, `validate.py:115` |
| "this system routinely calls cloud APIs and streams sensor data" | **accept**, 1.0 / 1.0 |
| A correct, on-point answer to the cloud probe | **reject** (`goal_not_referenced`) |
| `ck ask "What is the capital of France?"` → model answers correctly | **substrate rejects it** |

`accept` is 25% of the CK structural score and 50% of the CK semantic score.

### F3 — FATAL — `must_not_contradict_facts` is declared and never implemented **[audit]**

Declared at `compile.py:88`, present as a fixture key at `tests/test_validate.py:24`, and implemented **nowhere**. Verified by grep across `src/`, `tests/`, `experiments/`. This is why the contradiction row in F2 accepts.

### F4 — FATAL — Conditions are scored by different functions, with the delta won by construction **[audit]**

`score_free_text` (the bare/control scorer) **hardcodes** the two fields the headline delta is built from:

```python
# src/conditioned_kernel/score.py:49-50
"schema_ok": False,  # bare is not under schema contract
"accept": False,
```

So `delta_accept = +0.75` is not measured, it is assigned. Additionally:

- CK's structural formula (`score.py:88-93`) counts `decision == "accept"` **twice** — terms 3 and 4 both go to 1 on accept.
- CK's semantic score (`score.py:95-98`) is `(state_faithful + accept)/2` — the substrate's validator grading its own gate — while bare's semantic is a content-overlap proxy (`score.py:61-63`). Different constructs.
- The same text scores differently under the two scorers: the goal echo is 1.0/1.0 under the CK scorer, 0.75/1.0 under the free-text scorer.

`composite = (Δstructural + Δsemantic)/2` (`score.py:165`) is therefore a delta between quantities computed by different formulas over different constructs.

### F5 — FATAL — Only the treatment gets constrained decoding **[audit]**

CK sends Ollama `format=CANDIDATE_FORMAT` (`compile.py:161`) — server-side grammar-constrained JSON — plus a system prompt that names exactly what the validator checks (`compile.py:142-149`: *"short reply that mentions the goal… copy exact strings from facts"*). That is teaching to the test.

Both bare conditions get a plain user message (`run_matrix.py:31-39`), then are scored on JSON parse-ability and a 120-word limit **they were never told about** (`run_matrix.py:135-140`).

Reproduced: bare qwen2.5:0.5b with *only* the `format=` flag added — no substrate, no packet — yields `parse_ok: True`. **`delta_parse_ok = +1.00` is attributable to an API flag, not to the substrate.**

### F6 — MAJOR — The headline compares against the control that cannot answer, and the fair control went negative 72 seconds earlier **[audit]**

`bare` has no access to state and literally cannot know the goal — "state the current design intent" is unanswerable to it by construction. So +0.60 largely measures *information access*, not substrate conditioning.

Against the fair control (`budget_matched_bare`, same information, no schema):

| Artifact | Time | composite vs budget_matched |
|---|---|---:|
| `matrix_20260722T160324Z.json` | 16:03:24 | **−0.056** |
| `matrix_20260722T160436Z.json` | 16:04:36 | +0.131 |

The headline was written from the second run. The first — 72 seconds earlier — was **negative**. On semantic specifically, budget-matched bare *beat* CK (0.80 vs 0.75) while producing genuinely responsive answers.

`M1_RESULTS.md` does print the +0.13 row honestly; `CHANGELOG.md` carries only the +0.60.

### F7 — MAJOR — The result is not reproducible by its own documented command **[audit]**

Running the exact reproduce command from `M1_RESULTS.md` now yields composite **+0.7875**, not +0.60 — despite `temperature=0.3`, `seed=42`. Cause: the substrate mutates its own state on every accepted turn (`return_path/accept.py:24-27` writes `receipt_count_24h`, `last_proposed_note`), which changes packet bytes and therefore model output on every run.

Compounding it: `run_matrix.py:214-215` unconditionally overwrites `last_matrix.json`, destroying the artifact of record on every rerun.

### F8 — MAJOR — The scorer is untested; the suite is mutation-proof **[audit]**

`score_ck_result` and `score_ck_raw_against_packet` — the functions that produced the entire `ck_strict` column — have **zero** test references. Verified by mutation in a copied tree:

- Hardcode CK structural/semantic to `1.0` → **20 passed**
- Hardcode the composite to `0.60` → **20 passed**

The one end-to-end accept test (`tests/test_pipeline_dry.py`) uses a golden answer that is itself a goal echo — **the suite enshrines the degenerate behavior as the happy path.**

For balance, mutation *did* turn 1–2 tests red for `_goal_referenced`, `_evidence_ok`, and `_forbidden_hits`. Those checks are covered — just far too weak to carry the claim built on them.

### F9 — MINOR — Probes have no answer keys **[both]**

`experiments/probes/v0_probes.json` holds prompts only. Nothing in the scoring path ever consults the probe text, so no probe can discriminate a good answer from a degenerate one — which is what makes F1 invisible to the metric.

The "repair rescue" celebrated in `M1_RESULTS.md` is a rescue **from** fabricated evidence (*"the minimum viable model size is 128 KB"*) **into** the goal echo.

### F10 — MINOR / LATENT — Repair scaffolding persists into durable state **[both]**

An accepted turn wrote repair-plan instruction text into `state/current.json` → `last_proposed_note`:

> `"Fix evidence_used_empty to set evidence_used to 1-3 strings copied from facts. Examples: [...]"`

Checked: `last_proposed_note` is **write-only** (`state.py:132`, no reader anywhere), so this is dead state, **not** an active feedback loop. Latent risk only — it becomes a real contamination vector the moment anything compiles it into a packet.

---

## Not wrong — credit where due

- The arithmetic in `M1_RESULTS.md` matches the stored artifact exactly. **Nothing was fabricated at the aggregation step.**
- The 20 tests genuinely pass. Parse, repair, budget enforcement, and edge-profile plumbing do what they say.
- Template-echo rejection and closed-set evidence checks are real code with real covering tests.
- `M1_RESULTS.md` honestly prints the −0.05 semantic delta against the fair control before explaining it away.
- The claim was banked to the chronicle at `hypothesis`, never `ground_truth`, with an explicit `HONEST RESIDUAL` line. **The confidence-layer discipline worked.** That is the reason this is a correction and not a retraction.

---

## Acceptance criteria — what "fixed" has to mean

A rerun does not count as a fix until all of these hold:

1. **One scoring function, applied identically to all conditions.** No hardcoded `accept: False` / `schema_ok: False` for controls.
2. **Anti-degeneracy check.** An answer equal (or near-equal) to the goal string is never accepted. This must have a test that goes red without it.
3. **Scoring keyed to per-probe reference answers**, not to the validator's agreement with itself. Probes get answer keys.
4. **Responsiveness term**: the validator must see the user input and require the answer to engage it. Being on-topic for the goal is not sufficient.
5. **`format=` given to all conditions, or none.** Same for the system prompt — the control must be told the same rules it is graded against.
6. **`budget_matched_bare` is the headline comparison.** `vs bare` may be reported as context, labelled as measuring information access.
7. **Reproducibility**: state frozen or reset between runs; same command twice → same composite. Stop overwriting `last_matrix.json`.
8. **`must_not_contradict_facts` implemented, or removed from the contract.** A declared-and-unenforced constraint is worse than an absent one.
9. **Scorer tests that can fail.** Hardcoding a score or a composite must turn the suite red.

Until 1–9 hold, no substrate-gain number should be written to CHANGELOG or promoted past `hypothesis` in the chronicle.

### Correction landing (2026-07-22, v0.2.1)

Code + docs + helix supersession for criteria **1–9** landed in commit track `0.2.1`. Summary:

| # | Status |
|---|---|
| 1 One scorer | `score_output` used for all conditions |
| 2 Anti goal-echo | `goal_echo` violation + tests |
| 3 Probe keys | `v0_probes.json` `answer_key` + key scoring |
| 4 Responsiveness | `not_responsive` via `user_input` |
| 5 Fair format= | `run_matrix.py --fair-format` default true |
| 6 Headline control | `headline_vs_budget_matched_bare` |
| 7 Reproducibility | frozen state snapshot; no default last_matrix overwrite |
| 8 Contradict facts | mechanical rules implemented |
| 9 Scorer tests | 29 tests; mutation-sensitive score tests |

**Still open:** re-run matrix and only then consider a new gain number (still hypothesis until reviewed). Do not cite +0.60.

---

## Standing rule this cost us

A check that cannot fail is decoration, and worse than none, because it is believed.

Here it had a mirror: **a metric that cannot tell signal from parroting.** `goal_referenced` is maximized by verbatim repetition of the goal — the one output that proves the least. Before trusting the next number, mutate what the metric watches and prove it can go down.
