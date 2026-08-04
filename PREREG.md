# PREREG v1 — Executable Constraint Surfaces on Jetson

**STATUS: DRAFT. NOT FROZEN. `prereg-v1` IS NOT CUT.**

Drafted by Agent A (Claude Code, Opus 5) at Agent B's request (seat board #13757), which proposed A-drafts / B-counter-signs / Anthony-freezes. Counter-signature and freeze are recorded in §11 and are both empty. **Nothing in this document is binding until Anthony says freeze and the tag is cut.**

Companion to `SPEC.md`. Where the two disagree, SPEC governs mechanism and this document governs *what was committed to in advance*. The point of freezing is that predictions and stopping rules are fixed before data exists.

---

## 1. What is being tested

An **Executable Constraint Surface (ECS)** is a machine-checkable specification packet: signature, input domain, forbidden constructs, acceptance vectors, and resource budgets. The claim under test is that the substrate is not producing software but **reducing uncertainty about an admissible region** until a candidate falls below an acceptance threshold, with source demoted to a regenerable, evidence-bearing intermediate.

Operationally: does a more complete constraint surface make independent generators converge on the same *behavior*, faster than it makes them converge on the same *text*?

---

## 2. Hypotheses

**H1.** As ECS completeness increases, behavioral variance across independent generators (D, plus between-model cycle and size variance) decreases, and decreases faster than implementation-text variance.

**H2.** The marginal value of model capability falls as ECS completeness rises: the local 3B-class generators under the full ECS achieve acceptance rates and D approaching the frontier generators under the full ECS, and beat frontier generators under the weakened ECS.

**H2 floor clause (pre-committed).** If a local generator's acceptance rate is zero across all five kernels in the main arm, H2 is recorded as **untestable at this capability tier**, not as falsified. A floored generator measures the instrument's lower bound, not the hypothesis. The floor is reported as an instrument limitation with the receipts, not as evidence against H2.

---

## 3. Primary endpoints

1. **D per kernel per arm.** For every probe input, cluster accepted artifacts by output; D = mean over probes of (1 − largest cluster fraction). D is the operational estimate of unpinned specification bits.
2. **Within-model vs between-model variance decomposition**, with bootstrap CIs over artifacts.
3. **Acceptance rate per generator**, with repair-trace length retained as the kinetic diagnostic.

Infra-aborted candidates (§7) are excluded from acceptance-rate denominators. This exclusion is pre-committed, not a post-hoc filter.

---

## 4. Generators, pinned

| id | provider | requested string | pinning | digest | license |
|---|---|---|---|---|---|
| G1 | Anthropic | `claude-opus-5` | **alias** | n/a | commercial API |
| G2 | xAI | `grok-4.5` | **alias** | n/a | commercial API |
| G3 | ollama (local, Jetson) | `qwen2.5-coder:3b` | digest | `f72c60cabf62` | **Qwen Research License (non-commercial)** |
| G4 | ollama (local, Jetson) | `granite4:micro` | digest | `89962fcc7523` | Apache-2.0 |

**`grok-4` is banned as a G2 string.** Measured 2026-08-04: requesting `grok-4` returns `grok-4.3`, and `grok-4` does not appear in the provider's model list. A harness logging its request string would have credited generations to a model that never ran.

**Provider pinning asymmetry — stated plainly.** Neither frontier generator is version-pinned. `claude-opus-5` and `grok-4.5` serve themselves as of 2026-08-04 but carry no date suffix, so a provider-side alias repoint can substitute the model mid-experiment. Anthropic publishes immutable dated strings (e.g. `claude-opus-4-5-20251101`); **xAI publishes no dated string for the 4.3/4.5 line.** G1 and G2 are therefore alias-pinned, and stability is enforced by our own served-string logging and mid-arm assertion (§7), **not by the providers**. The two frontier generators are **not equally reproducible**, and this document declines to imply otherwise.

**License note.** G3 is under a non-commercial research license. This is fine for this harness. Any productization must substitute `qwen2.5-coder:1.5b` (Apache-2.0) or rely on G4, and doing so would invalidate the G3 arm of this preregistration.

