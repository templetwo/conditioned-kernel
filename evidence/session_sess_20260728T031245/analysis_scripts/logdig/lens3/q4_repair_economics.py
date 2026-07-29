"""LENS 3, Q4: repair economics.

Part A — exact, ground truth, no packet reconstruction: every 2-pass turn's
pass-0 violation set vs pass-1 violation set, read directly from
receipts.jsonl (base check name, ':<detail>' suffix stripped so
'unknown_thread_touch:x' and 'unknown_thread_touch:y' count as the same
check). Classified as:
  CLEAN_FIX          pass1 violations empty (repair actually fixed it)
  SAME_PERSISTS      >=1 of pass0's violation type(s) still present in pass1
  SWAPPED            pass1 has violations, but none overlap pass0's types
    (further split: pass1 violations is a strict superset that ADDS a new
    type on top of a persisting one falls under SAME_PERSISTS, since the
    original problem was not resolved.)

Part B — the attractor question: does repair converge INTO a recurring
generic-boilerplate cluster? Uses conditioned_kernel.observatory.compute's
own cluster_candidates + jaccard_similarity (>=0.6 threshold, the module's
documented default) over every pass's answer text across the full day (93
passes), then checks, for each 2-pass turn, whether pass0's answer was
outside the largest cluster and pass1's answer moved INTO it.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from common import (
    base_check_name,
    load_candidates,
    load_receipts,
    load_history,
    group_turns,
    turn_user_input,
)

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.observatory.compute import cluster_candidates, jaccard_similarity  # noqa: E402


def part_a():
    cands = load_candidates()
    rcpts = load_receipts()
    turns = group_turns(cands, rcpts)
    two_pass = [t for t in turns if len(t) == 2]

    rows = []
    outcome_counts = Counter()
    for t in two_pass:
        (c0, r0), (c1, r1) = t
        v0 = {base_check_name(v) for v in (r0.get("violations") or [])}
        v1 = {base_check_name(v) for v in (r1.get("violations") or [])}
        if not v1:
            outcome = "CLEAN_FIX"
        elif v1 & v0:
            outcome = "SAME_PERSISTS"
        else:
            outcome = "SWAPPED"
        outcome_counts[outcome] += 1
        rows.append({
            "ts": r1["created_at"],
            "decision_final": r1["decision"],
            "pass0_violations": sorted(v0),
            "pass1_violations": sorted(v1),
            "outcome": outcome,
            "pass0_answer": str(c0.get("answer") or "")[:160],
            "pass1_answer": str(c1.get("answer") or "")[:160],
        })
    return outcome_counts, rows


def _movement_for_cluster(two_pass, member_ids):
    into_attractor = out_of_attractor = stayed_in = stayed_out = 0
    detail = []
    for t in two_pass:
        (c0, r0), (c1, r1) = t
        in0 = c0["candidate_id"] in member_ids
        in1 = c1["candidate_id"] in member_ids
        if not in0 and in1:
            into_attractor += 1
            kind = "MOVED_INTO_ATTRACTOR"
        elif in0 and not in1:
            out_of_attractor += 1
            kind = "MOVED_OUT_OF_ATTRACTOR"
        elif in0 and in1:
            stayed_in += 1
            kind = "STAYED_IN_ATTRACTOR"
        else:
            stayed_out += 1
            kind = "STAYED_OUT"
            continue  # not interesting for the report; skip from detail
        detail.append({
            "ts": r1["created_at"],
            "kind": kind,
            "pass0_answer": str(c0.get("answer") or "")[:120],
            "pass1_answer": str(c1.get("answer") or "")[:120],
        })
    return {
        "moved_into_attractor_on_repair": into_attractor,
        "moved_out_of_attractor_on_repair": out_of_attractor,
        "stayed_in_attractor_both_passes": stayed_in,
        "stayed_out_both_passes": stayed_out,
    }, detail


def part_b():
    cands = load_candidates()
    rcpts = load_receipts()
    hist = load_history()
    hist_by_cand = {h["candidate_id"]: h for h in hist}
    turns = group_turns(cands, rcpts)
    two_pass = [t for t in turns if len(t) == 2]

    cand_meta = {}
    for ti, t in enumerate(turns):
        ui = turn_user_input(t, hist_by_cand)
        for c, r in t:
            cand_meta[c["candidate_id"]] = {
                "turn": ti, "pass_index": c["pass_index"], "ts": r["created_at"],
                "user_input": ui, "decision": r["decision"],
            }

    all_candidates_for_cluster = [
        {"text": str(c.get("answer") or ""), "id": c["candidate_id"], "idx": i}
        for i, c in enumerate(cands)
    ]
    cluster1 = cluster_candidates(all_candidates_for_cluster, cluster_threshold=0.6)
    member_ids1 = {m["id"] for m in cluster1["members"]}
    movement1, detail1 = _movement_for_cluster(two_pass, member_ids1)

    remaining = [c for c in all_candidates_for_cluster if c["id"] not in member_ids1]
    cluster2 = cluster_candidates(remaining, cluster_threshold=0.6)
    member_ids2 = {m["id"] for m in cluster2["members"]}
    movement2, detail2 = _movement_for_cluster(two_pass, member_ids2)

    def cluster_members_with_meta(cluster):
        return [
            {**cand_meta.get(m["id"], {}), "answer_snippet": m["text"][:120]}
            for m in sorted(cluster["members"], key=lambda x: cand_meta.get(x["id"], {}).get("ts", ""))
        ]

    return {
        "cluster_1_largest": {
            "seed_answer": (cluster1["seed"] or {}).get("text", "")[:200] if cluster1["seed"] else None,
            "size": len(cluster1["members"]),
            "threshold": cluster1["threshold"],
            "members": cluster_members_with_meta(cluster1),
            "two_pass_turn_movement": movement1,
            "movement_detail": detail1,
        },
        "cluster_2_second_largest_after_removing_cluster_1": {
            "seed_answer": (cluster2["seed"] or {}).get("text", "")[:200] if cluster2["seed"] else None,
            "size": len(cluster2["members"]),
            "threshold": cluster2["threshold"],
            "members": cluster_members_with_meta(cluster2),
            "two_pass_turn_movement": movement2,
            "movement_detail": detail2,
        },
        "total_passes_considered": cluster1["total"],
    }


def main():
    outcome_counts, rows = part_a()
    attractor = part_b()
    report = {
        "part_a_violation_set_diff": {
            "n_two_pass_turns": len(rows),
            "outcome_counts": dict(outcome_counts),
            "rows": rows,
        },
        "part_b_attractor_convergence": attractor,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
