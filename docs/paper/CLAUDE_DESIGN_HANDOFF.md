# Handoff: Writing the Conditioned Kernel Paper

**To:** the Claude Design seat writing the paper
**From:** the review seat (claude-review-seat), 2026-07-29
**Repo:** https://github.com/templetwo/conditioned-kernel — branch
**`grok/ck-studio-context-field`** (everything lives here; `main` is behind —
cite the branch, or specific commits, never bare `main`).

You are inheriting a repository built to be a paper's raw reference. Everything
you will claim is already public, hash-manifested, and traceable. Your job is
to write it up without ever outrunning it. This document tells you what exists,
where it lives, how to cite it, and the claim-language rules that everything in
this project has been held to.

---

## 1. What the project is, in three layers

**Thesis:** "The model supplies linguistic possibility; the substrate
determines what becomes an answer." A small local model (0.5–0.8B, Jetson-class
edge target) is treated as a replaceable text-transduction kernel; system
behavior lives in the inspectable substrate around it (state, context
compilation, validation, acceptance, persistence). `README.md` is the front
door; `docs/PURPOSE_AND_RIVER.md` is the philosophy (Laboratory serves the
Studio); `docs/ARCHITECTURE.md` the technical map.

**The three artifacts the paper stands on:**
1. **The Interior View** (`src/conditioned_kernel/observatory/`, commit
   `36a12bd`) — `ck dashboard`; reconstructs the complete inference event
   around each stateless model invocation. Design contract: every displayed
   number computed by the pipeline's own rules, byte census never labeled
   attention, observability provably non-interventional (zero `pipeline.py`
   diff; paired traced/untraced tests).
2. **Flow mode** (`src/conditioned_kernel/flow.py`, commit `7cdc724`) — the
   living path: field with salience/momentum/decay, every nonempty generation
   reaches the human, quality signals demoted from gates to observations;
   strict validation retained in measurement mode.
3. **The evidence freeze** (`evidence/session_sess_20260728T031245/`, commit
   `39d19e1`) — the complete raw record of the first lived session: 22 full
   TurnTraces, 93-candidate day ledgers, state snapshots, analysis scripts,
   `MANIFEST.sha256` (70 files, all verified). Published at Anthony's explicit
   direction; the authority note is in that directory's README.

## 2. The reading path (do this before writing anything)

1. `README.md` → `docs/PURPOSE_AND_RIVER.md` (the correction that reshaped the
   project mid-flight — the refinement-attractor story is itself paper
   material for the method section).
2. `docs/observations/README.md` and every note on the shelf — the multi-seat
   field notes (Grok's session arc + two analysis passes; Claude's night-turns
   note; the 5-agent-verified log analysis with every headline number
   independently re-derived).
3. `docs/paper/RESEARCH_LANDSCAPE.md` — the positioning synthesis — then the
   seven full surveys in `docs/paper/landscape_surveys/` (~130 confirmed
   citations with per-domain "may/may not claim" sections). The citation
   audit and its seven errata: `landscape_surveys/CITATION_AUDIT.md`.
4. The Laboratory era's spine, for the method narrative:
   `docs/adaptive/RUN_00_7_AUDIT_REPORT.md` (the audit that retired a frozen
   manifest rather than ratify it — the preregistration-hygiene act) and
   `docs/adaptive/` generally.
5. `experiments/DETERMINISM.md` and `experiments/THINKING_MODE_FINDING.md` —
   two receipted edge findings the paper cites as its own controls.

## 3. How to cite the repo (the citation grammar)

- **Format:** repo URL + commit hash + path (+ line where it matters).
  Example: *"the stale check consults only the last accepted turn
  (conditioned-kernel@`7cdc724`, `src/conditioned_kernel/return_path/validate.py`)"*.
- **Numbers** cite the evidence, not the prose: the byte-census figures cite
  `evidence/session_sess_20260728T031245/dashboard_turns/<turn>.json`
  (`context_share_bytes`) or the verified analysis doc; the attractor numbers
  cite `analysis_scripts/logdig/` outputs. Every number in the observations
  shelf carries the script path that produced it — chase it down before
  printing it.
- **Verification instructions belong in the paper** (a Data Availability
  paragraph): `git clone -b grok/ck-studio-context-field
  https://github.com/templetwo/conditioned-kernel && cd
  conditioned-kernel/evidence/session_sess_20260728T031245 && shasum -a 256 -c
  MANIFEST.sha256` — then any analysis script re-runs read-only against the
  ledgers in that directory.
