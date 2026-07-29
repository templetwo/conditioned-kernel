"""LENS 3, Q5: the "better response rejected" question.

For every 2-pass turn (35 total — every 1-pass turn either accepted cleanly
or was rejected with no alternative pass to compare against, so is out of
scope for this question by construction): pass0 is what the model produced
first; pass1 is what replaced it (repair). If the turn's FINAL decision is
`reject`, nothing reached the user at all — pass0 (and pass1) were both
discarded. If the turn's final decision is `accept`, pass0 was discarded
and pass1's answer is what the user actually saw.

`is_responsive` is re-run directly from
conditioned_kernel.return_path.validate on both pass0 and pass1's answer
against the turn's real user_input (recovered via history.jsonl + turn
grouping — see common.turn_user_input), as one objective, non-invented
signal of relative responsiveness alongside the full text for a human read.
"""

from __future__ import annotations

import json
import sys

from common import (
    base_check_name,
    load_candidates,
    load_history,
    load_receipts,
    group_turns,
    turn_user_input,
)

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.return_path.validate import is_responsive  # noqa: E402


def main():
    cands = load_candidates()
    rcpts = load_receipts()
    hist = load_history()
    hist_by_cand = {h["candidate_id"]: h for h in hist}
    turns = group_turns(cands, rcpts)
    two_pass = [t for t in turns if len(t) == 2]

    rows = []
    for i, t in enumerate(turns):
        if len(t) != 2:
            continue
        ui = turn_user_input(t, hist_by_cand) or ""
        (c0, r0), (c1, r1) = t
        a0 = str(c0.get("answer") or "")
        a1 = str(c1.get("answer") or "")
        v0 = [base_check_name(v) for v in (r0.get("violations") or [])]
        v1 = [base_check_name(v) for v in (r1.get("violations") or [])]
        final_decision = r1["decision"]
        rows.append({
            "turn": i,
            "ts": r1["created_at"],
            "user_input": ui,
            "final_decision": final_decision,  # "accept" (pass1 shown) or "reject" (nothing shown)
            "pass0_answer": a0,
            "pass0_killed_by": v0,
            "pass0_is_responsive": is_responsive(a0, ui) if (a0 and ui) else None,
            "pass1_answer": a1,
            "pass1_killed_by": v1,  # empty if pass1 was accepted
            "pass1_is_responsive": is_responsive(a1, ui) if (a1 and ui) else None,
            "authoritative_fallback_pass0": bool(r0.get("authoritative_fallback")),
            "authoritative_fallback_pass1": bool(r1.get("authoritative_fallback")),
        })

    # Candidate list: pass0 is_responsive True while pass1 is_responsive False,
    # OR final_decision is reject while pass0 was is_responsive True (a
    # plausible answer existed and was discarded entirely).
    candidates_for_review = [
        r for r in rows
        if (r["pass0_is_responsive"] and not r["pass1_is_responsive"])
        or (r["final_decision"] == "reject" and r["pass0_is_responsive"])
    ]

    print(json.dumps({
        "n_two_pass_turns": len(rows),
        "n_flagged_pass0_more_responsive_by_lexical_check": len(candidates_for_review),
        "flagged": candidates_for_review,
        "all_two_pass_turns": rows,
    }, indent=2))


if __name__ == "__main__":
    main()
