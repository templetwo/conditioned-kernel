# Canary twin — sealed draw bundle (DO NOT EDIT; supersede only)

drawn_at_utc: 2026-08-06T23:16:20.963175+00:00
algorithm: canary-draw/1.0  (HMAC-SHA256 counter stream, rejection-sampled uniform; see procedure below)
seed_hex: 04be37618ae52bac5a28b462c1f7910c529adf95dee0d2eeb66b91b3efe734b3
performed_by: Anthony Vasquez Sr (principal investigator), per SUPERSESSION-002

## Mapping — the draw

| id | choice point | drawn value |
|---|---|---|
| C1 | left boundary policy | zero-pad |
| C2 | accumulator | exact wide accumulation |
| C3 | saturation placement | clamp final shifted result once |
| C4 | rounding on right shift | round-to-nearest, half away from zero |
| C5 | shift amount s (nonce) | 12 |

## Procedure (verbatim, sealed with the draw)

# Canary twin — derivation procedure (pre-draw)

**Status: procedure authored BEFORE the draw, per `evidence/limitations_notes_v1.md`
(Canary — sealed derivation procedure) and `evidence/SUPERSESSION-002.md`.**
Drafted by Agent A under Anthony's proceed authorization (seat board, 2026-08-06).
The draw itself is performed by Anthony. Neither build agent sees the drawn
mapping before it is sealed and stamped: the runner writes the bundle to disk
and prints only its SHA-256.

This file is the *procedure* (sealed artifact component 1 of 4). Running
`draw_canary.py` produces `DRAW.md`, the single artifact holding all four
components — procedure, seed, algorithm, mapping — plus the resulting draw,
which is then OpenTimestamped in the same act.

## What the canary twin is

Kernel six (SUPERSESSION-002): a twin of `fir_q15` with the **same signature**

    void fir_q15_canary(const int16_t x[256], const int16_t h[16], int16_t y[256])

whose contested specification bits are assigned by this sealed random draw
rather than by convention. The conventional `fir_q15` packet TEXT-pins four
choice points (`ecs/fir_q15.ecs.yaml` notes; `evidence/choice_point_map.md`
[A1]–[A4]). The twin draws its analogues, plus one nonce parameter that gives
the construct no corpus entry.

## Drawn elements and their option sets

Each option is a behaviour a competent implementer could write against the
unchanged signature. Enumeration order below is the order the algorithm
consumes; it is fixed here, pre-draw, and is part of the commitment.

| id | choice point | options, in draw order |
|---|---|---|
| C1 | left boundary policy (window indices n−k < 0) | 0: zero-pad · 1: edge-replicate (use x[0]) · 2: circular wrap (use x[n−k+256]) |
| C2 | accumulator | 0: exact wide accumulation (no intermediate wrap) · 1: 32-bit two's-complement wraparound, specified as DEFINED modular arithmetic |
| C3 | saturation placement | 0: clamp the final shifted result once · 1: saturating accumulation at every add |
| C4 | rounding on the right shift | 0: truncate (arithmetic shift) · 1: round-to-nearest, half away from zero |
| C5 | shift amount s (nonce parameter) | uniform over {12, 13, 14, 16} — 15, the Q15 convention, is excluded by construction |

**Anti-degenerate constraint, declared pre-draw:** C5 excludes 15, so the drawn
kernel always differs from the conventional twin in at least the scaling row.
No rejection/redraw rule exists; the first draw stands. (An earlier draft used
redraw-if-fully-conventional; a fixed exclusion is simpler, and a redraw
counter is one more thing a skeptic must trust. The cost — the canary never
tests the conventional shift — is accepted and declared.)

**What this buys:** a 16-tap Q15-style FIR with, e.g., edge-replicate boundary,
wrapping accumulator and a >>13 scale has no textbook or corpus entry.
Convergence on the drawn behaviour cannot come from priors; that is the zero
anchor (`choice_point_map.md` §3).

## Algorithm (sealed artifact component 3)

`canary-draw/1.0`, Python 3 standard library only, fully reproducible:

1. Seed: 32 bytes from `os.urandom` at draw time, recorded in `DRAW.md` as hex.
2. Deterministic stream: HMAC-SHA256(key = seed, msg = 8-byte big-endian
   counter), counter = 0, 1, 2, …; concatenated digests form a byte stream.
3. Uniform sampling: to draw uniformly from k options, take one byte at a time
   from the stream, rejecting values ≥ 256 − (256 mod k); accept value mod k.
   (For k ∈ {2, 4}, no byte is ever rejected; for k = 3, values 255 is
   rejected. Rejections consume the byte and advance the stream.)
4. Draw order: C1 (k=3), C2 (k=2), C3 (k=2), C4 (k=2), C5 (k=4, mapped onto
   {12, 13, 14, 16} by index).

A third party re-running the algorithm on the recorded seed reproduces the
mapping exactly. `draw_canary.py --verify DRAW.md` does this check.

## Seed separation (required)

The draw seed is generated fresh on this machine at draw time. It is not the
probe seed, is not derived from it, and never touches the Jetson
(`~/ecs/.probe_seed` remains a separate, single-device secret — PREREG §12.7).
Independent failure domains are preserved.

## Sequence, per the signed canary entry — no step skippable

1. Anthony runs `python3 evidence/canary/draw_canary.py` (one command).
2. The runner performs the draw and writes procedure + seed + algorithm +
   mapping + draw into `evidence/canary/DRAW.md` — one artifact.
3. The runner OTS-stamps `DRAW.md` in the same invocation (`ots stamp`),
   producing `DRAW.md.ots`, and prints ONLY the SHA-256 and stamp status.
4. Both files are committed. Only then may any arm touch the twin, and only
   then do the build lanes read the mapping to author the packet, vectors,
   signatures and dual sealed oracles (SPEC §6 hash-and-seal, unchanged).

## What the mapping is NOT

The drawn mapping never reaches a generation or repair prompt. SPEC §9's
three-ingredient rule is enforced by construction in
`harness/generators/prompt.py`; the canary packet TEXT will pin nothing the
draw assigned — the drawn behaviour is pinned by VECTOR (gate 5) and judged by
the sealed oracles, exactly the generator-invisible channel documented in
`choice_point_map.md` §6. A generator can only match the drawn behaviour by
reading the constraint surface; convention has no answer to offer.

## What this proves and does not prove

Per the signed canary entry: the seal proves the procedure, seed, algorithm,
mapping and draw existed before any arm touched the twin. It does not prove
the draw was fair or the seed unforeknown. Procedural guarantee about
ordering, not an architectural guarantee about intent.

