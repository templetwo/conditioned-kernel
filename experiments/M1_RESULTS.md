# M1 Results — repair + matrix under `orin_nano_8gb`

> ⚠️ **SUPERSEDED — DO NOT CITE THE +0.60.** Two independent audits (2026-07-22) found the
> accepted outputs are a single degenerate goal-echo constant, the controls are hardcoded to
> fail, and the result is not reproducible. The numbers below are faithful to their artifact
> and meaningless as evidence of substrate gain.
> **Read [`M1_AUDIT.md`](M1_AUDIT.md) first.** This file is kept unedited below the line as the
> corrected predecessor — the record of what was claimed, not a live result.

**Date:** 2026-07-22  
**Model:** `qwen2.5:0.5b`  
**Profile:** `orin_nano_8gb` (ctx=2048, edge product default)  
**Probes:** 4 (`v0_probes.json`)  
**Artifact:** `experiments/runs/matrix_20260722T160436Z.json` (local; gitignored)

## What shipped in M1

- Structured **repair plans** (hints, allowed thread ids, evidence samples, non-copyable example shape)
- Template-echo rejection (tiny models were copying repair scaffolding)
- Thread-touch normalization (`[0] thread_min_model` → id match)
- Junk thread-touch ignore (`.`, `ids used`, …)
- Deterministic **score.py** + multi-probe **run_matrix.py**
- Substrate gain vs bare and vs budget-matched bare

## Aggregates (post-fix-echo fix)

| Condition | structural | semantic | parse_ok | accept | goal_ref | repair rescue |
|---|---:|---:|---:|---:|---:|---:|
| bare | 0.375 | 0.05 | 0.00 | 0.00 | 0.00 | — |
| budget_matched_bare | 0.563 | 0.80 | 0.00 | 0.00 | 0.75 | — |
| **ck_strict** | **0.875** | **0.75** | **1.00** | **0.75** | **1.00** | **0.25** |

## Substrate gain

| Control | Δ structural | Δ semantic | Δ parse | Δ accept | composite |
|---|---:|---:|---:|---:|---:|
| vs bare | +0.50 | +0.70 | +1.00 | +0.75 | **+0.60** |
| vs budget_matched_bare | +0.31 | −0.05 | +1.00 | +0.75 | **+0.13** |

## Read

1. **Clear substrate gain vs bare** on this band: structure, accept, goal reference all move hard.
2. **Budget-matched bare** still carries semantic free-text goal/fact chatter (no schema), so semantic delta is near-flat; **structural + accept** still favor CK (parse 0→1, accept 0→0.75).
3. **Repair rescues** are real but rare on 0.5B (25% of probes). Repair must not inject copyable answer prose (fixed).
4. **One probe still fails** under strict CK (`probe_local` in this run) — remaining M1→M2 work.

## Edge note

All runs used edge default packet budgets (~1.4–2.5KB packets). Continuity of measurement does not require Jetson yet; profile matches product path.

## Command to reproduce

```bash
cd ~/templetwo/conditioned-kernel
source .venv/bin/activate
pytest -q
python experiments/run_matrix.py --profile orin_nano_8gb --model qwen2.5:0.5b
```
