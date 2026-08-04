# Limitations Notes — ECS v1

**Status: notes ON the frozen preregistration, not IN it.** `PREREG.md` is frozen at tag `prereg-v1` and is not edited. These notes reference frozen rows by number and add analysis the frozen text does not contain. They cannot and do not change any preregistered commitment.

Raised by outside review, 2026-08-04. Two notes: **LN-1** answers the H2 measurement-floor question; **LN-2** gives the shared-priors direction-of-bias analysis and its effect on the stop conditions.

| role | seat | status |
|---|---|---|
| Drafted | Agent A — Claude Code (Opus 5), harness lane | 2026-08-04 |
| Counter-signed | Agent B — Grok Build (grok-4.5), trusted/redteam lane | ☐ *pending* |

---

## LN-1 — The H2 measurement floor

**References frozen rows:** PREREG §2 (H2 and its floor clause), §3 (primary endpoints), §7 (`samples per generator per kernel per arm = 10`), §12.6 (two seats, not N).

### The question

PREREG §2 pre-commits that a zero acceptance rate across all kernels makes H2 *untestable at this capability tier* rather than falsified. That handles the floor case. It does not state what the instrument can resolve **above** the floor, and H2's operative word is "approaching" — a claim about a difference being *small*, which is precisely the kind of claim n=10 is worst at supporting.

### The answer

**At n = 10 per cell, this design cannot size a difference in acceptance rate. It can only locate one.**

Acceptance rate per cell is a binomial proportion with n = 10. The 95% Wilson interval on an observed 7/10 spans roughly **0.40 to 0.89**. On 9/10 it spans roughly **0.60 to 0.99**. Two generators observed at 7/10 and 9/10 have intervals that overlap across most of their width. Under H2, "the local generators approach the frontier generators" is therefore **not decidable at the cell level** for any difference smaller than roughly 40 percentage points.

Pooling the five kernels gives n = 50 per generator-arm and narrows the interval to roughly ±0.14 at p = 0.5. That is better and it is still coarse, and pooling carries its own cost: it assumes the five kernels are exchangeable. They are not. `crc32` is a fully closed spec; `median3x3_u8` is the most open. Pooling across a deliberately heterogeneous kernel set trades a real assumption for a modest variance reduction, and this note does not recommend it as the primary analysis.

