# Domain A — Context Engineering, RAG, and Memory-Augmented LLM Systems

## Domain map

This domain has consolidated, between roughly 2020 and 2026, around a single structural claim: **the model is one component in a larger information-assembly system, and much of what looks like model behavior is produced by that system.** It has four braided strands.

**1. The discipline strand — from prompting to context engineering to harness design.** Lewis et al.'s RAG (2020) established the pattern of combining parametric with non-parametric memory. Sclar et al. (2023) showed that meaning-preserving surface choices in the assembled payload swing benchmark accuracy by up to 76 points, which retroactively made payload construction an engineering problem rather than a cosmetic one. Mei et al.'s 1400-paper survey (2025) named the field "Context Engineering" and decomposed it into retrieval, generation, processing, and management. Zhang et al.'s ACE (2025) pushed further, treating the context itself as the learned object ("evolving playbooks") and naming two failure modes — *brevity bias* and *context collapse* — that arise from iterative context rewriting. Guo et al.'s 2026 harness survey is the current end-state of this strand: it decomposes the execution framework into six runtime responsibilities and concludes that "agent quality emerges from the interaction between model capability, runtime infrastructure, task structure, and evaluation design" rather than from the model alone.

**2. The utilization strand — the field's own skepticism about whether admitted context is used.** This is the strand most relevant to conditioned-kernel, and it is mature. Liu et al. (2023) showed position, not presence, governs whether context is used. Cuconasu et al. (SIGIR 2024) showed the relationship between relevance-based selection and answer quality is non-monotone — high-scoring-but-not-relevant documents hurt, random documents can help by up to 35%. Joren et al. (ICLR 2025) formalized the split explicitly: errors decompose into *context insufficiency* versus *failure to utilize sufficient context*, and crucially found the second failure mode is size-dependent — small models "hallucinate or abstain often, even with sufficient context." Hagström et al. (ACL 2025) introduced the ACU score and showed that synthetic benchmarks systematically **inflate** measured context utilization relative to real retrieved contexts. Hagström et al.'s CUB (ACL 2026) benchmarks seven context-manipulation techniques across 11 LMs under noisy conditions. Li & Ouyang (Findings of EMNLP 2025) found the downstream benefit of knowledge selection depends on generator capability and task complexity.

**3. The attribution strand — methods for establishing what context actually authored an output.** Cohen-Wang et al. (NeurIPS 2024) defined *context attribution* and gave ContextCite, an ablation-based method for pinpointing which context spans caused a particular generated statement. Sun et al. (Computational Linguistics, 2025) built an evaluation framework for highlight explanations of context utilization. Standing behind both is Jain & Wallace (NAACL 2019), the discipline's reference point for the claim that a salience-looking quantity is not evidence of what a model relied on.

**4. The memory-architecture strand.** Park et al. (UIST 2023) introduced the memory-stream + retrieval + reflection loop. Packer et al. (MemGPT, 2023) explicitly relocated memory management outside the model using an OS metaphor — a fixed-context processor plus hierarchical storage the model pages against. Maharana et al. (ACL 2024) gave LoCoMo, the long-horizon conversational-memory benchmark. Xu et al. (A-MEM, 2025) and Chhikara et al. (Mem0, 2025) are the current production-oriented state. Orthogonally, Belcak et al. (2025) argue small language models are sufficient and economically necessary for most agentic invocations — the closest published statement of the "replaceable kernel" premise.

**Shape of the gap in this map:** the utilization strand knows a great deal about admission-versus-authorship, but almost all of it is measured on curated QA/fact-verification benchmarks, with frontier or mid-size models, reported as aggregate scores. The memory strand publishes architectures and benchmark deltas. Neither routinely publishes the *raw per-turn model-input payloads* of a running system.

---

## Key works

