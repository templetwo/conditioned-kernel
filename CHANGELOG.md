# Changelog

## 0.2.1 — 2026-07-22

### Corrected (M1 audit)
- **Do not cite** CHANGELOG 0.2.0 / pre-audit composite **+0.60**. See `experiments/M1_AUDIT.md`.
- Unified `score_output` for all conditions (no hardcoded `accept: False` on bare).
- Anti **goal_echo** rejection + tests that fail without it.
- Probe **answer keys** in `experiments/probes/v0_probes.json`; scoring uses them.
- Validator sees **user_input** (`not_responsive`); capital-of-France style backdoors closed.
- **`must_not_contradict_facts` implemented** (closed mechanical rules).
- Evidence min length 12; no 1-char substring grease.
- Matrix: fair `format=` on all conditions by default; **headline = vs budget_matched_bare**; frozen state snapshot; do not overwrite `last_matrix.json` unless `--write-last`.
- Dropped persistence of `proposed_note` (F10 contamination risk).
- Helix #9524 superseded in chronicle (hypothesis layer; never ground_truth).

### Not claimed
No new substrate-gain number is promoted until a post-audit matrix is re-run and reviewed under criteria 1–9.

## 0.2.0 — 2026-07-22

### SUPERSEDED CLAIM
Reported "CK vs bare composite **+0.60**". **Audit found this untrustworthy** (goal-echo degeneracy, unfair scoring, format= only on treatment). Kept for history only. See `experiments/M1_AUDIT.md` and `experiments/M1_RESULTS.md` banner.

### Added (code still largely present, metrics fixed in 0.2.1)
- Repair plans, template-echo rejection, thread-touch normalization
- Initial score.py / run_matrix (since rewritten for fairness)

## 0.1.1 — 2026-07-22

### Added
- Edge-first default profile `orin_nano_8gb`
- Packet budget enforcement, `ck edge`, Jetson bootstrap, EDGE_SPEC

## 0.1.0 — 2026-07-22

### Added
- Initial Conditioned Kernel scaffold
