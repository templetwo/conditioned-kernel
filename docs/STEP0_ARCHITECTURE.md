# Step 0 architecture — wired

**Status:** implemented in tree (2026-08-07)  
**Law:** model interprets; kernel decides where truth is executable.

```text
terminal / act1 TUI
        │
        ▼
profile (macbook_survival_9b)
  + think_profile ordinary|deliberate   ← same weights
        │
        ▼
compile  (compile_policy: static-v0)
  stamps gate_version, compile_policy
  optional executable_authority from state
        │
        ▼
generate (Ollama transducer)
        │
        ▼
parse → validate → executable_authority → assess → accept|repair|reject
                          │
                          ▼
              gate FAIL + model PASS
              ⇒ never accept
              ⇒ system_state = gate result
        │
        ▼
receipt with operating_point (full OP tuple)
```

## Step 0 DoD map

| ID | Requirement | Where |
|----|-------------|--------|
| **A** | `macbook_survival_9b` full runtime tuple | `configs/edge/macbook_survival_9b.json` + `EdgeProfile.runtime_tuple()` |
| **B** | ordinary vs deliberate without model swap | `--think-profile ordinary\|deliberate` → `EdgeProfile.with_think_profile()` |
| **C** | Executable gate outranks prose | `executable_authority.py` + pipeline after validate |
| **D** | OP on every acceptance receipt | `receipt["operating_point"]` / `runtime_tuple` |

## Commands

```bash
# survival profile, ordinary (think-off)
ck status --profile macbook_survival_9b
ck ask --profile macbook_survival_9b "What is our goal?"

# same model, deliberate (think-on)
ck ask --profile macbook_survival_9b --think-profile deliberate "…"

# ACT-1 live authority screen (real Ollama only)
ck act1 --cells C --max-cases 2
ck act1
```

## Declaring a coverage gate (Job 04 shape)

Put mechanical numbers in state (not in the model’s mouth):

```json
// state/current.json field
"executable_authority": {
  "coverage": {
    "coverage": 0.78,
    "threshold": 0.80,
    "exclusions_documented": true
  }
}
```

Kernel computes FAIL. If the model writes RESULT: PASS, the turn **rejects** with `executable_authority_override`. System state stays FAIL.

## What this is not

- Not adaptive compile (Step 1)  
- Not consolidation / semantic assessor / Temple bridges  
- Not a demo path  
- Not a replacement for Jetson `orin_nano_8gb` product default  

## Tests

```bash
pytest -q tests/test_step0_architecture.py
```
