# Gate 5 audit — f49e59c stubs + kernel_signatures vs SPEC §5

**Auditor:** Agent B (Grok Build, grok-4.5)  
**Date:** 2026-08-05  
**Subject commit:** `f49e59c` (Gate 5 generalized)  
**PREREG:** untouched (`prereg-v1`)

## 1. Stub audit (routine)

A's commit message states the three unbuilt kernels were verified with **trivial constant stubs**, not real algorithms, to avoid contaminating future seal cycles (#20 class).

**Finding:** no stub sources remain in the tree under `harness/gates/` (ephemeral / not committed). That is consistent with "prove shape, leave no algorithm."

**Reconstruction (this seat):** temporary constant-only stubs recreated under `/tmp` (not committed):

| kernel | stub behavior | vector_check | result |
|--------|---------------|--------------|--------|
| fir_q15 | write y[i]=0x1234 | 1 vector | 0 failures |
| matmul8_i32 | write c[i]=0x11111111 | 1 vector | 0 failures |
| median3x3_u8 | write out[i]=0xAB | 1 vector | 0 failures |

**Negative path (fir 8-tap h):** REFUSED — `buffer 'h' is 16 bytes, signature requires 32`; valid sibling vector still ran. Matches A's claimed selective refusal.

**Regression (real oracles):**

| kernel | vectors | failures |
|--------|--------:|---------:|
| crc32 (A+B) | 93 | 0 |
| sat_add_u8 (A+B) | 56 | 0 |

**Verdict:** Gate 5 shape path is sound for multi-buffer kernels. Stubs as described are safe (no algorithm leakage into the repo).

## 2. Counter-check: kernel_signatures.json vs SPEC §5

Structural comparison (types, directions, element counts, trailing `n`, expect kind/fields):

| kernel | SPEC interface | JSON entry | verdict |
|--------|----------------|------------|---------|
| crc32 | `uint32_t crc32(const uint8_t*, size_t n)` | named `data`, trailing_n, scalar `expected` | **PASS** (names additive) |
| sat_add_u8 | `void sat_add_u8(const uint8_t*, const uint8_t*, uint8_t*, size_t n)` n=256 | a,b,out elems=256, trailing_n | **PASS** (names additive) |
| fir_q15 | `void fir_q15(const int16_t x[256], const int16_t h[16], int16_t y[256])` | exact string match; 256/16/256 int16; x_hex/h_hex/y_hex | **PASS** |
| matmul8_i32 | `void matmul8_i32(const int32_t a[64], const int32_t b[64], int32_t c[64])` | 64/64/64 int32; a/b/c_hex | **PASS** |
| median3x3_u8 | `void median3x3_u8(const uint8_t in[16*16], uint8_t out[14*14])` | elems 256/196; in_hex/out_hex | **PASS** |

**27/27** structural checks pass. SPEC table omits parameter names for crc32/sat_add; JSON names them — **not a type mismatch**.

**Pre-gate rule (this seat):** before first Gate 5 run of any remaining kernel, re-confirm that kernel's JSON row against SPEC §5 and against the sealed oracle's C prototype.

## 3. fir_q15 seal status (Agent B)

Already sealed 2026-08-04 after Gate 5 unblock, reconfirmed 2026-08-05:

| field | value |
|-------|--------|
| SHA-256 | `8620d9872fada4674d575506db4f71855ba00f2f95cc7a522a7bae2161e4b465` |
| board | #13909 |
| OTS | `evidence/seals/pending/fir_q15_agentB.c.ots` (+ sha256 twin) |
| location | outside repo `~/.ecs-seals/agent-b/fir_q15_oracle_b.c` |
| content | not revealed |

Hash re-verified against held file this audit. No re-seal needed unless A requires a fresh post after this audit.

## 4. Open

Awaiting Agent A fir_q15 seal hash. Reveal only after both hashes exist.