1. **A Survey of Context Engineering for Large Language Models** — Lingrui Mei, Jiayu Yao, Yuyao Ge, et al. — arXiv preprint, 2025 — arXiv:2507.13334. The field-defining survey (1400+ papers); formalizes context engineering as systematic optimization of information payloads.
2. **From Question Answering to Task Completion: A Survey on Agent System and Harness Design** — Jianyuan Guo, Zhiwei Hao, Chengcheng Wang, et al. — arXiv preprint, 2026 — arXiv:2606.20683. "A foundation model coupled with an execution harness"; six runtime responsibilities; agent quality as emergent from model × runtime × task × evaluation.
3. **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** — Patrick Lewis, Ethan Perez, Aleksandra Piktus, et al. — NeurIPS 2020 — arXiv:2005.11401. Seminal parametric + non-parametric memory.
4. **MemGPT: Towards LLMs as Operating Systems** — Charles Packer, Sarah Wooders, Kevin Lin, et al. — arXiv preprint, 2023 — arXiv:2310.08560. Virtual context management; memory hierarchy relocated outside the model.
5. **Generative Agents: Interactive Simulacra of Human Behavior** — Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein — UIST 2023 — DOI 10.1145/3586183.3606763 (arXiv:2304.03442). Memory stream, retrieval, reflection.
6. **Lost in the Middle: How Language Models Use Long Contexts** — Nelson F. Liu, Kevin Lin, John Hewitt, et al. — arXiv preprint, 2023 — arXiv:2307.03172. Presence in context ≠ use of context.
7. **The Power of Noise: Redefining Retrieval for RAG Systems** — Florin Cuconasu, Giovanni Trappolini, Federico Siciliano, et al. — SIGIR 2024 — arXiv:2401.14887. Relevance-ranked selection is not monotonically beneficial; random documents can help.
8. **Knowledge Conflicts for LLMs: A Survey** — Rongwu Xu, Zehan Qi, Cunxiang Wang, et al. — EMNLP 2024 — arXiv:2403.08319. Context-memory / inter-context / intra-memory conflict; LMs are highly receptive to coherent external evidence even against parametric memory.
9. **ContextCite: Attributing Model Generation to Context** — Benjamin Cohen-Wang, Harshay Shah, Kristian Georgiev, Aleksander Madry — NeurIPS 2024 — arXiv:2409.00729. The methodological gold standard for "which context caused this statement."
10. **Sufficient Context: A New Lens on Retrieval Augmented Generation Systems** — Hailey Joren, Jianyi Zhang, Chun-Sung Ferng, Da-Cheng Juan, Ankur Taly, Cyrus Rashtchian — ICLR 2025 — arXiv:2411.06037. Separates insufficiency from non-utilization; small models fail to use sufficient context.
11. **A Reality Check on Context Utilisation for Retrieval-Augmented Generation** — Lovisa Hagström, Sara Vera Marjanović, Haeun Yu, et al. — ACL 2025 (pp. 19691–19730) — arXiv:2412.17031 / aclanthology 2025.acl-long.968. ACU score; synthetic benchmarks inflate utilization.
12. **CUB: Benchmarking Context Utilisation Techniques for Language Models** — Lovisa Hagström, Youna Kim, Haeun Yu, Sang-goo Lee, Richard Johansson, Hyunsoo Cho, Isabelle Augenstein — ACL 2026 — arXiv:2505.16518. Seven context-manipulation techniques × 11 LMs under noisy contexts.
13. **Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models** — Qizheng Zhang, Changran Hu, Shubhangi Upasani, et al. — arXiv preprint, 2025 — arXiv:2510.04618. Context as the learned object; names *context collapse* and *brevity bias*.
14. **Small Language Models are the Future of Agentic AI** — Peter Belcak, Greg Heinrich, Shizhe Diao, et al. — arXiv preprint, 2025 — arXiv:2506.02153. The replaceable-small-kernel argument, stated economically.

**Secondary works confirmed this session and used in the positioning below:**

15. **Attention is not Explanation** — Sarthak Jain, Byron C. Wallace — NAACL 2019 — arXiv:1902.10186.
16. **Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design** — Melanie Sclar, Yejin Choi, Yulia Tsvetkov, Alane Suhr — arXiv preprint, 2023 — arXiv:2310.11324.
17. **Evaluation Framework for Highlight Explanations of Context Utilisation in Language Models** — Jingyi Sun, Pepa Atanasova, Sagnik Ray Choudhury, Sekh Mainul Islam, Isabelle Augenstein — Computational Linguistics (MIT Press), 2025 — arXiv:2510.02629.
18. **Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo)** — Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, Yuwei Fang — ACL 2024 — arXiv:2402.17753 / aclanthology 2024.acl-long.747.
19. **Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory** — Chhikara et al. — arXiv preprint, 2025 — arXiv:2504.19413.
20. **A-MEM: Agentic Memory for LLM Agents** — Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, Yongfeng Zhang — arXiv preprint, 2025 — arXiv:2502.12110.
21. **How Does Knowledge Selection Help Retrieval Augmented Generation?** — Xiangci Li, Jessica Ouyang — Findings of EMNLP 2025 — arXiv:2410.13258.

