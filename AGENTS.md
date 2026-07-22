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

- Fully local. No cloud providers.
- No sensors. No autonomous tools.
- Do not stream Ollama to terminal before acceptance.
- Do not score model self-reported confidence.
- Faithfulness checks are closed-set / mechanical, not NLI.
- Do not import full Sovereign Stack. Bridge is P3.
- Prefer one compile module until ablations demand select/order/compress split.

## Success sentence

Same small local model through substrate must beat bare on coherence, state-faithfulness, continuity, repairability — and gains should survive model swap in band.