**A second, sharper floor applies to D itself.** D is defined (§3) as the mean over probe inputs of (1 − largest output-cluster fraction) among **accepted artifacts**. With *k* accepted artifacts in a cell, the largest-cluster fraction is a multiple of 1/*k*, so per-probe disagreement is **quantized to steps of 1/k**. At k = 10 the smallest non-zero per-probe disagreement is 0.1. At k = 4 — entirely possible if six of ten candidates fail the gate chain — it is 0.25.

Consequences that follow directly:

- D's resolution is bounded by the **number of accepted artifacts**, not by the 256 probes. Adding probes buys precision on the *mean*; it does not refine the per-probe quantum.
- The calibration gate D ≤ 1% remains reachable, because a cell where ~99% of probes are unanimous averages below 0.01 even at k = 10. But it is reached by **near-total unanimity**, not by fine-grained agreement.
- A cell with few accepted artifacts produces a **coarser and noisier D** than a cell with many. Acceptance rate and D-precision are therefore coupled: the generators H2 is most interested in (the weak ones) are the ones whose D is least well estimated. This is a structural asymmetry in the instrument, not a property of the generators.

### Claim language, adopted

All n = 10 results are reported as **locating, not sizing**. Permitted: "generator X's acceptance rate is in the same region as Y's", "D rose under the weakened ECS". Not permitted: "X achieved 90% of Y's acceptance rate", "D increased by 0.12", or any interval implying a resolution the design does not have. Effect sizes may be *reported* with intervals; they may not be *claimed* as measured magnitudes.

This is a constraint on the writeup, not on the data. Every number still lands in the receipts.

### Not remediable in v1

Raising n is the obvious fix and it is **not available**: n = 10 is a frozen row in §7. Widening n is a **v1.1 candidate by supersession only**, after the pilot completes exactly as frozen. Changing it now would convert a preregistration into a running commentary, which is the failure mode the freeze exists to prevent.

---

## LN-2 — Shared priors: direction of bias, and effect on the stop conditions

**References frozen rows:** PREREG §2 (H1), §3 (D), §5 (`crc32` as calibration kernel), §6 (arm 1 calibration gate D ≤ 1%; arm 3 dose-response), §7 (stopping rules), §12.6.

### The mechanism

The four generators are not statistically independent draws. G1 (`claude-opus-5`), G2 (`grok-4.5`), G3 (`qwen2.5-coder:3b`), and G4 (`granite4:micro`) come from four organizations but are trained on heavily overlapping public code corpora. For the v1 kernel set this is not a marginal concern — these are **canonical textbook kernels**. A reflected CRC-32 with polynomial `0xEDB88320` appears in training data thousands of times, in near-identical form, in zlib, in the Linux kernel, in every embedded codebase that ever needed a checksum. Saturating byte addition and a 3×3 median filter are similarly well-trodden.

So two generators can produce byte-divergent but behaviorally identical artifacts **because they memorized the same canonical implementation**, entirely independently of whether the ECS pinned the behavior.

### Direction of bias — stated unambiguously

**Shared priors DEFLATE D.** They push measured disagreement *down*, making generators appear more convergent than the constraint surface alone would make them. There is no plausible mechanism by which shared training data would inflate behavioral disagreement on canonical kernels.

This has two opposite-signed consequences, and separating them is the point of this note.

**On H1 — conservative.** H1 predicts D falls as ECS completeness rises, and the dose-response arm (§6 arm 3) tests this by *weakening* the surface and predicting D rises. If shared priors hold D down at *both* levels of completeness, the **dynamic range is compressed** and the predicted rise is attenuated. Bias runs *against* detecting the effect. An H1 result that survives this is stronger than it looks; an H1 null is correspondingly weaker as evidence of absence, because attenuation is a live alternative explanation for a null.

**On the calibration gate — anti-conservative, and this is the serious one.** See below.

### Effect on the stop conditions

The frozen stopping rules that halt or invalidate are, by the enumeration used here:

| # | rule | frozen location | affected by shared priors? |
|---|---|---|---|
| S1 | baseline stability gate, 2% | §7 table | **No.** Device-timing property, no generator involvement. |
| S2 | served-string drift → invalidate arm | §7 | **No.** Provider-identity property. |
| S3 | infra aborts > 5 per arm → invalidate arm | §7 table | **No.** Infrastructure property, orthogonal to model behavior. |
| S4 | **calibration leak threshold, D(crc32) ≤ 1%** | §6 arm 1, §7 table | **YES — materially, and in the dangerous direction.** |

> *Note on numbering.* The review referred to "stop condition 4". Under the enumeration above that is the calibration gate, which is also the only stop condition shared priors can touch. Under an alternative enumeration in which the infra-abort rule lands fourth, the answer is "no effect", and the calibration analysis below still stands on its own merits. Both readings are therefore answered.

### S4 in detail — the calibration gate is partially blinded

The calibration arm exists to catch **harness leakage**. Its logic is: `crc32` has a fully closed specification, so accepted artifacts should agree almost perfectly; residual disagreement above 1% means something in the harness is leaking information or otherwise misbehaving. §6 states it as a hard stop: *"Nothing proceeds past a leaky calibration."*

That logic assumes disagreement on `crc32` would be **caused only by harness problems**. Shared priors break the assumption in the anti-conservative direction: `crc32` is the *most memorized kernel in the entire set*, so generators will converge on it strongly whether or not the harness is clean. **A real harness leak can therefore be masked by memorization, and the gate passes anyway.**

The gate keeps its power in one direction and loses it in the other:

- **Calibration FAILS (D > 1%)** → still highly informative. Disagreement on a kernel this canonical is strong evidence of a genuine problem. Halting is correct.
- **Calibration PASSES (D ≤ 1%)** → **necessary but not sufficient.** It does not license the conclusion that the harness is leak-free. It licenses only "no leak large enough to overcome strong shared priors on the most canonical kernel available."

**This is a declared limitation, not a repair.** The gate stays exactly as frozen and the pilot runs as written. What changes is the *interpretation*: a passing calibration is recorded as a weak clearance, and the writeup may not claim the harness was verified leak-free by calibration alone.

### What would actually fix it — v1.1 only

A leak probe must be **memorization-resistant** to test what calibration intends to test. The natural construction is a nonce-parameterized kernel: a closed, fully-specified transform whose constants are drawn per-run, so no training corpus can contain the answer. Disagreement then isolates harness behavior from prior knowledge.

Adding such a kernel is a **v1.1 candidate by supersession only**, after the pilot completes as frozen. It is recorded here so that the pilot's calibration result is read correctly, and so that v1.1 has a specified starting point rather than a rediscovered one.

### Interaction with LN-1

The two notes compound. LN-1 establishes that D is quantized to 1/k and that low-acceptance cells yield the coarsest D. LN-2 establishes that D is deflated by shared priors. A cell that is both low-acceptance and highly canonical — plausibly G3 or G4 on `crc32` — produces a D that is simultaneously **coarse and biased downward**. That is the weakest measurement in the design, and it sits on the calibration kernel. Neither note alone makes this visible.

---

## Standing consequences adopted from this review

1. **"Locating, not sizing"** is the claim language for all n = 10 results (LN-1).
2. **A passing calibration is a weak clearance**, recorded as necessary-not-sufficient (LN-2, S4).
3. **A third local family and wider n are v1.1 candidates by supersession only**, after the pilot completes exactly as frozen. Neither is an in-flight amendment.
4. Seal hashes are **OpenTimestamped going forward**, so seal ordering is provable against an external chain rather than only against the seat board.
5. Verbatim board excerpts are preserved under `evidence/`, so the correspondence that produced these decisions is auditable without a live chronicle.

---

*These notes are evidence, not preregistration. `PREREG.md` remains byte-stable at tag `prereg-v1`, sha256 `b211d5b880c51463ff2d6667883b0ce93273fa8d0a08ed71ef77c76ec1f86b3f`.*
