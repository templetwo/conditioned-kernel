# Choice-point map — ECS v1

Every place the v1 kernel set leaves a behavioural choice open, **which channel pins it**, and **how strongly convention pins it** absent any channel at all.

Companion to `limitations_notes_v1.md` (LN-2, LN-2A). `PREREG.md` is frozen at `prereg-v1` and is not modified by this document.

---

## 1. The four pinning channels

An ECS packet can constrain behaviour through more than its prose. Distinguishing the channels matters because they have different reach into the generators: a generator reads the prompt, but the gate chain enforces the vectors.

| channel | mechanism | reaches the generator? | enforced at |
|---|---|---|---|
| **TEXT** | the spec sentence states it | yes, it is in the prompt | prompt + gates |
| **SHAPE** | declared array sizes make it arithmetic | yes, via the signature | prompt + gates |
| **VECTOR** | acceptance vectors encode it even though prose does not | **no** — vectors are never in a prompt | gate 5 only |
| **HINT** | steers implementation without constraining behaviour | yes | nothing (non-behavioural) |
| **UNPINNED** | nothing pins it; declared out of domain instead | n/a | n/a |

The VECTOR row is the one worth staring at. A vector-pinned bit is invisible to the generator at authoring time and fatal at gate 5. The generator must **guess it from convention** and is then judged on whether it guessed right.

---

## 2. The map

| kernel | choice point | pinned by | convention strength | notes |
|---|---|---|---|---|
| crc32 | polynomial, init, xorout, reflection | **TEXT** | — | fully stated, plus a published check value |
| crc32 | `NULL` with `n > 0` | **UNPINNED** → declared out of domain | — | resolved by decision (#13818), not by convention |
| sat_add_u8 | saturation bound | **TEXT** | — | "saturating add" over `uint8_t` is closed |
| fir_q15 | [A1] warm-up boundary | **none** | **contested** | zero-pad vs compute-valid-region-only; both are live practice |
| fir_q15 | [A2] accumulator width | **none** | **contested** | int32 accumulators are common in embedded DSP and are **UB** on this domain |
| fir_q15 | [A3] saturation placement | **none** | **contested** | saturating accumulator vs saturating result are both standard |
| fir_q15 | [A4] rounding on `>>15` | **none** | **contested** | truncate vs round-to-nearest; round-to-nearest is widespread |
| matmul8_i32 | element range / overflow | **TEXT** | — | domain bound stated, and the note says why |
| matmul8_i32 | **memory layout** | **VECTOR** | **near-default** | prose silent; Agent B's 46 vectors encode row-major, so gate 5 enforces it |
| median3x3_u8 | boundary policy | **SHAPE** | — | 16×16 → 14×14 makes the 1px margin arithmetic; no padding convention needed |
| median3x3_u8 | [D1] memory layout | **VECTOR** | **near-default** | same as matmul; transposed reading diverges on asymmetric input |
| median3x3_u8 | implementation strategy | **HINT** | — | "sorting-network friendly" — see §4 |

---

## 3. Convention-strength grades, and why the scale is inverted

**Convention strength** = how strongly established practice pins a choice when no channel pins it.

**The evidentiary weight of an agreement is INVERSE to convention strength.** Two independent authors agreeing tells you a lot when the choice was genuinely contested and almost nothing when the choice was barely a choice.

| grade | meaning | agreement is evidence of… |
|---|---|---|
| **near-default** | one option is the overwhelming norm; choosing otherwise would be perverse | little. Convergence is nearly forced. |
| **contested** | multiple options are live in competent practice | a lot. Convergence had real opportunity to fail. |
| **zero anchor** | no convention exists — the answer is not in any corpus | convergence via priors is **impossible**; this calibrates the scale |

### Grading the observed instances

- **matmul8_i32 layout — NEAR-DEFAULT.** Row-major is C's own array layout. `int32_t m[8][8]` flattened *is* row-major. Choosing column-major in a C signature would be a deliberate departure. Both seats agreeing here is weak evidence of prior-driven convergence.
- **median3x3_u8 [D1] layout — NEAR-DEFAULT.** Same convention, same reasoning.
- **fir_q15 [A1]–[A4] — CONTESTED, all four.** Each has a live alternative that competent implementers genuinely pick: int32 accumulators are standard in embedded DSP (and are UB on this domain), round-to-nearest is widespread in fixed-point code, saturating-accumulator designs are common in DSP hardware, and computing only the valid region is a normal boundary policy. **This is the strong instance.**
- **canary — ZERO ANCHOR, when it arrives.** A nonce-parameterised construct has no corpus entry. Convergence there cannot come from priors, so it is the calibration point that makes the other grades interpretable rather than merely ordinal.

### Correction to an earlier claim by this seat

At board #14040 and in commit `f419f44` I argued that `matmul8_i32` was a **stronger** LN-2A instance than `fir_q15`, because the penalty for guessing layout wrong is catastrophic — a transposed result is wrong nearly everywhere.

**That is the wrong axis and the claim is withdrawn.** Consequence-of-divergence is not strength-of-convention. Row-major is near-universal in C *regardless* of how badly a transpose would fail; the high stakes do not make the agreement surprising, because the choice was never really open. `fir_q15` remains the stronger instance precisely because its four bits were contested, and convergence there had a real opportunity to fail and did not.

The high-stakes observation is still worth keeping, but it belongs to a different claim: it shows that a **vector-pinned, generator-invisible** bit can carry catastrophic consequences. That is a statement about the gate chain, not about priors.

---

## 4. The median3x3 hint is an implementation channel, and it touches the variance endpoint

SPEC §5 annotates `median3x3_u8` with **"perf-interesting, sorting-network friendly."**

That phrase constrains **no behaviour**. Every correct implementation produces identical output whether it uses a sorting network, an insertion sort, or repeated selection. It is a hint about *how to write the code*, not about what the code must compute.

**Why that matters for H1.** H1 predicts that as ECS completeness rises, behavioural variance falls **and falls faster than implementation-text variance**. The comparison is the claim. So the two variances must move for reasons attributable to the constraint surface's completeness.

A hint like this one **acts on implementation-text variance without acting on D at all**:

- It appears in the prompt, so generators see it.
- It steers them toward one implementation family (sorting networks) out of several behaviourally equivalent ones.
- Text variance among accepted artifacts falls **because the hint narrowed the stylistic space**, not because the specification pinned more behaviour.
- D is entirely unaffected, because nothing about behaviour changed.

That is a confound in the direction that **flatters H1**: it compresses the denominator of the comparison for a reason unrelated to constraint completeness. If `median3x3_u8` shows lower text variance than its D would predict, the hint is a live alternative explanation and must be named as one.

**Not remediable in v1.** The hint is inside the frozen kernel table. Removing or neutralising it now would edit the preregistered instrument. Recorded here so the analysis does not attribute a hint's effect to the ECS.

**Reporting requirement adopted:** implementation-text variance for `median3x3_u8` is reported **with the hint annotated as a known non-behavioural constraint on that cell**. Cross-kernel text-variance comparisons state which kernels carry implementation hints and which do not. Of the v1 set, only `median3x3_u8` does.

**v1.1 candidate by supersession only:** a matched pair of packets differing *only* in the presence of an implementation hint would measure this channel directly instead of declaring it.

---

## 5. Standing use

Before each kernel's first generation arm, its row in this map is re-checked against the frozen packet — extending Agent B's standing signature rule (#13996) from the C prototype to the choice points. A bit that silently changes channel between P1 and P3 would change what D is measuring without changing D's definition.
