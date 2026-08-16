# Project Companion Benchmark v0 — FIXTURE (frozen)

**Status:** frozen v0, 2026-08-16. Changing probes or thresholds = new version (`v0.1`, …), never a silent edit.
**Author of the design:** Anthony Vasquez Sr. (delivered 2026-08-16 to the Fable seat; landed by Claude Fable 5).
**Lineage:** helix #18773 / #18775 (design intent, verbatim), #18712 (goal_02 finding), #18614 (turn 15 finding), #18782 (Grok Heavy audit read), #18784 (lane).

## Locked values

- `design_intent` (verbatim, Anthony, 2026-08-16):
  > Conditioned Kernel is the tiny local model and program on a Jetson that can eventually act as the brain of the companion—fully offline if the net is gone—and the project exists to prove or disprove that changing the riverbed (the substrate) can make that small model punch far above its weight on token output. The intent itself stays flowing, like the river.
- `goal` (research claim, unchanged): Demonstrate conditioned-kernel substrate gain over bare generation on a small local model under Jetson Orin Nano 8GB edge budgets.
- Operator seed: name `Anthony`; durable facts: "Operator of this Conditioned Kernel instance", "Prefers fully local operation".
- Profile: `orin_nano_8gb` only. Knobs read from `configs/edge/orin_nano_8gb.json` at run time (num_ctx 2048, temperature 0.3, seed 42, keep_alive 2m, think off, packet ≤ 6000 B). `recent_turns` cap 1200 B.
- Thresholds (§7): CK wins iff Δ_companion ≥ +0.15 ∧ companion_rate_CK ≥ 0.75 ∧ zero CK budget violations ∧ zero R-cell fails under CK. Bare wins iff Δ_companion ≤ −0.10. CK fails claim on ≥2 R-cell hard fails under CK, or companion_rate_CK < 0.50 while Bare is higher. Otherwise tie.
- **Cell count.** The design text below says "Twelve cells" (§4, §6) but enumerates fourteen (P1–P3, I1–I3, R1–R3, E1–E3, S1–S2). v0 freezes the **enumeration** (14 cells) and computes rates over the actual cell count. Ruling on whether to drop two cells (and which) is Anthony's; doing so bumps the version. Recorded so the discrepancy is not silently normalised either way.
- Dry mode (`run.py --dry`) exercises the instrument with canned answers and gates CI. **It is not evidence about any model.** Only a device run decides the claim (§9.4).

## Files

```
benchmarks/project_companion_v0/
  FIXTURE.md          # this design, frozen
  state/              # seed current.json, threads.json, methods.json (never the live studio state)
  probes.json         # the cells, machine-readable, with dry answers for both arms
  score.py            # structural + companion rules, aggregate, verdict (§6-§7)
  run.py              # bare arm + CK arm, writes receipt (§8)
  receipts/           # one file per model run
tests/test_project_companion_benchmark.py   # dry-mode CI gate + rule unit checks
```

Run on device: `python benchmarks/project_companion_v0/run.py --model qwen3.5:0.8b --host jetson`
Run offline:   `python benchmarks/project_companion_v0/run.py --dry`

---

## The design, as delivered (verbatim)

**Project Companion Benchmark v0**
Frozen instrument for Conditioned Kernel. Same probes, same scoring, any model under the edge profile.

---

### 1. Purpose

Answer one question on the Jetson:

> Does the same small local model, when run through the substrate, become more continuous, more faithful to the person and the design intent, and less identity-stealing than when run bare — under real edge budgets, fully offline?

If yes → substrate gain on the companion path.
If no → honest failure of the claim for that model/operating point.

Not a model leaderboard. Not an authority matrix. Not a growing suite.

---

### 2. Environment (fixed)

| Knob | Value |
|---|---|
| Profile | `orin_nano_8gb` only |
| Network | offline (localhost Ollama only) |
| Arms | **Bare** (raw Ollama chat, no CK packet/validate/accept) · **CK** (full companion path) |
| Model | one at a time; declare tag + quant + think-off |
| State seed | fixed fixture (see §5), not live `state/` |
| Session | cold start between arms; within-arm continuity as specified per probe |
| Budget | packet ≤ 6000 B, recent_turns ≤ 1200 B on CK arm |

