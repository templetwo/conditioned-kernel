## Domain map

Domain E is four braided threads, and their shared blind spot is what makes room for us.

**(1) Decoding-time degeneration — the classic line.** Likelihood-maximizing decoding produces bland, looping text (Holtzman et al., ICLR 2020). Remedies split into decoding-side (nucleus/truncated sampling) and training-side (unlikelihood training, Welleck et al. 2020; DITTO's pseudo-repetition penalty, Xu et al. NeurIPS 2022). The theory underneath: repetition is partly a property of language itself — many words feed into the same successor, so returning to a prior state is cheap ("high inflow," Fu et al. AAAI 2021) — and repetition is *self-reinforcing*: the more times a sentence appears in context, the higher the probability of emitting it again, with strength proportional to its initial probability (Xu et al. 2022). Repetition remains a live production problem, not a solved one (Wang et al. 2025).

**(2) Distributional narrowing / mode collapse.** Post-training trades diversity for generalization: RLHF generalizes better out-of-distribution but substantially reduces output diversity relative to SFT (Kirk et al., ICLR 2024). More sharply for us, *formatting itself* collapses diversity — instruction templates, role markers and structural tokens narrow the output space, and this "diversity collapse" **persists even under high-temperature sampling** (Yun et al. 2025). The recursive-feedback branch is where a system feeds model output back to itself: training on recursively generated data collapses the distribution (Shumailov et al., *Nature* 2024), a result mirrored in the self-consuming-loop literature.

**(3) Dialogue continuity and long-horizon memory.** Consistency was formalized as natural-language inference over dialogue (Welleck et al., ACL 2019) precisely because surface heuristics do not catch contradiction. Long-term conversational memory is benchmarked but unsolved (LoCoMo, Maharana et al., ACL 2024). And multi-turn performance degrades sharply — an average 39% drop across six generation tasks, with the key mechanism being that once a model "takes a wrong turn" it does not recover (Laban et al. 2025).

**(4) Systems-level loops.** Agent frameworks enter unbounded feedback paths (Hou et al. 2026 confirm 68 infinite-agentic-loop defects across 47 real projects). Persistent-memory work documents *self-reinforcing error cycles*: a corrupted outcome is stored as precedent, which amplifies the initial error and lowers the threshold for recurrence (Wei et al. 2025). And engineering practice has independently found that naively retaining conversation history **degrades** agent performance by biasing on stale information — 96% task completion with selective persistent memory vs. 71% with full history retention (Pedada et al. 2026). Priming as a measured cognitive construct in LLMs is only now being benchmarked (ImplicitMemBench, Qin et al. 2026).

**The shared blind spot.** Threads 1-2 model repetition with a horizon that is either the current decoding window or the training corpus. Thread 3 measures dialogue-history effects. Thread 4 studies external-store loops, but mostly *adversarially* (poisoning) or at *benchmark aggregate* level. Almost nothing instruments a **benign, inference-time, weights-frozen** repetition loop whose carrier is an ordinary durable project store outliving the conversation — with the exact model-input bytes published. That seam is where F2, F3 and F6 sit.

## Key works

1. **The Curious Case of Neural Text Degeneration** — Holtzman, Buys, Du, Forbes, Choi — ICLR 2020 — arXiv:1904.09751
2. **Neural Text Generation with Unlikelihood Training** — Welleck, Kulikov, Roller, Dinan, Cho, Weston — ICLR 2020 — arXiv:1908.04319
3. **A Theoretical Analysis of the Repetition Problem in Text Generation** — Fu, Lam, So, Shi — AAAI 2021 — arXiv:2012.14660
4. **Learning to Break the Loop: Analyzing and Mitigating Repetitions for Neural Text Generation (DITTO)** — Xu, Liu, et al. — NeurIPS 2022 — arXiv:2206.02369
5. **In-context Learning and Induction Heads** — Olsson, Elhage, Nanda, et al. — Transformer Circuits Thread, 2022 — arXiv:2209.11895
6. **Dialogue Natural Language Inference** — Welleck, Weston, Szlam, Cho — ACL 2019 — arXiv:1811.00671
7. **Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo)** — Maharana, Lee, Tulyakov, Bansal, Barbieri, Fang — ACL 2024 — arXiv:2402.17753
8. **LLMs Get Lost In Multi-Turn Conversation** — Laban, Hayashi, Zhou, Neville — 2025 — arXiv:2505.06120
9. **Understanding the Effects of RLHF on LLM Generalisation and Diversity** — Kirk, Mediratta, Nalmpantis, et al. — ICLR 2024 — arXiv:2310.06452
10. **The Price of Format: Diversity Collapse in LLMs** — Yun et al. — 2025 — arXiv:2505.18949
11. **AI models collapse when trained on recursively generated data** — Shumailov et al. — *Nature* 631:755–759, 2024 — https://www.nature.com/articles/s41586-024-07566-y
12. **A-MemGuard: A Proactive Defense Framework for LLM-Based Agent Memory** — Wei, Yang, Wang, Li, et al. — 2025 — arXiv:2510.02373
13. **When Agents Do Not Stop: Uncovering Infinite Agentic Loops in LLM Agents** — Hou, Wang, Zhao, Wang — 2026 — arXiv:2607.01641
14. **Shared Selective Persistent Memory for Agentic LLM Systems** — Pedada, Dhavala, Patil — 2026 — arXiv:2607.09493
15. **Defeating Nondeterminism in LLM Inference** — Thinking Machines Lab — blog, Sept 2025 — https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/ *(industry blog, not peer-reviewed; cited as the primary source for batch-invariance/determinism)*
16. **ImplicitMemBench: Measuring Unconscious Behavioral Adaptation in Large Language Models** — Qin, Feng, Ma, Feng, Kong — 2026 — arXiv:2604.08064

