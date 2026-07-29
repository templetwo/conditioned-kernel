# Research Landscape — Where This Work Sits

**Purpose:** the positioning layer for the conditioned-kernel paper. Seven Opus
literature surveys (fan-out 2026-07-29, ~130 citations, every one confirmed
against live search results; independent audit found **zero fabrications, zero
drops, seven minor errata** — see `landscape_surveys/CITATION_AUDIT.md`) were
synthesized into this document by the review seat. The full surveys with
complete citation lists live in [`landscape_surveys/`](landscape_surveys/).
This file is the map; those files are the territory.

**The one-sentence posture, everywhere:** almost every phenomenon we observed
is a known class in some literature. The contribution is the instrument, the
receipts-grade public evidence, the measurements the field does not currently
produce, and the framing — and the paper is *stronger* for saying that first.

---

## 1. The framing spine: the black-box question (survey G)

The "is AI a black box?" debate runs on tracks that rarely meet: the opacity
taxonomies (Burrell's three forms; Ananny & Crawford's transparency-is-not-
accountability), the interpretability skeptics (Rudin; Lipton's transparency
vs post-hoc split), XAI's faithfulness crisis (Jacovi & Goldberg; Slack; Ghassemi;
Bansal), auditing/regulation (Raji; Casper's black-box-access-is-insufficient
with its "outside-the-box" category; EU AI Act Arts. 13/50), and the popular
discourse that locates all opacity in the weights (TIME 2024; Amodei 2025).

The closest prior statements of our thesis exist and must be cited as such:
**Salvaggio (2025)** argues in essay form that the industry conflates genuine
mathematical opacity with knowable things (system prompts, deployment config) —
opacity as policy choice, no measurement, no artifact. **Neumann et al. (CHI
2026)** establish empirically that users want to see the system prompts steering
their conversations and that platforms actively conceal them — demand
documented, artifact not built. The cleanest single evidence of the gap: the
leading open local-LLM front end answers "how can I view the final prompt sent
to the provider?" with *browser DevTools*.

**Our reframing, with its bound:** *the black box is smaller than the
experience.* In the measured session the operator's words were 0.56%–14.00% of
model-input bytes; everything else was enumerable application-layer material.
We do not open the weights black box at all — Amodei's problem is untouched and
the abstract must say so. We relocate the opacity question and give an
existence proof that the *surround* can be made completely, honestly,
per-turn inspectable by the person in the conversation, on consumer hardware,
without intervening in what it observes. Pasquale's double metaphor is the
licensed rhetorical close: a black box is both the system nobody sees into and
the recorder that survives the crash — we built the second kind, around the
first.

## 2. Context engineering and memory systems (survey A)

The field has consolidated around our premise: the model is one component in an
information-assembly system (RAG → MemGPT → context-engineering surveys → 2026
harness surveys concluding agent quality is emergent from model × runtime ×
task). The **utilization strand is our closest kin**: Liu's lost-in-the-middle,
Cuconasu's non-monotone relevance, Joren's sufficiency-vs-utilization split
(small models fail to use sufficient context), Hagström's finding that
synthetic benchmarks inflate utilization. ContextCite (Cohen-Wang, NeurIPS
2024) is the methodological gold standard for actual influence claims — and the
reason we make none.

**Where we sit:** F6's admission-vs-authorship distinction ("Context Field is a
gate on what may be said with, not a guarantee of what gets said") is this
strand's central concern, measured in a live companion system rather than a QA
benchmark, with the raw payloads published — which the benchmark literature
never does. Ben Sghaier et al.'s controlled result ("the middleware scaffolding
layer — not the language model — significantly determines agent effectiveness")
said our thesis first in their setting; cite it plainly. What nobody in this
thread reports is the **byte census**: how much of the model's input the human
actually wrote. That measurement is ours.

## 3. Observability and transparency artifacts (survey B)

Every *component* of the Interior View has prior art, and the paper says so in
paragraph one: payload capture is standardized (OTel GenAI conventions),
hash-chained artifact integrity exists (Atlas), trace-as-evidence is
taxonomized, and two 2026 user-facing dashboards exist (TalkTuner-class systems
surface model internals). **The gap is exact:** production observability made
content capture opt-out-by-default; the user-facing systems show internals or
retrieved documents, not the assembled input. Nothing found offers a complete,
content-retaining, published reconstruction of a single inference event
boundary — every byte and its source, every check and its verdict — for a lay
operator on edge hardware, with the share measure explicitly disclaimed as
non-causal and instrument neutrality tested rather than assumed.

