# Changelog

## 0.1.1 — 2026-07-22

### Added
- **Edge-first product mode**: default profile `orin_nano_8gb` (Jetson Orin Nano 8GB class).
- Profiles under `configs/edge/`: `orin_nano_8gb`, `orin_nano_tight`, `desktop_dev`.
- Packet budget enforcement (facts/threads/bytes); fail closed on oversize.
- CLI: `ck edge`, `--profile`; status reports working-set estimates.
- Compact arrival serialization to save context tokens.
- `scripts/jetson_bootstrap.sh` and `docs/EDGE_SPEC.md`.

## 0.1.0 — 2026-07-22

### Added
- Initial **Conditioned Kernel** scaffold (working research name; supersedes handoff label SCG).
- Local circuit: `state` → `compile` → `generate` (Ollama) → `return_path` → accept/repair/reject.
- CLI: `ck ask`, `ck status`, `ck smoke`.
- Default filesystem substrate under `state/` with append-only logs.
- Deterministic validation (schema, closed-set evidence, forbidden phrases).
- One repair pass with receipts.
- Offline unit tests for compile / validate / repair path.
- Experiment protocol draft with budget-matched bare control.