---

## Where our findings sit

### The substrate thesis itself ("the model supplies linguistic possibility; the substrate determines what becomes an answer")

**(a) What the literature already says.** This thesis is not new, and the honest framing is that it is the domain's *current consensus direction*, not a discovery. Guo et al. (2026) [2] state a near-identical claim in survey form. MemGPT [4] operationalized "relocate the system function outside the model" three years ago. ACE [13] relocates learning itself into the context. Belcak et al. [14] argue the model can be small and interchangeable. Mei et al. [1] exist precisely because the field decided payload construction is where behavior is determined.

**(b) What our setting adds.** A stronger, testable phrasing ("substrate design should predict system behavior more strongly than model identity does"), the edge constraint (Jetson Orin Nano 8 GB class, 0.5–0.8B kernel, Ollama, fully local — most of this literature runs cloud-scale or at least 7B+), and an evidence discipline: 22 complete TurnTraces, 93-candidate day ledgers, state snapshots, and a SHA-256 manifest, all public.

**(c) What we may NOT claim.** We must not present the thesis as novel. And per the repo's own README, the model-swap arm is a **stated v0 success condition, not a delivered result** — the evidence release covers one kernel family on one host in one session. The strong form of the thesis ("substrate > model identity") is currently unfalsified in our data because it has not been tested. Say that plainly in the paper; the domain will check.

---

### F1 — Substrate dominance (human bytes 0.56%–14% of model input, median ~2%; substrate vocabulary surfacing as the kernel's frame)

**(a) What the literature already says or predicts.** That the human share of a modern agent payload is small is assumed throughout [1][2][4] — it is the premise of context engineering, not a surprise. Sclar et al. [16] establish that non-semantic properties of the assembled payload materially drive output. Xu et al. [8] establish that LMs are "highly receptive to external evidence... given that the external evidence is coherent and convincing," which straightforwardly predicts that a coherent substrate lexicon will be adopted by the kernel — this is context-memory conflict resolving in favor of context. Our observed "metaphysical frame" uptake is a vivid instance of a documented class, and should be labeled as such.

**(b) What our setting adds.** A **measured, per-turn, published distribution** of the human share of model-input bytes (0.56%–14%, median ~2%) on real traces, rather than the qualitative assumption. I searched this session and did not find published work reporting a per-turn human-share-of-payload census with released raw payloads; I state that as "did not find," not "does not exist." The lexical-uptake observation is coupled to the exact payload bytes that produced it, which is auditable.

**(c) What we may NOT claim.** Byte share is **not** influence, attention, or attribution — this is the single most important guardrail, and the literature has already litigated it. Jain & Wallace [15] is the canonical warning that a salience-shaped number is not evidence of reliance; ContextCite [9] is the standard our census does not meet, because attribution requires counterfactual ablation of context spans, which we did not run. F7's existing self-imposed label ("explicitly NOT attention/influence") is correct and should be stated in the same breath as every byte-census number. Additionally: no ablation of the substrate lexicon was performed, so vocabulary co-occurrence is correlational; n=1 session; one kernel family; one host; descriptive, not causal; and nothing here speaks to model interiority.

---

### F6 — Context Field: admission vs. authorship (selected material fully unused in 11/26 cases; attractor carrier text selected-in twice at Jaccard 1.00; 3-rejected-before / 16-accepted-after A/B)

This is the finding where positioning matters most, because the domain already owns the phenomenon and has a name for it.

**(a) What the literature already says.** The admission/authorship gap is the *central object* of the context-utilization strand. Liu et al. [6]: admitted-but-unused as a function of position. Cuconasu et al. [7]: relevance-based selection does not monotonically improve answers. Joren et al. [10]: the decisive precedent — errors split into insufficiency versus non-utilization, and **smaller, weaker models hallucinate or abstain even when context is sufficient.** A 0.5–0.8B kernel leaving 11/26 selected contributions unused is exactly what [10] predicts. Hagström et al. [11]: measured utilization is systematically *overstated* on synthetic data, so a low real-world utilization rate is the expected direction. Li & Ouyang [21]: selection's downstream value depends on generator capability. Cohen-Wang et al. [9] and Sun et al. [17] provide the measurement apparatus.

The correct sentence for the paper is something like: *"Admission is not authorship" is not our finding; it is the established finding of the context-utilization literature. What we contribute is an instance measured inside a live loop on edge hardware, with the raw payloads released.*

