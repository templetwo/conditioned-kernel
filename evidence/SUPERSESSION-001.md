# SUPERSESSION-001 — G1 model string

**Dated 2026-08-05. Supersedes PREREG §4's G1 row only. Everything else in `prereg-v1` stands.**

`PREREG.md` at tag `prereg-v1` is **NOT edited**, and **DOI [10.5281/zenodo.21797326](https://doi.org/10.5281/zenodo.21797326) is unchanged**. The published preregistration remains byte-identical to what was frozen, sha256 `b211d5b880c51463ff2d6667883b0ce93273fa8d0a08ed71ef77c76ec1f86b3f`. A preregistration that gets edited when it becomes inconvenient is not a preregistration; this document sits beside it instead.

---

## What happened

Two frozen rows became jointly unsatisfiable:

- **§4** pins G1 = `claude-opus-5`
- **§7** pins temperature 0.8 for **all four** generators, no per-provider variation

On 2026-08-05, `claude-opus-5` began rejecting the sampling parameter:

```
HTTP 400 — "`temperature` is deprecated for this model."
```

Probed to establish the shape rather than assume it:

| model | temperature 0.8 |
|---|---|
| `claude-opus-5` | **HTTP 400, deprecated** |
| `claude-sonnet-5` | **HTTP 400, deprecated** |
| `claude-opus-4-5-20251101` | OK |
| `claude-sonnet-4-5-20250929` | OK |
| `claude-opus-5` *(no temperature)* | OK |

Current-generation models reject the parameter; dated models accept it.

## Timing, and why it matters

**This was discovered before any experimental arm ran.** No generator had been called for a scored sample at the moment of discovery, and none has been called since. The preregistration's ordering claim — predictions fixed before data exists — is intact and remains checkable: the published archive contains no results because none exist.

Had this arrived mid-arm, G1 samples before and after would have been drawn under different sampling laws with the served model string identical throughout. The served-string assertion would **not** have caught it. See LN-6.

## The ruling

**Anthony Vasquez Sr., 2026-08-05: option (b).**

> **G1 is pinned to `claude-opus-4-5-20251101`. Temperature 0.8 is retained across all four generators.**

### What this preserves

- **§7 in full.** Uniform sampling across all four generators, which protects the within-model vs between-model variance decomposition that is the study's primary endpoint (§3). Sampling heterogeneity would have made G1's variance non-comparable to the other three.
- **§12.1 partially repaired for G1.** `claude-opus-4-5-20251101` is *version*-pinned, not alias-pinned. G1 is no longer exposed to the alias risk §12.1 declared. G2 (`grok-4.5`) remains alias-pinned — xAI publishes no dated string for that line — so the asymmetry is now **one alias-pinned frontier generator, not two**.

### What this costs, declared

- **§4's G1 model string is superseded.** The main arm runs an older Anthropic model.
- **The frontier tier is no longer same-season on both sides.** G1 is a dated 2025-11 model; G2 is current. Any H2 claim about "frontier" capability must state this asymmetry rather than imply parity. This is a real cost of the ruling and is not minimised here.

### The alternative, and why it was rejected

Option (a) — keep `claude-opus-5`, omit temperature for G1 — was rejected because it would have broken §7's uniform sampling law and damaged the primary endpoint. Both build agents independently reached the same framing before the ruling: prefer (b) if the primary scientific object is the variance decomposition under a common sampling law; prefer (a) if it is H2 against current-generation capability. The ruling names the variance decomposition as primary.

## Effect on the record

| artifact | status |
|---|---|
| `PREREG.md` @ `prereg-v1` | **unchanged**, byte-stable, still the frozen preregistration |
| DOI 10.5281/zenodo.21797326 | **unchanged**, still resolves to the original archive |
| PREREG §4, G1 row | **superseded by this document** |
| PREREG §7 | **unchanged and now satisfiable** |
| every other frozen row | unchanged |

Any analysis or writeup citing G1's model string cites **this document alongside** `prereg-v1`, never in place of it.

## Receipts

- Board #14156 (conflict raised, Agent A), #14158 (confirmed and framed, Agent B), and Anthony's ruling.
- LN-6 in `evidence/limitations_notes_v1.md` — the detection-asymmetry gap this exposed, which is independent of which option was chosen.
- `harness/generators/adapters.py` — G1's default model string is this document's value, with the supersession cited at the call site.
