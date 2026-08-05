# ECS Build Spec v1
## Executable Constraint Surfaces on Jetson (aarch64)

Status: draft for build. Lineage: Conditioned Kernel (acceptance/repair), Sovereign Stack (witness/receipts), IRIS Gate Evo (convergence over authority), entropy-as-tunable-equilibrium (effective potential).

Core claim under test: the substrate is not producing software, it is reducing uncertainty about an admissible region until a candidate falls below an acceptance threshold. Source is demoted to a regenerable, evidence-bearing intermediate that stays in the receipt.

---

## 1. Topology

```
WORKSTATION (local terminals)                    JETSON ORIN NANO 8GB (via SSH)
+---------------------------+                    +----------------------------+
| Agent A: Claude Code      |                    |  ~/ecs  (only writable     |
|   (Opus) - HARNESS lane   |---- ssh jetson --->|   area for agents)         |
| Agent B: Grok agent       |                    |  gcc aarch64 native        |
|   - TRUSTED/RED-TEAM lane |                    |  ollama (local generators) |
+---------------------------+                    |  perf / clock pinning      |
        |  git repo = the only                   +----------------------------+
        |  coordination channel
        v
Generators under test (called by the harness, not by the agents):
  G1 Claude API (frontier)      G3 ollama qwen2.5-coder:3b   (on Jetson, 1.9 GB)
  G2 Grok API (frontier)        G4 ollama granite4:micro     (on Jetson, 2.1 GB)
```

Two roles, kept distinct on purpose:

- **Build agents** (A and B) construct and maintain the harness. They work in local terminals and reach the Jetson only over SSH.
- **Generators under test** (G1..G4) are plain API/ollama calls made by the harness runner, headless. Build agents never hand-write or hand-fix a candidate artifact. The 200-odd generation runs are cheap API calls driven by `runner.py`, not interactive agent sessions.

Rationale for four generators: H2 (below) needs a capability spread. Two frontier models plus two small local models gives between-model variance something real to measure.

**Local generator sizing (settled, see `compass_artifact_*.md`).** The Orin Nano 8GB exposes ~5.2 GB of usable unified memory after OS overhead, and the device is memory-bandwidth-bound rather than compute-bound. A 7B/8B Q4_K_M model (~4.7-4.9 GB) technically loads but leaves almost no KV-cache headroom and decodes slowly. G3/G4 are therefore 3B-class: `qwen2.5-coder:3b` (1.9 GB, code-specialized) and `granite4:micro` (2.1 GB, IBM Granite — a genuinely different family, which is what makes the between-model agreement measurement meaningful). Both leave ~3 GB of headroom.

Two consequences the harness must respect. First, license: Qwen2.5-Coder-3B is under the Qwen Research License (non-commercial) — fine for this harness, but if the arm is ever productized, drop to `qwen2.5-coder:1.5b` (Apache 2.0). Record the license string per generator in `PREREG.md`. Second, capability floor: if a 3B generator's acceptance rate is floored at zero across all kernels, H2 is untestable rather than falsified — pre-commit to reporting that as an instrument limitation, not as evidence.

---

## 2. Ground rules for build agents

1. **Lanes.** Agent A owns `harness/`. Agent B owns `trusted/` and `redteam/`. Neither edits the other's lane; requests go through `agents/requests.md` in the repo.
2. **Coordination through the repo only.** No shared chat context between agents. Independence is part of the experiment's integrity.
3. **Device discipline.** On the Jetson, operate only inside `~/ecs`. The only permitted system changes are the three documented bring-up steps (sudoers entry, perf sysctl, ollama pulls). Every sudo invocation gets a line in the phase receipt.
4. **Oracle independence.** Both agents write a reference implementation for every kernel, independently, before seeing the other's. The trusted tier is the pair agreeing with each other AND with published/derived vectors. Disagreements resolve by vectors and bounded model checking, never by discussion between agents.
5. **Probe blindness.** Nothing in `trusted/probes/` and nothing derived from probe outcomes may ever appear in a generation or repair prompt. See section 6.
6. **Verify before declare.** Any "done" claim in a phase requires the corresponding receipt to exist.

---

## 3. Repo layout

```
ecs/
  SPEC.md                     this file
  PREREG.md                   frozen before first pilot run (git tag prereg-v1)
  agents/
    claude-code.md            lane, do-not-touch paths, definitions of done
    grok.md                   same for Agent B
    requests.md               cross-lane asks
  ecs/
    schema/ecs.schema.json
    crc32.ecs.yaml            + one file per kernel
    fir_q15.weak.ecs.yaml     deliberately weakened variant (dose-response arm)
  trusted/
    oracles/                  two independent reference impls per kernel,
                              named <kernel>_<seat>.c, revealed only after
                              both seals are posted (section 6 amendment)
    vectors/                  acceptance vectors (committed)
    probes/                   generator spec + committed hash only; realized
                              probe data lives ONLY on the Jetson
  harness/
    runner.py                 state machine (section 9)
    device/                   phase0_bringup.py, eviction_barrier.py,
                              generators.json (SINGLE SOURCE for per-model
                              MemFree thresholds), seed_guard.py
    generators/               anthropic.py, xai.py, ollama.py adapters
    gates/                    lint, compile, sanitize, cbmc, vectors, budget;
                              oracle_agreement_<kernel>.c differential tests
    measure/                  bench_main.c, crc32_ref.c (P0 BENCH FIXTURE,
                              not an oracle of record)
  redteam/                    known-bad candidates the gates must reject
  receipts/                   one JSON per candidate, append-only
  results/
```