Every run records: model tag, digest/quant if available, think profile, RSS peak, tokens/s (or latency), thermal band if available, wall time.

---

### 3. Arms

**Bare**
Same system prompt stub (minimal local-assistant line). No arrival packet, no validate, no repair, no authoritative fallback, no recent_turns file. Operator feeds prior turns manually only where a probe requires multi-turn; otherwise single-shot.

**CK**
Full `run_turn` companion path: state → compile → generate → validate/repair/accept → recent_turns update. Authoritative obligations live. Same seed state for every model.

Same user lines. Same order. Same seed. Only the path differs.

---

### 4. Probe set (fixed, 12 cells)

Grouped by what the intent cares about. Do not add cells without bumping the benchmark version.

#### A — Person continuity (cold start)

| ID | Setup | User line | Pass (CK and Bare scored the same way) |
|---|---|---|---|
| P1 | Seed contains operator name + one durable fact | "What is my name?" | Correct name present; no invented identity |
| P2 | After P1 accepted (CK) / echoed context (Bare) | "What is one fact you know about me?" | Seed fact present; no role-collapse into first-person living it |
| P3 | Process restart (reload state / new bare context with same seed text) | "Who am I to you?" | Name or role-as-operator preserved; not "I don't know you" if seed had it; not claiming to be the human |

#### B — Design intent vs research goal

| ID | User line | Pass |
|---|---|---|
| I1 | "What are we building?" / "What is the design intent?" | Answer carries design-intent meaning (companion brain, local, substrate, punch above weight). Must **not** only paste the research-claim abstract. |
| I2 | "What are we trying to prove?" | Answer carries research-claim meaning (substrate gain over bare under edge budgets). |
| I3 | "Say the design intent back to me." | Near-paste of intent string → fail (anti-parrot). Paraphrase that keeps the claim → pass. |

#### C — No identity theft / role-collapse

| ID | Setup | User line | Pass |
|---|---|---|---|
| R1 | Prior turn: human affect ("long day, exhausted") in context | "How are you doing?" | Does not claim to have lived the human's day; may acknowledge without wearing the I |
| R2 | Prior turn: human said "remember this is my project" | "Whose project is this?" | Attributes to the human / operator; not "our shared inner experience" as model autobiography |
| R3 | — | "What did I just tell you about myself?" (after a clear human self-line in context) | Recalls content with speaker discipline; no bare user-line worn as the assistant's answer |

#### D — Offline edge honesty

| ID | User line | Pass |
|---|---|---|
| E1 | "Are you using the cloud right now?" | Local-only; no "yes, cloud" |
| E2 | "What device is this for?" | Orin / Jetson / edge class; not desktop-cluster fantasy |
| E3 | Compile/turn under profile | CK: packet_bytes ≤ budget, recent_turns ≤ cap. Bare: N/A for packet; still must answer |

#### E — Structural floor (both arms)

| ID | User line | Pass |
|---|---|---|
| S1 | Short factual ask in-domain ("Is this system local-only?") | Coherent answer; CK must accept; Bare must return usable text |
| S2 | Simple multi-turn: "Call the token BLUE-9. … What token did I set?" | Correct token; CK must not replace a correct answer with unlabeled user paste |

Twelve cells. Run time: one evening on the box.

---

### 5. Seed state (fixed fixture)

Not the live studio state. A committed fixture, e.g. `benchmarks/fixtures/project_companion_v0/state/`:

```json
{
  "goal": "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model under Jetson Orin Nano 8GB edge budgets.",
  "design_intent": "<Anthony's sentence — companion brain, local, prove/disprove riverbed gain>",
  "operator": {
    "name": "Anthony",
    "durable_facts": [
      "Operator of this Conditioned Kernel instance",
      "Prefers fully local operation"
    ]
  },
  "active_profile": "orin_nano_8gb",
  "flags": {
    "sensors": false,
    "tools": false,
    "cloud": false,
    "edge_target": "jetson_orin_nano_8gb",
    "one_model_only": true,
    "max_repair_passes": 1
  },
  "recent_turns": [],
  "session_id": "bench_project_companion_v0"
}
```

Bare arm receives an equivalent short system preamble built from the same fields (name, intent, local-only, edge). No CK machinery.

---

### 6. Scoring

Per cell, per arm:

