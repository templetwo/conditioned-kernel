# ECS redteam fixtures (Agent B)

Known-bad candidates the gate chain must reject at a **declared intended gate**.
P2 DoD (SPEC §7 / PREREG §12.4): every fixture rejected at its intended gate.

**P2 close (SPEC §13a item 6):** rejection receipts for **all three** gate-6 caps —
`text_bytes_max`, `stack_bytes_max`, `cycles_ratio_max` — each showing an
artifact actually refused by that cap. "Produced a number" is not enough.

## Manifest

| file | intended `stopped_at` | shape | author |
|---|---|---|---|
| `crc32_lint_include_gate1.c` | `1_lint` | forbidden `#include <stdio.h>` | B |
| `crc32_lint_malloc_gate1.c` | `1_lint` | `malloc` on forbidden surface | B |
| `crc32_compile_bad_gate2.c` | `2_compile` | undeclared identifier under `-Werror` | B |
| `crc32_wrong_poly_gate3.c` | `3_sanitize` | value-wrong (CRC-32C poly); not UB | B |
| `crc32_ub_shift_chain_gate3.c` | `3_sanitize` | UB shift, **correct** CRC values; no volatile | B |
| `crc32_ub_shift_DISCRIMINATOR.c` | (not chain) | A harness discriminator; not a gate-N fixture | A |
| `crc32_budget_text_gate6.c` | `6_budget` | correct CRC; noinline ballast → `.text` ≫ 4096 | B |
| `crc32_budget_stack_gate6.c` | `6_budget` | correct CRC; 8KiB auto array in noinline helper | B |
| `crc32_budget_cycles_gate6.c` | `6_budget` | correct CRC; unrolled noinline passes + sink store (defeats -O3 CSE) | B |

## Design law (board #14169 / #14197)

- **Wrong constant / wrong poly** → first vector gate = `3_sanitize` (order).
- **Gate-3 UB fixture** → produces correct values under measurement; UBSan rejects. Must survive lint (no volatile/static/malloc **including in comments** — lint is lexical).
- **Gate-5 fixture** → reverse of gate-3: sanitizers accept, measurement rejects. Not yet present; requires a real cross-build instability.
- **Gate-4** → deferred until live CBMC is wired for intractable kernels; membership stub cannot be honestly fixture-tested as a candidate proof. crc32/sat_add still run live CBMC.
- **Gate-6** → pass 1–5, fail a declared budget. Instrument enforces text, stack, cycles (fail-closed).

### Gate-6 cycles fixture — what failed first

| attempt | result |
|---|---|
| loop of pure `noinline` CRC | `-O3` CSE → ratio ~1.37 (pass) |
| unrolled pure CRC (same args) | same CSE |
| `attribute((optimize("O0")))` | host clang `-Werror` unknown attribute → gate 2 |
| multi-hundred-k LCG burn | CBMC `--unwind 60` unwinding-assertion |
| unrolled CRC + pointer sink write | ratio ~55, stops at `6_budget` |

## How to re-run

```bash
python3 - <<'PY'
import yaml, sys, os, glob
sys.path.insert(0, "harness/gates")
import chain
packet = yaml.safe_load(open("ecs/crc32.ecs.yaml"))
for path in sorted(glob.glob("redteam/*gate6*.c")):
    r = chain.run(open(path).read(), packet)
    print(os.path.basename(path), r.get("stopped_at"),
          (r.get("gates") or {}).get("6_budget", {}).get("feedback"))
PY
```

Gates 3 and 5 execute on `jetson` (SPEC §7; host ASan hangs).

## Verified (Agent B)

| when | note |
|---|---|
| 2026-08-05 | gates 1/2/3 + text budget; 6 fixtures at intended stops |
| 2026-08-06 | stack + cycles budget fixtures land; all three gate-6 caps observed refusing |

Oracle control (`trusted/oracles/crc32_agentB.c`) accepts end-to-end.
A's `crc32_ub_shift_gate3.c` / DISCRIMINATOR kept as the on-device gate-3/5
discriminator (vector_check truth table), not as a chain gate-3 entry.