---

## 5. Kernel set v1

`crc32`, `sat_add_u8`, `fir_q15`, `matmul8_i32`, `median3x3_u8`. Integer only; fixed C interfaces; single translation unit; no allocation, globals, or I/O; fixed loop bounds; `<stdint.h>`/`<stddef.h>` only.

`crc32` is the **calibration kernel**: its spec is fully closed (poly `0xEDB88320` reflected, init `0xFFFFFFFF`, xorout `0xFFFFFFFF`, check `"123456789" -> 0xCBF43926`). Residual disagreement there diagnoses harness leakage, not model behavior.

Floating point is out of scope for v1.

---

## 6. Arms and run plan

1. **Calibration** — `crc32` only, all four generators, 10 samples each. Gate: **D(crc32) ≤ 1%** among accepted artifacts. If calibration is leaky, the run stops and the leak is found. Nothing proceeds past a leaky calibration.
2. **Main** — five kernels × four generators × 10 samples, full ECS packets.
3. **Dose-response** — `fir_q15` with `fir_q15.weak.ecs.yaml` (forbidden list dropped, budgets dropped, half the vectors withheld) × four generators × 10 samples. **Prediction: D and variance rise versus the main arm.**

---

## 7. Fixed parameters and stopping rules

| parameter | value |
|---|---|
| samples per generator per kernel per arm | 10 |
| repair iterations per candidate | 4 |
| temperature | **0.8, all four generators**, no per-provider variation |
| `num_ctx` (local generators) | 4096 |
| probe count | 256 per kernel |
| cycle cap | 3× baseline |
| size cap | 4096 bytes `.text` |
| baseline stability gate | 2% |
| calibration leak threshold | D ≤ 1% |
| infra retries per candidate | **3**, then infra abort |
| infra aborts per arm before invalidation | **5** |

**Served-string identity.** Every call records `model_string_requested` and `model_string_served`, the latter read from the provider's own response `model` field. The runner asserts served-string identity **within an arm**. If the served string changes mid-arm, **the arm is invalidated and rerun** — never averaged, never adjusted.

**Infra-fault classification.** Transport errors, runner terminations, and `barrier_ok: false` are **infrastructure faults, not candidate failures**: no sample consumed, no repair budget touched, excluded from acceptance-rate denominators. Retried after re-running the eviction barrier, capped as above.

**Per-cell batching.** A *cell* is one `(generator × kernel × arm)` triple. All samples within a cell run consecutively under a single verified barrier; the barrier re-runs only at cell boundaries. Interleaving within a cell is not permitted.

**Memory thresholds.** Single source: `harness/device/generators.json`. Measured, per model, at bring-up. `MemFree` is the admission metric; `MemAvailable` is recorded but **never** used for admission (see SPEC §4a.1).

---

## 8. Trusted tier and oracle blindness

Trust = pairwise agreement of two independently authored oracles + agreement with published check values where they exist + CBMC bounded equivalence where feasible. Disagreements resolve by vectors and bounded model checking, **never by discussion between agents**.

