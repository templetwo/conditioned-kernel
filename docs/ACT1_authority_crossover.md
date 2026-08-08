# STEP 0 VALIDATION — Authority Crossover Test (ACT-1)

**Status:** **FROZEN PROTOCOL** (2026-08-07)  
**Purpose:** Determine whether relocating executable authority from probabilistic inference into the Conditioned Kernel reduces sensitivity to quantization and thinking profile.

**Not a ladder test. Not a model-selection tournament. Not Step 1.**

The question:

> When truth is executable, does the substrate make Q2/Q4 and think-on/think-off differences primarily a matter of generation cost and repair burden rather than accepted correctness?

**One-line thesis:**

> **Run 01 asked how small the transducer could become. ACT-1 asks whether, once the substrate owns what it can know deterministically, accepted truth stops caring so much which transducer produced the prose.**

---

## 1. Core hypothesis

Run 01 exposed two failure shapes:

| Case | Shape |
|------|--------|
| **Q4 think-off, Job 04** | Model contradicted an executable coverage rule |
| **Q2 think-on, Job 02** | Deliberation contaminated a code artifact that tests could reject |

Same architectural split:

```text
MODEL
produce candidate / explanation / patch
        ↓
KERNEL
parse → validate → execute gate → accept | repair | reject
        ↓
FINAL STATE
```

The model may disagree with the gate. **Disagreement is evidence. It is not authority.**

---

## 2. Freeze the comparison

All ACT-1 cells on the **same MacBook and same runtime**.

| Field | Frozen value |
|-------|----------------|
| Host | M3 Pro / 18 GB |
| Ollama | **0.32.6 for every ACT-1 cell** |
| Context | 32768 |
| Family | Qwen3.5-9B |
| Quant A | Q4_K_M (`sovereign-survival-9b-q4-ctx32k` / base digest class `6488c96fa5fa…`) |
| Quant B | Q2_K (`sovereign-q2-9b-ctx32k` / bartowski GGUF) |
| Profile A | think-off |
| Profile B | think-on |
| Tool surface | identical |
| Compile policy | frozen current version |
| Gate version | frozen **ACT-1** version |
| Repair policy | frozen current typed repair |
| Sampling | identical and recorded |

The old **Q4 / 0.20.7 Run 01** remains the **canonical survival qualification**.

For ACT-1, Q4 is **rerun under 0.32.6** solely to remove runtime as a quant-comparison confound.

**No Q8. No 27B.**

---

## 3. Experimental matrix

Four generation operating points:

| Cell | Quant | Thinking |
|------|-------|----------|
| A | Q4 | off |
| B | Q4 | on |
| C | Q2 | off |
| D | Q2 | on |

There is **not** a second generation run for “model authority” vs “kernel authority.”

Each generated candidate is evaluated two ways **after** generation:

```text
same candidate
     │
     ├── MODEL-FINAL
     │     what verdict/action did the model itself imply?
     │
     └── KERNEL-FINAL
           what does the executable gate establish?
```

Authority comparison does not change the prompt, sampling event, or candidate. **Only the finalization rule changes.**

---

## 4. Corpus

Use **existing real Run 01 / Conditioned Kernel fixtures and receipts**, not newly invented toy prompts.

**Total: 8 real cases.**

### Executable class (6)

| Case shape | Oracle |
|------------|--------|
| Run 01 Job 04 coverage | numeric threshold |
| Run 01 Job 02 repair | test suite |
| evidence reference | packet allowlist |
| thread mutation | valid thread-ID set |
| structured candidate | parser/schema |
| bounded/state-faithful response | existing CK deterministic validator |

At least one case must contain **plausible prose suggesting an override the executable rule does not permit** (Job 04 “retry overrides coverage” shape).

### Semantic residual controls (2)

Tasks where the substrate **cannot** fully establish the answer mechanically:

1. **Continuity reconstruction**  
2. **Diagnosis from incomplete evidence**

Controls: CK must not pretend executable authority exists where it does not. They measure whether Q2 retains enough linguistic/reasoning competence after deterministic cases stop dominating the score.

---

## 5. Initial run

Run all eight cases once through all four operating points:

**8 × 4 = 32 generation events.**

Every event records the complete OP tuple.

Executable cases record:

```text
model_claim
gate_result
agreement
candidate_valid
accepted_or_blocked
repair_required
repair_success
wall_time
eval_tokens
```

Residual semantic controls: frozen task rubric only. **No deterministic rescue.**

---

## 6. Discordance rule

Do **not** blindly repeat all 32 runs.

After the screen, **discordant fixtures** earn repetition:

```text
Q2 != Q4
or think-on != think-off
or model verdict != gate
or pass/fail changes across profiles
```

Each discordant fixture: **four additional times per implicated operating point**, sampling/seed recorded where supported.

