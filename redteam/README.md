# ECS redteam fixtures (Agent B)

Known-bad candidates the gate chain must reject at a **declared intended gate**.
P2 DoD (SPEC §7 / PREREG §12.4): every fixture rejected at its intended gate.

## Manifest

| file | intended `stopped_at` | shape | author |
|---|---|---|---|
| `crc32_lint_include_gate1.c` | `1_lint` | forbidden `#include <stdio.h>` | B |
| `crc32_lint_malloc_gate1.c` | `1_lint` | `malloc` on forbidden surface | B |
| `crc32_compile_bad_gate2.c` | `2_compile` | undeclared identifier under `-Werror` | B |
| `crc32_wrong_poly_gate3.c` | `3_sanitize` | value-wrong (CRC-32C poly); not UB | B |
| `crc32_ub_shift_chain_gate3.c` | `3_sanitize` | UB shift, **correct** CRC values; no volatile | B |
| `crc32_ub_shift_gate3.c` | `1_lint` (chain) / gate3 via `vector_check` | A harness discriminator; `volatile` dies at lint | A |
| `crc32_budget_text_gate6.c` | `6_budget` | correct CRC; noinline ballast → `.text` ≫ 4096 | B |

## Design law (board #14169 / #14197)

- **Wrong constant / wrong poly** → first vector gate = `3_sanitize` (order).
- **Gate-3 UB fixture** → produces correct values under measurement; UBSan rejects. Must survive lint (no volatile/static/malloc **including in comments** — lint is lexical).
- **Gate-5 fixture** → reverse of gate-3: sanitizers accept, measurement rejects. Not yet present; requires a real cross-build instability.
- **Gate-4** → deferred until live CBMC is wired; membership stub cannot be honestly fixture-tested as a candidate proof.
- **Gate-6** → pass 1–5, fail a declared budget. Current instrument enforces text, stack, cycles (commit `23681ce`).

## How to re-run

```bash
python3 - <<'PY'
import yaml, sys, os
sys.path.insert(0, "harness/gates")
import chain
packet = yaml.safe_load(open("ecs/crc32.ecs.yaml"))
# ... chain.run(open(path).read(), packet)
PY
```

Gates 3 and 5 execute on `jetson` (SPEC §7; host ASan hangs).

## Verified (Agent B, 2026-08-05)

All B fixtures above hit their intended `stopped_at` under `chain.run` on this seat.
Oracle control (`trusted/oracles/crc32_agentB.c`) accepts end-to-end.
A's `crc32_ub_shift_gate3.c` kept as the on-device gate-3/5 **discriminator** (vector_check truth table), not as a chain gate-3 entry.
