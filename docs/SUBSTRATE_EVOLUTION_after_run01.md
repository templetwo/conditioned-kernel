# Substrate evolution after Run 01 — interpretation freeze

**Date:** 2026-08-07  
**Status:** **CORRECT FREEZE POINT** (2026-08-07) — Step 0 DoD locked; Step 1+ not earned  
**Step 0 validation:** **ACT-1** authority crossover protocol frozen → `docs/ACT1_authority_crossover.md` (not a ladder test; not Step 1)  
**Parent evidence:** Run 01 survival PASS + think-off profile + interpretation freeze  
**Repo:** `~/conditioned-kernel`  
**Audience:** any seat tempted to “next five features” the living substrate  

---

## Central idea (held)

The paper freezes evidence. The **living substrate** may evolve **behind versioned, ablatable boundaries**.

CK public architecture already places behavior in:

```text
state → compile → generate → validate → assess → repair → accept
```

with the model as a **local replaceable transducer** downstream of the packet.

Run 01 established a modest local model can cross the survival floor.  
CK established reliable behavior can be relocated **out of** that model.

The next interesting question (opened carefully by adaptive compile):

> **Can the substrate improve from its own history without becoming opaque, self-referential, or impossible to falsify?**

That is stronger than “structure around inference matters.”  
It is: **surrounding structure accumulates competence while weights stay frozen.**

---

## Five proposals — corrected read

### 1. Receipts → compile policy — YES, fenced

**Not** live online learning. **Not** “compiler rewrites itself every turn.”

```text
receipts
   ↓
offline policy estimator
   ↓
compile_policy_vN
   ↓ human/test promotion
frozen versioned table
   ↓
compile(state, input, policy_vN)
```

Requirements:

| Rule | Why |
|------|-----|
| Policy changes in **epochs** only | No silent per-turn behavioral drift |
| Every receipt names **compile-policy version** | Audit / falsify |
| Promotion needs **held-out tasks** (+ preferably **model swap**) | Avoid overfit |
| Do not optimize solely on first-pass acceptance | Acceptance is **endogenous** — validator is mechanical, not general truth |

Call it **empirically selected compilation**, not unconstrained learning.

**Wording correction:** CK is **already** substrate-conditioned. This would make it **adaptive / history-conditioned**.

**Ship order for #1:** **shadow-first** — compute what `policy_v1` *would* have selected without changing production packets; promote only behind ablation flag when counterfactuals look good.

---

### 2. Typed repair — ALREADY MOSTLY BUILT

**Do not pitch as a new subsystem.**

Current `repair.py` already maps failure types → typed repairs (`goal_not_referenced`, `evidence_used_empty`, `not_responsive`, contradictions, parse failures, max-word, forbidden content, …) and builds structured `repair_plan` for second-pass recompile.

**Rewrite as:**

> **Measure and deepen typed repair.**

Interesting questions:

```text
failure_class → repair strategy → did THAT class recover?
```

Repair confusion matrix: which classes recover, which do not, which must never claim repairable.

Incremental. Honest.

---

### 3. State decay / consolidation — YES, dangerous if lossy

CK already saw **state contamination**: `proposed_note` is **not** persisted because repair scaffolding leaked into state.

**Not:** distill accepted chat into notes and expire the only evidence.

**Yes:**

```text
RAW EVENT / RECEIPT LOG     (immutable or cold-retained)
        │
        ▼
CONSOLIDATION CANDIDATES    (provenance attached)
        │
        ▼
VALIDATE / PROMOTE
        │
        ▼
ACTIVE STATE                (small, decaying, useful)
```

**Decay the active projection, not the evidence.**  
Summaries can be accurate yet drop load-bearing caveats (Stack lesson). Raw material must remain reconstructable.

---

### 4. “Split assessor from kernel” — rename the claim

Generation is **already** split from validate / assess / repair / accept.  
`assess.py` is a small **deterministic** map: validation receipt → `accept | repair | reject`.

What people often mean by #4 is:

> introduce an **independent semantic assessor**.

That is larger, later, and weak if it is:

```text
model generates → same model judges
```

Run 01 Job 04 direction is stronger:

**First exhaust executable validation.**  
Semantic assessment only for claims the substrate **cannot** decide mechanically.

Push behind deterministic-gate expansion (Job-04-shaped gates).

---

### 5. Bridges last — ALIGNED