**Bounds that matter:** zero-diff observability is one configuration, not a
theorem (cite Mytkowicz on measurement bias). The dashboard has no user study —
we may say it made F3/F6 findable *by us*, nothing more. "Selected but unused"
must be phrased "did not surface in the output" (lexical judgment, not causal).

## 4. Small models and edge deployment (survey C)

The literature already bets our way: SLMs as the future of agentic AI (Belcak),
schema-validity as a production KPI, sub-1B models near-frontier on constrained
tasks. The 93/93 schema-validity is *predicted*; its value is the **paired
trace** showing structurally perfect outputs being rejected by the
substrate — the validity/quality dissociation the field argues in aggregate,
demonstrated per-item. The thinking-channel work is fully anticipated
(hybrid think surfaces are leaky; small models are the worst CoT beneficiaries)
— our addition is the **receipted instrumentation catch**: a ladder score of
0.000 that was an empty read of an unread thinking channel, i.e. a benchmark
number produced by the harness, not the model (`experiments/THINKING_MODE_FINDING.md`,
121.0s / 16,214 thinking chars / 0-char response on the Jetson).

**Own-goal to keep:** DETERMINISM.md's cold/warm VRAM-residency split (F-D1..4)
is a *complementary mechanism* to the batch-invariance literature and is also
the reason F2's byte-identical re-emissions are a substrate-plus-runtime fact,
not a pure model fact. The paper cites its own determinism work against its own
attractor claim. **Number discipline:** the think-flag "no answer in 240s"
wire probe from 2026-07-29 is unreceipted (chat-session only, Mac host); the
receipted figure is 121.0s on Jetson. Do not print 240s without re-running it
into a receipt.

## 5. Validation, guardrails, and self-repair (survey D)

Our courtroom findings land inside a mature skepticism: intrinsic
self-correction doesn't reliably work (Huang), gains are critique-bottlenecked
(Olausson), repair exploits the current draft rather than exploring (REx), and
repair behavior is governed more by orchestration than by the model (Kiecker
2026 — the substrate thesis arrived at independently inside the repair
literature; cite as convergent). **Our repair numbers are a confirmation of
predicted failure conditions, not a challenge to Self-Refine** — budget 1, weak
lexical critique, sub-1B kernel is exactly where the survey literature predicts
failure, and it failed. What we add: an escape-from-attractor metric that works
where there is no oracle (open-ended dialogue has no test suite), the extreme
low-budget regime the benchmarks never occupy, and per-instance receipts.

**Statistical discipline (non-negotiable):** 6/12 escape carries a 95% CI of
roughly 21–79% — print counts, not rates. "7/7 advisory precision" is
"no false fires observed among seven," not a property of the check (no
adversarial contrast set was built — cite XSTest as the bar). "Recall-poor"
becomes "demonstrably blind to three named failure classes" (echo-without-
answer, pasted-context token buffets, stance errors) — a miss taxonomy the
surveyed literature does not have. F3b's deepest point: the true goal *was in
the substrate* — feedback wiring absent, not feedback source weak — a design-
locus diagnosis only per-turn instrumentation could make. The wired-check
counterfactual is untested; say so or run it.

**The forward experiment worth pre-registering** (D6/Chen 2026): re-presenting
a model's failed draft as its own prior thought is the condition under which
correction collapses; relabeling identical content as external lifts correction
rates 23–93pp. Our repair prompt does the former. One-variable change,
re-measure the 63% and the 6/12.

## 6. Degeneration, attractors, and continuity (survey E)

The phenomenon inventory is all known: in-context self-reinforcement, induction
heads as the verbatim-copy mechanism, diversity collapse surviving temperature,
self-consuming loops (training-time and agent-memory). **What the literature
could not hand us is the attribution:** because the attractor survived a full
session reset, dialogue memory is ruled out as carrier — the carrier is durable
project state recompiled into the packet, traceable to specific state records,
with the priming material itself published. Benign, inference-time,
ordinary-store loops are unreported; the adversarial memory-poisoning work is
the nearest neighbor. F3a becomes a reframing: repetition control has an ROC
that belongs to the substrate (a measurable checker horizon), not the model.

**Bounds:** "attractor" is a metaphor — no basin characterized, no perturbation
stability, no half-life; 16 hours is one window. No ablation ran (remove the
implicated state records, re-run, watch it vanish) — F2 is descriptive
co-occurrence until that experiment exists; name it as the reviewer's first
demand and pre-empt it. The 3-before/16-after context-field A/B is an anecdote
with receipts — confounded with the mid-session code deploy — report it and stop.