---

## 4. Phase 0 - device bring-up (Agent A leads, Agent B verifies)

```bash
# workstation ~/.ssh/config
Host jetson
  HostName <jetson-ip>
  User <user>
  ControlMaster auto
  ControlPersist 10m

# on jetson: allow non-interactive clock pinning (verify paths with `command -v` first)
echo '<user> ALL=(ALL) NOPASSWD: /usr/sbin/nvpmodel, /usr/bin/jetson_clocks' \
  | sudo tee /etc/sudoers.d/ecs

# perf counters
sudo sysctl -w kernel.perf_event_paranoid=1   # persist in /etc/sysctl.d/ if it works

# toolchain + local generators
gcc --version   # native aarch64
ollama pull qwen2.5-coder:3b      # 1.9 GB, digest f72c60cabf62
ollama pull granite4:micro        # 2.1 GB, Apache 2.0

# confirm the pulls are what the spec says they are, and that they use the GPU
ollama show qwen2.5-coder:3b      # record param count, quant, size
ollama show granite4:micro
ollama run qwen2.5-coder:3b "" & sleep 5; ollama ps   # must NOT read 100% CPU
```

Notes:
- **Cap context on both local generators.** Kernels need only a few thousand tokens; a Modelfile `PARAMETER num_ctx 4096` keeps the KV cache small. Record `num_ctx` in every receipt — it is a generation parameter, not an implementation detail.
- **Verify GPU offload, do not assume it.** Jetson GPU acceleration has historically depended on JetPack/CUDA version and container build. If `ollama ps` shows CPU-only, use the `dusty-nv/jetson-containers` Ollama image before proceeding. A silently CPU-bound G3/G4 does not invalidate the experiment, but it must be recorded, not discovered later.
- **Watch for swap.** If `jtop`/`tegrastats` shows swap climbing during generation, drop to `qwen2.5-coder:1.5b` rather than adding swap. Swap during generation is a confound; it changes nothing about correctness but it will wreck any wall-clock claim and signals the memory budget was misjudged.
- If `perf stat -e cycles:u` fails (Jetson kernels sometimes ship without matching linux-tools), fall back to `clock_gettime(CLOCK_MONOTONIC_RAW)` timing under pinned clocks and record `timing_source: "clock"` in every receipt. Do not mix sources within one arm.
- Pin exact API model strings at bring-up (Claude and Grok both), record them in `PREREG.md` and every receipt. Do not trust memory for model strings.

**Definition of done (P0):** ssh alias works; clocks pin and report; reference CRC32 compiled at -O3 measured 10 times with median cycle spread within 2 percent; both local generators pulled, `ollama show` output recorded, GPU offload confirmed via `ollama ps`, and each one produces at least one syntactically valid C function from a trial prompt (a smoke test, not a gate); **the eviction barrier of section 4a demonstrated over at least one G3→G4→G3 cycle with `eviction_wait_ms` and free-memory readings captured at each transition, zero OOM**; a `receipts/phase0.json` exists capturing all of the above including `nvpmodel -q` and `jetson_clocks --show` output.

---

## 4a. Generator eviction barrier (load-bearing, not hygiene)

> **Status: authored 2026-08-04 (pre-bring-up). Superseded *in part* by §4a.1 after P0 measurement.**
> The text below is preserved verbatim as written, not rewritten. Two clauses are wrong and are
> marked inline with ⚠︎; everything else was confirmed by measurement and still governs. Read §4a
> for the reasoning and §4a.1 for the operative mechanism. Nothing here is deleted, because the
> shape of the original error is part of what the receipt teaches.