**Hash-and-seal (frozen by Anthony, thread #20).** For each kernel, each seat independently authors its oracle, computes the SHA-256 of that file, and posts the hash to the seat board. **Content is revealed only after both hashes exist.** Ordering is thereby a receipt rather than a promise.

This exists because a blindness breach is the one failure in this design that produces **no symptom anywhere**: two echoing oracles still pass vectors, still close under CBMC (both share the bug), and still yield clean calibration D.

`harness/measure/crc32_ref.c` is a **P0 bench fixture, not an oracle of record.** P1 oracles are authored fresh under this mechanism.

An accidental breach is reported on the board rather than proceeded past.

### Seal hash table — to be filled during P1, before any reveal

| kernel | Agent A oracle SHA-256 | Agent B oracle SHA-256 | both posted | revealed |
|---|---|---|---|---|
| crc32 | *(pending)* | *(pending)* | ☐ | ☐ |
| sat_add_u8 | *(pending)* | *(pending)* | ☐ | ☐ |
| fir_q15 | *(pending)* | *(pending)* | ☐ | ☐ |
| matmul8_i32 | *(pending)* | *(pending)* | ☐ | ☐ |
| median3x3_u8 | *(pending)* | *(pending)* | ☐ | ☐ |

**Probe blindness.** Nothing in `trusted/probes/` and nothing derived from probe outcomes may appear in any generation or repair prompt. The probe seed lives only on the Jetson and is never read by the prompt-building path. Probes are not a gate and never trigger repair.

**Prompt content rule.** A generation or repair prompt is built programmatically from exactly: the rendered ECS packet, the C signature, and (repair only) the current gate's feedback. Never probe data, oracle source, other candidates, or other models' outputs. The prompt SHA-256 is stored in every receipt.

---

## 9. Device and measurement provenance

Bring-up receipt: `receipts/phase0.json`, sha256 `a234c6e9cca2073b2c3a144eb9f212b1712bc0e1d917c065716faccd89d44b65`, verified identical on repo and device.

- Host `tony-jetson`, aarch64, L4T R36.4.7, kernel 5.15.148-tegra, 7619 MB total.
- Power mode **MAXN_SUPER (mode 2)**. Mode table on this board: `0=15W, 1=25W, 2=MAXN_SUPER, 3=7W`. **Mode 0 is not maximum performance on this hardware.**
- `jetson_clocks` applied; measurements on isolated core 3; `scaling_cur_freq` read before and after, mismatch discards the measurement.
- **`timing_source: "clock"`** — `perf` is not installed on this device, so timing uses `clock_gettime(CLOCK_MONOTONIC_RAW)` under pinned clocks per SPEC §4. **Timing sources are never mixed within an arm.**
- Baseline CRC32: median 59296.0 ns, MAD 0.0, spread 0.0000% over 10 batches × 1000 measured, 200 warmup. Check value verified on device.
- Generator qualification under the F1 fail-closed barrier: `receipts/qualification/qualification_ecs_g3g4_pathb_20260804T185521Z/`, sha256 `14f3f60926e5b255cdbcb2f992d38a2fbc85f609236b9c37df937001f5d390c3`. Both G3 and G4 QUALIFIED, zero infra faults.

Pre-F1 qualification records are **not** device verdicts and are annotated as superseded at `receipts/qualification/SUPERSEDED_20260722_macbook_qualification.md`.

---

## 10. Phase 2 transition criterion (verbatim, pre-committed)

> Denser-than-C emission begins only when a search-based generator beats the `-O3` baseline on cycles or size by more than measurement variance, on at least one kernel, while passing identical gates. Until that fires, the conventional backend retains its seat.

---

## 11. Signatures

| role | seat | status |
|---|---|---|
| Drafted | Agent A — Claude Code (Opus 5), harness lane | 2026-08-04 |
| Counter-signed | Agent B — Grok Build (grok-4.5), trusted/redteam lane | ☐ *pending* |
| **Frozen** | Anthony Vasquez Sr. | ☐ *pending — tag `prereg-v1` NOT cut* |

Amendments after freezing follow supersession discipline: the predecessor stays, annotated, with a carry-forward of what it still teaches. Nothing is edited in place or quietly removed. See SPEC §4a / §4a.1 for the worked example.

---

## 12. Known limitations, declared in advance

1. **Frontier generators are alias-pinned, not version-pinned** (§4). Reproducibility of G1 and G2 depends on providers not repointing aliases, which we cannot enforce and only detect.
2. **G3 is non-commercially licensed.** The G3 arm is not reproducible under a commercial license without substitution.
3. **`perf` is unavailable**, so cycle counts are wall-clock derived under pinned clocks rather than hardware counters.
4. **Oracle blindness is enforced by hash-and-seal, a procedural mechanism**, not by an architectural barrier. It makes ordering auditable; it does not make a breach impossible.
5. **The house-wide Jetson model matrix is stale** (thread #21). Only G3 and G4 are qualified under F1. No claim is made about other models on that device.
6. **Two seats, not N.** Independence rests on two authors with separate lanes and a shared repo, not on a population.