*(Roster runs slightly over the 8-14 target because the domain spans four sub-areas; every entry was confirmed by search/fetch this session.)*

## Where our findings sit

### F2 — Attractor genealogy (16-hour persistence, survival across session reset, byte-identical 285-char re-emission ×7 at temp 0.3/seed 42)

**(a) What the literature already says or predicts.** Nearly all of the *phenomenon* is predicted, and we should say so first.
- Self-reinforcement of in-context repeats is established: repeat probability rises with each occurrence in context, and high-initial-probability strings self-reinforce hardest [4]. Our carrier text was in the compiled context.
- Induction heads give the *mechanism* for byte-identical emission of a span already present in the input: pattern completion `[A][B]…[A] → [B]` is the canonical induction-head operation, and it is the proposed substrate for most in-context learning [5]. A 285-char string sitting in the compiled prompt is exactly this case. We should not present verbatim re-emission as mysterious.
- Persistence at temperature 0.3 is not evidence of anything unusual: diversity collapse induced by structural/template tokens **survives high-temperature sampling** [10], and post-training narrowing is well documented [9]. High inflow makes returning to a prior state structurally cheap [3].
- Determinism at fixed seed and fixed input bytes is the *expected* case, not a finding [15]; the interesting thing in [15] is that determinism is fragile to batching, i.e. the default assumption runs in our favor here.
- The "system re-consumes its own output" loop is a known class: training-time (model collapse [11]) and agent-memory-time (self-reinforcing error cycles where "the corrupted outcome is stored as precedent" [12]).
- Even the practical corollary is independently reported: retaining prior conversational content biases agents on stale material and *lowers* task completion (96% selective vs 71% full history) [14].

**(b) What our setting adds.** Not the phenomenon — the **attribution of the priming source**, and the receipts.
- The literature's self-reinforcement results are measured over the *decoding window* or *dialogue history*. Because the attractor survived a full session reset, dialogue memory is ruled out as carrier; the carrier is durable project state re-compiled into the prompt. That is a *different horizon* than threads 1-3 model, and closer to thread 4 — but non-adversarial and benign, where [12] and [11] are adversarial and training-time respectively.
- Every model-input byte is in a TurnTrace and hash-manifested, so the carrier is traceable to specific state records rather than inferred. Combined with F1 (substrate supplied ~98% of input bytes at median), the byte-identical re-emission *across different user prompts* has an ordinary explanation — largely overlapping compiled contexts — and we can show that rather than speculate it.
- Edge-class hardware (0.5-0.8B kernel, Jetson-class), where almost none of this literature runs.
- Priming as a construct in LLMs is only now being benchmarked [16]; we contribute a field instance with the priming material itself published.

**(c) What we may NOT claim.**
- **No causal claim.** We never ablated the implicated state records and re-ran to show the attractor disappears. Until that experiment exists, F2 is descriptive co-occurrence, not causation. This is the single most obvious reviewer demand and we should preempt it by naming it.
- n=1 session, one kernel family, one host, one substrate implementation.
- "Attractor" is a metaphor here. We observed persistence and re-emission; we did **not** characterize a basin, measure stability under perturbation, or estimate a persistence half-life. 16 hours is one wall-clock window, not a decay measurement.
- Jaccard ≥0.6 is a lexical clustering threshold, not semantic identity.
- Nothing about the model's interiority, "preference," or intent.