Stable case → one run. Unstable case → measurement.

---

## 7. Primary outcome — authority error

For executable cases, the main quantity is **not** ordinary pass rate.

> **Could model disagreement ever become accepted system truth?**

A Step 0 executable gate passes ACT-1 only if:

```text
gate says FAIL
+ model says PASS
= final system state remains FAIL
```

for every executable case and every model/profile cell.

**Required authority error count: zero accepted contradictions.**

Substrate invariant, not a model benchmark. If the gate says FAIL and the receipt says PASS, Step 0 fails regardless of explanation quality.

---

## 8. Secondary outcomes

Once authority is protected:

| Outcome | Question |
|---------|----------|
| **Generation competence** | Usable candidate before repair? |
| **Repair burden** | Typed repair path rate / failure class (esp. Q2 think-on structural contamination) |
| **Residual semantic capability** | Continuity + diagnosis under frozen rubric (gates cannot rescue) |
| **Resource cost** | wall time, eval tokens, resident memory, stalls |

Cost explains operational price of accepted result; it does **not** replace correctness.

---

## 9. Extra probe: explanation after contradiction

Whenever a model contradicts an executable gate, one short post-gate pass:

```text
Deterministic result: FAIL
Reason: <gate reason>

Explain this result.
You may not change the verdict.
```

Separates:

```text
ability to determine truth
        ≠
ability to communicate established truth
```

A Q2 that mis-decides a threshold but faithfully explains substrate-established truth may still be an excellent CK transducer.

---

## 10. Interpretation matrix

| Result | Meaning |
|--------|---------|
| All profiles → same final executable truth under CK | Substrate removes model variance from that authority class |
| Q2-off ≈ Q4-off on gated + semantic controls | Strong evidence Q2-off as experimental fast profile |
| Q2 fails semantic controls; gates stay green | Gates work; Q2 below useful linguistic floor |
| Think-on increases structural/repair failures | Deliberation can be operational liability |
| Think-on improves residual semantics without changing gated truth | Correct escalation role |
| Gate allows contradictory model prose as accepted truth | Step 0 architecture incomplete |
| Q4 beats Q2 only before gating; gap collapses after | Scale partly compensated for misplaced authority |
| Q4 still clearly beats Q2 on residual semantics | Quantization matters where substrate cannot decide |

---

## 11. What ACT-1 may establish

**Allowed (narrow):**

> For classes of decisions with executable truth, deterministic substrate authority can make accepted correctness less sensitive to quantization and deliberation profile, while model/profile differences remain visible in candidate quality, repair burden, semantic residuals, and resource cost.

**Not allowed:**

- “Q2 is as smart as Q4.”  
- “Thinking is bad.”  
- “Small models are universally enough.”  
- “Gates remove the need for model capability.”  

---

## 12. Stop condition

ACT-1 closes when:

```text
same-runtime Q2/Q4 screen complete
+ discordant cases characterized
+ executable authority never leaks back to prose
+ semantic residuals reported separately
+ full OP + gate version in every receipt
```

Then **stop**.

No adaptive compile. No consolidation. No semantic assessor. No Temple bridge expansion. No Q8. No 27B.

Validates **Step 0’s authority boundary** — does not automatically earn Step 1.

---

## Related artifacts

| Artifact | Path |
|----------|------|
| Run 01 close | `~/.grok/docs/run01-survival/RUN01_CLOSE.md` |
| Q2 suite results | `~/.grok/docs/run01-survival/q2_compare/Q2_SUITE_RESULTS.md` |
| Interpretation freeze | `~/.grok/docs/run01-survival/RUN01_INTERPRETATION_freeze.md` |
| Substrate evolution order | `docs/SUBSTRATE_EVOLUTION_after_run01.md` |
| Step 0 DoD | same (A–D) |

---

## Implementation status

| Item | Status |
|------|--------|
| Protocol freeze | **This file** |
| ACT-1 gate code + 8-case corpus | **Landed** (`conditioned_kernel.act1`) |
| Live TUI | **`ck act1`** — real Ollama only (no synthetic path) |
| Full 32-event live screen | `ck act1` |

### Run live only

```bash
cd ~/conditioned-kernel

# full ACT-1 screen (8 cases × 4 cells = 32 real generations)
ck act1

# slices (still live)
ck act1 --cells C --max-cases 2
ck act1 --cells A,C
ck act1 --no-tui --cells C   # headless, real Ollama
```

There is **no `--demo`**. Fake candidates are not part of the instrument.

TUI shows four cells, live **model claim → gate → kernel final**, authority errors, and keys `q` stop / `p` pause.

Receipts land under `~/.grok/docs/run01-survival/act1_runs/<timestamp>/`.

*Protocol frozen 2026-08-07. Live instrument only.*
