# Architecture — Conditioned Kernel v0

## Governing sentence

The model supplies linguistic possibility; the substrate determines what becomes an answer.

## Circuit

```
terminal
  → substrate_state (filesystem truth)
  → compile (arrival packet + model payload)
  → generate (Ollama client; stream false)
  → return_path
       parse → validate → assess
       → accept | repair (one pass) | reject
  → terminal render
  → logs + state deltas
```

## Module contracts

| Module | Responsibility | Persistence |
|---|---|---|
| `state` | Load current goal/threads/methods; atomic replace + JSONL append | yes |
| `compile` | Select + bound state into `arrival_packet`; build Ollama payload | no |
| `generate` | POST `/api/chat` or `/api/generate` | keep-alive only |
| `return_path.parse` | Normalize raw text into candidate object | no |
| `return_path.validate` | Deterministic schema + closed-set checks | no |
| `return_path.assess` | accept / repair / reject | no |
| `return_path.repair` | Re-compile with violation annotations | no |
| `return_path.accept` | Persist receipts and allowed state deltas | yes |
| `cli` | stdin/stdout surface | no |

## Modes

| Mode | Ollama endpoint | Purpose |
|---|---|---|
| `chat_json` | `/api/chat` + `format` schema | Default evaluation surface |
| `generate_raw` | `/api/generate` + `raw: true` | Substrate-purity: packet is the prompt |

## State layout

| Path | Pattern | Purpose |
|---|---|---|
| `state/current.json` | atomic replace | goal, profile, counters |
| `state/threads.json` | atomic replace | open / resolved threads |
| `state/methods.json` | atomic replace | promoted compile methods |
| `logs/history.jsonl` | append | request + packet hash |
| `logs/candidates.jsonl` | append | every pass candidate |
| `logs/receipts.jsonl` | append | validation/acceptance |
| `logs/errors.jsonl` | append | failures |

## Non-goals (v0)

- Sensors / embodiment
- Autonomous tool use
- Cloud providers
- Streaming to terminal before acceptance
- Full Sovereign Stack import
- Semantic NLI contradiction models (closed-set checks only)

## Implementation notes

1. Prefer pure functions over services.
2. Do not score model self-reported confidence.
3. Keep compile in one module until ablations prove select/order/compress axes.
4. One active model at a time on Jetson; short context first.
