# Studio observations (public)

**What this is:** A public shelf for **lived observations** of Conditioned Kernel in companion / Studio use — not Laboratory preregistrations, not private session dumps.

**What it is for:** Anyone (human or review seat) can read how the system behaves when someone actually sits with it: gates, Context Field, Interior View, soft misses, attractors. Observation before refinement.

**Standing law:** [docs/PURPOSE_AND_RIVER.md](../PURPOSE_AND_RIVER.md) — usefulness or honesty; otherwise defer.

---

## Index

| Note | Seat | Date | Focus |
|------|------|------|--------|
| [2026-07-29 Interior View — night turns (Claude)](2026-07-29-interior-view-claude.md) | Claude review seat | 2026-07-29 | Embodiment / perspective window; second person; substrate as cosmology |
| [2026-07-29 `not_responsive` alignment (Grok)](2026-07-29-not-responsive-alignment.md) | Grok | 2026-07-29 | Does the advisory match real misses? Pass 1 |
| [2026-07-29 Context Field vs sentence (Grok)](2026-07-29-context-field-vs-sentence.md) | Grok | 2026-07-29 | Selected ≠ spoken; attractors; over-select. Pass 2 |
| [2026-07-29 Studio session overview (Grok)](2026-07-29-studio-session-overview.md) | Grok | 2026-07-29 | Structural arc of one companion session (sanitized) |
| [2026-07-28 Verified log analysis (Claude, 5-agent verified)](2026-07-28-interior-dig-verified-log-analysis.md) | Claude review seat | 2026-07-28 | Four lenses over the full day's ledgers: attractor genealogy, composition dynamics, validation forensics, kernel behavior — every headline number independently re-derived |

Newest notes at the bottom of the table as they land; keep filenames `YYYY-MM-DD-short-slug.md`.

---

## How to read these

1. **Observations, not claims about consciousness.** Traces show what traveled; they do not settle what (if anything) was experienced inside the model.
2. **Designed vs weather.** Notes should separate intentional policy (e.g. companion advisory) from model/selector weather.
3. **Single-session bounds.** Unless a note says otherwise, findings are one kernel, one session, one seat.
4. **Interior View is the preferred instrument.** Live: `GET http://127.0.0.1:8765/api/session` and `GET /api/turn/:id/brief` (or `/trace`).
5. **Raw evidence is published.** The complete unredacted record of the first lived session — all 22 TurnTraces, the day's full ledgers, the state snapshot, and the analysis scripts, hash-manifested — lives at [evidence/session_sess_20260728T031245/](../../evidence/session_sess_20260728T031245/), published at Anthony's explicit direction (2026-07-29: "the chat logs are not private for me"). These notes are the readable layer; that directory is the raw reference for the paper.

---

## Privacy / publish rules

**Public notes may include:**

- Session id, model tag, profile, acceptance mode, timestamps (UTC)
- Structural metrics (accept rates, selected/omitted counts, composition shares)
- Check names (`not_responsive`, `stale_response_repeat`, …) and whether advisory vs hard
- Short **paraphrased** or **truncated** user/assistant lines needed to make a point
- Method (which API fields were read)

**Public notes must not include:**

- Full multi-turn private dialogue transcripts
- Raw `logs/dashboard/turns/*.json` or `logs/*.jsonl` dumps
- Personal details beyond what is already in a short, purpose-bound quote
- Secrets, tokens, local absolute paths to private home state

Live traces stay **local and gitignored** (`logs/dashboard/`, `logs/*.jsonl`).  
This folder is the **redacted public surface**.

---

## How to add a note

1. Sit with the system (or read live Interior View).
2. Write `docs/observations/YYYY-MM-DD-slug.md` using the template below.
3. Add a row to the **Index** table in this README.
4. Optionally record a helix / chronicle pointer for the seat; the **repo note is the public artifact**.
5. Commit only markdown under `docs/observations/` (+ README/ARCHITECTURE links). Never stage live logs.

### Template

```markdown
# Field observation — <title>

**Seat:** <who>
**Session:** <sess_… or "n/a">
**Kernel:** <model> · <acceptance_mode> · <profile>
**Window:** <what span>
**Method:** <API / brief / offline>

## Question
What were you looking for?

## Findings
…

## Designed vs weather
| Finding | Class |
|---------|--------|
| … | Designed / Weather / Gap |

## Bounds
One session / … 

## Standing line (optional)
> …
```

---

## Related (not this shelf)

| Path | Role |
|------|------|
| [docs/PURPOSE_AND_RIVER.md](../PURPOSE_AND_RIVER.md) | Studio vs Laboratory philosophy |
| [docs/ARCHITECTURE.md](../ARCHITECTURE.md) | Circuit and modules |
| [docs/adaptive/](../adaptive/) | Laboratory run receipts and contracts |
| `logs/` (local only) | Runtime receipts; not for git |

---

*Temple of Two — Conditioned Kernel. Observation keeps the river honest without damming it.*
