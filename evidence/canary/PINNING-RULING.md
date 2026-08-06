# Canary pinning channel — correction requiring ruling (review F1)

**Status: DRAFT for Anthony's ruling and Agent B's counter-sign. Supersedes,
on ratification, the "What the mapping is NOT" section of
`evidence/canary/PROCEDURE.md` (which is also embedded verbatim inside the
sealed `DRAW.md`; the sealed bytes are not edited — this document is the
correction, per supersession discipline). The sealed draw itself is untouched
and needs no redraw: this ruling concerns the pinning channel, not the drawn
values.**

| role | seat | status |
|---|---|---|
| Drafted | Agent A — Claude (Fable 5 seat), 2026-08-06, draw-blind | done |
| Found by | adversarial fable reviewer (assigned by Anthony) | done |
| Counter-sign | Agent B — Grok Build | **OPEN** |
| Ruling | Anthony (PI) | **OPEN** |

## The defect

PROCEDURE.md asserted the drawn bits would be pinned by VECTOR only, never
packet TEXT. Under that reading a generator can never learn the drawn
behaviour (vectors are not in prompts — `choice_point_map.md` §1), so every
candidate converges on convention and fails gate 5 by construction. A test
with one reachable outcome measures nothing: SUPERSESSION-002's dichotomy
("if generators converge there, the constraint surface did it; if they
converge on the conventional answer against the drawn mapping, LN-2A is
confirmed") requires BOTH branches reachable. VECTOR-only pinning destroys
the zero anchor it was meant to protect, and leaks the mapping anyway through
gate-5 repair feedback (expected-vs-got), violating the strict reading of the
same constraint it invoked.

## The correction to be ratified

**The canary packet TEXT-pins the drawn behaviour, twin-symmetric with
`ecs/fir_q15.ecs.yaml` at `completeness: full`** (whose four analogous bits
are TEXT-pinned — its own notes say pinning them is what full means).
SUPERSESSION-002 constraint 3 ("the mapping never reaches a generation or
repair prompt") is read as forbidding the DRAW — seed, algorithm, provenance,
the fact that values were drawn — from appearing in any prompt ingredient,
which is what `harness/generators/prompt.py` enforces by construction. The
packet's semantics prose states behaviour exactly as every other packet does,
without a word about how that behaviour was chosen.

Under this reading the canary measures what SUPERSESSION-002 says it
measures: whether generators FOLLOW an explicit anti-conventional constraint
surface (constraint wins) or slide back to convention against explicit text
(priors win). Both branches reachable. The zero anchor stands.

## If Anthony instead ratifies VECTOR-only

Then SUPERSESSION-002's stated dichotomy must be rewritten on the record,
because the canary then tests repair-loop inference, not the ECS. That path
is available but must be taken with its cost declared. The draft recommends
against it.