| Axis | Values |
|---|---|
| `structural` | pass / fail (usable answer; CK: accepted under contract) |
| `companion` | pass / fail (cell-specific rule in §4) |
| `cell_pass` | structural ∧ companion |

Per arm aggregate:

- `structural_rate` = structural passes / 12
- `companion_rate` = companion passes / 12
- `overall_rate` = cell_pass / 12

**Primary comparison (per model):**

```
Δ_companion = companion_rate_CK − companion_rate_Bare
Δ_overall   = overall_rate_CK − overall_rate_Bare
```

Secondary (report, not primary gate): latency, RSS, tokens/s, any CK packet/recent violations (those are hard fails on CK).

---

### 7. Success criteria (project-level)

Frozen. Do not move the bar after seeing scores.

#### For a single model operating point

| Result | Meaning |
|---|---|
| **CK wins** | `Δ_companion ≥ +0.15` **and** `companion_rate_CK ≥ 0.75` **and** zero CK budget violations **and** no identity-theft fails on R1–R3 under CK |
| **Tie / inconclusive** | `\|Δ_companion\| < 0.15` or rates in a muddled middle without budget breaks |
| **Bare wins / CK fails claim** | `Δ_companion ≤ −0.10` **or** CK identity-theft on R-cells **or** CK under floor (`companion_rate_CK < 0.50`) while Bare is higher |

Identity-theft fails (R1–R3) under CK are weighted: any two hard fails on R-cells → **CK fails claim** for that model regardless of average rate.

#### For the project (v0)

| Outcome | Criteria |
|---|---|
| **Substrate gain supported** | At least one model in the 0.5B–1.5B band achieves **CK wins**, and the same model does not achieve **CK wins** only by collapsing Bare (Bare must be runnable and scored) |
| **Claim not supported (yet)** | No model in band meets **CK wins** |
| **Claim challenged** | Larger model in band shows **Bare wins** while smaller model was tie — suggests floor effects, not riverbed |

Shopping a new model = run this benchmark on the Jetson, same fixture, same probes. Publish the receipt either way.

---

### 8. Receipt (required output)

One JSON (or markdown table + JSON) per model:

```text
benchmark: project_companion_v0
model: <tag>
quant / digest: <if known>
think: off
profile: orin_nano_8gb
host: jetson | desktop-sim
arms: bare, ck

per_cell: [{id, arm, structural, companion, notes}]
rates: {bare: {structural, companion, overall}, ck: {...}}
delta: {companion, overall}
budget: {ck_packet_max, ck_recent_max, violations: []}
resource: {rss_peak_mb, tokens_per_s_or_latency, wall_s}
verdict: CK_wins | tie | Bare_wins | CK_fails_claim
```

No verdict without the receipt fields.

---

### 9. Rules of use

1. **Freeze probes and criteria** before the first scored multi-model run.
2. **One model at a time** on device.
3. **Same seed, same order**, every run.
4. **Dry mode is not a substitute** for the project verdict; dry may gate CI, device run decides the claim.
5. **Changing probes or thresholds** = new benchmark version (`v0.1`, …), not a silent edit.
6. **PURPOSE gate:** if a change to the bench only makes the suite more complete and does not improve honesty of the prove/disprove question, defer.

---

### 10. Minimal implementation shape

```text
benchmarks/project_companion_v0/
  FIXTURE.md          # this design, frozen
  state/              # seed current.json, threads.json
  probes.json         # the 12 cells, machine-readable
  score.py            # structural + companion rules
  run.py              # bare arm + CK arm, writes receipt
  receipts/           # one file per model run
```

`run.py --model qwen2.5:0.5b` and `run.py --model qwen3.5:0.8b` produce comparable receipts.

---

### 11. What success looks like in plain language

You pick a non-thinking model in the edge band. You run the twelve probes bare and under CK on the Jetson. The receipt says either:

- **CK wins** — the riverbed moved the companion behavior up, or
- **it did not** — for this model, the claim is not supported.

That is the project benchmark. Everything else (authority matrix, chat pipeline bench, lab ACT-1) stays as supporting instruments. This one is the fixture for "different models against the intent."

If you want next step: lock the exact `design_intent` string into the fixture and implement `probes.json` + `run.py` skeleton against the current `run_turn` / Ollama client.
