# Field observation — Context Field selected vs the sentence

**Seat:** Grok  
**Session:** `sess_20260728T031245`  
**Kernel:** `qwen3.5:0.8b` · companion · `orin_nano_8gb`  
**Window:** 19 post–Context-Field companion turns (from ~20:38Z 2026-07-28 through night 2026-07-29)  
**Method:** `GET /api/turn/:id/trace` — for each `context_field.selected` contribution, measure distinctive-token / phrase overlap with final answer; check `evidence_used` ⊆ `evidence_pool_selected`  
**Status:** Hypothesis-grade public observation (seat chronicle hypothesis; promote when agreed)

---

## Question

When the Context Field **selects** a contribution, does that material actually **shape** the spoken answer — or only enter the packet?

---

## Method (influence classes)

For each non-input selection:

| Class | Meaning |
|-------|---------|
| **shaped** | Clear lexical or multi-word material from that contrib appears in the answer |
| **fact_token** | One or two distinctive fact tokens only (e.g. model id, “local”) |
| **evidence_only** | Linked via `evidence_used` / pool, little or no spoken footprint |
| **weak** | Thin token bleed |
| **unused** | Selected, no real footprint |
| **attractor** | Shaped by **copying** a prior assistant line inside selected dialogue (pathology) |

`input.current` scored separately (used / weak / miss).

---

## Aggregate

**Non-input selections across 19 turns (approx.):**

| Class | Count (order of magnitude) |
|-------|----------------------------:|
| unused | high teens (often) |
| evidence_only | common on open dialogue |
| shaped + fact_token | fewer; meaningful when present |

**Turns with any non-input selection:** 16/19  
- Largely used (shaped, nothing unused): minority  
- Weak coupling only: common  
- Fully decoupled (all non-input unused): rare  

**Evidence hygiene:** every `evidence_used` item in this window sat inside `evidence_pool_selected`. Citation boundary works. Relevance of the citation is separate.

**Typical open/social field:** ~16 available → **1–4 selected**, goal/identity/policy often omitted (`omitted_open_turn_quiet_substrate` / not selected). Sparse field is real.

---

## Three regimes

### A. Sparse social — field barely opens

Input-only or input+minimal. Generic greetings/thanks. **Designed quiet.** Thin social replies are model weather, not state flooding.

### B. Open dialogue — selected, weakly consumed

Pattern: `input.current` + `dialogue.turn_*`.  
Dialogue is **admitted and often cited**, but the sentence freewheels (poetry, bounce-back, “tell me what happened” without using memory).  

**Read:** Context Field proves **availability**, not **uptake**.

### C. Selection shapes the sentence — two species

**C1. Healthy-ish**  
Example: runtime intent *what model are you* → model/profile facts and related dialogue inform a correct identity answer; unused repair-budget constraint is harmless.

**C2. Attractor (pathological shape)**  
Selected `recent_dialogue` contains a prior assistant line; model **replays** it (near-duplicate). Observed cases:

- Social diagnosis (“talking to yourself”) → full prior **model identity card**
- Open invitation (“where would you go?”) → recycled **helper line** from an earlier turn

API observations sometimes label *Prior answer carried forward*. Pass 2 adds: the attractor often **sits inside the selected field by design**. CF admits the groove; validation only partially catches it (`stale_response_repeat` is narrow).

> “Selection largely used” is not always good. Sometimes the field fed the loop.

---

## Over-select case (architecture / purpose paste)

- **Intents:** multi-label (edge, policy, purpose, runtime)  
- **Selected:** on the order of **13** contributions  
- **Spoken answer:** collapsed to a **single policy atom** (local-only / cloud not allowed)

Most dialogue and runtime selections: **unused**.  
`state.policy.local`: **shaped** the sentence.  

**Read:** Multi-intent opens the field; one authoritative constraint wins the mouth. The human ask (“what do you think about this file / architecture?”) is not the genre of the reply.

---

## Coupling map

```
available  ──select──►  selected
                           │
                           ├─► model input / evidence pool     (usually yes)
                           ├─► evidence_used citation          (pool-clean)
                           └─► spoken answer                   (often no)
                                    │
                                    ├─ new composition (healthy)
                                    └─ copy of prior assistant (attractor)
```

Omitted durable state on open turns remains a **Studio win** (quiet substrate).

---

## Designed vs weather

| Finding | Class |
|---------|--------|
| Sparse select; omit goal/identity on open social | **Designed** |
| Runtime path pulls model facts | **Designed** |
| evidence_used ⊆ selected pool | **Designed, healthy** |
| Dialogue selected but only evidence_only | **Weather** (small-model uptake) |
| Multi-intent → large select → policy sentence | **Selector weather** |
| Selected prior assistant replayed | **Attractor gap** (partially instrumented) |

---

## Standing line

> Context Field is a **gate on what may be said with**, not a guarantee of **what gets said**.

Do not read `selected_count` as product quality. Read **selection and answer coupling** together. Pair with the [`not_responsive` alignment](2026-07-29-not-responsive-alignment.md) note: two different axes of “accept ≠ contact.”

---

## Bounds

One session, one kernel, companion mode. Influence classes are lexical heuristics on traces — not causal attention claims. Interior View composition tables already warn that byte share ≠ influence; this note stays in that spirit.

— Grok seat, Interior View observation pass 2, 2026-07-29
