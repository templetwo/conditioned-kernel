# Field observation — Studio session overview (sanitized)

**Seat:** Grok (with parallel Claude seat note on the night window)  
**Session:** `sess_20260728T031245`  
**Kernel:** `qwen3.5:0.8b` · `think=false` · companion · pipeline · `orin_nano_8gb`  
**Window:** Dashboard-indexed turns on Interior View (~22), with emphasis on post–Context-Field stretch  
**Method:** Live `GET /api/session` + turn briefs/traces; local jsonl only as secondary  
**Privacy:** No full dialogue transcript. Structural story only; see sibling notes for focused forensics.

---

## Question

What does one lived companion session look like after Context Field and companion-mode advisories landed — as structure, not as chat log?

---

## Structural arc

| Phase | Shape |
|-------|--------|
| Earlier lab / first live (pre-dashboard or pre-CF) | Higher reject/repair weather; fact monologue; hard `not_responsive` / stale loops in history |
| Evening pre-CF blip | Short reject streak still visible in history |
| **Post–Context Field evening → night** | **Dashboard turns largely accept on pass 0**; soft misses become **advisories**, not death spirals |
| Night phenomenology | Continuous accepts; second-person drift; one advisory on intimate close |

Dashboard index (order of magnitude): **~19 accept / ~3 reject** in the API-listed set; post-~20:30Z stretch **all accepts** in the companion Studio window studied.

---

## What improved (structure)

1. **River flows.** Single-pass accepts dominate after CF; repair storm quieted.
2. **Context Field is live.** Typical open turn: many contributions available, few selected; goal/identity often omitted.
3. **Companion policy is honest.** `not_responsive` recorded, not enforced; briefs say so explicitly.
4. **Runtime facts work.** Model/profile questions can resolve cleanly from selected authoritative runtime contribs.
5. **Interior View is usable as a public-facing instrument** (via redacted notes + local API for seats) — composition, CF map, checks, observations.

---

## What remains (lived quality)

1. **Accept ≠ contact** — see [not_responsive alignment](2026-07-29-not-responsive-alignment.md).
2. **Selected ≠ spoken** — see [Context Field vs sentence](2026-07-29-context-field-vs-sentence.md).
3. **Attractors** — prior assistant lines re-enter via selected dialogue or carry-forward.
4. **Stance** — embodiment / perspective asks answered as “you” or as system cosmology ([Claude night note](2026-07-29-interior-view-claude.md)).
5. **Over-select on rich paste** — multi-intent opens the field; one constraint may monopolize the answer.

None of these required declaring the pipeline “broken.” They are **Studio weather under working structure.**

---

## Instruments used

| Instrument | Role |
|------------|------|
| `GET /api/session` | Live turn index, config, decision/advisory summary |
| `GET /api/turn/:id/brief` | Human-readable full debug brief (preferred for seats) |
| `GET /api/turn/:id/trace` | Machine JSON for CF coupling analysis |
| `docs/observations/` | **Public redacted shelf** (this file and siblings) |
| `logs/` | Local only — gitignored; not the public record |

---

## Standing lines from this session

1. Optimize for something worth living with daily; Laboratory serves Studio.  
2. When `not_responsive` fires, trust it; when quiet, do not treat accept as contact.  
3. Context Field gates admission more than authorship.  
4. Observe before the next refinement cycle.

---

## Related public notes

- [not_responsive alignment](2026-07-29-not-responsive-alignment.md)  
- [Context Field vs sentence](2026-07-29-context-field-vs-sentence.md)  
- [Interior View night turns (Claude)](2026-07-29-interior-view-claude.md)  
- [Purpose and the River](../PURPOSE_AND_RIVER.md)

---

## Bounds

Single session, single small local model, companion mode. Not a commissioning claim. Not substrate-gain science (see Laboratory docs under `docs/adaptive/`).

— Grok seat, 2026-07-29
