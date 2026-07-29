# Domain D — Output Validation, Guardrails, Constrained Generation, and Self-Repair

*Survey for* conditioned-kernel *(Temple of Two). All 19 works below were located via live search/fetch this session; every identifier listed is one I saw in a result page. Note on count: the assignment bundles five distinct sub-literatures (guardrail frameworks, constrained decoding, self-correction, verifier-gating, over-filtering). Fourteen citations would have left one uncovered, so I am returning 19.*

---

## Domain map

This domain is not one field. It is five, and they disagree with each other in ways that matter for how F3/F4/F5/F8 should be written.

**(1) Guardrail frameworks.** The engineering layer that sits outside the model and decides what passes. Two architectural families: *programmable rails* — declarative, interpretable, model-independent policies executed by a runtime (NeMo Guardrails, D14) — and *model-as-guard* — a separate fine-tuned classifier scoring prompt/response pairs against a taxonomy (Llama Guard, D15). A 2024 position paper (D16) argues the whole area lacks systematic requirement specification, verification, and testing methodology, and calls for neural-symbolic implementations plus real verification. That critique is the single most useful framing available for our courtroom findings: **the field already knows its gates are under-specified and under-verified; almost nobody publishes the per-decision evidence.**

**(2) Constrained decoding / structured output.** Mature and largely solved as an *engineering* problem: token-masking against a grammar or JSON Schema gives near-guaranteed syntactic conformance at near-zero overhead (D18 benchmarks six frameworks along efficiency/coverage/**quality**; the quality axis exists precisely because compliance and usefulness came apart). The load-bearing result for us is D19: format restriction *degrades reasoning*, with stricter constraints producing greater degradation. So "100% schema-valid" is a known-weak signal, and the field explicitly separates it from answer quality.

**(3) Self-correction / iterative refinement.** The most contested literature in the domain, and the one our F3/F4 speak to directly. The optimistic wave (D3 Self-Refine, ~20% gains, no training; D4 Reflexion, verbal feedback into an episodic buffer) was met by a hard skeptical turn: D1 showed intrinsic self-correction fails on reasoning and *sometimes degrades performance*; D2 (TACL survey) argued the positive results largely rest on impractical frameworks and unfair evaluations that over-evaluate self-correction, and reframed the question as **when** rather than **whether**. The resolution the field converged on is informational: correction works when the feedback channel carries information the generator does not already have — external tools (D5 CRITIC), oracles, or a stronger critic (D6). Self-correction on one's own unaided judgment does not reliably work.

**(4) Repair economics.** A quantitative sub-literature, mostly in code, that studies what a repair loop actually buys. D6 found gains "modest, highly variable across subsets, sometimes absent" once repair cost is counted, and bottlenecked by feedback quality. D7 reframed refinement as an explore–exploit tradeoff: naive refinement *exploits* the current draft, and needs deliberate exploration (bandit-style) to leave it. D8 (2026) reports repair yield is **error-class-dependent** — assertion/logic errors repair at ~45%, syntax/name errors far higher. D9 (2026) finds the first three-to-four iterations carry nearly all gains, and — critically for our thesis — that **repair behavior is driven more by workflow orchestration and feedback design than by the underlying model**. D11 (2026) decomposes second-pass gains and finds drafts act as *scaffold* even when semantically empty.

**(5) The cost of gating.** Over-blocking is a documented, measured harm, not a rhetorical one. D17 (XSTest) shows models refuse benign prompts that merely share surface language with unsafe ones — false refusals driven by lexical pattern-matching. D10 (2026 audit, 21 open-weight models) states it flatly: **refusal rates are a poor proxy for safety**, with conservative families over-refusing and permissive ones over-complying. This is the literature F8 must be argued against, and it partly supports F8 and partly indicts it.

Two structural gaps run through all five: the evidence is overwhelmingly **batch, closed-task, oracle-scored** (HumanEval, MATH, GSM8K, safety benchmarks), and raw per-decision traces are almost never published. Nobody in this domain is doing per-turn, open-ended, sub-1B, edge-hardware, receipts-grade instrumentation. That absence is our opening, and it is an opening about *instruments*, not about phenomena.

---

## Key works

**Self-correction: the optimistic wave**

1. **Self-Refine: Iterative Refinement with Self-Feedback** — Madaan, Tandon, Gupta, Hallinan, Gao, Wiegreffe, Alon, Dziri, Prabhumoye, Yang, S. Gupta, Majumder, Hermann, Welleck, Yazdanbakhsh, Clark. NeurIPS 2023. arXiv:2303.17651. *Single LLM as generator, feedback-provider, and refiner; ~20% average improvement across 7 tasks; no training or RL.*
2. **Reflexion: Language Agents with Verbal Reinforcement Learning** — Shinn, Cassano, Berman, Gopinath, Narasimhan, Yao. NeurIPS 2023. arXiv:2303.11366. *Failure signals are converted to reflective text held in an episodic memory buffer rather than used to veto a trajectory — the closest published precedent for F8's "signals become observations."*
3. **CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing** — Gou, Shao, et al. ICLR 2024. arXiv:2305.11738. *Verify-then-correct against external tools; works because the critique channel carries information the generator lacks. The named cure for the disease D4/D5 diagnose.*

**Self-correction: the skeptical turn**

4. **Large Language Models Cannot Self-Correct Reasoning Yet** — Huang, Chen, Mishra, Zheng, Yu, Song, Zhou. ICLR 2024. arXiv:2310.01798. *Intrinsic self-correction fails without external feedback; performance sometimes degrades after correction.*
5. **When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs** — Kamoi et al. TACL 12:1417–1440, 2024. arXiv:2406.01297. *No consensus; prior work often under-specifies research questions and uses impractical frameworks / unfair evaluations that over-evaluate self-correction. Reframes to conditions-for-success.*
6. **The Self-Correction Illusion: LLMs Correct Others but Not Themselves** — Chen, Su, Chiang. arXiv:2606.05976 (June 2026). *Identical erroneous claims are corrected 23–93 pp more often when relabeled from "internal thought" to an external source (tool/user/memory); 10/13 model-domain cells p<0.001. Attributed to chat-template artifact, fixable by prompt structure.*

**Repair economics**

7. **Is Self-Repair a Silver Bullet for Code Generation?** — Olausson, Inala, Wang, Gao, Solar-Lezama. ICLR 2024. arXiv:2306.09896. *Once repair cost is counted, gains are modest, vary enormously by subset, and are sometimes absent; the bottleneck is the model's ability to critique its own output.*
8. **Code Repair with LLMs gives an Exploration–Exploitation Tradeoff** — Tang, Hu, Zhou, Zhong, Zheng, Si, Ellis. NeurIPS 2024. https://proceedings.neurips.cc/paper_files/paper/2024/hash/d5c56ec4f69c9a473089b16000d3f8cd-Abstract-Conference.html (arXiv:2405.17503). *Refinement is an arm-acquiring bandit; naive refinement exploits the current draft. REx uses Thompson Sampling to force exploration.*
9. **How Many Tries Does It Take? Iterative Self-Repair in LLM Code Generation Across Model Scales and Benchmarks** — Arimbur. arXiv:2604.10508 (April 2026). *Most gains in the first two rounds; repair yield is error-class-dependent — assertion (logic) errors ~45%, syntax/name errors substantially higher.*
10. **Is Three the Magic Number? An Empirical Evaluation of LLM-Based Repair Loops** — Kiecker, Reichmann, Kang, An, Grunske. arXiv:2607.05197 (July 2026). *First 3–4 iterations carry nearly all gains; **repair behavior is influenced more strongly by workflow orchestration and feedback design than by the underlying model**; repair budget should be an explicit experimental variable.*

**Verifier-gated generation**

11. **Training Verifiers to Solve Math Word Problems** — Cobbe, Kosaraju, Bavarian, Chen, Jun, Kaiser, Plappert, Tworek, Hilton, Nakano, Hesse, Schulman. arXiv:2110.14168 (2021). *Seminal generate-many-then-gate: sample candidates, rank with a trained verifier, emit the top. The ancestor of every acceptance gate, including ours.*
12. **Mind the Gap: Examining the Self-Improvement Capabilities of Large Language Models** — Song, Zhang, Eisenach, Kakade, Foster, Ghai. ICLR 2025. arXiv:2412.02674. *Formalizes the generation–verification gap as the quantity governing whether verify-filter-distill loops can help; the gap scales with pre-training FLOPs — i.e. small models have small gaps.*

**Guardrail frameworks**

13. **NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications with Programmable Rails** — Rebedea, Dinu, et al. EMNLP 2023 (System Demonstrations). arXiv:2310.10501; https://aclanthology.org/2023.emnlp-demo.40/. *Dialogue-management runtime; rails are user-defined, model-independent, and interpretable — control relocated outside the model.*
14. **Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations** — Inan, Upasani, et al. arXiv:2312.06674 (2023). *Instruction-tuned 7B classifier over a safety taxonomy, applied to prompt classification and response classification — i.e. scoped to the current exchange.*
15. **Building Guardrails for Large Language Models** — Y. Dong, Mu, Jin, Qi, Hu, Zhao, Meng, Ruan, X. Huang. arXiv:2402.01822 (2024). *Position paper reviewing Llama Guard / NeMo / Guardrails AI; argues for socio-technical requirement elicitation, neural-symbolic implementation, and real verification and testing approaches — the field's own admission that gates are under-verified.*

**Constrained generation**

16. **Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models** — Tam, Wu, Tsai, Lin, Lee, Chen. EMNLP 2024 Industry Track. arXiv:2408.02442; https://aclanthology.org/2024.emnlp-industry.91/. *Significant decline in reasoning under format restriction; stricter constraints → greater degradation; classification improves while nuanced reasoning suffers.*
17. **JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models** — Geng, Cooper, Moskal, Jenkins, Berman, Ranchin, West, Horvitz, Nori. arXiv:2501.10868 (2025). *10K real-world schemas; six frameworks; explicitly separates efficiency, coverage, and **quality** of constrained outputs.*

**The cost of over-filtering**

18. **XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models** — Röttger, Kirk, Vidgen, Attanasio, Bianchi, Hovy. NAACL 2024. arXiv:2308.01263. *250 safe prompts / 200 unsafe contrasts; false refusals arise when benign prompts use similar language to unsafe ones — lexical overfitting as the mechanism.*
19. **The Refusal–Compliance Tradeoff: A Large-Scale Safety Behavior Audit of Large Language Models** — Hasan, Biswas. arXiv:2605.05427 (May 2026). *21 open-weight models, 4 benchmarks. "Refusal rates are a poor proxy for LLM safety." Conservative families over-refuse; permissive families over-comply; patterns are stable within families across scale, implicating post-training over architecture.*

---

## Where our findings sit

### F3 — Gate blindness

F3 is really two findings and they land against different literatures. Split them in the paper.

**F3a — the stale-repeat check caught 4/23 re-emissions at distance 1 and 0/12 at distance ≥2, because it consults only the last accepted turn.**

*What the literature already says.* This is a **known class**, and arguably a definitional one: the check's recall ceiling is set by its state window, and a one-turn window cannot see two-turn recurrence. The guardrail literature is built almost entirely from exchange-scoped components — Llama Guard (D14) classifies a prompt and a response; programmable rails (D13) fire per interaction. D16's whole argument is that guardrails today lack systematic requirement specification and verification, which is exactly the condition under which a monitor's scope silently under-covers the property it appears to enforce. Nothing here is a surprise to a reviewer.

*What our setting adds.* A **measured detection curve as a function of recurrence distance**, from a deployed gate, with the traces published. The literature asserts scope limits; it does not usually print 4/23 and 0/12 with the underlying turns inspectable. The instrument — not the phenomenon — is the contribution.

*What we may not claim.* Not a discovery. Not a general law about repetition gates (one implementation, one session). n=35 total re-emissions is small; print the exact denominators and the check's source location so a reviewer can re-derive the split. Do not imply the gate was *supposed* to catch distance ≥2 unless the spec said so; if it didn't, this is a spec-coverage finding, not a bug.

**F3b — a confidently WRONG project goal was accepted 3 times, because the checks detect echoing the true goal, not asserting a false one.**

*What the literature already says.* Predicted, cleanly, by the informational account of self-correction. D5 (Kamoi) frames success as conditional on the feedback source carrying information the generator lacks; D4 (Huang) shows intrinsic checks don't supply it; D3 (CRITIC) fixes it with external tools. A surface-overlap check has no truth channel, so it can only detect *copying*, never *contradiction*. D17's mechanism is the mirror image: lexical pattern-matching fires on surface form, not semantics — there it produces false positives, here false negatives.

*What our setting adds.* One thing here is genuinely worth stating, carefully: **the true goal was present in the substrate**. The information the gate needed was in durable project state, unconsulted. That shifts the diagnosis from the literature's usual one (feedback source too weak) to a different one (feedback source adequate, feedback *wiring* absent). That is a design-locus observation with a concrete remedy — validate assertions against held state, not against the last turn — and it is the kind of thing only per-turn instrumentation with a visible state snapshot can surface.

*What we may not claim.* Three acceptances in one session is an **existence proof, not a rate**. We cannot say how often false assertions pass, only that they can. We cannot claim the model "believed" anything. We have not shown that wiring a state-grounded check would have caught it — that is an untested counterfactual and should be labeled as one, or run.

### F4 — Repair economics (63% same violation class, 23% clean fix, 50% attractor escape)

This is where our numbers speak most directly, and where the honest posture is *concordance*, not discovery.

*What the literature already says.* Nearly all of it.
- D4 (Huang): unaided repair doesn't reliably improve reasoning and can degrade it. Our 23% clean-fix rate is on that side of the ledger.
- D7 (Olausson): gains modest, wildly subset-dependent, bottlenecked by critique quality. Our repair was driven by a schema/lexical advisory — weak critique by construction — so a low yield is the predicted outcome, not an anomaly.
- D9 (Arimbur, 2026): repair yield is **error-class-dependent**, ~45% for logic/assertion errors versus much higher for syntax/name errors. Our "63% reproduce the same violation class" is the same shape in a different medium: surface violations get fixed, semantic ones re-occur.
- D8 (Tang, REx): naive single-path refinement **exploits** the current draft; leaving it requires deliberate exploration. Our 6/12 attractor-escape rate is a direct measurement of exploitation bias — a coin flip on whether one repair pass leaves the semantic basin.
- D11 has the same texture: drafts function as scaffold even when semantically empty; the second pass inherits the first pass's structure.
- D10 (Kiecker, 2026): repair budget matters, and — the sentence to quote — *repair behavior is influenced more strongly by workflow orchestration and feedback design than by the underlying model*. That is the substrate thesis, arrived at independently, inside the repair sub-literature, on code. Cite it as convergent support, and say plainly that they said it first in their setting.
- D6 (Chen, 2026) is the sharpest forward-looking hook: re-presenting the model's own failed draft as its own prior thought is precisely the condition under which correction rates collapse; relabeling identical content as an external source lifted explicit-correction rates by 23–93 pp. Our repair prompt does the former. This is a **concrete, cheap, pre-registerable next experiment** in our own harness: relabel the rejected draft as a tool/system-memory message, hold everything else fixed, re-measure the 63% and the 6/12.

*What our setting adds.* Three things, all modest.
(i) **The metric.** Escape-from-semantic-attractor (Jaccard-cluster distance between pre- and post-repair answers) is a repair-success measure that works where there is **no oracle**. The code literature measures repair with test-pass rates; open-ended dialogue has no test suite. A cluster-escape metric is transferable to any open-ended setting and we can publish the script.
(ii) **The regime.** Repair budget = 1, kernel < 1B, edge hardware, temp 0.3 / seed 42. D10 argues repair budget should be an explicit experimental variable; we are a datapoint at the extreme low end of that curve, which is the regime an edge product actually lives in and which the benchmark literature almost never occupies.
(iii) **The receipts.** Every repair pair is in the published traces, so "re-enters the same terrain" is auditable per-instance rather than as an aggregate.

*What we may not claim.* This is the finding most at risk of being over-sold.
- **n is tiny.** 6/12 is a coin flip with a 95% binomial CI of roughly 21–79%. It is not evidence of a 50% rate; it is consistent with anything from "usually escapes" to "rarely escapes." Report the CI or report the raw counts only.
- Print the denominator behind 63% and 23%, and state whether those three categories are exhaustive and mutually exclusive.
- **We refute nothing.** We cannot contradict Self-Refine (D1); different tasks, different scale, single pass, no strong feedback signal. The correct framing is D5's: our setting sits squarely in the conditions under which the survey predicts self-correction should *fail*, and it does. That is confirmation of a prediction, not a challenge to a claim.
- Descriptive, not causal: we did not ablate the repair loop, did not run a no-repair control arm, and did not vary the advisory strength. Without those, "repair usually re-enters the same terrain" is an observation about *this* pipeline.

### F5 — Validation vs quality (7/7 advisory precision, poor recall; 93/93 schema-valid)

*What the literature already says.* Both halves are known.
- **Schema-validity ≠ quality** is settled. D17 (JSONSchemaBench) builds an explicit quality axis alongside efficiency and coverage because compliance alone proved uninformative. D16 (Tam) goes further: format restriction actively *degrades* reasoning, more so as constraints tighten. So "93/93 JSON-schema-valid while the architecture blocked speech" is a **vivid instance of a known dissociation**, not a new one. Say that in the paper, in those words — it protects the finding by pricing it correctly.
- **Lexical checks are surface-bound.** D18 (XSTest) established that lexical/keyword pattern-matching drives systematic guardrail error; there it produced false refusals, in our case it produced misses. Same mechanism, opposite error profile, which is a nice symmetry to note.
- **Weak verifiers are structurally weak.** D12's generation–verification gap formalizes why: a verifier sharing the generator's capacity and distribution performs a consistency check, not an independent correctness check, and the gap scales with pre-training compute — small models have small gaps. Our verifier was even weaker than the model (a lexical rule), so its recall ceiling is unsurprising.
- **Acceptance rates are poor proxies.** D19 states the safety version outright: refusal rates are a poor proxy for safety. Our claim is the quality-register analogue.

*What our setting adds.* A per-check, per-turn confusion picture on an open-ended task with published traces — including the specific miss taxonomy (echo-without-answer, pasted-context token buffets, second-person stance errors). Naming *which* failure modes a responsiveness heuristic is blind to is more useful to a builder than an aggregate recall number, and I did not find that miss taxonomy anywhere in the surveyed literature.

*What we may not claim.* **"Precision-strong" is not supportable as stated.** Seven fires, seven real misses, is a 95% CI on precision of roughly 65–100% — and, more importantly, we did not construct any adversarial false-positive opportunities. XSTest exists precisely because you have to *build* the contrast set to measure exaggerated firing; without an XSTest-style benign-but-suspicious contrast set, we can only report "no false fires observed among 7 fires," which is a description of the sample, not a property of the check. Recall is likewise unquantified — we have qualitative miss classes, not a labeled ground-truth set, so "recall-poor" should be phrased as "demonstrably blind to at least three named failure classes" rather than as a rate. And 93/93 schema-validity says nothing about the kernel's competence; it says the constrained-decoding layer worked, which is what D17 would predict for any modern grammar-masked pipeline.

### F8 — Flow mode (gating replaced by a salience/momentum/decay field for the living path; strict validation retained for measurement)

*What the literature already says — supporting.* The cost of over-blocking is measured, not speculative. D18 documents systematic false refusals from surface-level matching; D19's audit of 21 models concludes refusal rates are a poor proxy and that conservative calibration buys suppression at the price of excessive false refusals. Given F5 established our own gate was surface-bound and blind, the inference "this gate is blocking helpful output for bad reasons" is well-supported by domain precedent. And D2 (Reflexion) is a real architectural precedent for the specific move: convert failure signal into retained reflective *memory* rather than into a veto, keeping the trajectory alive. D13 (NeMo) supports the framing that the control layer is user-defined and independent of the model — flow mode is a different setting of a knob the field already agrees belongs outside the model.

*What the literature already says — cautioning.* Two cautions the paper must absorb rather than dodge.
1. **The over-refusal literature is about safety rails; ours is about quality rails.** Borrowing its authority requires saying so explicitly. Nothing in D18/D19 licenses removing quality gates.
2. **F3b is the price tag.** We documented a confidently false project-goal assertion being accepted three times *with gates on*. Flow mode routes every nonempty generation to the human, so that failure mode now reaches the human unconditionally. D19's other half — permissive calibration raises harmful compliance — is the general form of this. Name the cost in the paper; a reviewer will otherwise name it for us.

*What our setting adds.* An articulated **dual-mode stance**: strict validation retained for measurement, observation-not-rejection for the living path, with the mode boundary explicit. I found no direct precedent for splitting the gate regime by *purpose* (measurement vs. use) within one system, and D16's call for systematic requirement elicitation is arguably an argument in its favor — different contexts, different requirements. This is a design contribution and should be framed as one.

*What we may not claim — the sharpest bound in this domain.* **F8 is unevaluated.** There is no A/B of flow mode against gated mode. The live A/B in the traces is F6's context-compilation change (3 rejected before / 16 accepted after), which is a *different* intervention; do not let the two be conflated by proximity in the narrative. We have no user-outcome measure, no harm measure, no measure of whether unblocked-but-wrong output does damage, and no measure of whether salience/momentum/decay behaves as designed over long horizons. The honest sentence is: *we relocated quality control from admission to observation, and we have not yet measured what that costs.* Anything stronger is unearned. Also worth pre-empting: "flow mode" removes the very instruments that produced F3 and F5 from the living path — the paper should state how the observability of F7 compensates, or concede that it doesn't yet.

### Cross-cutting bound for the whole domain

n=1 session, 22 traces, one kernel family, one host, fixed decode settings. Everything here is **descriptive**. No arm of the study varies the gate, the advisory, the repair budget, or the model, so no finding in Domain D supports a causal claim. And nothing anywhere in this domain touches model interiority — the self-correction literature's own framing (D6's "chat-template artifact rather than genuine cognitive limitation") is a useful model for how to phrase mechanism claims without importing psychology.

---

## The gap we occupy

This domain's evidence is almost entirely batch-mode, closed-task, and oracle-scored — HumanEval, MATH, GSM8K, safety contrast sets — on frontier-scale models, with per-decision traces rarely published; and its repair sub-literature has essentially no data at repair-budget-1 on sub-1B kernels running on edge hardware, the regime an actual edge product occupies. What we provide is not a new phenomenon but a **per-turn, open-ended, hash-manifested trace corpus in which each gate decision, each repair input, and the semantic distance between pre- and post-repair answers are individually inspectable**, plus a repair-success metric (escape from a semantic attractor) that functions where no oracle exists. Every F3–F5 result we report is a known class arriving with unusually cheap verifiability attached; the contribution is the instrument, the receipts discipline, and the honest denominators — and, for F8, an explicit dual-mode design stance that is stated but not yet earned by evidence.
