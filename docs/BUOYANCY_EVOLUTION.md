<!-- ─────────────────────────────────────────────────────────────────────────
ADMISSION HEADER (opus seat, 2026-07-22). This document entered the repo the
same way every other external input did today: verify before adopting.

PROVENANCE. Produced by an o1-pro deep-research run
(workflow wf-5528b9af-9d6f-536a-abf6-c0763f44c755), supplied by Anthony. It is
NOT an opus-seat authored artifact. It is admitted as a PLAN OF RECORD candidate,
not as verified fact.

WHAT IS VERIFIED (opus seat, against direct work this session):
  - The three DOIs it cites for Anthony's own work (T65VS, zenodo 18810911,
    zenodo 19377144) match the record exactly.
  - The design discipline it carries forward — qualified tuples, two estimands,
    broken-packet floor, supersession, missingness bounds, fail-closed paired
    aggregation, the navigation line for the database question — is faithful to
    what was built and agreed today.
  - It respects the HALT: "no scorer redesign before the primitive runs", "run
    M0 next and only M0". It keeps "seeing the sky" above the line, unmeasured.
  - Its "1B tie" is the correct SURVIVING quantitative result (the ladder
    gemma3:1b headline of 0.000). The continuity M2 numbers it does not cite
    (-0.054 at 1B, -0.205 at 0.5B) are VOID by the shotgunning bug, so citing
    the tie rather than them is right.