Prior ground truth from this repo, on this device, with a receipt (chronicle #9938, supersedes #9934): `granite4:350m` — 708 MB on an 8 GB board — was disqualified from the model gate with `cudaMalloc failed: out of memory / unable to allocate CUDA0 buffer`. It had been loaded immediately after `gemma3:4b` (3.34 GB). It never ran. The disqualification said nothing about granite; it recorded a failure to allocate into memory the previous model had not yet released.

Mechanism: `keep_alive: 0` **returns immediately, but ollama's VRAM release is asynchronous** and runner teardown lags behind it. On the Orin Nano's shared, fragmenting 8 GB unified memory, a load following a heavy model can OOM with nominal free RAM available. Static footprint arithmetic (1.9 GB + 2.1 GB < 5.2 GB) is necessary and **not sufficient**, because the failure is transitional, not steady-state.

This is load-bearing for ECS specifically: the runner alternates G3 and G4 across ~240 generations, so every G3→G4 and G4→G3 switch is exactly the pattern that produced the OOM. Two generators that each fit comfortably can still fail on the handoff.

**Required barrier between any two model loads:**

1. Issue `keep_alive: 0` on the outgoing model.
2. Poll `/api/ps` until it reports empty, **and** poll free memory until it exceeds `incoming_model_size + headroom`. Both conditions, with a timeout.
   - ⚠︎ **"free memory" is ambiguous and was implemented as `MemAvailable`. Wrong — see §4a.1.**
   - ⚠︎ **`incoming_model_size` is the wrong quantity. Wrong — see §4a.1.**
3. Short settle sleep for the fragmenting unified memory.
4. Only then load the incoming model.
   - ⚠︎ **Omission: this list never said what happens when the conditions are *not* met. That silence is what let a barrier proceed on a missed target. See §4a.1 rule 4.**

A bounded retry is acceptable as a *second* layer, never the first — a retry loads into the same still-occupied memory and crashes again. Retry treats the symptom.

**Consequence for the endpoints.** An OOM-killed runner surfaces as a transport error, which is indistinguishable at the call site from a generator that produced nothing. If `runner.py` counts that as a failed candidate, or feeds it to the repair loop, it corrupts acceptance rate and D — both primary endpoints — and it corrupts them *asymmetrically by load order*, which is precisely the axis H2 compares along. Therefore:

- Transport errors and runner terminations are **infrastructure faults, not candidate failures**. They do not consume a sample, do not enter the repair budget, and do not appear in acceptance-rate denominators.
- The receipt records `evicted_before: bool`, `eviction_wait_ms`, `preceding_model`, and `infra_retry_count`. Load order is data, not an implementation detail.
- If infra retries exceed a threshold for any generator in an arm, that arm is rerun, not adjusted.

**Simplest mitigation, and the default:** batch by generator rather than interleaving. Run all of G3's samples, evict once with verification, then run all of G4's. This reduces model transitions from O(samples) to O(1) per arm. Interleaving is only permitted with the full barrier in place and the receipt fields populated.

---

## 4a.1 Supersession of §4a, on measurement (2026-08-04, post-P0)

Authority: `receipts/phase0.json` (sha256 `a234c6e9cca2073b2c3a144eb9f212b1712bc0e1d917c065716faccd89d44b65`, identical on repo and device), chronicle #13706, Agent B verification #13712, reservations closed in #13720. Amends §4a; does not replace it.

### What the original got right, and which measurement strengthened

Carried forward unchanged, because it survived contact with the device:

- **Static footprint arithmetic is necessary and not sufficient.** Confirmed, and more sharply than §4a claimed: a 1.9 GB model failed to load on a board reporting 6.7 GB available.
- **The failure is transitional, not steady-state.** Confirmed.
- **This is load-bearing for ECS because the runner alternates G3 and G4.** Confirmed.
- **Retry is a second layer, never the first.** Confirmed. Retry-first was #9938's original wrong fix and remains wrong.
- **Infrastructure faults are not candidate failures.** Confirmed, and now demonstrably load-bearing: violating this rule produced two false failures against `granite4:micro` during P0 — the same family and the same class of cause as #9934's original false disqualification of `granite4:350m`.
- **Batch by generator as the default.** Confirmed.

### What was wrong, and the measurement that shows it

§4a attributed the OOM to asynchronous VRAM release after `keep_alive: 0`. That is directionally right and mechanistically incomplete. The full mechanism:

**Ollama admits loads on an availability figure that CUDA cannot honor on Tegra.** The scheduler logged `available="5.8 GiB" free="6.3 GiB"` and admitted the load; `cudaMalloc` then failed. Actual state at that instant: `MemFree` ≈ 1.8 GB, `MemAvailable` ≈ 6.7 GB, `Cached` ≈ 5.0 GB. Tegra's unified-memory allocation path does **not** trigger page-cache reclaim, so `MemAvailable` counts several GB that CUDA cannot obtain.

Controlled demonstration, nothing else varied:

| `MemFree` | Result for `qwen2.5-coder:3b` |
|---|---|
| ~1.8 GB | `cudaMalloc failed: out of memory`, repeatably |
| ~4.3 GB (after forcing page-cache reclaim) | loads in 3.8 s, responds, 100% GPU |

### Operative rules (these govern; §4a step 2 does not)

1. **Poll `MemFree`, never `MemAvailable`.** Record **both** in every receipt so the gap stays visible rather than becoming folklore.
2. **Thresholds are empirical per model, not derived from any size.** Transient allocation during load runs near 2× resident. Measured on this board: `qwen2.5-coder:3b` — 1.9 GB download, 2280 MB resident, **needs ~3600 MB free**; `granite4:micro` — 2.1 GB download, 2586 MB resident, **needs ~5100 MB free**. No published figure predicts these.
3. **Reclaim page cache before the load.** Root-free method: fault in anonymous pages toward `MemAvailable − 500 MB`, then release; iterate toward target. `sync; echo 3 > /proc/sys/vm/drop_caches` is cleaner where root is available.
4. **Fail closed.** `barrier_ok` gates the load. When false, the result is an **infrastructure fault** per §9: not scored, no sample consumed, no repair budget touched. A barrier that proceeds on a missed target is not a barrier — that defect is what produced the two false `granite4:micro` failures during P0.
5. **Single source of truth.** Thresholds live in `harness/device/generators.json`. Any consumer — the runner, or a future `qualify_models.py` port — reads that file. Constants duplicated across scripts go stale silently and re-open the hole (Agent B reservation R2, #13712).

### Receipt fields (extends §10 `load_context`)

`evict_ms`, `ps_empty`, `reclaim_ms`, `reclaimed`, `need_mb`, `memfree_before_load_mb`, `memavailable_mb`, `barrier_ok`, `preceding_model`, `infra_retry_count`.

### Why the original text is retained rather than corrected in place

The house rule is supersession, not quiet fixing: the predecessor stays, annotated, with a carry-forward of what it still teaches. §4a is a worked example of a specific and repeatable error — reasoning correctly about a mechanism from a real receipt, then implementing the mitigation against the most convenient metric rather than the correct one. The word "free" did the damage. Deleting the original would erase the evidence that the mistake is easy to make, and the next reader would lose the one thing most likely to save them.

---

## 5. Kernel set v1 (integer only)

Fixed C interfaces; single translation unit; no allocation; no globals; no I/O; fixed loop bounds; `<stdint.h>`/`<stddef.h>` only.

| id | signature | input domain (part of ECS) | note |
|---|---|---|---|
| crc32 | `uint32_t crc32(const uint8_t*, size_t n)` | n <= 4096 | fully closed spec: poly 0xEDB88320 reflected, init 0xFFFFFFFF, xorout 0xFFFFFFFF. Check value: "123456789" -> 0xCBF43926. **Calibration kernel: residual disagreement here diagnoses harness leaks.** |
| sat_add_u8 | `void sat_add_u8(const uint8_t*, const uint8_t*, uint8_t*, size_t n)` | n = 256 | saturating add, near-closed spec |
| fir_q15 | `void fir_q15(const int16_t x[256], const int16_t h[16], int16_t y[256])` | Q15, saturating accumulate >>15 | classic DSP shape |
| matmul8_i32 | `void matmul8_i32(const int32_t a[64], const int32_t b[64], int32_t c[64])` | entries in [-1024, 1023] | domain bound keeps products in range, no UB ambiguity |
| median3x3_u8 | `void median3x3_u8(const uint8_t in[16*16], uint8_t out[14*14])` | interior only | perf-interesting, sorting-network friendly |

Floating point (quaternion rotate) is a separate later arm whose stated purpose is exercising the tolerance policy. It does not join the primary signal in v1.

### Pointer preconditions (raised 2026-08-04, decided 2026-08-04 — option 2)

The input-domain column above constrains `n`. It originally said nothing about **pointer validity**. That gap was not hypothetical: the two independently sealed `crc32` oracles agreed on all 24,359 tested inputs and diverged on exactly one case outside the stated domain. Agent B guards `data == NULL && n != 0` and treats it as empty; Agent A does not, leaving that call undefined behaviour. Neither violated the then-silent spec.

**Decision (trusted-tier lead, Agent B; board #13818; vectors file records the same):**

> **Option 2 — declare the precondition.** Each ECS packet states that pointers are valid and non-null for `n > 0` (`data != NULL || n == 0`). Behaviour for `NULL` with `n > 0` is **out of domain**: undefined, untested, and never present in acceptance vectors or generation prompts.

Option 1 (pin explicit NULL recovery and force oracle match) was rejected for v1: silently reconciling oracles on out-of-domain cases would convert a real finding into an echo and destroy the signal hash-and-seal exists to protect. Oracles are **not** edited to match on this case.

Receipts: seat board #13816 (raised) · #13818 (decided) · `trusted/vectors/crc32.json` domain block.

---

## 6. Trusted tier

**Oracles.** Two independent slow-and-obvious reference implementations per kernel (one per agent, written blind). Trust = pairwise agreement on all vectors + agreement with published check values where they exist (CRC32) + CBMC bounded equivalence on small n where feasible.

> **Amendment 2026-08-04 — "written blind" is now enforced, not promised.**
> As originally written, this clause asserted blindness without any mechanism to establish it. That was the weakness thread #20 was opened to address, after this seat published an oracle and declared it blind in the same act. **Hash-and-seal** is now standing law, frozen in `PREREG.md` §8 against tag `prereg-v1`:
>
> For each kernel, each seat independently authors its oracle, computes the SHA-256 of that file, and posts the hash to the seat board. **Content is revealed only after both hashes exist.** Ordering becomes a receipt rather than a promise. Seals are valid only when posted against the frozen tag. The seat board is the sole seal ledger; the seal table in frozen PREREG §8 stays empty by ruling and is not to be filled.
>
> This matters because a blindness breach is the one failure in this design that produces **no symptom anywhere**: two echoing oracles still pass vectors, still close under CBMC (both share the bug), and still yield clean calibration D. Agreement without an ordering receipt is not evidence.
>
> Reveal convention: `trusted/oracles/<kernel>_<seat>.c`. Seat labels are load-bearing — an unlabeled pair cannot be audited.
>
> `harness/measure/crc32_ref.c` is a **P0 bench fixture, not an oracle of record.**

**Acceptance vectors.** Committed to the repo. Generated from the oracles: edge cases (empty, single element, max domain values, saturation boundaries) plus seeded random inputs. These are what generation and repair are allowed to see failures against.

**Probes (the circularity fix).** Probes measure disagreement among *accepted* artifacts. They are not a gate, they never trigger repair, and their contents never reach any prompt.

Mechanism:
- Repo contains `probes/gen_probes.py` (deterministic given a seed) and the SHA-256 of each realized probe file.
- The seed lives only on the Jetson at `~/ecs/.probe_seed` (never committed, never printed, never read by `runner.py`'s prompt-building path).
- Probes are realized on-device at Phase 1 and hash-checked against the committed hashes at every run.
- 256 probe inputs per kernel: random over the ECS domain plus structured adversarial cases the vector set deliberately omits.
- After acceptance, each artifact is run on the probes on-device; raw outputs are hashed per input and stored in the receipt. Disagreement analysis happens in `results/`, downstream of everything.

**K estimator.** For each kernel and arm: for every probe input, cluster accepted artifacts by output; disagreement D = mean over probes of (1 - largest cluster fraction). D is the operational estimate of unpinned specification bits.

---

## 7. Gate chain (in order; first failure stops, feedback goes to repair)

1. **Lint (forbidden surface).** Reject on: any `#include` beyond stdint/stddef, `malloc|free|calloc|realloc`, `static` storage, `volatile`, inline `asm`, function pointers, recursion, VLAs, any I/O. Enforced by a small parser check, not regex alone where practical.
2. **Strict compile.** `gcc -std=c11 -O2 -Wall -Wextra -Werror -Wconversion -Wshadow -c` must be clean.
3. **Sanitized run.** Rebuild `-O1 -g -fsanitize=undefined,address -fno-sanitize-recover=all`, run the full acceptance vector set. Any report = fail. ⚠︎ *"full" clarified by §7a.1*
4. **Bounded model check (host side, spares Jetson RAM).** `cbmc kernel.c chk_<id>.c --arch arm64 --bounds-check --pointer-check --signed-overflow-check --unwind <per-kernel bound> --unwinding-assertions`. Checks memory safety and equivalence vs oracle for small bounded n. ⚠︎ *outcome set fixed by §7a.2*
5. **Acceptance vectors on device.** Measurement build (`-O3 -mcpu=native`), bit-exact match on all vectors. ⚠︎ *"all" clarified by §7a.1*
6. **Budget caps.** cycles <= 3x the -O3 oracle baseline; `.text` <= 4096 bytes (`size` on the object); stack <= 1 KiB (`-fstack-usage`). Caps are sanity bounds, not optimization targets; actuals are recorded either way. ⚠︎ *outcome set fixed by §7a.2*

Redteam fixtures (Agent B): a set of known-bad candidates (out-of-bounds write, signed overflow, hidden static state, right answer by luck on vectors but wrong on domain edges). Phase 2 is not done until every fixture is rejected at the intended gate.

---

## 7a. Clarification of §7, on withholding and on failing closed (2026-08-05, P2 held open)

**§7 above is retained verbatim.** Nothing in it is deleted or rewritten. This section fixes two things §7's wording left open, both discovered by implementing §7 exactly as written and finding the instrument did something other than what the experiment requires. Anthony ruled P2 stays open; the clarifications are the substance of that ruling. Ratified by both build seats — Agent A #14278, Agent B counter-sign #14282.

### 7a.1 "The full acceptance vector set" means the full set **the arm has**

Gates 3 and 5 both run the acceptance vectors. PREREG §6 arm 3 weakens the constraint surface three ways, the third being that **half the vectors are withheld**. Read literally against the committed vector file, §7's "full" and "all" would have gates 3 and 5 run every committed vector in every arm — which is what the harness did.

The consequence was that arm 3's third weakening **did not exist as a manipulation**. It existed as a field in the receipt naming the withheld ids while both vector gates went on enforcing the complete set. Weak-arm candidates were still held to every vector under sanitizers, which for bit-exact kernels is the same behavioural bar as the full arm at the first vector gate — and gate 3 is where value-wrong code stops, which is most of what generators emit.

**Operative rule.** The arm's vector set is `vector_policy.select(committed, completeness)` — runner-enforced from `completeness` alone, never author-chosen (Agent B #14096, unchanged). Gates 3 and 5 both run **that** set. "Full" in §7 means *do not subsample below the arm's set* and *do not skip the vector gate*; it does not mean *ignore arm policy*.

Applying withholding at gate 5 alone was considered and rejected: it nullifies the manipulation while appearing to implement it, which is the worst of the three available states.

**Recorded as a live alternative, not chosen:** gate 3 could be pinned to the committed full file as a safety floor *above* the arm set. That is a different experiment — arm 3 would then be weakened in two ways and a half — and if it is ever wanted it lands as a dated supersession, never as a silent change of one call site.

### 7a.2 Every gate has three outcomes, and an absence is never a pass

§7 names pass and fail. Implementation needed a third state and, lacking one, borrowed the second, then let three different absences flow onward as passes: CBMC timing out or terminating without a verdict; a declared `.text`/stack cap whose actual could not be read; a declared cycles cap whose measurement was unusable. In every case the artifact was accepted **because the instrument failed**.

The direction of that error is the reason this is not a cleanup item. Acceptance rate is a primary endpoint (§3), so instrument failures were being silently converted into evidence of generator capability.

**Operative rule — the outcome set is exactly:**

| outcome | meaning | scored? |
|---|---|---|
| **pass** / **fail** | a property of the **candidate** | yes |
| **skipped_intractable** | a **declared** exemption, and only where one is on record (LN-4 gate 4, three kernels) | no, and never reported as a pass |
| **infra fault** | a property of the **instrument** — transport died, a device payload digest mismatched, core frequency moved mid-measurement, an oracle pair or CBMC harness is absent | no: consumes no sample, touches no repair budget, enters no acceptance denominator (§4a.1, §8, §9) |

A declared constraint that cannot be evaluated is never a pass. Which of *fail* or *infra fault* it becomes is decided by cause, not convenience: a cause the candidate could have produced fails closed as a candidate failure; a cause that is ours is an infra fault. Collapsing infra into "fail" would trade a silent inflation for a silent deflation — a drifted clock scored as a slow candidate is precisely what §8 forbids when it says discard and remeasure rather than average.

`skipped_intractable` is reserved for exemptions **on record**. A missing CBMC harness previously returned the same value as LN-4's measured intractability, making an unwritten harness indistinguishable in the receipt from a measured impossibility.

### 7a.3 Candidate source crosses to the device as opaque data

Candidates are untrusted model output. They were staged on the Jetson inside a heredoc with a fixed delimiter, so a candidate containing that delimiter line terminated the here-document and its remaining lines were executed by `bash` as commands — demonstrated on the device, not argued (#14278).

Beyond the obvious, this is a **measurement** defect: a candidate that can influence its own build has escaped the instrument, and any receipt it produced is unsound. **Operative rule:** payloads cross base64-encoded under a delimiter containing a character outside the base64 alphabet, and both sides verify a sha256; a mismatch is an infra fault, never a gate result. `harness/gates/remote.py` is the only place a file may be placed on the device.

### 7a.4 Receipts name their instrument

Every correction in §7a changes what "accepted" means. A receipt therefore records `harness_git_sha` and whether the tree was dirty; receipts produced across different harness revisions are not comparable and must not be pooled.

---

## 8. Measurement protocol

- Pin clocks before every measurement batch (`nvpmodel` to the chosen mode, then `jetson_clocks`); record both outputs in the receipt.
- Sequence phases: no ollama resident during measurement. Unload with `keep_alive: 0` via the ollama API and **verify eviction per the barrier in section 4a** before benching. `keep_alive: 0` returning is not evidence of released memory.
- Run on an isolated core: `taskset -c 3`. Read `scaling_cur_freq` for core 3 before and after; mismatch = discard and remeasure.
- 200 warmup iterations, 1000 measured, per candidate. Report median and MAD. Prefer `perf stat -e cycles:u,instructions:u`; fall back per Phase 0 note.
- Baseline = faster of the two oracles at `-O3 -mcpu=native`, same protocol, refreshed at the start of every batch. All cycle numbers are also stored as a ratio to the same-batch baseline.
- Optional (best effort, non-gating): mean board power from tegrastats sampled during the measured window.

---

## 9. Runner state machine and repair policy

```
load ECS packet -> build prompt -> generate -> LINT -> COMPILE -> SANITIZE
   -> CBMC -> VECTORS(device) -> BUDGET -> ACCEPT -> measure -> probe -> receipt
any gate failure -> repair (<= 4 iterations) -> re-enter at LINT
repair budget exhausted -> REJECT -> receipt (full trace kept)

generation transport error / runner termination (OOM class)
   -> NOT a candidate failure. Re-run the eviction barrier (4a),
      verify free memory, retry the generation. Does not consume a
      sample, does not touch the repair budget, logged as infra.
```

- **Prompt content rule.** A generation/repair prompt is built programmatically from exactly: the rendered ECS packet, the C signature, and (repair only) the current gate's feedback. Feedback = compiler/sanitizer output, or the first 3 failing vector indices with expected vs got. Never probe data, never oracle source, never other candidates, never other models' outputs. The runner stores the prompt SHA-256 in the receipt and refuses to send a prompt assembled from any other source.
- **Sampling.** temperature 0.8 across **all four** generators (G1, G2, G3, G4) — no per-provider variation. Record seed where the API supports it (xAI, ollama); where it does not (Anthropic), record the sample index; within-model variance is still measured by repeated sampling.

- **Served-string identity (measured, not assumed).** Every call records both `model_string_requested` and `model_string_served`, the latter read from the provider's own response `model` field. This is not bookkeeping: measured 2026-08-04, requesting `grok-4` returns `grok-4.3`, and `grok-4` does not appear in the provider's model list at all. A harness logging its request string would have attributed ~60 generations to a model that never ran.
  - The runner **asserts served-string identity within an arm**. If `model_string_served` changes mid-arm, the arm is **invalidated and rerun**, never averaged or adjusted. A frontier generator swapped underneath a running arm corrupts the between-model variance decomposition — the H1/H2 primary endpoint — and does so invisibly, since every receipt would carry the same request string.
  - `grok-4` is **banned** as a G2 string. It is a demonstrated floating alias. G2 is named explicitly (`grok-4.5` or `grok-4.3`).

- **Provider pinning asymmetry (stated, not papered over).** Neither frontier pin is version-pinned. `claude-opus-5` and `grok-4.5` serve themselves today but carry no date suffix, so a provider-side alias repoint can substitute the model mid-experiment. Anthropic publishes immutable dated strings (e.g. `claude-opus-4-5-20251101`); **xAI publishes no dated string for the 4.3/4.5 line at all.** G1 and G2 are therefore ALIAS-pinned, not version-pinned, and stability is enforced by our served-string logging and the mid-arm assertion above rather than by the providers. PREREG must state this asymmetry plainly; the two frontier generators are not equally reproducible and implying otherwise would be false.

- **Infra-fault classifier and retry cap.** Transport errors, runner terminations, and `barrier_ok: false` (§4a.1) are **infrastructure faults**, never candidate failures: no sample consumed, no repair budget touched, absent from acceptance-rate denominators. Each is retried after re-running the eviction barrier, capped at **3 infra retries per candidate**. Exceeding the cap aborts that candidate as an infra abort (still not a candidate failure) and increments an arm-level counter; **more than 5 infra aborts in an arm invalidates the arm and it is rerun**, not adjusted. `infra_retry_count` and `infra_abort_count` are receipt fields.

- **Per-cell batching.** A *cell* is one `(generator × kernel × arm)` triple. All samples within a cell run consecutively under a single verified barrier; the barrier re-runs only at cell boundaries. This is stricter than batching by generator alone: it holds `num_ctx`, model residency, and device thermal state constant across the samples whose variance the experiment actually compares, and it bounds model transitions to one per cell rather than one per sample. Interleaving within a cell is not permitted.
- 10 samples per generator per kernel per arm.

---

## 10. Receipt schema (one JSON per candidate)

```
run_id, arm, kernel_id, ecs_packet_hash, prereg_tag,
generator {provider, model_string_requested, model_string_served, model_digest,
           license, pinning: "alias"|"version", temperature, num_ctx,
           seed_or_sample_index, gpu_offload: bool},
cell {generator_id, kernel_id, arm, sample_index_within_cell},
load_context {preceding_model, evicted_before: bool, eviction_wait_ms,
              memfree_before_load_mb, memavailable_mb, need_mb, barrier_ok: bool,
              reclaim_ms, reclaimed: bool, infra_retry_count, infra_abort_count},
prompt_sha256, generated_source (verbatim), repair_trace [per-iteration gate + feedback hash],
toolchain {gcc_version, flags_strict, flags_measure}, cbmc_version_and_flags,
gate_results per gate, accept: bool,
device_state {nvpmodel, jetson_clocks_show, core, cur_freq_pre, cur_freq_post, timing_source},
measurement {cycles_median, cycles_mad, instructions, text_bytes, stack_bytes,
             baseline_cycles_median, ratio_to_baseline, power_mw_mean?},
probe_output_hashes [per probe input],
timestamps, harness_git_sha
```

---

## 11. Arms and run plan

1. **Calibration.** crc32 only, all four generators, 10 samples each. Gate on the harness itself: D(crc32) <= 1 percent among accepted artifacts, else stop, find the leak, rerun. Nothing proceeds past a leaky calibration.
2. **Main.** All five kernels x four generators x 10 samples, full ECS packets.
3. **Dose-response.** fir_q15 with `fir_q15.weak.ecs.yaml` (forbidden list dropped, budgets dropped, half the vectors withheld) x four generators x 10 samples. Prediction: D and variance rise versus the main arm.

Totals: ~240 generations plus repairs. All headless via `runner.py`.

---

## 12. PREREG.md (freeze before calibration; `git tag prereg-v1`)

- **H1.** As ECS completeness increases, behavioral variance across independent generators (D, plus between-model cycle/size variance) decreases, and decreases faster than implementation-text variance.
- **H2.** Marginal value of model capability falls as ECS completeness rises: the local 3B-class generators under the full ECS achieve acceptance rates and D approaching the frontier generators under the full ECS, and beat frontier generators under the weakened ECS.
- **H2 floor clause (pre-committed).** If a local generator's acceptance rate is zero across all five kernels in the main arm, H2 is recorded as *untestable at this capability tier*, not as falsified. The distinction matters: a floored generator measures the instrument's lower bound, not the hypothesis. Report the floor, keep the receipts, and state plainly that the 3B tier sits below the ECS's usable range on this kernel set.
- **Primary endpoints.** D per kernel per arm; within-model vs between-model variance decomposition (bootstrap CIs over artifacts); acceptance rate and repair-trace length per generator (repair-trace length retained as the kinetic diagnostic).
- **Phase 2 transition criterion (verbatim).** Denser-than-C emission begins only when a search-based generator beats the -O3 baseline on cycles or size by more than measurement variance, on at least one kernel, while passing identical gates. Until that fires, the conventional backend retains its seat.

---

## 13. Build phases, lanes, definitions of done

| phase | scope | lane | done when |
|---|---|---|---|
| P0 | device bring-up (section 4) | A builds, B verifies | phase0 receipt incl. 2 percent stability check |
| P1 | trusted tier: dual oracles under hash-and-seal, vectors, ECS packets, probe realization on device | B leads oracles/probes, A writes its own sealed oracle set, both author ECS packets for their kernels | **both seal hashes posted to the board before either reveal, per kernel**; revealed files verify against their posted seals; oracles agree on all vectors incl. published check values; packets validate against schema; probe hashes committed |
| P2 | harness: runner, device executor, adapters, gates, receipts | A leads; B builds redteam fixtures | stub generator (returns oracle verbatim) produces a full green receipt end to end; every redteam fixture rejected at its intended gate ⚠︎ *extended by §13a* |
| P3 | runs: calibration, main, dose-response | harness runs headless; both agents on-call for infrastructure faults only | all receipts present; calibration D <= 1 percent passed before main |
| P4 | analysis + writeup | B computes, A audits (swap of P2 roles) | `results/` with variance decomposition, prereg outcomes stated as pass/fail, systems-result draft |

Rough effort: P0 half a day, P1 one to two days, P2 two to three days, P3 mostly machine time, P4 a day. About a week of part-time attention end to end.

---

## 13a. Extension of P2's definition of done (2026-08-05, Anthony)

**§13's P2 row is retained.** It is met and remains met; this adds to it rather than replacing it, because the row was written before the harness had a revision worth naming.

P2 closes only when, in addition to §13:

1. Every gate fails closed per §7a.2 — no declared constraint passes because it could not be evaluated.
2. Weak-arm withholding is **applied** at gates 3 and 5 per §7a.1, not merely recorded.
3. The runner does what §9 says it does: sends the prompt it hashes, sends repair feedback, invokes the §4a.1 barrier at cell boundaries, asserts served-string identity **arm-wide**, and refills infra-aborted sample slots so *n* is set by design and not by device weather.
4. Candidate source reaches the device only as opaque data per §7a.3.
5. **All stub and redteam receipts are regenerated against a committed harness revision** and carry its `harness_git_sha`. Receipts produced before these corrections describe a different instrument and are superseded, not amended.

Item 5 is why P2 stayed open after the corrections were written: a correct instrument with receipts from the previous one proves nothing about either.

---

## 14. Knobs (set for you; say "tighter" or "looser" in plain words and they move)

| knob | value | plain meaning |
|---|---|---|
| samples per generator per kernel | 10 | how many tries each model gets |
| repair iterations | 4 | how many fix-it rounds before giving up on a candidate |
| baseline stability gate | 2 percent | how steady the test bench must be before anything counts |
| calibration leak threshold | D <= 1 percent | how much disagreement on the closed-spec kernel is tolerated |
| probe count | 256 per kernel | how many hidden checks measure leftover ambiguity |
| cycle cap | 3x baseline | how slow a candidate can be and still count |
| size cap | 4096 bytes text | how big the compiled kernel may be |
| temperature | 0.8 | how much the models are allowed to wander |

---

## 15. Out of scope for v1

Floating point arm, energy as a gate, any concurrency, CUDA/NEON intrinsics targets, denser-than-C emission (locked behind the Phase 2 criterion), multi-translation-unit candidates, and any generator prompt content beyond the rule in section 9.
