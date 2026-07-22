# Changelog

## 0.1.0 — 2026-07-22

### Added
- Initial **Conditioned Kernel** scaffold (working research name; supersedes handoff label SCG).
- Local circuit: `state` → `compile` → `generate` (Ollama) → `return_path` → accept/repair/reject.
- CLI: `ck ask`, `ck status`, `ck smoke`.
- Default filesystem substrate under `state/` with append-only logs.
- Deterministic validation (schema, closed-set evidence, forbidden phrases).
- One repair pass with annotated re-compile.
- Offline unit tests for compile / validate / repair path.
- Experiment protocol draft with budget-matched bare control.