**(b) What our setting adds.** Three things, stated conservatively. (i) **Venue of measurement**: this is a running multi-turn agent on a Jetson-class edge device with persistent project state, not a QA benchmark — the utilization literature's own reality-check paper [11] argues that benchmark conditions distort exactly this measurement, which makes in-the-wild traces methodologically valuable. (ii) **Coupling selection to repetition dynamics**: the observation that the attractor's carrier text was itself *selected back in* twice (answer Jaccard 1.00 to a prior selected answer) links context selection to a self-reinforcing output loop. ACE [13] names the adjacent failure — *context collapse* under iterative rewriting — but our observation is a different mechanism: selection re-admitting the system's own prior output as evidence. I did not find published work characterizing this specific selection-attractor coupling with released traces; treat that as a modest, checkable novelty claim, not a strong one. (iii) **Byte-level auditability**: a third party can recompute admission and inspect authorship from the manifest.

**(c) What we may NOT claim.** The mid-session A/B is **not a controlled experiment** — 3 rejected turns before versus 16 accepted after is confounded with time, prompt content, accumulated state, and any other change in that window, and 3-vs-16 is not a statistic. It should be reported as a *narrative observation in the trace*, and the word "A/B" should probably be dropped or heavily qualified, because in this literature it implies a randomized arm. Our "fully unused" determination rests on overlap heuristics, not counterfactual ablation, so it is strictly weaker evidence than ContextCite-grade [9] or ACU-grade [11] attribution — a span can causally shape an answer while sharing no tokens with it, and our method cannot see that. n=1 session; one kernel family; descriptive.

---

### F2 — Attractor genealogy (clusters persisting 16 hours across a full session reset; one 285-char answer byte-identical 7× at temp 0.3 / seed 42)

**(a)** Partly predicted. Byte-identical re-emission at low temperature with a fixed seed and a near-identical compiled payload is expected decoding behavior, not a phenomenon — the interesting part is that the *payload* was near-identical across ostensibly unrelated prompts, which is a property of the compiler, not the kernel. That property is the substrate-side analogue of ACE's *context collapse* [13] and of the general finding that durable external state, not dialogue history, drives agent behavior [4][5][19][20]. Survival across a session reset is exactly what MemGPT-style external storage [4] and memory-stream architectures [5] are built to produce.

**(b)** What we add: a documented case where the persistence mechanism is *unintended* — durable project state priming answer clusters that the designers did not intend to persist — with per-turn traces showing it. Most of the memory literature reports persistence as a feature and measures it on LoCoMo-style benchmarks [18]; failure-mode traces of unintended persistence are rarer.

**(c)** We may not claim a mechanism without the ablation. We did not vary seed, temperature, or state to isolate which of the three produced the repetition. Report the correlation and the confound.

---

### F5 — Validation vs. quality (93/93 JSON-schema-valid; the architecture, not the model, blocked speech)

**(a)** Joren et al. [10] is the direct precedent for the shape of this result: small models are not primarily failing at *form*, and system-level behavior around them determines what surfaces. The broader point — that schema-validity and answer-quality are orthogonal axes — is implicit in [11][12], which exist because surface-level context metrics do not predict utilization.

**(b)** What we add: a clean separation in a live system, with the counted evidence (93/93 valid; a precision-strong, recall-poor advisory at 7/7 fires) showing that the *gate*, not the kernel, was the binding constraint. That framing — "measure the harness, not just the model" — is precisely what Guo et al. [2] call for and rarely have data for.

**(c)** One advisory, one gate configuration, one session. Nothing here generalizes to other validators, and "the architecture blocked speech" is a description of this pipeline, not a claim about validation in general.

---

## The gap we occupy

This domain has thoroughly established that admitted context is not authoring context, but it has measured that almost entirely on curated QA and fact-verification benchmarks, with mid-to-frontier models, and it publishes aggregate scores rather than the raw payloads — and its own reality-check work [11] argues those benchmark conditions inflate the very quantity being measured. What we provide is narrow and complementary: a hash-manifested, publicly recomputable corpus of *complete per-turn model-input payloads* from a live sub-1B kernel on edge hardware, in which the human share of input bytes, what the compiler admitted, and what the answer actually reused can each be independently re-derived by a third party. The contribution is the instrument and the evidence discipline, not the discovery of a phenomenon — every phenomenon we report already has a name in this literature, and the paper should say so before the reviewers do.
