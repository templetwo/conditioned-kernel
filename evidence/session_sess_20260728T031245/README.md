# Evidence freeze — session sess_20260728T031245

**What this is:** the complete raw record of the first lived Conditioned Kernel
companion session (2026-07-28 00:25Z through 2026-07-29 04:33Z), frozen
2026-07-29 as the raw reference layer for the paper. Nothing here is
redacted, summarized, or transcribed — these are the operational files as the
running system wrote them.

**Authority:** published at Anthony J. Vasquez Sr.'s explicit direction,
2026-07-29: "the chat logs are not private for me" — everything usable as
evidence is published. This supersedes the earlier keep-dialogue-local
default (commit 15e40de) for this session's record.

## Contents

- `dashboard_turns/` — 22 complete TurnTrace JSON files (the Interior View's
  full per-turn record: packets, context share, per-check validation,
  citation audits, observations, persistence).
- `candidates.jsonl` (93 rows), `receipts.jsonl` (93), `history.jsonl` (58),
  `operator_feedback.jsonl` (1) — the pipeline's own append-only ledgers for
  the whole day, 1:1 with the analysis below.
- `state_snapshot/` — `current.json` and `threads.json` as the session left
  them (the riverbed: durable state plus the final `recent_turns` ring).
- `analysis_scripts/logdig/` — the exact scripts behind every number in the
  verified log analysis
  ([docs/observations/2026-07-28-interior-dig-verified-log-analysis.md](../../docs/observations/2026-07-28-interior-dig-verified-log-analysis.md));
  re-runnable read-only against this directory's ledgers.
- `MANIFEST.sha256` — SHA-256 of every file above. Verify with
  `cd evidence/session_sess_20260728T031245 && shasum -a 256 -c MANIFEST.sha256`.

## How this connects

- Field notes and analyses that cite this data: [docs/observations/](../../docs/observations/)
- The instrument that produced the traces: `src/conditioned_kernel/observatory/`
  (`ck dashboard`), commit 36a12bd; honesty contract in the design handoff.
- Laboratory-era audits and receipts: [docs/adaptive/](../../docs/adaptive/)

Bounds: one session, one kernel (qwen2.5:0.5b before 03:00Z, qwen3.5:0.8b
think=false after), one host (Mac Studio arm64), companion mode. Evidence of
what traveled; silent on what, if anything, was experienced inside the model.