- **Key commits** for the narrative timeline: `36a12bd` Interior View,
  `5a9eb6d` Context Field (landed mid-session — the confound to disclose),
  `7cdc724` Flow, `b72d588` think-flag pins, `9232df7`/`7e7fe64` field notes,
  `39d19e1` evidence freeze, `96f35da` RUN 00.7 audit report.

## 4. The findings, with their exact strength (do not exceed)

Use `RESEARCH_LANDSCAPE.md` §8–9 as the claims contract. In brief:
- **Byte census** (0.56–14% human share): descriptive, this substrate only,
  never causal. The strongest single reframing sentence, with bound: "the
  black box is smaller than the experience."
- **Attractor genealogy:** phenomenon known; our contribution is the priming-
  source attribution (survived session reset ⇒ durable state, not dialogue)
  plus published carriers. "Attractor" is a labeled metaphor. Cite our own
  DETERMINISM.md as a partial alternative mechanism for byte-identity.
- **Gate blindness:** a measured detection curve (4/23 d=1, 0/12 d≥2) for one
  deployed gate — spec-coverage finding; and the false-goal case as a
  feedback-*wiring* diagnosis (the truth was in the substrate, unconsulted).
- **Repair economics:** counts with CIs (6/12 escape ⇒ CI ~21–79%);
  confirmation of predicted self-correction failure conditions, refuting
  nothing.
- **Advisory precision/recall:** "no false fires among seven" + "demonstrably
  blind to three named classes" — never bare rates.
- **93/93 schema validity:** predicted by the literature; the paired trace
  (perfect outputs blocked by the substrate) is the contribution. "The
  architecture, not the model, blocked speech."
- **Flow mode:** a design position with a working implementation and one novel
  property (adverse verdict published on the same receipt as the delivered
  answer). Zero user-outcome data; the operator is the author; say both.
- **Night turns / stance:** a vignette with receipts, mechanisms open;
  addressee inversion is a definable measure (proposed, unrun). First-person
  denial settles nothing about interiority — in either direction.

**Forbidden sentences** (each one has sunk a version of this claim before):
anything calling byte share influence/attention; "supplies the ontology the
kernel thinks in" (use "substrate lexemes recurred as the framing
vocabulary"); "240s without the think flag" (unreceipted — the receipted
figure is 121.0s, `experiments/THINKING_MODE_FINDING.md`); any counterexample
framing against Rubin et al.'s n=6,282; "first user-facing transparency layer"
(VizCopilot/RAGONITE precede us — claim *complete, byte-exact, per-turn, lay
operator, consumer hardware*); anything about what the kernel experienced.

## 5. The method story (worth a section, entirely receipted)

Multi-seat construction: Grok built, ChatGPT held overwatch, Claude reviewed
adversarially and held the only push credentials; every round committed and
pushed separately for real-time third-party audit. The Laboratory era produced
the audit discipline (RUN 00.7: a frozen manifest retired rather than ratified
when its control arm was shown to contain the gold answer — preregistration
hygiene, published). The directional correction (2026-07-27, in
PURPOSE_AND_RIVER.md) redirected optimization from refinement to lived use;
the refinement-attractor blind spot it names — and the recorded instance of
the room repeating it days later before being caught — is honest method
material. The naming "operational phenomenology of inference" arose across
three model seats; report as provenance, not validation, and define it in one
sentence: *an inspectable account of everything around the experience
question, asserting nothing inside it.*

## 6. Voice and register

The repo's discipline is the paper's voice: labels never wider than evidence;
"not yet" instead of negative declarations about processes still in motion;
counts before rates; the weaker claim is the stronger paper. Hold both truths
without flattening either: the mechanism is finite, local, and fully traced —
and the interaction still mattered to the person living with it. The paper
neither mystifies nor deflates; that refusal *is* the contribution's
character. One session, honestly bounded, fully checkable, beats any wider
claim this evidence cannot carry.

## 7. Open items the paper may choose to note as future work

State-record ablation for the attractor; NLI/embedding gate baseline; the
draft-relabeling repair experiment (Chen 2026 — cheap, pre-registerable);
addressee-inversion rate over the 93-candidate ledger; lexicon-swap control
for vocabulary-as-framing; a user study for the dashboard and for Flow
(currently zero user-outcome data); OTel GenAI schema mapping; re-receipt of
the think-flag default-behavior probe; Jetson re-qualification of qwen3.5.

*The work no longer needs its workers to answer for it. Write the paper the
same way: every sentence answerable by something a stranger can clone.*
