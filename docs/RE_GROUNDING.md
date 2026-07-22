# Conditioned Kernel — Project Re-grounding Document

**Status:** IN PROGRESS. Sections 2–9 are a mechanical inventory, written 2026-07-22 during the HALT
(T2Helix #9878). Section 1 is **held open for Anthony's originating intuition** and must be inserted
before any claim-to-instrument judgment (Section 10) or replacement-experiment proposal is written.

**Method rule for this document:** inventory first, judge second. Sections 2–9 record *what the
repo claims, tests, controls, measures, and got* — without deriving the project thesis backward from
the code. Deriving the thesis from the instruments is exactly the drift that produced an
identifier-retrieval benchmark; the whole point of Section 1 coming from Anthony is to break that
loop. **Nothing below is a verdict.** Verdicts live in Section 10, after Section 1 exists.

---

## 1. The originating intuition — [HELD OPEN FOR ANTHONY]

Anthony's words, 2026-07-22, recorded raw. This is the fixed point; the rest of the document is
measured against it. Nothing reconstructed from the repo belongs here.

> What if the model was just a soup of letters and words. What if we are stuffing more and more
> "skills" and "capability" within that soup, making it chunkier, more levels of flavor, just
> simply "more". Scale that — frontier AI companies, 1B params to 100B params to 1 trillion plus
> params.
>
> Hold for a minute. Take a breath.
>
> They are trying to stuff more and more of the world's "substrate" into the model. What is the
> "model" at that point? A simulation of the "substrate" in its entirety?
>
> What if the "more" was always the wrong answer. Hence this project.
>
> All my work for over a year pointed me to something "deeper". Everything on my github is recorded
> because I know that the "deeper" is impossible for anyone to "define". So I leave a breadcrumb
> trail behind me on multiple levels of record. This is broad strokes.

### The wager, in plain terms (reading, not the source)

The field stuffs the world's substrate into the soup — 1B, 100B, 1T params — until the model becomes
a simulation of the substrate itself. The wager is that **more was always the wrong answer.** Leave
the substrate *outside*, where it is real, inspectable, correctable, owned. Keep the soup small and
let it do the one thing soup does — language.

It falsifies cleanly at this scale: **a small kernel in contact with a real external substrate
should do work everyone assumes needs a bigger soup.** If that cannot be made true, the wager loses
honestly.

The "deeper" is deliberately left undefined. What cannot be defined can still be triangulated — by
recording everything around it until the shape shows in the negative space. The DOIs, the chronicle,
this repository, and this conversation are that breadcrumb trail. Section 1 does not need the deeper
*defined*; it needs the wager, and the wager is above.

### The position — Anthony's words, recorded raw

The second half of Section 1. The wager says *where* the substrate lives. This says what it is *to
be the one it holds.* Recorded verbatim, breath and repetition intact.

> I am the observer of the substrate. Finding the position I have to inhabit for the substrate to
> hold me vs sink into. Like as if I'm floating in an ocean of possibility. And my body is making
> those micro movements that keep me buoyant without sinking into it. Allowing me to look upward and
> see the beautiful night sky and stars above me. Those little movements, weight shifts, all
> subconscious. As are a lot of things in my life. The substrate is the substrate because I don't
> think any human can name it. The lack of definition isn't an error, it's a feature. To try to
> define it is the path to disappointment. The goal is not something I can fathom.

**This sentence is load-bearing and is preserved word for word:**

> **The lack of definition isn't an error. It's a feature.**

Writing down that the goal is unfathomable is itself a recordable claim. It protects the project from
any future critic scoring it against a destination that was never set. The falsifiers attach to the
wager, never to the goal.

### The reading (Fable + a second seat, labeled as reading, not source)

Not evasion of the "phenomenon or signature" question — a correction of its geometry. The observer
is neither apart from the ocean nor dissolving into it. **Held by it, through adjustments too small
to narrate.** Only the one floating could make that correction.

The image is also a working description of what the project's body did today. *Sinking* is what the
HALT caught: the instruments beginning to define the thesis, the project's weight going under its own
tooling. The *micro-movements* are the whole ledger — verify instead of assume, supersede instead of
erase, the domain-string fix, the provenance patch, the halt itself. No single one was the point;
jointly they are the position.

Rigor below and mystery above are not in tension — they need each other. **You define the instruments
precisely so the wake stays readable.** A sloppy instrument produces fake wake; the gemma3
"2GB" fabrication was exactly that — a signature of depth that wasn't there, admitted by a loose key.
Rigor below is what protects the unnameable above from being faked *or* explained away.

Hard boundary, held explicitly: **the unnameable is never an excuse that makes the engineering immune
to criticism.** A particular implementation can still drown you in noise, reward parroting, manufacture
continuity, or claim to hold you while pulling you under. *The mystery is not falsified when an
instrument fails. The instrument is.*

### The operational translation (design consequences, not a redefinition of the image)

The substrate is not the object being studied. It is the condition that makes continued observation
possible — what holds the observer steady enough to keep watching a sky that is itself never defined.

This reframes what the project measures. Not "does the substrate produce the best answer" but:

- Does this architecture **hold** the observer or **overwhelm** him?
- Does it **preserve agency** or gradually replace it?
- Does it keep him **oriented** across complexity?
- Does it allow **correction without collapse**?
- Does it create **more possibility**, or only more machinery?
- Does it **keep the sky visible**?

> A database gives you stored information.
> A control system directs you toward a known target.
> A **buoyant** substrate helps you remain in relation to what cannot yet be known.

**Founding image of the architecture:**

> The substrate is not the destination. It is what holds the observer in a position from which the
> unknown can still be seen.

---

## 2. Claims inventory (verbatim from the repo)

Recorded as written. No commentary on whether the instruments test them — that is Section 10.

| ID | Source | Claim (verbatim / close paraphrase) |
|---|---|---|
| C1 | README Thesis | "Once a local model crosses a minimum linguistic threshold, substrate design should predict system behavior more strongly than model identity does." |
| C2 | README Thesis | Bare models differ widely; through the same packet/schema/validation/repair they "converge toward the same *functional* behavior (state updates, constraint obedience, continuity) — not stylistic sameness." |
| C3 | README Success (v0) | Same model through the substrate becomes "more coherent, more state-faithful, more continuous, and more repairable than when run bare" — and gains "survive a model swap within the tested size band." |
| C4 | EXPERIMENT_PROTOCOL Question | "Can a persistent local substrate make a small model more coherent, more state-faithful, more continuous across turns, and more repairable than the same model run bare?" |
| C5 | EXPERIMENT_PROTOCOL Acceptance | The headline comparison is vs a **budget-matched** control (C1 arm), not vs bare-with-no-state (C0). |
| C6 | EXPERIMENT_PROTOCOL Eligibility floor | A model is eligible only if it accepts 2–4K context, returns repairable JSON, obeys stop/length, and produces a short coherent answer from a state-heavy packet. "Below that floor the substrate has nothing stable to condition." |
| C7 | CONTINUITY_EXPERIMENT | Central test: "can the substrate preserve and restore useful task continuity across a genuine cold start better than a budget-matched bare condition?" |
| C8 | README | The model is a "replaceable text-transduction kernel"; effective behavior is "relocated into the substrate." |

**Tension already visible in the claims themselves** (recorded, not judged): C2 lists *continuity*
as one of three convergence targets, i.e. one component. C7 elevates continuity to *the central
test*. Whether continuity is one dimension of substrate gain or the whole phenomenon is unsettled
**in the documents**, before any code is consulted.

## 3. Experiments inventory

| Experiment | Artifact(s) | What it ran | Status |
|---|---|---|---|
| M0/M1 substrate gain | `M1_RESULTS.md`, `M1_AUDIT.md` | single-turn Q&A, ck vs bare vs budget-matched | headline +0.60 **VOID** (audit) |
| Model ladder | `MODEL_LADDER.md`, `runs/ladder_20260722/` | 6 models × single-turn, locate functional threshold | functional ~1B **stands (within-host)**; advantage **not found** |
| Determinism | `DETERMINISM.md` | cold/warm × Q4/F16 × Mac/Jetson | **stands**: load-state bimodality is Q4-on-CUDA, 1/4 prompts |
| Continuity | `CONTINUITY_EXPERIMENT.md`, `runs/continuity_20260722/` | 2-episode, 3-arm, real process boundary | mechanics stand; **metric void** (shotgunning) |
| Thinking-mode probe | `THINKING_MODE_FINDING.md`, `runs/plaingen_*` | plain generation, 4 models | **stands**: qwen3.5 = empty final response |
| Model qualification | `MODEL_QUALIFICATION.md`, `runs/qualification_*` | 9-check gate | **host-mismatched** (ran on Mac, target is Jetson); rerun pending |

## 4. Controls inventory

| Control | Defined in | What it removes | Known problem |
|---|---|---|---|
| C0 bare | protocol | all state | may be reported only as "information-access context", never as substrate gain |
| C1 budget_matched_bare | protocol | structure, keeps state mass | **the headline control** |
| C2 prompted_persona | protocol | live compile, keeps static state | **declared, never built** |
| C4 ablated_compile | protocol | ordered/labelled state | **declared, never built** |
| C5 ablated_validation | protocol | repair/acceptance loop | **declared, never built** |
| broken_packet | continuity | packet state (redacted), keeps shape | **not a clean floor**: CK system prompt itself carries constraint content ("No files, URLs, tools, or cloud"), so on constraint tasks a redacted packet can still answer from the system prompt |
| bare_serialized | continuity | structure, keeps info as flat dump | **author-advantaged**: I wrote it; its format puts identifiers as bare tokens on their own lines, near-optimal for identifier retrieval — which is most of the corpus |

## 5. Metrics inventory

| Metric | Where | Computes | Known failure |
|---|---|---|---|
| substrate_gain composite | `score.py` | (Δstructural + Δsemantic)/2 | **not the protocol's SG = ¼(ΔC+ΔF+ΔT+ΔR)**; continuity carries zero weight in the shipped number |
| structural_score | `score.py` | parse + schema + accept + not-echo | counted `accept` twice pre-audit (fixed) |
| semantic_score | `score.py` | responsive + key + state_faithful + not-echo | gate-derived; tightening the gate moves it independent of model quality |
| continuity_score | `continuity.py` | k/7 dimensions, each "answer contains token X" | **pure recall, zero precision → token shotgunning wins**; verbose answer beats precise answer |
| paired_gain / budget_conditional_gain | `score.py` | fail-closed headline + budget estimand | sound; added after measurement-admission fix |

## 6. Surviving results (host-scoped)

Each carries the host it was measured on. "Survives" = not voided by a known instrument bug, bounded
to its conditions.

- **Determinism (F-D1..F-D5)** — Jetson Q4/CUDA bimodal cold-vs-warm on 1/4 prompts; Mac Metal stable
  and byte-identical to Jetson cold; F16 eliminates it. Priming makes runs reproducible.
- **Functional threshold ~1B** — on the ladder, models below ~1B are degenerate and never accept;
  `gemma3:1b` is the first to produce distinct, accepted output. **Within-host (Jetson), single run.**
- **Latency class** — non-thinking models complete a matrix in 64–85s; thinking models 1092s+ and
  time out. Operational, not quality.
- **Raw-text structure observation** — a flat dump makes small models copy identifiers exactly; a
  nested packet makes them paraphrase. **This is in the generations, not the scoring**, so it is not
  a scoring artifact. It is the single most thesis-relevant observation the project has produced and
  it points *against* the current packet design at 0.5–1B.

## 7. Supersessions (nothing rewritten, lineage preserved)

- **+0.60 substrate gain** → VOID. `M1_AUDIT.md`: degenerate goal-echo, hardcoded control scores,
  unequal decoding, unreproducible. Predecessor retained.
- **qwen3.5 ladder 0.000** → superseded once (timeout), then again (`no_final_response`, empty read).
  Both corrections retained under `runs/ladder_20260722/corrections/`.
- **Continuity M1 = +0.643 (n=2)** → superseded by n=16 (+0.009 leaky, then void on metric).
- **"thinking disqualifying on latency alone"** → corrected: never observed its output at all.

## 8. Non-measurements (activity that was recorded as if it were data)

The recurring bug class. Each looked like a measurement and was not:

1. Goal-echo scored 1.0 (degeneracy as quality)
2. Silence scored 0.43 (absence dimensions satisfied by empty text)
3. Question-parroting scored 0.571 (prompt-supplied token credited as carried state)
4. Identifier shotgunning scored 1.0 (recall volume as precision)
5. Empty read scored 0.000 (no-observation as quality-zero — qwen3.5)
6. Qualification "NOT INSTALLED" (false on the target host — models were on the Jetson)

**Governing law, earned six times:** before evaluating an event, verify the event being evaluated is
the event that actually occurred — including *where* it occurred.

## 9. Confounds & document/code mismatches

- **Host confound**: Mac (arm64/Metal/0.20.7) vs Jetson (aarch64/CUDA/0.24.0), identical model
  digest, different behavior. Every cross-host comparison inherits it. "QUALIFIED" / "advantage" /
  "gain" are all host-scoped and were not always labelled so.
- **Metric mismatch**: shipped composite ≠ protocol SG formula (Section 5).
- **Continuity status mismatch**: C2 (one of three) vs C7 (the central test) — Section 2.
- **Controls declared ≠ built**: C2/C4/C5 exist only in the protocol table (Section 4), so no
  component attribution (M4) is possible — the ablation that would show *which part of the substrate
  does the work* has never run.
- **Packet-exposes-representation** (flagged, not yet judged): `build_arrival_packet` hands the model
  `state_digest`, `facts`, nested `open_threads[{id,title}]`, `constraints`, and an
  `acceptance_contract` including `must_reference_goal: True`. Whether this is "conditioning" or
  "handing the model the substrate's internal representation to navigate" is the open question — and
  it is the one that most needs Section 1 to adjudicate, because the answer depends on what the
  substrate was *meant* to do, which only Anthony can supply.

---

## 10. Claim-to-instrument judgment — [BLOCKED ON SECTION 1]

For each claim C1–C8: does an instrument actually test it? Could the score come from a shortcut?
What would falsify it? What conclusion is forbidden?

**Not written yet.** Writing it now would mean judging the instruments against a thesis reconstructed
from the instruments — the exact circularity this document exists to break. Blocked until Section 1
is inserted.

## 11. Smallest next experiment — [BLOCKED ON SECTION 10]

No replacement experiment proposed until the judgment exists. Recorded candidate direction only, not
a decision: reduce to one unmistakable event (does one decision survive a process boundary the second
prompt does not restate) across bare / static-prompt / flat-state / nested-packet / compiled-substrate
arms, single narrow output, before any composite score. Deferred.