## 7. Companionship, anthropomorphism, and the phenomenology boundary (survey F)

The stance findings have theory waiting for them: simulacra/role-play framing
(Shanahan), persona-installation as a trained dimension, attribution gates
suppressing experience claims (which makes the kernel's first-person denial
*as uninformative as an affirmation would be* — say this explicitly), and
unanchored deixis predicted for subjectless address. **The small genuine
novelty:** addressee inversion ("answered the right person's question") appears
to have no published detector or measure — define a first-person-question /
second-person-answer rate over the 93-candidate ledger and turn the vignette
into a statistic.

**The exposure to manage:** the 2025–2026 companion-HCI wave is a restraint
literature (dependence outcomes, engagement dark patterns, companion framing
raising attributed mental capacities). Flow mode will be read as removing
friction from an engagement loop and must be defended, not assumed benign. The
defensible design contribution the dark-pattern literature has no name for:
**the system publishes its own adverse verdict on the same receipt as the
answer it delivers anyway** — intent, quality judgment, and the decision to
speak are contemporaneously on the record. And the hardest bound in the whole
paper: Rubin et al. (2025; nine studies, n=6,282) found AI involvement reduces
perceived empathy. Our n=1 builder-operator reporting meaning under full
transparency is *not a counterexample* — different construct, different
outcome. The honest sentence: *we do not test the transparency-relationship
tension; we exhibit one configuration in which full mechanical transparency
coexisted with reported meaning, for one person who built the mechanism.*

**Language ruling for the paper:** replace "the substrate supplies the ontology
the kernel thinks in" (cognition claim from lexical evidence) with "substrate
lexemes recurred as the framing vocabulary of an affectively loaded exchange";
keep the riverbed as a labeled metaphor. "Operational phenomenology of
inference" survives only with its one-sentence boundary definition attached
(everything around the experience-question, nothing inside it) — and three
model seats converging on the name is provenance, not validation.

---

## 8. The contribution inventory (what the paper actually claims)

1. **The instrument.** A complete, byte-exact, per-turn reconstruction of the
   inference event boundary for a lay operator on consumer hardware,
   content-retaining where the industry defaults to content-off,
   non-interventional by construction and by named test.
2. **The corpus.** 93 candidates / 22 full traces / state snapshots / analysis
   scripts, hash-manifested and public (`evidence/session_sess_20260728T031245/`).
   The object being frozen — a study's raw behavioral traces with its scripts —
   is the unusual part, not the freezing.
3. **The measurements the field lacks:** the human-share byte census
   (0.56–14%, labeled non-causal); a distance-resolved detection curve for a
   deployed repetition gate (4/23 at d=1, 0/12 at d≥2); admission-vs-authorship
   coupling for selected context (unused-in-answer 11/26); repair economics at
   budget=1 on sub-1B (counts, with CIs); an attractor whose priming source is
   attributed (durable state, not dialogue) because it survived a session reset.
4. **The design position:** observation-not-gating for the living path with
   strict gates retained for measurement, and the adverse-verdict-on-the-same-
   receipt property.
5. **The method:** multi-seat adversarial construction with receipts-or-silence
   discipline; a preregistration halt with the retired manifest published.

## 9. Standing rules for every claim (synthesis of all seven (c)-sections)

- n=1 session, one kernel family, one host, one operator (who is the author).
  Structural claims may generalize; the percentages may not.
- Byte share is never attention, influence, or causal contribution.
- No claims about model interiority, in either direction; a trained denial
  settles nothing.
- Descriptive throughout: no ablations ran; the named upgrades (state-record
  ablation, NLI-gate baseline, draft-relabeling repair experiment, addressee-
  inversion rate, lexicon-swap control) are listed as unrun.
- We do not open the weights; we relocate the opacity question.
- Counts and CIs, never bare rates, for anything with n under ~30.
- The regime shift is code-confounded (`5a9eb6d` landed mid-session); disclose.
- Exclude the flagged sentience preprint (B:S10) — auditor's caution stands.
- Apply the seven citation errata in `landscape_surveys/CITATION_AUDIT.md`
  at typesetting.

*Synthesized 2026-07-29 by the review seat from seven Opus surveys; audit
trail and full citation lists in* [`landscape_surveys/`](landscape_surveys/).