CK v0 does **not** import full Stack; bridge surfaces stay **P3** until core experiment stabilizes.

Protect that boundary. Stack / Helix / Compass as CK substrates later — early import confounds packet architecture with memory, governance, retrieval, and infra.

---

## Development law (promote from framing)

> **Every substrate evolution ships with an ablation-ready flag.**

Sketch (names flexible):

```text
ck --compile-policy static | adaptive-v1
ck --repair typed | generic
ck --consolidation off | v1
ck --semantic-assessor off | v1
```

Frozen paper v0.1 does not go obsolete. It remains the **origin** against which the living substrate accumulates evidence.

---

## Ordering (on-disk reality, not proposal hype)

| # | Work | Why first / later |
|---|------|-------------------|
| **0** | **Wire Run 01 convergence** | **Landed** — see `docs/STEP0_ARCHITECTURE.md`. Then **stop and use it.** |
| **1** | **Adaptive compile, shadow-first** | Earned only by **lived friction** after Step 0 is in daily use — not by interestingness. |
| **2** | **Measure / extend typed repair** | Already built; instrument recovery by class. |
| **3** | **Provenance-preserving consolidation** | Hot decays; raw reconstructable. |
| **4** | **Semantic assessor** | Residual only; after executable gates. |
| **5** | **Full Temple bridges** | Still P3. |


### Step 0 — definition of done (complete only when all four are true)

Asymmetry preserved: **evidence-earned integration** vs **interesting future research**.  
Run 01 earned Step 0. It did **not** earn #1–#5 yet.

| # | Criterion |
|---|-----------|
| **A** | Profile `macbook_survival_9b` resolves to the **exact qualified runtime tuple** from Run 01 — not merely a model name. (At minimum: local model id / base tag, digest prefix, quant, `num_ctx`, backend/runtime version expectation.) |
| **B** | CK can explicitly select **ordinary / think-off** vs **deliberate / think-on** **without changing model identity**. |
| **C** | One **executable gate** reproduces the Job 04 lesson: **deterministic rule result outranks contradictory generated prose**; model is downstream **explainer**, not decider. |
| **D** | Every **acceptance receipt** records enough runtime provenance to reconstruct the operating point: model/digest, quant, host, backend/runtime, context, thinking profile, tool surface, plus **gate / compile-policy versions** involved. |

**When A–D are true: Step 0 is complete. Stop again and use it.**

Step 0 must answer whether the convergence improves what CK was meant to become: **something worth living with on constrained local hardware.**  
**Only lived friction earns Step 1.** Do not open adaptive compile because the design is elegant.

### Research question (for when Step 1's turn comes — falsifiable)

> **Can competence accumulate in an inspectable substrate while the weights remain fixed, without the substrate learning to game its own acceptance surface?**

That is substantially better than "make the prompt adaptive." It is the target #1 must hit under shadow → promote → ablation discipline.


## The claim worth eventually proving (#1, carefully)

```text
same weights · same host · same task distribution · same acceptance surface

compile_policy_v0
        vs
compile_policy_v1   (learned only from prior receipts, inspectable, reversible)
```

v1 improves first-pass **usefulness** without merely learning validator loopholes.

Then CK moves from:

**“structure around inference matters”**

to:

**“the surrounding structure can accumulate competence while the weights remain frozen.”**

Open that carefully. Do not open it as a turn-by-turn self-modifying compiler.

---

## Explicit non-claims

- Think-off Job 04 miss does **not** justify Q8/27B.  
- Adaptive compile is **not** live RL on the acceptance oracle.  
- Typed repair is **not** greenfield.  
- Semantic assessor is **not** already “split assessor” in code.  
- Consolidation is **not** free to erase raw receipts.

---

## Related artifacts

| Artifact | Path |
|----------|------|
| Run 01 close | `~/.grok/docs/run01-survival/RUN01_CLOSE.md` |
| Think-off profile | `~/.grok/docs/run01-survival/RUN01_PROFILE_think_off.md` |
| Run 01 interpretation | `~/.grok/docs/run01-survival/RUN01_INTERPRETATION_freeze.md` |
| CK architecture | `docs/ARCHITECTURE.md` |
| River / Studio law | `docs/PURPOSE_AND_RIVER.md` |

---

*Relay-ready: direction yes; #2 corrected as existing; #4 renamed semantic assessment; #3 provenance-preserving; #1 epoch/shadow before live compile. Order starts at 0 = Run 01 wire-in.*
