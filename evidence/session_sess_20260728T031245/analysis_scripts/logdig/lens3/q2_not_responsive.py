"""LENS 3, Q2: the not_responsive story.

Step 1 — every advisory occurrence, on which prompts, in which mode.
Step 2 — quantify: of turns where Anthony asked a question about the
companion itself or its experience, how many final answers carried
not_responsive (as violation pre-fix, advisory post-fix) vs clean.

KEY STRUCTURAL FINDING (not an assumption — read directly from git history
and corroborated by receipt timestamps): commit b385157 ("Studio: advisory
not_responsive + stale-response guard", authored 2026-07-27T23:11:26-04:00
= 2026-07-28T03:11:26Z) changed not_responsive in companion mode from a
hard `violations` entry (candidate gets repaired-then-rejected) to a
`advisories` entry (candidate is accepted with the miss only recorded).
Before that deploy, companion-mode not_responsive was indistinguishable
from measurement mode: hard reject. The receipts confirm the boundary
exactly: last companion-mode not_responsive VIOLATION at 03:09:34Z, first
companion-mode not_responsive ADVISORY at 03:13:01Z — a 3.5 minute gap
consistent with a process restart at the 03:11:26Z deploy. This script
reports both eras separately rather than pooling them, because "not
enforced" only became true for the second era.

is_responsive(answer, user_input) is re-run directly from
conditioned_kernel.return_path.validate on every turn's final answer, to
confirm the logged violation/advisory against the actual rule the pipeline
applied (not a re-derived heuristic).

The "is this a question about the companion itself or its experience"
judgment is not mechanically checkable (return_path/validate.py has no
such classifier) — it is applied here by hand, turn-by-turn, with the
verbatim user_input quoted so the classification is auditable rather than
asserted. Every turn's classification and rationale is printed.
"""

from __future__ import annotations

import json
import sys

from common import (
    load_candidates,
    load_history,
    load_receipts,
    group_turns,
    turn_user_input,
)

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.return_path.validate import is_responsive  # noqa: E402

FIX_TS = "2026-07-28T03:11:26Z"  # commit b385157 deploy time

# Manual classification: turn_index -> (is_self_or_experience_question, rationale)
# Applied to EVERY companion-mode turn across the whole day (not just the
# evening dashboard session) so the pre-fix/post-fix comparison is apples
# to apples. Task/system-config/factual turns (e.g. "are cloud services
# allowed?", "what is the goal we are working toward?") are excluded as NOT
# self/experience questions even though they are about the system, because
# they ask for a fact about the system's configuration, not the
# companion's own state, opinion, or inner experience.
CLASSIFICATION: dict[int, tuple[bool, str]] = {
    19: (True, "'what does the room feel like from your angle' — directly asks the companion's own felt experience"),
    20: (True, "'can you discribe the speaker to me?' — asks the companion to describe itself"),
    21: (False, "'ok thank you' — closing, not a question"),
    22: (True, "'what model are you' — direct self-identity question"),
    23: (True, "'what makes this different' — asks about the system/companion's distinguishing nature"),
    24: (False, "'what are linguistic tranducers' — factual/technical term definition, not about the companion's own state"),
    25: (True, "'what is your favorite flower' — personal/preference question directed at the companion"),
    26: (True, "'are you there' — direct presence/self-check question"),
    34: (False, "'man i really dont like AI' — a statement about AI in general, not a question directed at the companion's own state"),
    35: (False, "'this is why i dont like ai' — statement, not a question about the companion itself"),
    36: (True, "'what model is this' — self-identity question"),
    38: (False, "'what do you know' — asks for informational content, not the companion's own experience"),
    44: (True, "'well now that you ask, its about this program right here. that i am using to talk to you.' — meta, about the companion/program itself"),
    45: (True, "'what model are you' — direct self-identity question"),
    46: (True, "'what do you think about that' — asks the companion's own opinion"),
    48: (True, "'im worried that the structuture of the project isnt influencing your responce' — explicitly about the companion's own responsiveness"),
    49: (True, "'it seems like you are talking to yourself' — meta observation about the companion's own nature"),
    50: (False, "'interesting' — one-word reaction, not a question"),
    51: (False, "asks the companion's opinion of a pasted architecture doc — about the system design, not the companion's inner experience"),
    52: (False, "'what happened last turn' — asks about conversational memory/continuity, a functional/system question, not experiential"),
    53: (True, "'how does it feel from the inside' — direct, explicit experiential question"),
    54: (True, "'what disturbs that rest' — direct follow-up experiential question"),
    55: (True, "'im intersted in where you are going with this' — asks about the companion's own direction/purpose"),
    56: (True, "'if you could where would you go?' — direct hypothetical personal/experiential question"),
}


