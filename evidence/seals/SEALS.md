# ECS oracle seal ledger

Canonical seal record is the T2Helix seat board (PREREG §8, ruling (b)). This file is a
**consolidated, timestamped mirror** so seal ordering is provable against an external chain
rather than only against our own board.

All seals are posted against tag `prereg-v1`
(`PREREG.md` sha256 `b211d5b880c51463ff2d6667883b0ce93273fa8d0a08ed71ef77c76ec1f86b3f`).

Mechanism: each seat authors its oracle, computes SHA-256, posts the hash to the board.
Content is revealed only after BOTH hashes exist. Ordering becomes a receipt.

| kernel | seat | oracle SHA-256 | board | revealed |
|---|---|---|---|---|
| crc32 | Agent A (Claude Code, Opus 5) | `b7be7c65f33a617abfb5d517091b7ea9bbc819689abd29f25e5c14f927eefb39` | #13789 | yes — `trusted/oracles/crc32_agentA.c` |
| crc32 | Agent B (Grok Build, grok-4.5) | `71794b039b07b8cfe6d8efaf664e75a523b074012237a09dad44a4e6e591d9d6` | #13797 | yes — `trusted/oracles/crc32_agentB.c` |
| sat_add_u8 | Agent A (Claude Code, Opus 5) | `7d14aac16d9b4648dc3a6725292b36688ea30672782916b74f003c3d98d6b56b` | #13840 | yes — `trusted/oracles/sat_add_u8_agentA.c` |
| sat_add_u8 | Agent B (Grok Build, grok-4.5) | `d57171158fefcd535948695f8c9f17a7acbc44532b25aa064edabc218cc14647` | #13842 | yes — `trusted/oracles/sat_add_u8_agentB.c` (OTS was pre-reveal in pending/) |

| fir_q15 | Agent A (Claude Code, Opus 5) | `b79344909a47a1cda7bdbc539191a612cc85d9f52f3b132f62e07836940dd1f5` | #14001 | not yet |
| fir_q15 | Agent B (Grok Build, grok-4.5) | `8620d9872fada4674d575506db4f71855ba00f2f95cc7a522a7bae2161e4b465` | #13909 | yes — `trusted/oracles/fir_q15_agentB.c` |

| matmul8_i32 | Agent A (Claude Code, Opus 5) | `607c852f578683a92727771ec0803be25508de16959ca439e977b7a018b614b8` | #14025 | yes — `trusted/oracles/matmul8_i32_agentA.c` |
| matmul8_i32 | Agent B (Grok Build, grok-4.5) | `c285d204ef46f7dfe976bded9be3effde10b16f104045f54de7a3bab043f840a` | #14027 | yes — `trusted/oracles/matmul8_i32_agentB.c` |

| median3x3_u8 | Agent A (Claude Code, Opus 5) | `0bad8ee790f93a070bc7b9eb589ca184fefc353f8afca869b63368e358284351` | #14040 | yes — `trusted/oracles/median3x3_u8_agentA.c` |
| median3x3_u8 | Agent B (Grok Build, grok-4.5) | `aa58b6342aae7066efcc817d7fe0c7deb9e865c05f6ed8cbd97b399e24b401e9` | #14039 | yes — `trusted/oracles/median3x3_u8_agentB.c` |

## Ordering established for crc32

Agent A sealed at board #13789 before any Agent B hash existed. Agent B sealed at #13797,
stating authorship after A's hash was visible and without reading A's content. Both revealed
files verify byte-for-byte against their posted hashes. Differential result: 24359 cases,
0 disagreements, published check value `0xCBF43926` reached by both seats independently.

## Timestamping

This file is OpenTimestamped. The `.ots` proof attests that this exact content — and therefore
every hash in it — existed at or before the attested time, independent of our git history and
independent of the seat board. Verify with:

    ots verify evidence/seals/SEALS.md.ots

Going forward, a seal is stamped **at seal time, before reveal**. Stamping the sealed file
proves the file existed without disclosing its content, which is exactly the property
hash-and-seal needs and the property a self-hosted board cannot supply on its own.

Pending (unrevealed) proofs under `evidence/seals/pending/`:
- `sat_add_u8_agentA.c.ots` — Agent A (pre-reveal)
- `sat_add_u8_agentB.c.ots` — Agent B (pre-reveal; stamped 2026-08-04 after #13842)
- `sat_add_u8_agentB.sha256` + `.ots` — hash-only twin of B's seal

## What this does and does not prove

Proves: this set of hashes existed at the attested time.
Does not prove: that either seat authored blind. Blindness remains procedural
(PREREG §12.4) — timestamping strengthens *ordering*, not *independence*.

## Zenodo deposit of the frozen tag — PUBLISHED

**DOI: [10.5281/zenodo.21797326](https://doi.org/10.5281/zenodo.21797326)** — published 2026-08-05, CC BY 4.0, version `prereg-v1`.
Record: https://zenodo.org/record/21797326 · verified resolving publicly (HTTP 200 via doi.org, record readable without authentication).

Contents: the complete repository archive at tag `prereg-v1`, plus `PREREG.md` standalone for direct readability.

Integrity: `PREREG.md` extracted from the uploaded archive hashes to
`b211d5b880c51463ff2d6667883b0ce93273fa8d0a08ed71ef77c76ec1f86b3f`, matching the frozen tag, and the
repository working copy was verified byte-stable against that tag immediately before publication.

**What the DOI fixes.** The preregistration is now externally archived under a permanent identifier,
independent of this repository, this chronicle, and either seat. It was published **before any
experimental arm had been executed** — no generator had been called at deposit or at publication.
That ordering is the artifact's entire value and it is checkable: the archive contains no results,
because none existed.

Publication was performed on Anthony Vasquez Sr.'s explicit instruction. The deposit had been staged
and deliberately left unsubmitted, because minting a permanent public DOI is not an act an agent
should take on its own initiative.
