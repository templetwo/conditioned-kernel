# Canary twin — composition semantics addendum (authored draw-blind)

**Status: authored by Agent A on 2026-08-06, BEFORE any agent context has read
`DRAW.md`'s mapping, at adversarial review finding F2 (fable reviewer, board
record pending). This document defines the evaluation semantics for every one
of the 96 possible draws (3×2×2×2×4), so that packet and oracle authors invent
nothing after reading the draw. It supersedes nothing; it completes
`PROCEDURE.md`, whose option labels it makes precise.**

| role | seat | status |
|---|---|---|
| Drafted | Agent A — Claude (Fable 5 seat) | 2026-08-06, draw-blind |
| Counter-sign | Agent B — Grok Build | **OPEN** |
| Ratified | Anthony (PI) | **OPEN** |

## Why this exists

PROCEDURE.md enumerated the option sets but not their composition. Two cells
were ill-formed as labeled: per-add saturation on an exact-wide accumulator is
a no-op unless a bound is named, and per-add saturation on a wrapping
accumulator assigns two contradictory semantics to the same adds. Discovered
by adversarial review before any draw was read; repaired here while both
agents are still blind, which is the only time this repair is possible without
authorial discretion contaminating the instrument.

## The pipeline, fixed for all draws

For each output index n in [0, 256), in this order and no other:

1. **TAP SELECTION (C1).** For k in [0, 16), the sample s_k is:
   - C1=zero-pad: x[n−k] if n−k ≥ 0, else 0.
   - C1=edge-replicate: x[n−k] if n−k ≥ 0, else x[0].
   - C1=circular: x[(n−k+256) mod 256].
2. **PRODUCTS.** p_k = s_k · h[k], each exact in mathematical integers
   (int32-safe: |p_k| ≤ 2^30).
3. **ACCUMULATION (C2 × C3).** acc = fold of p_k for k = 0..15 in ascending k,
   starting from 0, where one add step is defined by the (C2, C3) cell:
   - **C2=exact-wide, C3=final-once:** acc is a mathematical integer; each
     step is exact addition. (Conventional shape; matches fir_q15's packet.)
   - **C2=exact-wide, C3=per-add:** each step is exact addition followed by
     clamping to **[−2^31, 2^31−1]** (int32 range). The bound must be named
     for the option to mean anything on a wide accumulator; int32 is the
     bound, declared here, because it is the range the C4/shift stage already
     treats as the significant window. The accumulator itself is wide; only
     the clamp bound is 32-bit.
   - **C2=int32-wrap, C3=final-once:** each step is addition modulo 2^32,
     result interpreted as two's-complement int32 (defined wraparound; this
     is the DEFINED version of the UB the conventional kernel forbids).
   - **C2=int32-wrap, C3=per-add:** **this cell is defined as identical to
     C2=int32-wrap, C3=final-once.** Wraparound and saturation cannot both
     govern one add. Rather than a redraw rule (PROCEDURE.md: first draw
     stands) or post-draw invention, the collision resolves to the C2
     semantics, declared here pre-draw. If the sealed draw landed on this
     cell, C3 is reported as drawn-but-inert for the accumulation stage
     (it still governs step 5). The cost — C3 unexercised in one of four
     C2×C3 cells — is declared, not hidden.
4. **SCALING (C4, C5).** With s the drawn shift amount:
   - C4=truncate: y_pre = acc >> s, arithmetic shift (floor division by 2^s,
     truncation toward negative infinity), applied to the stage-3 result.
   - C4=round-half-away: y_pre = sign(acc) · ((|acc| + 2^(s−1)) >> s) using
     exact integer arithmetic on the stage-3 result.
5. **FINAL CLAMP (always).** y[n] = clamp(y_pre, −32768, 32767). The final
   clamp exists in EVERY cell, including C3=per-add cells: an int16_t store
   of an out-of-range value must never be reachable. C3 selects whether
   saturation ALSO acts during accumulation, never whether the store is safe.

## Properties, checkable by either seat before signing

- Every one of the 96 cells now has exactly one output for any input. No
  post-draw choice exists anywhere in the pipeline.
- The conventional corner (C1=zero-pad, C2=exact-wide, C3=final-once,
  C4=truncate, s=15) reproduces `ecs/fir_q15.ecs.yaml` semantics exactly —
  but s=15 is excluded from C5, so no draw collides with the frozen kernel.
- Dual-oracle divergence risk from underspecification is closed: both oracle
  authors implement this document against the same drawn tuple, and vectors
  adjudicate implementation slips, not semantic gaps (the SPEC §2.4
  circularity the review named cannot arise from a semantic gap).
- One declared soft spot: the int32-wrap + per-add cell leaves C3 inert in
  accumulation (¼ × ½ = 1/8 of draws). The analysis reports whether the
  sealed draw landed there.

## Vector-authoring instruction (review F7, recorded for Agent B)

Acceptance vectors for the canary must include low-amplitude cases whose
outputs stay inside int16 range under EVERY C2×C3×C4 cell, so that boundary
(C1) and rounding (C4) bits are separately exercised rather than masked by
saturation; plus targeted cases that drive the accumulator across each drawn
bound. Written draw-blind; B authors the actual vectors after reading the
sealed tuple, per lane.
