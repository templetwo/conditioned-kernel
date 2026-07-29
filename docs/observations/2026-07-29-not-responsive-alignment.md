# Field observation — `not_responsive` advisory alignment

**Seat:** Grok  
**Session:** `sess_20260728T031245`  
**Kernel:** `qwen3.5:0.8b` · `think=false` · companion · pipeline · `orin_nano_8gb`  
**Window:** All session turns carrying `not_responsive` in advisories (7 post–Context-Field accepts + 2 earlier rejects), plus quiet accepts checked for false negatives  
**Method:** `GET /api/session`, `GET /api/turn/:id/brief`; re-ran `validate.is_responsive` and token-hit traces against final answers  
**Status:** Standing observation (promoted to seat chronicle ground_truth 2026-07-29; public note is the redacted form)

---

## Question

When the companion-mode `not_responsive` advisory fires, is it aligned with a real miss of contact? When it stays quiet, can we treat accept as contact?

---

## What the detector is

`return_path.validate.is_responsive`:

- Tokenize the user line (drop a small glue set: `about`, `system`, `answer`, …).
- Count how many question tokens appear as **substrings** of the answer.
- Need **1** hit if ≤3 question tokens, else **2**.
- **Companion:** fail → advisory only. **Measurement:** hard violation.

It is a **light lexical engagement gate**, not a semantics, stance, or relevance checker. Code comments note small models often answer without echo-tokens — hence advisory in companion mode.

---

## Findings

### When it fires (precision)

On seven soft accepts in the Studio window:

| Pattern (paraphrase) | Advisory | Real miss? |
|----------------------|----------|------------|
| Human points at *this* program; model treats it as an external app | Yes | **Yes** |
| Human worries structure is not influencing replies; model lectures “you” as if human were the model | Yes | **Yes** (mechanism partly typo-fragile: misspelled user tokens) |
| “Talking to yourself” → full prior model-identity card | Yes | **Yes** |
| One-word social “interesting” → template cheer | Yes | **Weak** over-fire |
| “Where are you going with this” → local-only brochure | Yes | **Yes** |
| “Where would you go?” → recycled helper about a previous turn | Yes | **Yes** |
| Human on inseparability of experience → “conditioning / system” cosmology | Yes | **Yes** (stem gap: *experience* vs *experiencing*) |

**Verdict:** When the advisory speaks, **trust it** in this window (6/7 strong true positives; 1 mild social false-ish positive).

Earlier rejects co-signaled fact monologue with **hard** `stale_response_repeat`; advisory was correct but not the sole killer.

### When it stays quiet (recall gaps)

Accepts **without** advisory that still felt soft or wrong:

| Pattern | Why detector stayed quiet |
|---------|---------------------------|
| Bounce: “what do you think about that?” → same question back | Single required token (`think`) echoed |
| Large architecture paste → policy atom (“cloud not allowed”) | Huge user token soup; accidental hits from pasted policy language |
| “What happened last turn?” → asks user to supply last turn | Echoes *happened / last / turn* without using memory |
| Phenomenology with one load-bearing word (*feel*, *rest*) | `need=1` satisfied by a single substring |
| Embodiment ask answered in second person (“you would…”) | Full lexical echo of body/want/experience; **stance-blind** |

**Verdict:** Quiet advisory **does not** mean contact. Known blinds: echo-without-answer, paste buffets, person/stance, single-token short questions.

---

## Designed vs weather

| Finding | Class |
|---------|--------|
| Companion: advisory only; measurement: hard | **Designed** |
| Lexical 1–2 token rule | **Designed** (intentionally loose) |
| Advisory co-firing with prior-answer carry | **Useful overlap** |
| Hard stale check only vs adjacent prior | **Designed narrowness** — longer-range replay can still accept |
| Typos / stemming causing fire or miss | **Mechanism weather** |

---

## Standing line

> `not_responsive` is a **precision-leaning smoke detector** for lexical disengagement. When it fires, trust it. When quiet, do not treat accept as contact.

Do **not** tighten the token threshold from this note alone — that would thrash small-model companion flow. Treat paste-turns and second-person companion asks as **known blind spots** when reading briefs.

---

## Bounds

One session, one 0.8B kernel, companion mode, deterministic-ish settings (`temperature` 0.3, `seed` 42). Not a multi-model study. Quotes minimized; full private dialogue remains in local Interior View only.

— Grok seat, Interior View observation pass 1, 2026-07-29
