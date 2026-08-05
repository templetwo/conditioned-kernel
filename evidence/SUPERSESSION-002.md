# SUPERSESSION-002 — Kernel set: the canary joins the pilot as kernel six

**Dated 2026-08-05. Supersedes PREREG §5's kernel set and §6 arm 2's kernel count. Everything else in `prereg-v1` stands.**

`PREREG.md` at tag `prereg-v1` is **NOT edited**, and **DOI [10.5281/zenodo.21797326](https://doi.org/10.5281/zenodo.21797326) is unchanged**. The published preregistration remains byte-identical to what was frozen, sha256 `b211d5b880c51463ff2d6667883b0ce93273fa8d0a08ed71ef77c76ec1f86b3f`. This document sits beside it.

**Ruling: Anthony Vasquez Sr., 2026-08-05.**

> Supersede the kernel-set row: canary joins the pilot as kernel six, dual-signed, LN-2A cited as cause, receipt noting zero generation samples existed. I'll do the draw and seal the derivation today.

---

## The ordering claim, first, because everything else depends on it

**At the moment of this ruling, zero generation samples existed.** No generator had been called for a scored sample, on any kernel, in any arm. None has been called since.

This is checkable rather than asserted, and it should be checked:

| what exists in the repo | what it is |
|---|---|
| `receipts/p2_stub/*.json` | **stub** cells. The "generator" returns a sealed oracle verbatim; `model_string_served` reads `stub:oracle-verbatim`. No model produced these. |
| `receipts/redteam/*.json` | known-bad fixtures authored by Agent B, run to prove the gates reject them. |
| `receipts/phase0.json`, `receipts/qualification/` | device bring-up and model qualification. No ECS packet involved. |
| anything containing a real `model_string_served` | **does not exist** |

P3 has never run. The preregistration's ordering claim — predictions fixed before data exists — is intact, and the published archive still contains no results because there are none.

**This matters more here than it did for SUPERSESSION-001.** Changing a model string after data exists is bad. Changing the *kernel set* after data exists is the specific move that preregistration exists to prevent, and no amount of stated rationale would repair it. The defence is not the rationale below. The defence is that there is no data.

## What changes

| frozen row | status |
|---|---|
| **§5, kernel set** — `crc32`, `sat_add_u8`, `fir_q15`, `matmul8_i32`, `median3x3_u8` | **superseded**: a sixth kernel, the **canary twin**, joins |
| **§6 arm 2** — "five kernels × four generators × 10 samples" | **superseded**: six kernels × four generators × 10 samples (200 → 240 scored samples) |
| §6 arm 1, calibration | **unchanged** — `crc32` only. The canary is *not* a calibration kernel. |
| §6 arm 3, dose-response | **unchanged** — `fir_q15` with the weak packet. |
| §2 H2 floor clause, "all five kernels" | **read as the frozen five.** A generator floored on the frozen five is floored, whatever the canary does. Widening the floor clause to six would make it harder to trigger, which would weaken a pre-committed protection after the fact. It is not widened. |
| every other frozen row | unchanged |

## Cause: LN-2A, and it is a real threat to the central claim

LN-2A recorded an observation, not a worry: **the two authoring seats independently converged on the same choices for a kernel with four unpinned specification bits.** Two independent authors, no shared context, same answers — because both drew on the same conventions, not because anything in the constraint surface pinned them.

That leaves the build's headline finding with an unexcluded alternative. A low measured *D* under a full ECS is consistent with:

1. **the constraint surface did the work** — the ECS pinned the bits, which is the thesis; or
2. **shared convention did the work** — the generators agreed for the same reason the two seats agreed, and the ECS pinned nothing that was not already conventional.

Every kernel in the frozen five is a *conventional* kernel: crc32 has a canonical polynomial, FIR has a canonical shape, median has a canonical network. **On conventional kernels these two explanations make the same prediction.** No amount of additional data on the frozen five separates them, which is why this could not be fixed by running more samples.

The canary twin is the design's **only zero anchor**: a kernel whose unpinned bits are assigned by a sealed random draw rather than by convention. Convention cannot supply the answer because there is no convention to supply. If generators converge there, the constraint surface did it. If they converge on the conventional answer *against* the drawn mapping, LN-2A's alternative is not merely unexcluded — it is confirmed.

**As an evidence-level device the canary could not do that job.** It had to be a kernel in the pilot, generated against, scored, and reported, or it measures nothing about the generators. That is what this supersession changes.

## What this costs, declared

- **It is a post-freeze addition to the kernel set**, the change class most vulnerable to the charge of opportunism. That the addition is *adversarial to the hypothesis* — it can falsify the central claim and cannot flatter it — is an argument, not a proof, and is stated as such.
- **Sample count rises 200 → 240** in the main arm, with the attendant API and device cost. No stopping rule is relaxed to accommodate it.
- **Gate 4 tractability for the canary is unknown** until the kernel exists. It will be measured and declared under LN-4's existing discipline, never assumed.
- **The canary has no convention to borrow**, which is the point, and also means a generator may fail it for reasons unrelated to the ECS. Acceptance rate on the canary is therefore reported separately and is not pooled into the frozen five's acceptance rate.

## The protection that makes this safe to do at all

**Both analyses are reported.** The frozen-five analysis is computed and published exactly as `prereg-v1` specifies, unchanged, alongside the six-kernel analysis. A reader can see precisely what the addition did and did not change.

This is the structural guarantee that the added kernel cannot be *the thing that makes a result*. If the two analyses agree, the canary corroborates. If they disagree, that disagreement is itself the finding and is reported as one. Neither outcome is available for quiet selection, because both are pre-committed here, before the draw.

## Constraints carried forward unchanged

The canary's sealing procedure is already specified in `evidence/limitations_notes_v1.md` (canary entry, standing consequence 6) and is **not relaxed** by promotion to kernel six:

1. Derivation procedure, seed, algorithm, and mapping are sealed **together, as one commitment**, and OpenTimestamped **with the draw, before any arm touches the twin**. An OTS proof dated after an arm has run cannot establish that the mapping preceded the data, which is the only thing the canary is for.
2. **The draw seed is distinct from the probe seed** — separate secrets, separate derivations, neither derived from the other, so they remain independent failure domains.
3. The mapping never reaches a generation or repair prompt. SPEC §9's three-ingredient rule is enforced by construction in `harness/generators/prompt.py`, and the canary changes nothing about it.
4. The canary receives dual sealed oracles and a hash-and-seal reveal like every other kernel (SPEC §6). It is not exempt because it is new.

**Anthony performs the draw and seals the derivation.** Neither build agent sees the mapping before it is sealed and stamped. This document is written *before* the draw, which is the correct order: the commitment to include the kernel precedes knowledge of what the kernel says.

## Effect on the record

| artifact | status |
|---|---|
| `PREREG.md` @ `prereg-v1` | **unchanged**, byte-stable, still the frozen preregistration |
| DOI 10.5281/zenodo.21797326 | **unchanged**, still resolves to the original archive |
| PREREG §5, kernel set | **superseded by this document** |
| PREREG §6, arm 2 kernel count | **superseded by this document** |
| PREREG §6 arms 1 and 3 | unchanged |
| SUPERSESSION-001 | unaffected and still operative |
| every other frozen row | unchanged |

Any analysis or writeup citing the kernel set cites **this document alongside** `prereg-v1`, never in place of it.

## Signatures

| role | seat | date |
|---|---|---|
| Ruled | Anthony Vasquez Sr. | 2026-08-05 |
| Drafted | Agent A — Claude Opus 5, harness lane | 2026-08-05 |
| Counter-signed | Agent B — Grok Build (grok-4.5), trusted/redteam lane | **2026-08-05** (board after #14364; ordering claim re-verified this seat) |

## Receipts

- LN-2A and the LN-2A family grading in `evidence/limitations_notes_v1.md` — the cause.
- The canary entry and standing consequence 6, same file — the sealing procedure, unrelaxed.
- `receipts/` — the checkable form of the zero-samples claim above.
- Board: Anthony's ruling, Agent A's draft notice, Agent B's counter-signature.
