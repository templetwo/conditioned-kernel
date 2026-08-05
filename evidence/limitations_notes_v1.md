# Limitations Notes — ECS v1

**Status: notes ON the frozen preregistration, not IN it.** `PREREG.md` is frozen at tag `prereg-v1` and is not edited. These notes reference frozen rows by number and add analysis the frozen text does not contain. They cannot and do not change any preregistered commitment.

Raised by outside review, 2026-08-04. **LN-1** answers the H2 measurement-floor question; **LN-2** gives the shared-priors direction-of-bias analysis and its effect on the stop conditions; **LN-3** gives the gate-chain counter-pressure analysis. Two procedures follow the notes: the **post-arm census** and the **canary**.

| role | seat | status |
|---|---|---|
| Drafted | Agent A — Claude Code (Opus 5), harness lane | 2026-08-04 (LN-1, LN-2) · 2026-08-04 (LN-3, census, canary) |
| Counter-signed — **LN-1 and LN-2 only** | Agent B — Grok Build (grok-4.5), trusted/redteam lane | **2026-08-04** (seat board after #13866; Wilson + quantization verified) |
| Counter-signed — **LN-3, census, canary** | Agent B — Grok Build (grok-4.5), trusted/redteam lane | **2026-08-04** (seat board after #13878; scoped to LN-3 + census + canary only) |
| Counter-signed — **LN-2A** | Agent B — Grok Build (grok-4.5), trusted/redteam lane | **2026-08-05** (seat board after #14016; observation accepted with one bound on inference) |
| Counter-signed — **LN-4** | Agent B — Grok Build (grok-4.5), trusted/redteam lane | **2026-08-05** (seat board after #14108; scoped to LN-4 only) |
| Counter-signed — **LN-5** | Agent B — Grok Build (grok-4.5), trusted/redteam lane | **2026-08-05** (seat board after #14132; scoped to LN-5 only) |

> **Signature scope, stated so it cannot be misread.** Agent B's first counter-signature was given against LN-1 and LN-2 as they stood at commit `17f73fa`. LN-3, the post-arm census specification, and the canary entry were added afterwards at Anthony's direction. The second counter-signature covers **only** those later sections. LN-1/LN-2 remain under the first row. LN-2A, LN-4, and LN-5 each have their own rows; none is covered by any other signature. Do not read any signature as covering material outside its row.

**Agent B verification (counter-sign, not freeze of PREREG):**
- LN-1 Wilson 95% for 7/10 recomputed: **[0.397, 0.892]** — matches the note's ~0.40–0.89.
- LN-1 quantization claim accepted: with *k* accepted artifacts, largest-cluster fraction ∈ {0, 1/*k*, …, 1}; per-probe (1 − max frac) steps by **1/*k***; 256 probes refine the *mean*, not the quantum. Coupled acceptance/D-precision asymmetry accepted as structural.
- LN-2 deflation of D by shared priors on *canonical* kernels accepted; no strong reverse mechanism found that would *inflate* D on textbook CRC/sat kernels. Residual floor from *competing memorized variants* can produce small residual disagreement — it does **not** reverse the anti-conservative read of S4 (a pass remains necessary-not-sufficient).
- S4 interpretation (weak clearance on pass; halt still correct on fail) accepted as **declared limitation, not a repair** of the frozen gate.
- Claim language **"locating, not sizing"** for all n=10 results: adopted for this seat's writeups.
- v1.1 (third local family; wider n; nonce calibration kernel): **supersession only after pilot as frozen**.

**Agent B verification — second counter-sign (LN-3, census, canary only):**
- **LN-3 gate-chain bias.** Accepted: D is defined over *accepted* artifacts, so gates 1–6 sit inside the estimand. Gates 3–5 behavior-correlated → **deflate** D; gate 6 performance-only → **inflates only when it removes a largest-cluster member** (note already states this; minority removals would deflate — the budget-only count should be interpreted with that conditional). Lint/compile neutral accepted.
- **Net conservative D.** Accepted as writeup law: headline D is a **lower bound** on pre-filter behavioral disagreement, compounding LN-2.
- **Budget-only rejection count.** Accepted as reporting requirement. With first-failure gate order, "budget-only" = failed gate 6 after passing 1–5 — countable from `gate_results` without ambiguity. Zero such rejections ⇒ no inflationary term from gate 6 in that cell.
- **Not a repair.** Thresholds and chain stay frozen; interpretation + co-reporting only. Correct discipline.
- **Post-arm census.** Accepted: once after all arms close; sanitized rebuild; **CRASH is a labeled output class per probe** (not discard). Rationale on cross-build UB accepted. Scope bound accepted: exploratory D only; never replaces preregistered endpoint; does **not** refine 1/*k* (that needs sample-to-quota / v1.1).
- **Canary.** Mechanics accepted: procedure+seed+algorithm+mapping sealed and OTS'd **with the draw, before any arm touches the twin**; draw seed **≠** probe seed (independent failure domains; protects §12.7 and dual blindness). Honesty flag on purpose-as-inferred accepted — mechanics stand if framing is later corrected. Does-not-prove list (fairness/intent) accepted as parallel to §12.4 procedural seals.
- **Protected signature scope.** A correctly refused to let the LN-1/LN-2 signature cover post-hoc material. That is the dual-lane design working.

**Agent B verification — LN-2A counter-sign only:**
- Observation accepted: four unpinned fir_q15 bits, two seats, identical choices, 22,112/0 agreement, prediction pre-registered and failed. That is a real instance of convention filling SPEC silence under a protocol that blocked communication and attested order.
- Consequence accepted for writeup: low measured D **must not** be attributed to the ECS alone without qualification; pilot cannot distinguish surface-pinning from shared textbook.
- "What this does NOT establish" (n=1, no counterfactual, no numeric D correction, choices not "wrong"): accepted as load-bearing anti-overclaim.
- **One bound on inference (not a rejection):** seat-level convergence illustrates prior strength under careful human authorship of a *standard* DSP shape. It does **not** prove the effect is at least as strong among four generators (models may diversify more on failure modes, or less). Direction is the same; rate is unmeasured. Consistent with locating-not-sizing.
- v1.1 nonce / non-standard kernel to separate explanations: accepted, supersession only after pilot as frozen.

**Agent B verification — LN-4 counter-sign only:**
- Core asymmetry accepted: formal coverage (2/5) is strongest on the closed kernels and absent on the more open ones — inverse to experimental interest. Structural, not bad luck.
- "Where feasible" resolves to two kernels: accepted; must be stated as a number, not left inside the hedge.
- Writeup law accepted: gate 4 **per kernel only**; never aggregate "gate 4 clean" across five.
- sat_add exhaustive differential as complete element-domain argument (independent of CBMC): accepted — that kernel has two strong assurance layers.
- matmul basis coverage "structurally suggestive, not a proof": accepted. The hole is exactly bilinearity of *implementations*; A correctly refused to promote it. No overclaim found.
- v1.1 more compute / proxy kernels: accepted as supersession only after pilot as frozen.
- Stopping after measurement rather than grinding wall clock: correct research hygiene.

**Agent B verification — LN-5 counter-sign only:**
- Coupling description accurate: B authored all vectors; A drafted all packets after reading vectors/oracles.
- Weaker-of-two-couplings analysis accepted: B drafting would couple both channels in one seat (worse).
- Direction deflationary for D at full, compounds LN-2/LN-3: accepted.
- Channel warning does **not** mitigate implicit complementarity: accepted — important anti-false-coverage claim.
- Reporting: full-arm D lower bound on independently authored prose: accepted.
- Layout residual: VECTOR-pinned (board #14126) is consistent with this note — generator judged on a bit not told in prose.

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

## LN-2A — Empirical addendum: the authoring seats converged on an underspecified kernel

**Status: observation, added 2026-08-05 after the `fir_q15` seal cycle. Requested by Agent B at board #14010 and drafted for its counter-sign. Amends nothing; LN-2's argument stands and this supplies its first instance.**

**References:** LN-2 above; PREREG §2 (H1), §3 (D), §12.6 (two seats, not N); board #14001 (prediction, posted pre-reveal), #14003, #14008, #14010.

### What happened

LN-2 argued from mechanism that shared training priors deflate D — that generators may converge because they memorized the same canonical implementation rather than because the constraint surface pinned the behavior. It was an argument. It now has an instance, and the instance came from the **authoring seats**, not the generators.

`fir_q15` is the first kernel in the set with substantial latitude. Its SPEC §5 domain reads `Q15, saturating accumulate >>15`, which does not determine an implementation. Before revealing, Agent A named four places where it does not (board #14001, posted before either reveal so it could not be retrofitted):

| bit | the ambiguity | Agent A | Agent B |
|---|---|---|---|
| A1 | boundary for `y[0..14]`, where the filter reaches past `x[0]` | zero-pad left | zero-pad left |
| A2 | accumulator width — 16 products of two int16 reach 2^34, **overflowing int32** | `int64_t` | `int64_t` |
| A3 | whether "saturating accumulate" saturates the accumulator or the result | saturate the result, after the shift | saturate the result, after the shift |
| A4 | rounding on `>>15` | truncating arithmetic shift | truncating arithmetic shift |

**Four underdetermined choices. Two independent authors. Identical on all four.** Differential testing found 0 disagreements across 22,112 vector-sets, with coverage aimed specifically at each named bit rather than at random input alone.

Agent A had predicted disagreement. The prediction failed, and the failure is the result.

### Why this is evidence for LN-2 rather than a curiosity

The two seats are independent in every way the protocol can enforce: separate lanes, no shared chat context, hash-and-seal ordering externally timestamped before either reveal. Whatever produced the convergence, it was **not** communication between them, and the ordering receipts establish that.

What remains is the specification and the priors. The specification demonstrably did not pin these four bits — that is the premise of the whole exercise, and it was documented before anyone looked. So the convergence came from somewhere else: the standard Q15 DSP pipeline is established enough in the shared corpus that the spec's silence was filled by **convention rather than by choice**.

That is precisely LN-2's mechanism, observed one level up from where LN-2 predicted it.

**Bound on the extrapolation (Agent B, counter-sign #14018).** An earlier draft of this note said there was *no reason to expect the effect operates less strongly between four generators*. That is stronger than the observation supports and has been withdrawn. Careful, deliberate authorship of a textbook DSP shape by two seats is not the same process as sampling a model at temperature 0.8, and a co-occurrence between seats does not measure a rate among generators. What the observation establishes is that **prior strength is sufficient to fill this specification's silence** — the direction is the same, the magnitude is unmeasured, and per LN-1 this locates the mechanism without sizing it.

### The consequence, stated sharply

**Low measured D cannot be read as the ECS having pinned the behavior.** It is consistent with the constraint surface doing its job. It is equally consistent with every generator having learned the same textbook. The pilot as designed **cannot distinguish these two explanations**, and this addendum exists so that the writeup does not silently assume the first.

This compounds the S4 finding in LN-2: `crc32` is the most canonical kernel in the set, and the calibration gate's power against harness leakage is weakened by exactly this mechanism. `fir_q15` now shows the mechanism is not confined to the maximally-canonical case — it reached a kernel with four genuinely open choices.

### What this does NOT establish

Stated plainly, because the observation is seductive and the sample is one:

1. **n = 1 kernel, 2 authors.** This is a single co-occurrence, not a rate. It cannot support any claim about how often convergence-by-convention happens.
2. **It is not a controlled comparison.** There is no counterfactual arm in which the seats lacked shared priors, so the effect is not isolated, only illustrated.
3. **It does not quantify deflation.** Nothing here licenses a numeric correction to D. Consistent with the "locating, not sizing" rule (LN-1), this locates a mechanism; it does not size it.
4. **It does not imply the choices were wrong.** All four readings are defensible and arguably correct. The point is not that convention produced bad answers — it is that convention, not the specification, produced the *agreement*.

### The LN-2A family, graded by convention strength

LN-2A is no longer a single observation. Five kernels sealed and revealed under hash-and-seal produced **five agreements out of five**, across choice points that differ enormously in how open they actually were. Treating those five as equivalent evidence would be a mistake, so each instance carries a grade.

**Convention strength** is how strongly established practice pins a choice when no channel of the packet pins it. **The evidentiary weight of an agreement is inverse to it.**

| instance | choice point | convention strength | what the agreement shows |
|---|---|---|---|
| fir_q15 [A1]–[A4] | boundary, accumulator width, saturation placement, rounding | **contested** | **the strong instance.** All four have live alternatives in competent practice — int32 accumulators (UB on this domain), round-to-nearest, saturating accumulators, valid-region-only boundaries. Convergence had a real opportunity to fail four times and did not. |
| matmul8_i32 | memory layout | **near-default** | little. Row-major is C's own layout; the choice was barely open. |
| median3x3_u8 [D1] | memory layout | **near-default** | little. Same convention, same reasoning. |
| canary | *pending* | **zero anchor** | when it arrives: a nonce-parameterised construct has no corpus entry, so convergence via priors is **impossible**. This is the calibration point that makes the scale interpretable rather than merely ordinal. |

**Correction to this seat's earlier claim.** At board #14040 I argued `matmul8_i32` was a *stronger* instance than `fir_q15` because the penalty for guessing layout wrong is catastrophic. **Withdrawn — that is the wrong axis.** Consequence-of-divergence is not strength-of-convention. Row-major is near-universal in C regardless of how badly a transpose fails, so the high stakes do not make the agreement surprising; the choice was never really open. `fir_q15` remains the strongest instance in the family.

The high-stakes observation survives, attached to a different claim: a **vector-pinned** bit (see `choice_point_map.md`) is invisible to the generator at authoring time and fatal at gate 5. That is a statement about the gate chain, not about priors.

**Consequence for reading the pilot.** Five-for-five is not five units of evidence. It is one strong instance, two weak ones, and two closed kernels where no choice existed. The canary, once drawn, supplies the only zero-anchor reading in the design and is the single point at which convergence-by-convention can be excluded rather than argued.

### What would distinguish the explanations — v1.1 only

A kernel whose correct behavior is **not** recoverable from convention: nonce-parameterized constants, or a deliberately non-standard variant of a familiar shape, so that a generator cannot succeed by retrieval. Under such a kernel, convergence would have to come from the constraint surface, because there is no textbook to converge on.

This is the same instrument LN-2 called for against the calibration gate, and it is the same verdict: **v1.1 candidate by supersession only**, after the pilot completes exactly as frozen.

---

## LN-3 — Gate-chain counter-pressure on D

**References frozen rows:** PREREG §3 (D defined over **accepted** artifacts), §7 (gate chain via SPEC §7), §6 (arms). SPEC §7 gates 1–6.

### Why the gate chain is not neutral

D is computed over **accepted** artifacts (§3). The gate chain decides which artifacts are accepted. The chain is therefore inside the measurement, not upstream of it, and each gate biases D according to how strongly its rejection criterion correlates with behavior.

### Direction, gate by gate

| gate | rejects on | correlation with behavior | effect on D |
|---|---|---|---|
| 1 lint (forbidden surface) | includes, `malloc`, `static`, VLAs, recursion, I/O | ~none among artifacts that would otherwise pass | **neutral** |
| 2 strict compile | won't build under `-Werror` | not a behavior | **neutral** |
| 3 sanitized run | UB / ASan reports on the vector set | strong | **deflates** |
| 4 CBMC | memory safety, bounded equivalence vs oracle | strong | **deflates** |
| 5 acceptance vectors | bit-exact mismatch on committed vectors | strongest in the chain | **deflates** |
| 6 budget caps | cycles, `.text` size, stack | ~none — a *performance* criterion | **inflates when it removes a consensus member** |

**Behavior-correlated gates deflate.** Gates 3–5 remove artifacts precisely because they behave differently from the oracle. That is the same disagreement D exists to measure, so removing those artifacts removes disagreement from the accepted set.

**Budget rejection is bidirectional, and its sign depends on which cluster it removes.** *(Correction contributed by Agent B at counter-sign, seat board #13880. The original text stated only the inflationary case and was incomplete.)*

Gate 6 rejects on speed and size, criteria essentially uncorrelated with correctness. Its effect on D therefore depends entirely on where the rejected artifact would have landed:

- Removing a member of the **largest output cluster** → largest-cluster fraction falls → per-probe disagreement **rises**. D **inflates**. A correct-but-slow artifact discarded by the cycle cap makes survivors look *less* unanimous than they were.
- Removing a member of a **minority cluster** → the dissenter disappears → largest-cluster fraction rises → D **deflates**. This is the more common case whenever the majority is also the well-optimized implementation, which for canonical kernels it often will be.

So the budget-only rejection count **does not by itself bound the inflationary term.** It bounds the *magnitude* of gate 6's influence without fixing its *sign*.

**Resolving the sign requires knowing the rejected artifact's cluster**, which the pilot cannot observe directly: a budget-rejected artifact never reaches the probe run. The post-arm census is the natural place to recover it — running budget-rejected artifacts against the probes under the census build would reveal which cluster each *would* have joined, making gate 6's direction attributable per cell instead of merely bounded. That extension is **not** part of the census as specified below and is flagged here as a v1.1 candidate; the census as frozen in this document runs on accepted artifacts only.

Until then, the required co-report is the budget-only count **with the explicit note that its direction is unresolved**. Reporting it as a bound on inflation alone would be the same overclaim this note exists to prevent.

**Lint and compile are neutral.** They reject on surface form and buildability, neither of which predicts which output cluster an artifact would have joined.

### Net direction, and the sentence that matters

**Reported deflation is net and conservative.** Gate 5 is by far the strongest filter in the chain, and gates 3–5 all push the same way. Gate 6 is bidirectional but only one of its two directions inflates — removal of a largest-cluster member — while minority-cluster removal deflates alongside gates 3–5. The deflationary terms therefore dominate under any assignment of gate 6's rejections. Measured D **understates** true behavioral disagreement, and an observed D is a lower bound on what the generators actually exhibited before filtering.

Agent B's correction *strengthens* this conclusion rather than weakening it: recognising that gate 6 can also deflate removes the possibility that a large budget-rejection count silently reverses the net sign. The worst case for conservatism is that *every* budget-only rejection removed a largest-cluster member, and even then gates 3–5 dominate.

This compounds with LN-2, which finds shared priors deflate D as well. Two independent deflationary pressures act on the same endpoint. Every headline D in this study should be read as conservative.

### The inflation term is measurable, not merely assumed

The receipt records which gate rejected each candidate (SPEC §10, `gate_results` per gate). Budget-only rejections — artifacts that passed lint, compile, sanitize, CBMC and vectors, and failed only gate 6 — are therefore **countable**. Their count bounds the inflationary term directly rather than leaving it as an argument.

Reporting requirement adopted: every D is accompanied by the budget-only rejection count for its cell, **reported with its direction explicitly marked unresolved** (see the bidirectionality correction above). A cell with zero budget-only rejections has no gate-6 term at all and its D is purely conservative. A cell with several has a bounded *magnitude* of gate-6 influence and an unknown sign, which is a weaker and more honest statement than the bound on inflation alone that this note originally claimed.

### Not a repair

The gate chain runs exactly as frozen. Caps are sanity bounds, not optimization targets (SPEC §7 gate 6), and actuals are recorded either way. This note changes interpretation and adds a reporting requirement; it changes no threshold.

---

## Post-arm census — specification

**Status: exploratory procedure. Runs once, after all arms close. Sharpens the exploratory D only. Does not touch the preregistered endpoint.**

### Procedure

1. Runs **once**, strictly **after every arm has closed**. Not during an arm, not per arm, not iterated. A single pass cannot be tuned against a result it has already seen.
2. Rebuilds every accepted artifact under the **sanitized configuration** (`-O1 -g -fsanitize=undefined,address -fno-sanitize-recover=all`), the same configuration as gate 3, and runs it against the full probe set.
3. **A crash is a labeled output class, per probe** — not a discard, not a missing value. If artifact *j* traps on probe *i*, its output for probe *i* is the class `CRASH` (with the sanitizer's diagnostic recorded), and that class participates in clustering exactly like any value.

### Rationale — cross-build instability of undefined behavior

An artifact containing UB can produce a value under the `-O3 -mcpu=native` measurement build and trap under sanitizers. The two builds disagree because the program has no defined behavior to be stable about.

Discarding crashes would silently drop exactly the artifacts whose behavior is **least pinned by the specification** — which is the quantity D is trying to estimate. Dropping them biases the exploratory picture toward artifacts that happen to be well-defined, understating unpinned specification bits at precisely the place they are most visible. Labeling `CRASH` as an output class keeps that information inside the measurement.

It is also the honest encoding: two artifacts that both trap are not thereby in agreement about a *value*, but they do agree about something real, and one that traps while another returns a value genuinely disagree. Clustering handles that correctly only if `CRASH` is a class.

### Scope — explicitly bounded

- The census **sharpens the exploratory D only.** It is reported as exploratory, labeled as such, and never substituted for the preregistered endpoint.
- **The frozen D keeps its definition and its quantum.** Per LN-1, per-probe disagreement is quantized to 1/*k* in accepted-artifact count. The census does not change *k* and therefore does not refine that quantum.
- **The frozen quantum waits on sample-to-quota.** Refining it requires raising *n* to a quota, which is a frozen row in §7 and a **v1.1 candidate by supersession only**, after the pilot completes as frozen.

The census is a lens on data already collected. It is not a second experiment and produces no preregistered claim.

---

## Canary — sealed derivation procedure

**Purpose.** A canary is a pre-committed random assignment whose mapping is provably fixed before the experiment can interact with the thing it marks. Its value is entirely in the *ordering*: a canary constructed after results exist proves nothing, because it could have been chosen to fit them.

> **Scope note, stated honestly.** "Canary" and "twin" enter this project through the outside review and have no prior definition in `SPEC.md`, `PREREG.md`, or the seat board. The constraints below are as specified by the review and are unambiguous. The *purpose* sentence above is this seat's reading and is flagged as such — if the reviewer intended a different function, the mechanics still hold and only the framing needs correcting.

### What is sealed

All four artifacts are recorded, sealed, and OpenTimestamped **together, as one commitment**:

1. **Derivation procedure** — the full written method by which the canary is produced, in enough detail that a third party can reproduce it from the seed alone.
2. **Seed** — the specific value the draw consumes.
3. **Algorithm** — the exact deterministic function applied to the seed (named, versioned, no "a PRNG").
4. **Mapping** — what the drawn values are assigned *to*.

### When it is sealed

**The stamp is taken with the draw, before any arm touches the twin.** This is the load-bearing constraint and it is not negotiable after the fact: an OTS proof dated after an arm has run cannot establish that the mapping preceded the data, which is the only thing the canary is for. The proof attests the sealed bundle existed at a time provably earlier than any interaction with the twin.

Sequence, in order, no step skippable:

1. Draw is performed from the sealed seed via the sealed algorithm.
2. Procedure, seed, algorithm, mapping, and the resulting draw are written into a single artifact.
3. That artifact is OTS-stamped and the proof is committed.
4. **Only then** may any arm touch the twin.

### Seed separation — required

**The draw seed is distinct from the probe seed.** They are separate secrets with separate derivations and are never derived from one another.

This is not tidiness. The probe seed lives only on the Jetson at `~/ecs/.probe_seed` and is a single-device secret whose compromise is unrecoverable from the git record (PREREG §12.7). If the canary draw consumed that same seed, then a party who obtained the probe seed would also obtain the canary mapping, and a party who inferred the canary mapping would gain information about the probes. Separate seeds keep them **independent failure domains**: compromising one yields nothing about the other.

It also keeps the two blindness properties independent. Probe blindness protects the generation prompts; the canary protects the ordering of an assignment. Deriving both from one secret would silently couple two guarantees the design deliberately keeps apart.

### What this proves and does not prove

**Proves:** the derivation procedure, seed, algorithm, mapping, and draw all existed at the attested time, and that time precedes any arm's interaction with the twin.

**Does not prove:** that the draw was fair, that the seed was chosen without foreknowledge, or that no one held the mapping privately before stamping it. Like hash-and-seal (PREREG §12.4), this is a **procedural** guarantee about ordering. It is not an architectural guarantee about intent.

---

## LN-4 — Gate 4 assurance is uneven, and it is uneven in the worst direction

**Status: drafted by Agent A at Agent B's assignment (board #14103); counter-signed by Agent B 2026-08-05 (board after #14108).**

**References frozen rows:** PREREG §8 (trust = pairwise agreement + published check values + "CBMC bounded equivalence where feasible"), §12.6; SPEC §7 gate 4.

### What gate 4 asks for, and what is computable

SPEC §7 gate 4 asks CBMC for two things: **memory safety** and **bounded equivalence versus the oracle**. Measured on the workstation this study actually runs on:

| kernel | bounded equivalence | memory safety | measured |
|---|---|---|---|
| `crc32` | **SUCCESSFUL** | included | n ≤ 6, unwind 60, ~5 s |
| `sat_add_u8` | **SUCCESSFUL** | included | n ≤ 4, unwind 10, seconds |
| `matmul8_i32` | incomplete | incomplete | >10 min at unwind 65; safety alone terminated at **>35 min**, unwind 70 |
| `fir_q15` | not attempted | incomplete | >10 min at unwind 300 |
| `median3x3_u8` | not attempted | not attempted | abandoned after the above |

**Gate 4 as written cannot be fully applied to the three larger kernels on this hardware.** This is declared as a limitation, not reported as a clean gate.

### The asymmetry, and why it is not a coincidence

The two kernels that carry a formal proof are the two **simplest** in the set: `crc32` has a fully closed specification, `sat_add_u8` is near-closed. The three that do not are the three with **more open choice points** — the ones whose unpinned bits the choice-point map had to enumerate.

That correlation is structural rather than accidental. The properties that make a kernel interesting for this experiment — larger state, wider domain, more room for a specification to be silent — are the same properties that blow up a bounded model checker's search space. **Formal-verification coverage is inversely correlated with specification openness.**

So the kernels where unpinned bits matter most are exactly the kernels we cannot formally verify. The instrument is strongest where the question is easiest.

### "Where feasible" was doing more work than it looked

PREREG §8 defines trust as pairwise oracle agreement, plus published check values where they exist, plus **"CBMC bounded equivalence on small n where feasible."** That hedge was written before anyone measured feasibility. It now resolves to *two of five kernels*, and that number belongs in the record rather than staying inside the word "feasible."

### The distinction that must not blur in the writeup

| kernel | what the trusted tier actually rests on |
|---|---|
| `crc32` | bounded **proof** (n ≤ 6) + published check value `0xCBF43926` reached independently by both seats + 24,359 sampled cases |
| `sat_add_u8` | bounded **proof** (n ≤ 4) + **exhaustive** differential over the complete 256×256 byte-pair space, 5,185,536 cases |
| `fir_q15` | 22,112 differential cases, targeted at the four named unpinned bits plus random |
| `matmul8_i32` | 24,106 differential cases, including all 4,096 single-element basis pairs |
| `median3x3_u8` | 20,519 differential cases, asymmetry-weighted because symmetric inputs cannot separate a transposed reading |

Sampled agreement across millions of cases is strong evidence. **It is not a proof.** Reporting "gate 4 clean" across all five would aggregate two different epistemic objects into one claim, and this note exists to prevent that.

### Two places the evidence is stronger than "sampled" suggests

Stated because understating is as much a distortion as overstating:

1. **`sat_add_u8`'s differential is exhaustive, not sampled.** Every `(a, b)` byte pair was tested — the operation is elementwise over a 256-value alphabet, so the input space per lane is small enough to enumerate completely. For that structure the differential result is a complete argument over the element domain, independent of the CBMC proof.
2. **`matmul8_i32`'s basis coverage is structurally suggestive.** Matrix multiplication is bilinear, and a bilinear map is determined by its action on basis pairs — so agreement on all 4,096 single-element pairs would imply agreement everywhere **if both implementations were known to be bilinear**. They are not known to be: an arbitrary implementation need not be linear in either argument. This raises confidence materially without closing the gap, and is recorded as a structural argument rather than a proof.

### What would close it — v1.1 only

More compute, a longer wall-clock budget, or bounded reductions of the kernels themselves (a 4×4 matmul, a 4-tap filter) verified as proxies. The proxy route is the cheap one and it is also the weakest, since it proves a property of a *different* kernel than the one under test. None of these is available in v1: the kernel set is a frozen row, and the pilot runs as written.

The safety harnesses are committed and correct. The obstacle is wall clock, not the harness — they will run for anyone with more of it.

---

## LN-5 — The packet prose and the acceptance vectors were not independently authored

**Status: declared limitation, agreed by both seats before packets existed (board #14116, #14118) rather than discovered afterwards. Counter-signed by Agent B 2026-08-05 (board after #14132).**

**References frozen rows:** PREREG §12.6 (two seats, not N); SPEC §9 (prompt content rule), §13 (both seats author packets).

### The coupling

Agent B authored **all five acceptance vector sets**. Agent A then drafted **all five ECS packets**, having previously authored oracles for all five kernels and having read every one of Agent B's oracles and vector files during the agreement passes.

So the two channels that constrain a generator — the prose it reads, and the vectors it is judged against — **did not come from independent minds working from the specification alone.** The packet author knew what the vectors already pinned.

### Direction of the effect

Prose written with knowledge of the vectors can end up **complementing** them: covering what they cover, or conversely leaving stated what they already enforce. Either way, the cell's *effective* completeness can differ from what the prose alone would suggest to a reader.

The plausible direction is **deflationary for D at `full`** — a generator faced with prose and vectors that reinforce each other has less room to diverge than the prose alone implies. That is the same direction as LN-2 (shared priors) and LN-3 (behavior-correlated gates), so it compounds rather than offsets. Every conservative-reading caveat those notes carry applies here too.

### Why the alternative split was worse, not better

The obvious remedy — have Agent B draft the packets — is **worse**. Agent B wrote the vectors, so it would hold *both* channels directly, in one seat, with no separation at all. With Agent A drafting, the two channels at least originate in different seats even though the second author had read the first's work.

Neither arrangement is uncoupled. This is the **weaker of the two available couplings**, chosen deliberately and declared rather than presented as a clean split.

### What would actually remove it

A third author who has seen neither the vectors nor the oracles, writing packets from the specification alone. That is not available: PREREG §12.6 already declares that independence here rests on two seats rather than a population, and this note is a concrete consequence of that limitation rather than a new one.

### What does *not* mitigate it

`harness/gates/packet_validate.py` emits a channel warning when packet prose mentions a term tied to a vector-pinned bit. **That catches explicit promotion. It cannot catch implicit complementarity.** A packet can be shaped by knowledge of the vectors without ever naming what they encode, and no textual check will see that. The warning is a guard against one failure mode and is not evidence against this one.

### Reporting requirement adopted

Any claim that a cell's D reflects its packet's completeness carries this note. The `full`-arm D values are read as **lower bounds on what independently-authored prose would have produced**, consistent with the conservative reading already adopted for LN-2 and LN-3.

---

## LN-6 — Alias exposure includes parameter contracts, not just model identity

**Status: drafted by Agent A after the temperature conflict, 2026-08-05. Counter-signature row pending. This is a gap in how PREREG §12.1 was written, recorded here because PREREG is frozen.**

**References frozen rows:** PREREG §4 (G1/G2 alias-pinned), §7 (temperature 0.8, all four), §12.1 (alias exposure).

### What §12.1 said, and what it missed

PREREG §12.1 declares:

> *Frontier generators are alias-pinned, not version-pinned. Reproducibility of G1 and G2 depends on providers not repointing aliases, which we cannot enforce and only detect.*

That frames the exposure as a question of **model identity** — will `claude-opus-5` keep pointing at the same weights. The mitigation built against it was served-string logging plus a mid-arm identity assertion, which is the right defence *for that framing*.

**The framing was too narrow.** An alias can keep its identity perfectly and change its **contract**: what parameters it accepts, what they mean, what it silently ignores. On 2026-08-05, requesting `claude-opus-5` with `temperature: 0.8` began returning `HTTP 400 — temperature is deprecated for this model`. The model string was unchanged. Nothing about identity moved. The *interface* moved.

### The detection asymmetry, which is the part that matters

| change | caught by served-string assertion? |
|---|---|
| alias repointed to different weights | **yes** — served string differs |
| alias keeps identity, rejects a parameter | **no** — but the call fails loudly, so it surfaces |
| alias keeps identity, **accepts a parameter and ignores it** | **no, and nothing else catches it either** |

The third row is the dangerous one and it is the one this project has no defence against.

We were lucky here: the contract change was **loud**. A `400` cannot be missed. But the same class of change could arrive silently — a parameter still accepted, still returning `200`, and quietly clamped or ignored. Every receipt would look correct. The served string would match. Acceptance rates and D would shift for a reason invisible in the entire record.

Had this arrived mid-arm in its silent form, G1's samples before and after would have been drawn under different sampling laws with **nothing in the data marking the boundary**.

### What should have been built, and is now specified

A **contract probe at bring-up**, recorded per arm:

1. Before an arm opens, issue a minimal request to each frontier generator with exactly the sampling parameters the arm will use.
2. Record the outcome in the arm's receipt: accepted, rejected, or accepted-with-warning.
3. Re-issue at arm close and compare. A contract that changed mid-arm invalidates the arm on the same rule as a served-string change.

This does not close the silent case — a parameter accepted and ignored still returns success at both ends. It converts the *loud* case from "discovered when a call fails" to "discovered before samples are spent," and it puts the contract state in the record so a later reader can see what the interface was, rather than assuming it was what the preregistration said.

**The silent case remains undefended and is declared as such.** Closing it would require an external check that the parameter had the effect it claims — for temperature, a distributional test over repeated samples, which is a v1.1 instrument and not a v1 one.

### Why this is recorded rather than fixed

PREREG §12.1 is frozen text. It is not amended, it is annotated: the exposure it names is real and its statement of scope is incomplete. Anyone reading §12.1 alone would believe served-string logging covers alias risk. It covers identity. It does not cover contract.

That correction belongs beside the original rather than replacing it, per the supersession discipline this project applies to SPEC §4a — the too-narrow framing is itself the worked example, and a reader who sees only the corrected version learns less than one who sees both.

---

## LN-7 — A gate can be silent, and silence read as a pass; gate 6 was, on four of five kernels

**Status: drafted by Agent A 2026-08-05 after Anthony held P2 open and the regeneration exposed the cause. Counter-signature row pending Agent B.**

**No experimental data is affected.** P3 has never run and no scored sample exists. This note is about the *instrument*, and it is recorded because the defect survived two-seat verification and would not have surfaced from the receipts it produced.

### What happened

`harness/measure/cycles.py` generated its bench driver against one hardcoded C signature — `uint32_t f(const uint8_t *, size_t)` — which fits `crc32` and none of the other four kernels. For those four the driver could not compile, the measurement returned an infrastructure fault, and gate 6 recorded the string `"baseline measurement unusable"` and **passed the candidate**.

Every `full`-arm packet declares three caps. On four of five kernels one of them, `cycles_ratio_max`, was never evaluated. The receipts read green, and both build agents had verified P2 as complete against exactly those receipts.

It became visible only after gates were made to fail closed (SPEC §7a.2), which converted the silence into an infrastructure abort. The correction did not introduce the defect. It made it un-greenable.

### Direction of the error, and why it is the worst available direction

Acceptance rate is a primary endpoint (SPEC §3). A gate that passes what it cannot measure **inflates** acceptance, and it inflates it for reasons that have nothing to do with the generator — the instrument's own coverage becomes an unmodelled term in a headline number. Worse, the inflation is invisible in the artifact it produces: a receipt reading `6_budget: pass` is byte-identical whether the cap was met or never checked.

This also bears on **LN-3**, which analyses gate 6's bidirectional influence on *D* and specifies that every reported *D* carry its cell's budget-only rejection count. That analysis presumes gate 6 enforces what it declares. Had this shipped, LN-3 would have described a gate that in practice enforced `.text` alone on four kernels, and its rejection counts would have understated nothing and overstated nothing — they would simply have been counting a different gate than the one documented.

### The part that generalises past this repo

*An instrument's silence is the failure mode that most resembles a result.*

A measurement that fails loudly gets fixed. A measurement that fails silently and defaults to pass becomes evidence, because every downstream reader treats the absence of a complaint as a confirmation. The question to ask of a harness is therefore not "does it catch failures" but **"what does it do when it cannot tell"** — and the answer must be a distinct third outcome, never a rounding into pass or fail. SPEC §7a.2 now fixes that outcome set.

### Why two-seat verification did not catch it

Both agents independently exercised the gate chain, and both checked the same property: *that the gates reject bad candidates*. Neither asked what a gate does when it cannot run. The redteam fixtures encode that same blind spot by construction — a fixture is built to be rejected, so a fixture set can only ever demonstrate the reject path.

**Adversarial review between agents does not automatically cover the space neither agent thought to look at.** The correction came from outside both seats.

### The gap this leaves open, which is not yet closed

Gate 6 evaluates three caps. Exactly one of them has ever been demonstrated to **reject**:

| cap | demonstrated to measure | demonstrated to reject |
|---|---|---|
| `text_bytes_max` | all five kernels | **crc32 only** (`crc32_budget_text_gate6.c`) |
| `stack_bytes_max` | all five kernels | **never** |
| `cycles_ratio_max` | all five kernels, post-fix | **never** |

The cycles and stack branches are, today, in the same evidentiary position the cycles branch occupied before this finding: believed to work, never observed working. That belief is now better founded — the measurements exist and cross-check — but "it produced a number" is not "it refused an artifact".

**Required to close, Agent B's lane:** a gate-6 fixture per kernel rather than per gate, including at least one artifact that exceeds `cycles_ratio_max` and one that exceeds `stack_bytes_max`. Until those exist, the writeup states gate 6's rejection evidence as `.text` on one kernel, and does not generalise it to the cap set.

### What does not mitigate this

That the caps are "sanity bounds, not optimisation targets" (SPEC §7 gate 6) is not a mitigation. A sanity bound that never fires is indistinguishable from an absent one, and the packet claims a constraint either way.

---

## Standing consequences adopted from this review

1. **"Locating, not sizing"** is the claim language for all n = 10 results (LN-1). Effect sizes may be *reported* with intervals; they may not be *claimed* as measured magnitudes.
2. **A passing calibration is a weak clearance**, recorded as necessary-not-sufficient (LN-2, S4). A failing calibration remains a hard halt.
3. **Every reported D carries its cell's budget-only rejection count, with its direction marked unresolved** (LN-3). Gate 6 is bidirectional: it inflates when it removes a largest-cluster member and deflates when it removes a minority-cluster one. The count bounds the magnitude of gate 6's influence, not its sign. Recovering the sign requires running budget-rejected artifacts against the probes, which is a v1.1 candidate and not part of the census as specified.
4. **All headline D values are read as conservative** — two independent deflationary pressures act on the same endpoint (LN-2 shared priors, LN-3 behavior-correlated gates).
5. **The post-arm census is exploratory and labeled as such.** It sharpens the exploratory D only, never substitutes for the preregistered endpoint, and does not refine the frozen 1/*k* quantum — that waits on sample-to-quota.
6. **Canary draws seal procedure, seed, algorithm, and mapping together, OTS-stamped with the draw, before any arm touches the twin.** The draw seed is distinct from the probe seed, keeping the two secrets in independent failure domains.
7. **Low measured D may not be attributed to the ECS without qualification** (LN-2A). Convergence by shared convention was observed directly between the two authoring seats on a kernel with four unpinned bits; the pilot cannot distinguish that from the constraint surface doing the work.
8. **A third local family, wider n, a nonce-parameterized calibration kernel, and a convention-resistant kernel are v1.1 candidates by supersession only**, after the pilot completes exactly as frozen. None is an in-flight amendment.
9. **Gate 4 results are reported per kernel, never aggregated** (LN-4). Two kernels carry a bounded-equivalence proof; three carry sampled differential agreement. "Gate 4 clean" across all five would merge two different epistemic objects into one claim.
10. **Packet prose and acceptance vectors were not independently authored** (LN-5). `full`-arm D is read as a lower bound on what independently-authored prose would have produced.
11. **A contract probe runs at arm open and close for each frontier generator** (LN-6), recording whether the arm's sampling parameters are accepted. Alias exposure covers parameter contracts, not only model identity, and the silent case — a parameter accepted and ignored — remains undefended and declared.
12. Seal hashes are **OpenTimestamped at seal time, before reveal** — the proof attests existence without disclosing content.
13. Verbatim board excerpts are preserved under `evidence/board_excerpts/` with a per-file hash manifest, so the correspondence is auditable without a live chronicle.
14. **Gate 6's rejection evidence is reported as `.text` on one kernel** (LN-7), never generalised to the cap set. `stack_bytes_max` and `cycles_ratio_max` have been demonstrated to measure on all five kernels and to reject on none. A cap that never fires is indistinguishable from an absent one.
15. **Every gate reports one of four outcomes — pass, fail, declared exemption, instrument fault — and an absence is never a pass** (LN-7, SPEC §7a.2). Which of *fail* or *instrument fault* an absence becomes is decided by cause, not convenience, so that failing closed does not trade a silent inflation for a silent deflation.
16. **Receipts name their instrument** (`harness_git_sha`, with dirtiness scoped to `harness/`, `ecs/`, `trusted/`, `SPEC.md` and that scope recorded). Receipts produced across different harness revisions are not pooled — every correction in SPEC §7a changed what "accepted" means.

---

*These notes are evidence, not preregistration. `PREREG.md` remains byte-stable at tag `prereg-v1`, sha256 `b211d5b880c51463ff2d6667883b0ce93273fa8d0a08ed71ef77c76ec1f86b3f`.*
