# RUN 00 — Receipt

## Identity

| Field | Value |
|---|---|
| Run | RUN 00 — Read-Only Grounding Audit |
| Commit inspected | `db668a91e32843c3e53de58325cc17fff4b9c746` |
| Source branch | `main` tracking `origin/main` |
| Audit branch | `codex/ck-run-00-audit` |
| Start status | clean: `## main...origin/main` |
| End status | only the four authorized uncommitted files under `docs/adaptive/` |
| Commit created | none |
| Push performed | none |
| Live model matrix | not run |

## Inputs

Supplied external briefs:

1. `deep-research-report 2.md`
2. `Conditioned_Kernel_Codex_Adoption_Plan_v0.1.md`
3. `Conditioned_Kernel_Codex_Run_Orders_Tonight.md`

Repository instructions and required reading:

- `AGENTS.md`, `COSMIC.md`, `README.md`, `pyproject.toml`
- every file under `docs/`
- all modules under `src/conditioned_kernel/`
- all Python experiment runners and committed experiment documentation/artifacts
- all files under `tests/`
- edge configs and state templates
- recent 12-commit history, with focused inspection of measurement/continuity/qualification commits

## Commands and observed results

### Baseline

```text
git rev-parse HEAD
→ db668a91e32843c3e53de58325cc17fff4b9c746

git status --porcelain=v1 --branch
→ ## main...origin/main

git switch -c codex/ck-run-00-audit
→ Switched to a new branch 'codex/ck-run-00-audit'
```

### Helix context

```text
/Users/vaquez/bin/cosmic-cli helix boot 'conditioned kernel'
/Users/vaquez/bin/cosmic-cli helix recall 'substrate OR arrival packet OR repair'
/Users/vaquez/bin/cosmic-cli helix state
```

Boot created session `8604b82d-502a-46b8-8261-b8afb96d92f2`. Recall/state failed because `better_sqlite3.node` was built for `NODE_MODULE_VERSION 115`, while active Node requires 127. No Helix facts were used as verified context.

### Offline suite

First attempt:

```text
python3 -m pytest -q
→ /opt/homebrew/opt/python@3.14/bin/python3.14: No module named pytest
```

Existing installed pytest interpreter:

```text
/Library/Frameworks/Python.framework/Versions/3.13/bin/pytest -q
→ 85 passed in 2.42s
```

No dependency install was required.

### Isolated dry smoke

State templates were copied to a fresh `/tmp/ck-run00-smoke.*` directory; all receipt/log writes were redirected there.

```text
PYTHONPATH=src python3.13 -m conditioned_kernel smoke --dry \
  --state-dir /tmp/ck-run00-smoke.*/state \
  --logs-dir /tmp/ck-run00-smoke.*/logs

decision: accept
ok: True
profile: orin_nano_8gb
packet_bytes: 1444
passes: 1
```

### Continuity dry smoke

```text
PYTHONPATH=src python3.13 experiments/run_continuity.py \
  --limit 2 --dry --out /tmp/ck-run00-continuity-dry.json

2 tasks × 3 arms
all six rows reported completed
all boundaries distinct
M1 = 0.0
M2 = 0.0
rows_valid = 6
rows_expected = 6
```

This command exposed CK-R00-003: neither the report nor event marks the artifact dry.

### Focused falsification checks

Read-only/offline reproductions verified:

- first continuity corpus task compiles with none of its task-specific facts and `open_threads=[]`;
- missing required `next_state` validates with `valid_schema=true`, `state_faithful=true`, and no violations;
- a thinking-only response sent through `run_turn` becomes ordinary parse/repair/reject, not `NO_FINAL_RESPONSE`;
- current C1 prompt is 724 bytes versus 1,310 bytes for the CK serialized packet;
- committed `gemma3:1b` qualification labels the raw path working while recording empty raw output.

### Repository preservation

Before creating the audit files:

```text
git status --porcelain=v1 --branch
→ ## codex/ck-run-00-audit

git diff -- state logs experiments/runs
→ (empty)
```

The final verification command and final diff summary are recorded below.

## Files created

Only:

- `docs/adaptive/RUN_00_CURRENT_SYSTEM_AUDIT.md`
- `docs/adaptive/RUN_00_FAILURE_REGISTER.md`
- `docs/adaptive/RUN_00_OPEN_QUESTIONS.md`
- `docs/adaptive/RUN_00_RECEIPT.md`

## Prohibited surfaces confirmation

- Production code changed: **no**
- Tests changed: **no**
- Prompts changed: **no**
- Models changed/pulled: **no**
- Thresholds/configs changed: **no**
- State templates changed: **no**
- Committed experiment artifacts changed: **no**
- Live state/logs mutated: **no**; dry writes were redirected to `/tmp`
- Scientific model matrix run: **no**
- Commit or push: **no**

## Unverifiable in this run

- Live Ollama behavior on this host was not tested.
- No Jetson was accessed; memory fit, latency, model digest, quantization, runtime, and load-state claims were not re-measured.
- No prior Helix chronicle/state was recalled because of the Node ABI failure.
- External citations and external report claims were not internet-verified; RUN 00 treated them as supplied planning inputs and checked repository claims against local code/artifacts.
- No scientific gain number was recomputed or promoted.
- No independent fresh-context RUN 04 review was performed; it is outside RUN 00 and requires later authorization/sequencing.

## Final verification

```text
/Library/Frameworks/Python.framework/Versions/3.13/bin/pytest -q
→ 85 passed in 2.24s

git diff -- state logs experiments src tests configs
→ (empty)

wc -l docs/adaptive/RUN_00_*.md
→ 637 total lines across four documents

git status --porcelain=v1 --branch
→ ## codex/ck-run-00-audit
→ ?? docs/adaptive/
```

## What / evidence / residual

- **What:** mapped the static runtime and experiment paths; created the four authorized RUN 00 documents; made no code/test/config/science change.
- **Evidence:** 85 passing offline tests, isolated dry smoke, focused falsification reproductions, clean production/state/artifact diff.
- **Residual:** five critical instrument blockers, contradictory plan authority, unratified thresholds, incomplete provenance/replay, and unavailable Helix recall. Stop for Anthony's review.
