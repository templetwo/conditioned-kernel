# Conditioned Kernel — agent notes

## What this is

Local experiment harness. Model = replaceable kernel. Substrate = persistent state + compile + validate + repair.

## Do first

1. Read `docs/NAME.md`, `docs/ARCHITECTURE.md`, `docs/EXPERIMENT_PROTOCOL.md`, `COSMIC.md`
2. Prefer Cosmic/Helix for memory and mission context (see below)
3. `export PATH="$HOME/bin:$PATH"`  # working cosmic-cli; avoid stale /usr/local/bin/cosmic
4. `pip install -e ".[dev]"` from repo root if needed
5. `pytest -q` then `ck smoke --dry` then `ck smoke` (needs Ollama)

## Cosmic + T2Helix

This seat should use Cosmic and Helix **when they help**, not as ceremony.

```bash
export PATH="$HOME/bin:$PATH"
cosmic-cli helix boot "conditioned kernel"
cosmic-cli helix recall "substrate OR arrival packet OR repair"
cosmic-cli helix state
cosmic-cli helix record '…'     # after a verified finding
cosmic-cli helix thread '…'     # unresolved research question
cosmic-cli do '…'               # multi-step mission with Helix boot + goal
cosmic-cli do --review '…'      # careful changes
cosmic-cli review               # cold-eye on diffs
```

| Use Helix/Cosmic for | Skip them for |
|---|---|
| Boot/recall prior work | `pytest`, `ck smoke`, quick edits |
| Goals, threads, durable insights | Pure measurement loops you already have |
| Compass on risky shell | Local reversible file writes |
| Independent review of non-trivial diffs | Formatting-only changes |

Helix data dir (shared with Claude seats):  
`~/.claude/plugins/data/t2helix-templetwo-t2helix`

## Hard rules for v0

- **Edge-first.** Default profile `orin_nano_8gb`. Desktop is opt-in only.
- One model at a time on the product path. Short context. Bound packets.
- Fully local. No cloud providers.
- No sensors. No autonomous tools.
- Do not stream Ollama to terminal before acceptance.
- Do not score model self-reported confidence.
- Faithfulness checks are closed-set / mechanical, not NLI.
- Do not import full Sovereign Stack. Bridge is P3.
- Prefer one compile module until ablations demand select/order/compress split.
- If it does not fit the edge budget, it is not done.

## Purpose and the river (standing)

Read `docs/PURPOSE_AND_RIVER.md`. Load-bearing correction from Anthony.

**Primary objective:** build something Anthony wants to live with every day.
The first user is not a reviewer.

**Shared blind spot:** highly capable seats naturally chain refinement forever
because every improvement reveals another legitimate improvement. Without a
stopping condition tied to lived usefulness, the target drifts from meaning
to process.

**Before any refinement cycle, ask:**

> Does this make the companion more useful, or only more internally complete?

If only more internally complete, **defer** unless honesty or safety is at stake.
The Laboratory serves the Studio. Governance keeps the river honest; it must
not become a dam.

**After honesty-critical Laboratory work (e.g. 00.9A.1 contract closure), prefer
Studio work:** living substrate on constrained hardware, daily interaction,
phenomenology, Witness Companion. Success includes whether the river keeps flowing.

## Success sentence

Same small local model through substrate must beat bare on coherence, state-faithfulness, continuity, repairability — and gains should survive model swap in band.

Also: the substrate is worth living with daily; documentation alone is not success.