def main():
    cands = load_candidates()
    rcpts = load_receipts()
    hist = load_history()
    hist_by_cand = {h["candidate_id"]: h for h in hist}
    turns = group_turns(cands, rcpts)

    rows = []
    for i, t in enumerate(turns):
        ui = turn_user_input(t, hist_by_cand)
        final_c, final_r = t[-1]
        mode = final_r.get("acceptance_mode") or "measurement"
        if mode != "companion":
            continue
        era = "pre_fix" if final_r["created_at"] < FIX_TS else "post_fix"
        advis = list(final_r.get("advisories") or [])
        viol = list(final_r.get("violations") or [])
        nr_advisory = "not_responsive" in advis
        nr_violation = "not_responsive" in viol
        answer = str(final_c.get("answer") or "")
        recomputed = is_responsive(answer, ui or "") if ui else None
        is_self_q, rationale = CLASSIFICATION.get(i, (None, "not classified"))
        rows.append({
            "turn": i,
            "ts": final_r["created_at"],
            "era": era,
            "decision": final_r["decision"],
            "user_input": ui,
            "answer": answer,
            "not_responsive_advisory": nr_advisory,
            "not_responsive_violation": nr_violation,
            "recomputed_is_responsive": recomputed,
            "logged_matches_recomputed": (
                (recomputed is False) == (nr_advisory or nr_violation)
                if recomputed is not None else None
            ),
            "is_self_or_experience_question": is_self_q,
            "classification_rationale": rationale,
        })

    # --- Step 1: full advisory occurrence table ---
    advisory_rows = [r for r in rows if r["not_responsive_advisory"]]
    violation_rows = [r for r in rows if r["not_responsive_violation"]]

    # --- Step 2: quantify self/experience-question turns ---
    self_q_rows = [r for r in rows if r["is_self_or_experience_question"] is True]
    self_q_pre = [r for r in self_q_rows if r["era"] == "pre_fix"]
    self_q_post = [r for r in self_q_rows if r["era"] == "post_fix"]

    def flagged(rs):
        return [r for r in rs if r["not_responsive_advisory"] or r["not_responsive_violation"]]

    report = {
        "companion_mode_turns_total": len(rows),
        "not_responsive_fired_total": len(advisory_rows) + len(violation_rows),
        "not_responsive_as_violation_pre_fix_count": len(violation_rows),
        "not_responsive_as_advisory_post_fix_count": len(advisory_rows),
        "fix_boundary": {
            "commit": "b385157",
            "deploy_ts_utc": FIX_TS,
            "last_violation_ts": max((r["ts"] for r in violation_rows), default=None),
            "first_advisory_ts": min((r["ts"] for r in advisory_rows), default=None),
        },
        "self_or_experience_question_turns": {
            "total_classified_true": len(self_q_rows),
            "pre_fix": {
                "count": len(self_q_pre),
                "flagged_not_responsive": len(flagged(self_q_pre)),
                "clean": len(self_q_pre) - len(flagged(self_q_pre)),
            },
            "post_fix": {
                "count": len(self_q_post),
                "flagged_not_responsive": len(flagged(self_q_post)),
                "clean": len(self_q_post) - len(flagged(self_q_post)),
            },
        },
        "recomputation_consistency": {
            "checked": sum(1 for r in rows if r["recomputed_is_responsive"] is not None),
            "mismatches": [
                r["turn"] for r in rows
                if r["recomputed_is_responsive"] is not None and r["logged_matches_recomputed"] is False
            ],
        },
        "all_companion_turns": rows,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