### F3 — Gate blindness (4/23 caught at distance 1, 0/12 at distance ≥2; false project goal accepted 3×)

**(a) What the literature already says or predicts.** This is a *confirmed prediction*, not a discovery. Repetition in this literature is modeled over sentence- and sequence-level horizons [3][4]; nothing supports a distance-1 detector being adequate. A check consulting only the last accepted turn is under-powered by the standards of every work in thread 1. The false-goal result is precisely the gap that motivated Dialogue NLI [6]: consistency was reframed as *entailment/contradiction* detection because surface-overlap heuristics catch echoes but not assertions of a falsehood. Our gate is a surface-overlap heuristic, and it failed exactly where NLI-style checking was invented to help. That an accepted error then persists is what [8] predicts — models that take a wrong turn do not recover — and unbounded feedback paths at the systems level are now empirically catalogued [13].

**(b) What our setting adds.** A **detection curve by distance for a deployed substrate-side gate**, with per-turn traces public. The literature characterizes repetition as a model/decoding property; we measure the *checker's* effective horizon as an independent, tunable design parameter and publish the misses. The reframing is the contribution: repetition control has an ROC that belongs to the substrate, not the model.

**(c) What we may NOT claim.**
- These are small-n counts (4/23, 0/12, 3 acceptances) from one session.
- This is a property of *our* gate, not of stale-repeat checks in general. We ran **no baseline** — no NLI-based checker [6], no embedding-similarity checker over a wider window — so we cannot claim the failure was unavoidable or that a wider window would have fixed it.
- We may not claim the kernel "would have" produced a correct goal under a better gate. F5 already establishes the kernel was 93/93 schema-valid; that is an argument about where the blocking happened, not a counterfactual about content.

### F6 — Context field: selection readmits the attractor's carrier (selected material unused in 11/26; carrier selected-in twice, answer Jaccard 1.00 to a prior selected answer)

**(a) What the literature already says or predicts.** A selector that re-surfaces the system's own prior outputs, closing a loop, is a known failure class: self-consuming loops at training time [11], self-reinforcing precedent cycles in agent memory [12], and the practical finding that carrying prior content forward biases and degrades [14]. Once readmitted, verbatim copying is the mechanistically expected outcome [5], amplified by self-reinforcement [4]. So "relevance-based selection can readmit exactly the text you wanted to escape" should be presented as an *instance of a known class*.

**(b) What our setting adds.** Two things, both modest and both measurement-shaped.
- **The admission/authorship separation.** Retrieval and context-selection evaluations typically score relevance or downstream accuracy. We measure whether selected material *appears in the answer at all* — unused in 11/26 cases. That is a cheap, reusable diagnostic the surveyed literature does not routinely report, and it disciplines the common inference that "selected ⇒ used."
- **A visible mid-session natural experiment** (3 rejected turns before the switch, 16 accepted after), with the compiled contexts on both sides published.

**(c) What we may NOT claim.**
- The A/B is **unrandomized and confounded** — with time-in-session, with prompt content, with everything else that changed at the switch. It is an anecdote with receipts, not an effect size. Reporting 3-vs-16 as evidence of the selector's benefit would overclaim; report it as "a live A/B is visible in the traces" and stop.
- "Unused" is a lexical-overlap judgement over answer text. Consistent with F7's explicit refusal to label byte census as attention or influence, we cannot claim selected-but-unused material had no effect on the generation.
- One selector implementation, one session; nothing generalizes to retrieval systems broadly.

### Cross-cutting honest note for the paper

For all three findings in this domain the correct posture is: **the phenomena are known classes; the instrument, the byte-level public evidence, the identification of the priming source, and the substrate framing are the contribution.** Domain E's literature would predict every one of F2, F3 and F6 in advance. What it could not have handed you is the trace set.

## The gap we occupy

The degeneration and mode-collapse literatures measure repetition inside a single generation or inside a training loop; the work that studies self-reinforcing loops through an *external* store is largely adversarial (memory poisoning) or reported only as benchmark aggregates. What does not yet exist, as far as this survey found, is per-turn byte-level public evidence of a **benign, inference-time** repetition loop whose carrier is an ordinary durable project store — with the selection decisions, the exact model-input bytes, and the gate's per-distance detection record all published together, on edge-class hardware. We supply one such case, descriptively: an instrument and a corpus others can re-run and contradict, not a new phenomenon and not a causal result. The experiments that would upgrade it — state-record ablation with re-run, an NLI or embedding-based gate baseline, and a randomized selector A/B — are named and unrun.