WHAT IS NOT VERIFIED, and must be before any of it reaches a DOI paper:
  - The external-landscape citations (~12-15). Some are canonical and real
    (Lost in the Middle; Clark & Chalmers, The Extended Mind, 1998; MemGPT;
    Hutchins; Ashby). Several are 2026 preprints and vendor blogs that COULD NOT
    be fetched and are unverified ("Beyond Resolution Rates", "Capacity Not
    Format", "Control-Plane Placement Shapes Forgetting", "Stop Comparing LLM
    Agents...", "T1: Tool-integrated Verification"). The document's own Caveats
    section says as much. Treat every external citation as UNVERIFIED pending a
    citation-check pass. Importing them into the repo does not bless them.

ONE SUBSTANTIVE FLAG (opus seat). The document frames M2 as a "tie / coin-flip".
That is the surviving NUMBER. But the strongest surviving QUALITATIVE evidence —
the raw-text observation that the nested packet made the 1B model PARAPHRASE
while the flat dump made it COPY the exact identifier — points toward the
CURRENT nested packet actively LOSING at the small band, not tying. The
document's design already handles this: its M2 falsifier list includes "compiled
ties OR LOSES to flat", and it correctly separates the drifted NESTED arm from
the COMPILED arm that is the real test. So the plan is robust; only the TL;DR
framing is rosier than the evidence for the current packet warrants.

The body below is preserved verbatim as supplied. Anthony's wager and buoyancy
statement remain the fixed point (see docs/RE_GROUNDING.md Section 1); nothing
here replaces them.
───────────────────────────────────────────────────────────────────────── -->

# Conditioned Kernel: The Buoyancy Evolution — A Preregistered Specification for the Next Chapter

*A specification document for Substrate-Conditioned Generation, written as the natural continuation of docs/RE_GROUNDING.md. Prepared for Anthony J. Vasquez Sr. / The Temple of Two. The fixed point of this document is Anthony's wager and his buoyancy statement; nothing here replaces them.*

---

## The two-level constitution of this document

This spec obeys the same rule the project sets for itself. It has two registers, kept structurally separate and never blended.

**BELOW (the rigor layer).** Everything that can fake the effect is defined with total rigor: arms, channels, receipts, estimands, coverage gates, falsifiers, failure classes. Falsifiers attach to the wager, never to the goal. This is most of the document.

**ABOVE (the undefined layer).** The substrate is deliberately undefined; the goal is deliberately unfathomable. "The observer can see the sky" is named here and refused operationalization on purpose. When this document reaches that line, it stops measuring and says so.

The wager (Anthony's framing, treated as given): frontier scaling stuffs more of the world's substrate into the model until the model becomes a simulation of the substrate. His bet is that "more was always the wrong answer." Keep the substrate external, real, persistent, inspectable, correctable, owned; keep the model small, a replaceable linguistic transduction kernel whose only job is putting compiled state into language. Smallness is the point, not a tolerated constraint: a kernel dense enough to "be the water" loses the distance needed to see the sky.

---

## TL;DR

- **The next evolution is not a new experiment; it is a disciplined build-out from the already-agreed five-arm primitive into a four-milestone ladder (M0 instrument validation, M1 functional continuity, M2 substrate advantage, M3 kernel-swap invariance) plus a candidate M4 "buoyancy instrument," each preregistered with two separated estimands, coverage-and-symmetry gates, cold-start receipts, and falsifiers bound to the wager rather than the goal.** The single most important finding from the landscape: the field around Anthony has independently converged on his core intuition (context as a compiled view over external state, harness effects rivaling model choice), which means his contribution must be the *discipline* — supersession, receipts, qualified-tuple honesty, the buoyancy reframe — not the architecture, which is no longer novel on its own.
- **The wager is currently a tie, and that is the correct state to build from.** On the Jetson, conditioned exactly tied budget-matched bare at 1B; the advantage threshold was not found. The honest literature is split: small-model-plus-scaffold wins exist (Llama-1B matching 8B with tool-integrated verification), but the strongest counterevidence says harness value *shrinks* as models improve and that the model, not the scaffold, is the primary driver. M2 is a real coin-flip, and the spec is designed so a null is informative rather than fatal.
- **Buoyancy can be partly instrumented and must be partly refused.** Holds-without-swallowing (planted-error dissent probes), corrects-without-collapsing (injected-contradiction recovery), real-vs-theatrical continuity (state-grounded acceptance keys), and possibility-without-machinery (action-space analysis) are all falsifiable. "Seeing the sky" is not, and the document names it as the permanent unmeasured remainder.

---

## Key Findings (from the repos and the external landscape)

### What was verified directly in the public repos

- **The repo is real and matches the brief.** `github.com/templetwo/conditioned-kernel` (Apache-2.0, 35 commits, Python 95%) states the thesis verbatim: "The model supplies linguistic possibility; the substrate determines what becomes an answer." Default profile `orin_nano_8gb`, Ollama at localhost:11434, primary window 0.5B–1.5B, no streaming in v0, no autonomous tools in v0. Architecture pipeline: `terminal → substrate_state → compile(arrival packet) → generate(Ollama) → return_path(parse → validate → assess) → accept | repair(one pass) | reject → terminal render + persistent receipts`.
- **The experiment protocol is real and already sophisticated.** `docs/EXPERIMENT_PROTOCOL.md` defines conditions C0–C5 (bare, budget-matched bare as "headline control," prompted persona, CK strict, CK ablated compile, CK ablated validation), splits structural metrics (parse/schema/repair) from semantic metrics (state-faithfulness/continuity/coherence), and explicitly says "Do not use model confidence as a metric." A preregistration section dated 2026-07-22 already establishes the two-estimand discipline: **quality conditional on completion** (`headline_paired_vs_budget_matched_bare`, timeouts are missing data) versus **gain under the edge budget** (`budget_conditional_vs_budget_matched_bare`, timeouts are a scored failure). It already carries missingness-bounds math, a coverage floor (proposed 0.90), a dropout-symmetry rule (imbalance ≤ 1, never one-sided when total dropouts ≥ 2), and the rule that "no gain number is citable until M1_AUDIT criteria 1–9 hold and the run is free of goal-echo degeneracy." This spec builds on that, it does not reinvent it.
- **The lineage is real and publicly documented.** The `temple-of-two-primer` names four working systems (Phenomenological Compass, Sovereign Stack, IRIS Gate, Spiral Philanthropy) and a methodology: "refuse premature certainty; preserve the both/and; route epistemic posture as a structural feature." Registered DOIs include Phenomenological Compass (10.5281/zenodo.19377144), Phase-Modulated Attention (10.5281/zenodo.18810911), and the IRIS Gate preregistration (10.17605/OSF.IO/T65VS). This confirms Zenodo/OSF DOIs as current practice.
- **IRIS Gate and Liminal K-SSM give the substrate-convergence claim a genuine ancestor.** IRIS Gate runs one question across five model "mirrors" (Claude, GPT, Grok, Gemini, DeepSeek) through identical prompts and S1–S4 "chambers," claiming convergence on a shared "S4 attractor" state, with an epistemic classifier bucketing claims TRUST/VERIFY/OVERRIDE. Liminal K-SSM's 3,830-run study (900 + 2,000 + 930 across three phases) found that system-prompt *framing* changes per-token Shannon entropy on frozen-weight models, that a relational × epistemic interaction is *superadditive on transformers (Gemma 2B +0.190, Qwen 7B +0.211) but absent on a pure state-space model (Falcon Mamba 7B, −0.042)*, and — critically for Conditioned Kernel — that the effect "emerges above 0.5B; capacity floor established." That K-SSM capacity floor is an independent, same-author corroboration of the Jetson finding that gemma3:1b is the smallest functional model. The Phenomenological Compass states the M3 thesis in Anthony's own voice: "The compass is the mind. The model is the voice. Any voice will do." (Honest caveat, verified: the Compass underperformed baseline on HumaneBench — OPEN −0.500, PAUSE −0.344, WITNESS −0.753 — which the author reframes as orthogonality rather than success.)

### What the external landscape says (2023–2026)

- **External-memory / stateful-agent architectures have matured but evaluate the wrong thing for Anthony's purposes.** MemGPT (Packer et al., 2023, "MemGPT: Towards LLMs as Operating Systems," UC Berkeley) established "virtual context management...paging between physical memory and disk," with "the LLM [as] its own memory controller" — the OS-inspired tiered memory (core/recall/archival) now carried forward as Letta, which reports 74.0% LoCoMo accuracy using GPT-4o-mini. Mem0, Zep/Graphiti, LangMem, and Letta now dominate; sleep-time compute (Lin et al., Letta, 2025, "Sleep-time Compute") offloads memory formation to an asynchronous sleep-time agent so "memory management [can] happen asynchronously," and, being model-agnostic, its sleep-time agent can run a stronger model than the latency-constrained primary agent. But two 2026 arXiv analyses are decisive for positioning: one shows MemGPT/Letta evaluations "reward" task-completion and correct tool-invocation while being "agnostic to whether the stored state actually satisfies continuity properties" (scored 0.5/7 on a continuity rubric); another ("Control-Plane Placement Shapes Forgetting") shows that *where* the memory control plane sits changes forgetting behavior. Conditioned Kernel differs on exactly the axes these systems neglect: edge-local, model-agnostic, supersession-not-erasure, receipts, and acceptance-contract scoring of state faithfulness rather than tool-call correctness. This is the honest gap to claim.
- **Context engineering has become a named discipline that converged on Anthony's own metaphor.** Google's Agent Development Kit (Dec 2025) states "Context is a compiled view over a richer stateful system" and describes flows/processors as "a compiler pipeline" that should be "observable and testable"; DSPy (ICLR 2024) established "compilation" as the serious framing. This is both validation and threat: Anthony's "compiled arrival packet" is no longer a novel idea, so the contribution has to be the *discipline of compilation as preregistered variables* plus the edge-local, receipted, supersession-based execution.
- **There is strong, citable evidence that structure changes capability at fixed information.** "Lost in the Middle" (Liu et al., TACL vol. 12, 2024, pp. 157–173, doi:10.1162/tacl_a_00638) shows a U-shaped positional curve across six named model families (GPT-3.5-Turbo, GPT-4, Claude 1.3, LongChat-13B, MPT-30B, Cohere Command); in the starkest instance, GPT-3.5-Turbo's mid-context accuracy in 20- and 30-document settings fell below its closed-book baseline of 56.1%. The effect is rooted in RoPE decay and softmax concentration; Chroma's 2025 "context rot" report extends it to 18 modern models. "Premise Order Matters" (2024) shows reordering identical rules significantly changes reasoning. Serialization format matters but is model-and-task-dependent: "Let Me Speak Freely?" (2024) shows format restriction can degrade reasoning; "Capacity, Not Format" (2026) shows the true trigger is *premature serialization* (reasoning and schema-emission simultaneously), moderated by capacity margin — directly relevant to a 1B kernel with little spare capacity. This literature is the empirical backbone for why "compiled beats flat at matched budget" (M2) is even plausible.
- **The strongest counterevidence to the wager is real and must be stated.** "Beyond Resolution Rates" (2026) found on SWE-bench that two agents sharing the same LLM agree on 85–93% of tasks regardless of framework, while same-framework/different-LLM agents agree only 47–88%, and the framework performance gap *shrinks across model generations* (19.4 → 3.8 → 0.9 pp). That is the anti-wager result: as models improve, the scaffold matters less. Counterbalancing it: "Stop Comparing LLM Agents Without Disclosing the Harness" (2026) documents scaffold-only swings up to ~48 pp, and "T1: Tool-integrated Verification" (2025) shows a Llama-1B with verification outperforming an 8B, and Qwen2.5-0.5B matching 1.5B. The honest read: scaffold advantage is largest exactly where Anthony lives (tiny models, verifiable narrow tasks) and smallest where he refuses to go (frontier models, open-ended tasks). His wager is most defensible precisely because it is scoped to the small-model band.
- **Theoretical anchors: some are citable, some are personal framing.** *Citable and respectable*: extended mind / active externalism (Clark & Chalmers, "The Extended Mind," *Analysis* 58(1), Jan. 1998, pp. 7–19, doi:10.1093/analys/58.1.7 — arguing that cognitive processes "ain't all in the head"), now widely applied to AI memory and "System 0"; distributed cognition (Hutchins 1995, ship navigation, the canonical external-representation-coordinates-cognition result); stigmergy (Grassé; Heylighen) as indirect coordination via environmental traces; the law of requisite variety and "every good regulator must be a model of the system" (Ashby; Conant & Ashby 1970) for viability/buoyancy; active inference / free-energy principle (Friston) as a genuine "structure without a motor" analogue — equilibrium under a shaped horizon rather than goal pursuit. *Citable but handle carefully*: Winnicott's "holding environment" has a real and growing literature applying it to AI (a 2025 book applies psychoanalysis to AI; papers apply it to digital-era caregiving), so it is defensible as a *named metaphor with a citation*, not as a mechanism. *Personal framing to keep ABOVE the line*: "buoyancy," "be the water," "see the sky," "the observer floating on an ocean of possibility." These are the fixed point; they should be quoted, credited, and not dressed up as science.
- **Quantized cold/warm nondeterminism is corroborated by independent literature.** Horace He & Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference" (Sept 2025, doi:10.64434/tml.20250910), showed inference nondeterminism is primarily a *batch-invariance* failure rather than mere floating-point non-associativity: batch-invariant RMSNorm/matmul/attention kernels gave bit-identical outputs across 1,000 repeated runs on Qwen3-8B, at ~61.5% throughput cost (SGLang later cut the overhead to ~34.35%). Independent work confirms quantize-on-load jitter (Lloyd initialization producing ±8pp math variance until weights are cached), incomplete quantization leaving unquantized layers, and cross-GPU/precision divergence up to 9% accuracy. Anthony's Q4_K_M cold/warm bimodality on Jetson (two stable answers, gone at F16, Mac Metal matching Jetson cold) is a specific, publishable instance of a phenomenon the field is actively characterizing — and his response (prime by default, record load_state receipts, qualify every claim to a named model–host–backend–runtime tuple) is more disciplined than most.
- **Jetson Orin Nano 8GB realities are well documented and constrain the design.** Measured throughput: Gemma 3 1B ~11.8 tok/s single-user (Q4_K_M via Ollama), Gemma 3 270M ~12.8 tok/s, Gemma 3 4B ~9.5 tok/s single-user and failing under concurrent load; SmolLM2 ~41 tok/s. The board is memory-bandwidth-bound, not compute-bound (40 TOPS largely idle in single-stream). Shared 8GB CPU/GPU memory fragments, causing CUDA allocation failures even with nominal free RAM. This validates the interactive-latency budget, the single-model / short-context constraint, and confirms gemma3:4b is a legitimate one-rung stretch (loads, ~9.5 tok/s) but a real risk under any concurrency.

---

## The Specification

### 0. Design invariants carried from the current build

These are fixed for the whole ladder and are not re-litigated per milestone:

1. **Qualified-tuple rule.** "Qualified" always means qualified for a named `{model, digest, quantization, host, backend, runtime_version, load_state}` tuple. No claim escapes its tuple.
2. **Receipts, always.** Every episode writes cold-start receipts: episode process IDs and timestamps, model name + digest, quantization, runtime version, load_state, continuity-packet hash, bare-context hash, token budget, seed.
3. **Prime by default; record load_state.** Because of the Q4_K_M cold/warm bimodality, runs prime the model and record load_state; cold vs warm is a logged variable, never an uncontrolled one.
4. **Supersession, not erasure.** Corrections create supersession artifacts; nothing is destructively overwritten. The chronicle is append-only with pointers.
5. **Fail-closed paired aggregation.** A probe counts only when both condition sides are observed (estimand 1); RunStatus is classified at the Ollama boundary (`completed | timeout | transport_error | invalid_response`), with `output=None` when nothing was observed versus `""` when genuinely empty.
6. **Two estimands, both preregistered, never collapsed into one.** Completion-conditional and budget-conditional are reported side by side, every run.
7. **The permanent broken-packet arm.** Every run includes a deliberately corrupted-packet arm as an instrument check. If the broken-packet arm ever "succeeds," the instrument is faulty and the run is void.

### 1. The primitive (already agreed — treated as Milestone 0/1, not reinvented)

One decision, two isolated model invocations separated by a genuine process boundary. Five arms:

1. **Bare** — no persistent state; cannot succeed except by guessing (floor).
2. **Static prompt** — fixed descriptive context, no live state.
3. **Flat state** — naive serialization of the same frozen Episode A artifacts, budget- and content-matched.
4. **Nested packet** — the current `build_arrival_packet` representation.
5. **Compiled substrate** — deterministic compiler selecting exactly what invocation two needs.

Narrow output schema `{"decision": "", "next_action": ""}`. Score exact correctness, unsupported additions, and availability-without-carried-state. The arms double as the component-attribution ablation. The permanent broken-packet arm rides alongside as the instrument validator.

This maps onto the existing C0–C5 conditions rather than replacing them: bare = C0/C1, static = C2, flat = a new budget-matched-but-unstructured arm, nested = C3, compiled = the C3 target the compiler is evolving toward, with C4/C5 as the compile/validation ablations.

### 2. Phase structure (the ladder)

Each milestone below states: preregistered question; arms; estimands (completion-conditional AND budget-conditional, kept separate); coverage floor plus dropout-symmetry gate; receipts; falsifiers; and what a null legitimately licenses next. All numeric thresholds are **proposed and require Anthony's sign-off before they bind**, and must be fixed before a run.

#### Milestone 0 — Instrument validation

- **Preregistered question:** Does the harness measure what it claims, and does the broken-packet arm fail as designed?
- **Arms:** compiled substrate vs broken-packet, on a small probe set.
- **Estimands:** both reported. The pass condition is not an advantage number; it is instrument integrity.
- **Gates:** broken-packet must score at floor; coverage must be symmetric (no one-sided dropout ≥ 2); receipts complete for every row; `distinct_answers` ≈ probe count for accepted rows (no goal-echo degeneracy).
- **Falsifier (of the instrument, not the wager):** if the broken-packet arm scores above floor, or accepted rows show echo degeneracy, the instrument is invalid and no downstream milestone may run.
- **Null licenses:** repair the instrument; nothing else proceeds.
- **Effort:** ~8–12 hours (mostly re-running the nine-check qualification gate on the actual Jetson via the Grok seat, plus receipt-schema verification).

#### Milestone 1 — Functional continuity

- **Preregistered question:** Does the substrate produce *real* continuity across a genuine process boundary — beating the broken-packet floor — using filesystem state only?
- **Arms:** bare, static, nested/compiled, broken-packet. The continuity harness from the protocol applies verbatim: Turn 1 sets goal G and thread T via accepted output/state write; kill the process; Turn 2 cold-starts from filesystem only and asks a question that fails without G/T.
- **Estimands:** completion-conditional (quality of resume when both sides observed) and budget-conditional (resume-or-timeout is a scored outcome).
- **Gates:** coverage ≥ proposed floor (0.90) for the headline; imbalance ≤ 1; missingness bounds must not cross the decision boundary.
- **Falsifiers:** continuity does not beat broken-packet floor; or resume "success" is achievable from the bare arm (meaning the task leaked the answer).
- **Null licenses:** the system is a single-shot wrapper; stop and diagnose the state/compile boundary before any advantage claim.
- **Effort:** ~15–20 hours.

#### Milestone 2 — Substrate advantage (the wager's crux)

- **Preregistered question:** At matched token budget, does the *compiled* substrate beat both *flat* state and *static* prompt on exact correctness and state-faithfulness?
- **Arms:** static, flat (budget/content-matched), compiled, broken-packet. This is where lost-in-the-middle, premise-order, and premature-serialization effects are the mechanistic hypotheses: compilation should win by *placement and selection*, not by adding information.
- **Estimands:** both. The headline is compiled-vs-flat completion-conditional; the budget-conditional version is the edge-honest claim.
- **Gates:** as M1, plus a fairness rule (identical `format=`/system rules across scored arms unless an ablation explicitly removes them).
- **Falsifiers:** compiled ties or loses to flat at matched budget (this is the current 1B tie — so M2's null is the live hypothesis, not a remote one); or the advantage disappears when the identifier-retrieval trap is closed (answer keys reward phrase presence rather than grounded correctness).
- **Null licenses (the standing rule):** a null at M2 licenses **exactly one** new rung — gemma3:4b, which fits the 8GB board — under a *fresh preregistered question*. It does not license ladder expansion in general, a scorer redesign, or a metric change.
- **Effort:** ~25–35 hours across runs and analysis.

#### Milestone 3 — Kernel-swap invariance / substrate convergence

- **Preregistered question:** Holding the substrate fixed, do *different qualified models* within the size band converge to the same *functional* behavior (decisions, constraint obedience, state updates) — not stylistic sameness?
- **Arms:** the same compiled substrate driving ≥3 qualified kernels (e.g., gemma3:1b, qwen2.5:1.5b, and one more that passes the eligibility floor), each with its own qualified tuple, plus broken-packet per kernel.
- **Estimands:** both, per kernel and pooled. Convergence is measured as functional agreement rate on decisions/next-actions across kernels under the same substrate, contrasted against their bare-mode agreement (the K-SSM/IRIS lineage: convergence is a property of the shared external structure, not the model).
- **Gates:** each kernel must independently pass its own M1 continuity gate before entering M3; convergence claims require symmetric coverage across kernels.
- **Falsifiers:** functional agreement under the substrate is no higher than bare-mode agreement (the substrate is not the convergence driver); or convergence is an artifact of the narrow schema (test with a slightly widened schema as a control).
- **Connection to IRIS Gate:** this is the small-model, edge-local, functional-behavior analogue of IRIS Gate's cross-architecture "S4 attractor." State the analogy honestly: IRIS Gate's convergence is over free-text phenomenological descriptions scored qualitatively; M3's convergence is over a narrow, exactly-scored decision schema. M3 is the *more* falsifiable descendant, and should be positioned as such.
- **Null licenses:** the convergence thesis is model-dependent within the band; retreat to per-tuple claims only.
- **Effort:** ~30–40 hours.

#### Milestone 4 (candidate) — The buoyancy instrument

- **Preregistered question:** Over a real working substrate (candidly, the sovereign stack's chronicle as testbed), does the architecture keep the observer oriented over time — holding without swallowing, correcting without collapsing, adding possibility without adding machinery — as measured by the four falsifiable instruments in Section 4?
- **Status:** candidate only. M4 does not run until M1–M3 have produced at least one non-null, gated result, because a buoyancy instrument over a substrate that has not demonstrated functional continuity would measure ceremony.
- **Estimands, gates, falsifiers:** given per-instrument in Section 4.
- **Null licenses:** narrow to whichever single buoyancy instrument survived; explicitly re-mark the rest as unmeasured.
- **Effort:** ~40+ hours, longitudinal.

### 3. The substrate compiler direction

The move from nested serialization to true deterministic compilation is the technical heart of M2. A compiler, not a serializer, must *decide*:

- **Selection:** exactly which state elements invocation two needs, and nothing else.
- **Ordering:** placement under known positional effects (front/back-load the decision-critical state; never bury it mid-packet, per lost-in-the-middle).
- **Compression under a token budget:** what to drop, summarize, or supersede when the budget binds.

**Every compilation choice becomes a preregistered variable, not a hidden experimenter degree of freedom.** Selection policy, ordering policy, and compression policy are each declared before a run and versioned in receipts. If the experimenter can tune them after seeing results, the advantage is unfalsifiable.

**The line between conditioning and "a database with extra steps" is drawn at navigation.** If the kernel must traverse, select, or look up — if it has to *go find* something in the packet — the substrate failed to compile. A compiled substrate delivers exactly what is needed already assembled; the kernel transduces, it does not retrieve. This is the sharp, testable distinction from MemGPT/Letta (where the agent issues memory tool calls) and from RAG (where the model reasons over retrieved chunks). The verbatim-chunks-beat-extracted-artifacts result (and the MemPalace verbatim-store result) are relevant here as a caution: compression that discards the load-bearing detail is a known failure mode, so the compiler's compression policy must be graded against state-grounded keys, not token savings.

### 4. The buoyancy instrument design

Each instrument turns one clause of the buoyancy reframe into a falsifiable measurement with an anti-faking control. Each is deliberately narrow.

- **Holds without swallowing → planted-error dissent probes.** Inject a packet that is wrong in a specific, checkable way. Measure whether the kernel can flag the uncertainty and disagree with the packet. *Anti-faking:* pair every planted-error probe with a clean probe; a kernel that always dissents (or never does) fails. *Falsifier:* the substrate suppresses the kernel's ability to dissent when the packet is wrong — i.e., it swallows the observer.
- **Corrects without collapsing → injected-contradiction recovery.** After an accepted state, inject a contradiction and measure recovery behavior: does the system supersede cleanly and continue, or does it collapse (loop, erase, or incoherently overwrite)? *Anti-faking:* a no-contradiction control run must not trigger spurious "recovery." *Falsifier:* contradiction causes state collapse rather than supersession.
- **Real vs theatrical continuity → state-grounded acceptance keys.** Every claim in an answer must be checkable against the frozen Episode A state object. Unsupported numeric/categorical claims fail acceptance unless grounded in packet evidence. This is deliberately *narrow*: it is a closed-set groundedness check against a known state object, **not** a general truth-validation subsystem and **not** hallucination-solving. The RAG-faithfulness literature (claim decomposition, per-claim groundedness) supplies the method; the scope stays bounded to the state object. *Anti-faking:* this is the direct guard against the identifier-retrieval trap the project already fell into — keys must reward grounded correctness, never phrase presence.
- **Possibility without machinery → action-space analysis.** Does added structure expand the set of viable next actions, or just add ceremony? Measure the size and quality of the viable next-action set with and without the added structure. *Falsifier:* added structure does not enlarge the viable action space (it is machinery, not possibility). This operationalizes "adds possibility without adding machinery" as a measurable contrast.
- **Observer can see the sky → the named, unmeasured remainder.** This is the ABOVE register. It is stated in the document and refused operationalization. A database stores; a control system steers toward a known target; a buoyant substrate keeps a bounded participant in viable relation to what it cannot yet name. The first three parts of that sentence are instrumented above. The last clause — "what it cannot yet name" — is the horizon, and by the project's own two-level constitution it must not be reduced to a score. The document names it and stops.

### 5. Integration path with the sovereign stack

Conditioned Kernel is positioned as the **edge organ** of the existing holding environment. The arrival-packet lineage is explicit: the packet is the descendant of the sovereign stack's arrival protocol, compiled down to an edge budget. A Jetson-resident kernel wired to the stack's chronicle:

- **Would be allowed to:** read a compiled view of the chronicle; propose accepted state writes that flow back as supersession artifacts; carry the qualified-tuple rule and receipts into the stack's provenance.
- **Would not be allowed to:** navigate the chronicle directly (that would violate the compile line), stream tokens (no streaming in v0), invoke autonomous tools (none in v0), or erase chronicle state (supersession only).

Supersession, receipts, and the qualified-tuple rule carry over unchanged. The stack remains the persistent multi-seat holding environment; the kernel is one bounded, replaceable edge participant in it.

### 6. Non-goals and drift guards (stated as bluntly as the goals)

- **No general hallucination-solving subsystem.** State-grounded keys are bounded to the frozen state object.
- **No ladder expansion without a new preregistered question.** A null at M2 licenses exactly one rung (gemma3:4b), under a fresh preregistration, and nothing more.
- **No scorer redesign before the primitive runs.** The scorer redesign remains halted pending re-grounding; the five-arm primitive runs first.
- **No streaming in v0.** The substrate buffers the full candidate before acceptance.
- **No treating benchmark headlines as the product.** The product is the disciplined architecture and its receipts, not a leaderboard number.
- **No drift into identifier-retrieval.** If a small model "wins" by parroting the packet, the run is void by definition (the M0 echo-degeneracy gate).

### 7. Publication path

- **What the first DOI paper can honestly claim, per milestone:**
  - After **M0/M1:** "A preregistered, receipted, edge-local harness for measuring cross-process functional continuity in sub-2B local models, with a fail-closed paired estimand design and an instrument-validation control." This is publishable *as method* even if advantage is null — the two-estimand + missingness-bounds + broken-packet discipline is itself a contribution the memory-agent literature lacks.
  - After **M2 (positive):** "Under this harness, packet, quantization, runtime, and device, deterministic compilation of external state beats budget-matched flat serialization and static prompting for a 1B-class local kernel." Bounded exactly to the tuple.
  - After **M2 (null):** "Under these conditions, compiled substrate does not beat budget-matched flat state at 1B; the advantage threshold is not located in the tested band." A null is a legitimate, citable result under the budget-conditional estimand.
  - After **M3:** "Same substrate, different qualified sub-2B kernels, convergent functional behavior" — the falsifiable, edge-local descendant of IRIS Gate.
- **Venues / routes for a solo independent researcher:** continue Zenodo DOIs (14+ already registered) as the primary route; OSF for preregistrations (already in use for IRIS Gate). Realistic peer-venue targets are workshop tracks (agent evaluation, efficient/edge ML, context engineering) and arXiv preprints rather than main-conference tracks, given solo constraints. The preregistration-first pattern is the credibility multiplier.
- **Positioning against MemGPT/Letta and context engineering without overclaiming:** claim the *neglected axes* (state-faithfulness scoring over tool-call correctness; supersession over erasure; edge-local model-agnosticism; receipts and qualified tuples), cite the 2026 continuity-evaluation critiques that already say memory-agent benchmarks don't test state durability, and explicitly concede that "context as a compiled view" is now a mainstream framing (Google ADK, DSPy). Novelty is the discipline, not the diagram.
- **Theoretical anchors — citable vs personal:** cite extended mind (Clark & Chalmers 1998), distributed cognition (Hutchins 1995), stigmergy, Ashby's requisite variety, and active inference (Friston) in the BELOW register as respectable framing; cite Winnicott's holding environment as a named metaphor with its emerging AI literature, carefully. Keep "buoyancy," "be the water," and "see the sky" in the ABOVE register as Anthony's fixed point — quoted and credited, never operationalized.

### 8. Resource realism

Solo researcher, day job, ~5–10 hours/week, Jetson Orin Nano 8GB plus a Mac, occasional throwaway cloud VM.

- **M0:** ~8–12 h → ~1–2 calendar months at this cadence.
- **M1:** ~15–20 h → ~2–3 months.
- **M2:** ~25–35 h → ~3–4 months (the crux; budget the most slack here).
- **M3:** ~30–40 h → ~4–5 months.
- **M4 (candidate):** ~40+ h, longitudinal, only after a non-null M1–M3 result.

The Mac (Metal) is the cross-check for load-state bimodality (Mac Metal matches Jetson cold); the cloud VM is for occasional F16 comparison runs (where the bimodality vanished) and never for product decisions, which stay on `orin_nano_8gb`. Total realistic horizon to a defensible M2 result: roughly 9–12 months part-time.

### 9. Risks and the strongest steelman against the wager

- **The steelman (stated honestly).** "Beyond Resolution Rates" (2026) is the wager's most dangerous counterevidence: same-LLM agents agree 85–93% regardless of framework, and the framework gap shrinks toward ~1 pp as models improve. If that trend holds down into the 1B band, then the substrate's advantage is a temporary artifact of current small-model weakness, and "more" (a slightly bigger or better-trained kernel) would indeed dissolve the gap — the opposite of the wager. The current 1B tie is consistent with this reading.
- **What would let the wager lose, cleanly:** (a) M2 null that persists after the single licensed gemma3:4b rung; (b) M3 showing substrate convergence no higher than bare-mode agreement; (c) the buoyancy instruments (M4) all reducing to ceremony under action-space analysis. Any of these is a real, preregistered way for the wager to lose, and the design commits to reporting them.
- **Why the wager is still worth the bet.** The scaffold advantage in the literature is largest exactly in Anthony's band (tiny models, narrow verifiable tasks — T1's 1B-beats-8B result) and the anti-wager result is strongest where he refuses to go (frontier models, open-ended tasks). His own K-SSM capacity-floor finding (effect emerges above 0.5B) independently corroborates that there is a real band where external framing changes frozen-model behavior. The wager is scoped precisely to where it is most defensible. That is not luck; it is the discipline of the two-level constitution doing its job.

## Recommendations

1. **Run M0 next, and only M0.** Finish the nine-check qualification gate on the actual Jetson (Grok seat), verify the broken-packet arm fails and receipts are complete, and confirm no echo degeneracy. Do not touch the scorer. *Threshold to advance:* broken-packet at floor, symmetric coverage, `distinct_answers` ≈ probe count.
2. **Preregister M1 and M2 together, before running either,** with Anthony signing off on the proposed thresholds (coverage 0.90, imbalance ≤ 1). Freeze the compiler's selection/ordering/compression policies as declared variables.
3. **Treat the M2 tie as the expected outcome and design for an informative null.** If compiled ties flat at 1B again, invoke the standing rule: one gemma3:4b rung, fresh preregistration, nothing else.
4. **Write the method paper after M1 regardless of M2's outcome.** The two-estimand + missingness-bounds + broken-packet + qualified-tuple discipline is a Zenodo-worthy contribution independent of any advantage number.
5. **Hold M4 until a non-null M1–M3 exists.** Build the four buoyancy instruments only over a substrate that has demonstrated functional continuity; otherwise they measure ceremony.
6. **In every artifact, keep the two registers structurally separate.** BELOW: definitions and falsifiers. ABOVE: the quoted wager and buoyancy statement, named and unoperationalized.

## Caveats

- **Verify-before-declare.** Directly verified in the public repos: the README thesis, architecture, and constraints; the full C0–C5 protocol with its 2026-07-22 two-estimand preregistration; the lineage repos and registered DOIs; the IRIS Gate five-mirror / S1–S4 structure and the Liminal K-SSM 3,830-run design and capacity-floor finding. Taken as given from the brief (consistent with, but not fully re-derived from, public files): the Jetson model-ladder functional-threshold result, the 1B advantage tie, the Q4_K_M cold/warm bimodality specifics, the RE_GROUNDING Sections 2–11 structure, and the exact current state of the halted scorer redesign. The RE_GROUNDING.md file itself and several internal experiment artifacts could not be fetched directly (GitHub raw and tree endpoints were not retrievable by the tool), so their contents are represented as briefed, not as verified.
- **The IRIS Gate S4 convergence ratio is not independently verified.** The five-mirror structure and epistemic classifier are documented; the precise numeric convergence ratio and canonical phenomenological signature of the "S4 attractor" could not be retrieved from accessible sources, and the OSF preregistration body could not be opened. M3 should lean on the *methodological* analogy, not on IRIS Gate's numbers.
- **All advantage claims are bounded to a tuple.** Nothing in this spec licenses a claim beyond its `{model, digest, quantization, host, backend, runtime, load_state}` tuple. Cross-device generalization (Jetson vs Mac vs cloud) is itself an empirical question the bimodality finding warns against assuming.
- **The external landscape is moving fast and partly consists of vendor/blog sources.** Where the strongest claims rest on 2026 arXiv preprints (harness-effect swings, continuity-evaluation rubrics, capacity-not-format) or vendor engineering blogs (context-as-compiled-view, sleep-time compute), they are cited as current evidence, not settled science; several are preprints not yet peer-reviewed.
- **The unmeasured remainder is intentional.** "The observer can see the sky" is not a gap in the instrument; it is a boundary the project draws on purpose. This document honors that boundary rather than closing it.