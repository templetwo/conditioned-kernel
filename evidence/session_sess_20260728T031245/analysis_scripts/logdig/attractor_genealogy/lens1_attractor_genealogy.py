#!/usr/bin/env python3
"""LENS 1 - Attractor genealogy over all 93 candidates in
/Users/vaquez/conditioned-kernel/logs/.

READ-ONLY. Uses the pipeline's own similarity/validation rules:
  - conditioned_kernel.observatory.compute.jaccard_similarity  (symmetric
    Jaccard, >=4-char lowercase tokens -- the same function the Interior
    View dashboard uses for its own attractor clustering, spec S10/S6).
  - conditioned_kernel.return_path.validate.is_template_echo_text /
    prior_accepted_answer / user_prompt_changed / is_substantial_repeat
  - conditioned_kernel.state.fit_recent_turns / recent_turns_byte_size /
    RECENT_TURNS_MAX_BYTES / _clip_text (the exact byte-capped ring logic
    that decides what stays in state.recent_turns()).

Every number below is produced by executing this script over the real log
files; nothing is hand-computed or eyeballed.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path("/Users/vaquez/conditioned-kernel")
sys.path.insert(0, str(REPO / "src"))

from conditioned_kernel.observatory.compute import jaccard_similarity, stored_answer_carried  # noqa: E402
from conditioned_kernel.return_path.validate import (  # noqa: E402
    is_template_echo_text,
    is_substantial_repeat,
)
from conditioned_kernel.state import (  # noqa: E402
    RECENT_TURNS_MAX_BYTES,
    RECENT_TURN_ANSWER_MAX_CHARS,
    RECENT_TURN_USER_MAX_CHARS,
    _clip_text,
    fit_recent_turns,
    recent_turns_byte_size,
)

LOGS = REPO / "logs"
CLUSTER_THRESHOLD = 0.6  # spec S10: "cluster at >=0.6 Jaccard"

OUT_DIR = Path("/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/attractor_genealogy")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    cands = load_jsonl(LOGS / "candidates.jsonl")
    rcpts = load_jsonl(LOGS / "receipts.jsonl")
    hist = load_jsonl(LOGS / "history.jsonl")

    assert len(cands) == 93 and len(rcpts) == 93 and len(hist) == 58

    # candidates.jsonl / receipts.jsonl are 1:1, line-aligned (verified).
    for c, r in zip(cands, rcpts):
        assert c["candidate_id"] == r["candidate_id"]

    # ---- Group the 93 (candidate, receipt) pairs into 58 turns. --------
    # A turn starts at pass_index==0 and optionally continues with the
    # repair's pass_index==1 record immediately after it (file order is
    # emission order). Verified against 93 = 58 (pass0) + 35 (pass1 repairs).
    turns: list[list[tuple[dict, dict]]] = []
    for c, r in zip(cands, rcpts):
        if c["pass_index"] == 0:
            turns.append([(c, r)])
        else:
            assert turns, "pass_index==1 with no preceding pass_index==0"
            turns[-1].append((c, r))
    assert len(turns) == 58, len(turns)

    # ---- Attach each turn's authoritative user_input / final decision / ts
    # from history.jsonl, matched by the *final* pass's candidate_id (history
    # logs exactly one record per turn: the terminal pass). -------------
    hist_by_cid = {h["candidate_id"]: h for h in hist}
    turn_meta = []
    for t in turns:
        final_c, final_r = t[-1]
        h = hist_by_cid.get(final_c["candidate_id"])
        assert h is not None, f"no history match for {final_c['candidate_id']}"
        turn_meta.append(h)
    assert len(turn_meta) == len(hist) == 58
    # Confirm strict chronological order (history.jsonl append order == turn order).
    for i in range(1, len(turn_meta)):
        assert turn_meta[i]["ts"] >= turn_meta[i - 1]["ts"]

    # ---- Flatten into one record per (candidate,receipt) pass, carrying
    # the turn's user_input/final decision down onto every pass (pass0 and
    # pass1 of a repaired turn share one user_input -- verified against the
    # dashboard traces, both passes' packet.user_input are identical). ----
    records = []
    for turn_no, (t, h) in enumerate(zip(turns, turn_meta), start=1):
        for c, r in t:
            records.append(
                {
                    "turn_no": turn_no,
                    "pass_index": c["pass_index"],
                    "candidate_id": c["candidate_id"],
                    "packet_id": c["packet_id"],
                    "ts": c["parsed_at"],
                    "user_input": h["user_input"],
                    "answer": c.get("answer") or "",
                    "evidence_used": c.get("evidence_used") or [],
                    "receipt_decision": r["decision"],
                    "violations": r.get("violations") or [],
                    "advisories": r.get("advisories") or [],
                    "acceptance_mode": r.get("acceptance_mode"),
                    "authoritative_fallback": bool(c.get("authoritative_fallback")),
                    "turn_final_decision": h["decision"],
                    "turn_ts": h["ts"],
                }
            )
    assert len(records) == 93

    # =====================================================================
    # PART 1 -- cluster ALL 93 candidate answers at >=0.6 symmetric Jaccard
    # (compute.jaccard_similarity), connected components over the pairwise
    # graph (this generalizes compute.cluster_candidates, which only
    # returns the single largest cluster, to the full genealogy).
    # =====================================================================
    n = len(records)
    sim = [[0.0] * n for _ in range(n)]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edges = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = jaccard_similarity(records[i]["answer"], records[j]["answer"])
            sim[i][j] = sim[j][i] = s
            if s >= CLUSTER_THRESHOLD:
                union(i, j)
                edges += 1

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    # Sort members of each cluster by ts (emission order).
    cluster_list = []
    for root, idxs in clusters.items():
        idxs_sorted = sorted(idxs, key=lambda i: records[i]["ts"])
        cluster_list.append(idxs_sorted)
    cluster_list.sort(key=lambda idxs: (-len(idxs), records[idxs[0]]["ts"]))

    multi = [c for c in cluster_list if len(c) >= 2]
    singles = [c for c in cluster_list if len(c) == 1]

    print("=" * 100)
    print(f"PART 1: clustering all {n} candidate answers at >=0.6 symmetric Jaccard")
    print(f"  total clusters: {len(cluster_list)}  (multi-member: {len(multi)}, singletons: {len(singles)})")
    print(f"  total candidate pairs with jaccard>=0.6: {edges}")
    print("=" * 100)

    genealogy = []
    for ci, idxs in enumerate(multi, start=1):
        first = records[idxs[0]]
        entry = {
            "cluster_id": ci,
            "size": len(idxs),
            "first_emission": {
                "turn_no": first["turn_no"],
                "ts": first["ts"],
                "pass_index": first["pass_index"],
                "prompt": first["user_input"],
                "answer": first["answer"],
                "receipt_decision": first["receipt_decision"],
                "turn_final_decision": first["turn_final_decision"],
                "violations": first["violations"],
            },
            "re_emissions": [],
        }
        print(f"\n--- CLUSTER {ci}  (size={len(idxs)}) ---")
        print(f"  FIRST  turn#{first['turn_no']:>2} {first['ts']}  prompt={first['user_input']!r}")
        print(f"         answer={first['answer']!r}")
        print(f"         pass={first['pass_index']} receipt_decision={first['receipt_decision']} turn_final={first['turn_final_decision']} violations={first['violations']}")
        for i in idxs[1:]:
            rec = records[i]
            print(f"  RE-EMIT turn#{rec['turn_no']:>2} {rec['ts']}  prompt={rec['user_input']!r}")
            print(f"         answer={rec['answer']!r}")
            print(f"         pass={rec['pass_index']} receipt_decision={rec['receipt_decision']} turn_final={rec['turn_final_decision']} violations={rec['violations']}")
            entry["re_emissions"].append(
                {
                    "turn_no": rec["turn_no"],
                    "ts": rec["ts"],
                    "pass_index": rec["pass_index"],
                    "prompt": rec["user_input"],
                    "answer": rec["answer"],
                    "receipt_decision": rec["receipt_decision"],
                    "turn_final_decision": rec["turn_final_decision"],
                    "violations": rec["violations"],
                }
            )
        genealogy.append(entry)

    # =====================================================================
    # PART 2 -- for every cluster re-emission, was it caught by
    # stale_response_repeat, and how many turns after its most recent same-
    # cluster occurrence did it land? (distance==1 vs distance>=2)
    #
    # Turn-level collapse: within one turn, pass0 and pass1 (a repair) are
    # not "turns apart" -- they're the same user turn re-emitting the same
    # cluster one repair-loop iteration later. That intra-turn phenomenon is
    # reported separately (repair_loop_same_cluster_echoes) from the
    # cross-turn attractor re-emission this lens is about.
    # =====================================================================
    print("\n" + "=" * 100)
    print("PART 2: stale_response_repeat catch rate vs turn-distance to prior same-cluster occurrence")
    print("=" * 100)

    repair_loop_echoes = 0
    for idxs in multi:
        by_turn = defaultdict(list)
        for i in idxs:
            by_turn[records[i]["turn_no"]].append(i)
        for tno, is_ in by_turn.items():
            if len(is_) > 1:
                repair_loop_echoes += len(is_) - 1

    dist_buckets = {"==1": {"caught": 0, "not_caught": 0}, ">=2": {"caught": 0, "not_caught": 0}}
    reemission_rows = []
    for idxs in multi:
        # collapse to one entry per turn (first pass by ts), but remember
        # whether *any* pass in that turn was caught.
        by_turn: dict[int, list[int]] = {}
        for i in idxs:
            by_turn.setdefault(records[i]["turn_no"], []).append(i)
        turn_occurrences = sorted(by_turn.keys())
        for k in range(1, len(turn_occurrences)):
            tno = turn_occurrences[k]
            prev_tno = turn_occurrences[k - 1]
            distance = tno - prev_tno
            pass_idxs = by_turn[tno]
            caught_any = any("stale_response_repeat" in records[i]["violations"] for i in pass_idxs)
            rep = records[pass_idxs[0]]
            bucket = "==1" if distance == 1 else ">=2"
            dist_buckets[bucket]["caught" if caught_any else "not_caught"] += 1
            reemission_rows.append(
                {
                    "cluster_size": len(idxs),
                    "re_emission_turn": tno,
                    "prior_occurrence_turn": prev_tno,
                    "turn_distance": distance,
                    "caught_by_stale_check_any_pass": caught_any,
                    "prompt": rep["user_input"],
                    "answer": rep["answer"][:80],
                    "turn_final_decision": rep["turn_final_decision"],
                }
            )
            print(
                f"  turn#{tno:>2} (prior same-cluster TURN: turn#{prev_tno:>2}, "
                f"distance={distance:>2})  caught_any_pass={caught_any!s:5}  turn_final={rep['turn_final_decision']:6}  "
                f"prompt={rep['user_input']!r}"
            )

    total_reemissions = sum(dist_buckets[b]["caught"] + dist_buckets[b]["not_caught"] for b in dist_buckets)
    print(f"\n  total cross-turn cluster re-emissions (turn-collapsed): {total_reemissions}")
    print(f"  (separately: {repair_loop_echoes} intra-turn repair-loop echoes -- pass1 re-emitting the same")
    print(f"   cluster as pass0 within one turn -- excluded from the distance analysis above)")
    for bucket, counts in dist_buckets.items():
        total_b = counts["caught"] + counts["not_caught"]
        print(f"  distance {bucket}: {total_b} re-emissions -> caught={counts['caught']}  not_caught={counts['not_caught']}")

    # ---- Mechanism check: replicate compile.py's prior_accepted_answer_control
    # (= state.recent_turns()[-1]["answer"], i.e. the single most-recently
    # ACCEPTED-AND-NOT-POISONED turn's *clipped* answer -- exactly one turn
    # of memory, never a window) to show *why* distance>=2 cases are
    # structurally invisible to the check, using accept.py's own poison rule.
    print("\n  --- mechanism trace: prior_accepted_answer_control per turn (one-turn-deep, by construction) ---")
    last_accepted_clipped = None  # str | None
    last_accepted_turn_no = None
    control_trace = []
    for turn_no, (t, h) in enumerate(zip(turns, turn_meta), start=1):
        final_c, final_r = t[-1]
        prior_for_this_turn = last_accepted_clipped
        prior_turn_for_this_turn = last_accepted_turn_no
        control_trace.append(
            {
                "turn_no": turn_no,
                "prior_accepted_answer_control": prior_for_this_turn,
                "prior_accepted_answer_control_from_turn": prior_turn_for_this_turn,
            }
        )
        # Did this turn get appended to state.recent_turns() (accept.py's rule)?
        answer_text = str(final_c.get("answer") or "").strip()
        user_text = str(h.get("user_input") or "").strip()
        violations = list(final_r.get("violations") or [])
        poison = (
            "template_echo" in violations
            or "template_echo_evidence" in violations
            or "stale_response_repeat" in violations
            or is_template_echo_text(answer_text)
        )
        if final_r["decision"] == "accept" and answer_text and user_text and not poison:
            last_accepted_clipped = _clip_text(answer_text, RECENT_TURN_ANSWER_MAX_CHARS)
            last_accepted_turn_no = turn_no

    # For every cross-turn re-emission, check: was the *actual* one-turn-deep
    # control field (at the moment this turn ran) a member of the SAME
    # cluster as this candidate's own answer? This is the structural
    # precondition for stale_response_repeat to have any chance of firing.
    # (turn-collapsed: one row per re-emitting turn, using that turn's first
    # pass -- both passes of a repaired turn share the same control value.)
    print("  turn#  had_prior_control  prior_from_turn#  prior_same_cluster_as_candidate  caught_any_pass")
    structural_rows = []
    for idxs in multi:
        by_turn: dict[int, list[int]] = {}
        for i in idxs:
            by_turn.setdefault(records[i]["turn_no"], []).append(i)
        turn_occurrences = sorted(by_turn.keys())
        for tno in turn_occurrences[1:]:
            pass_idxs = by_turn[tno]
            cur = records[pass_idxs[0]]
            caught_any = any("stale_response_repeat" in records[i]["violations"] for i in pass_idxs)
            ctrl = control_trace[tno - 1]
            prior_text = ctrl["prior_accepted_answer_control"]
            same_cluster = False
            sim_val = None
            if prior_text is not None:
                sim_val = jaccard_similarity(prior_text, cur["answer"])
                same_cluster = sim_val >= CLUSTER_THRESHOLD
            structural_rows.append(
                {
                    "turn_no": tno,
                    "had_prior_control": prior_text is not None,
                    "prior_control_from_turn": ctrl["prior_accepted_answer_control_from_turn"],
                    "prior_control_same_cluster": same_cluster,
                    "control_vs_candidate_jaccard": sim_val,
                    "caught_any_pass": caught_any,
                }
            )
            print(
                f"  {tno:>4}  {str(prior_text is not None):5}              "
                f"{str(ctrl['prior_accepted_answer_control_from_turn']):4}              "
                f"{str(same_cluster):5} (jaccard={sim_val})               {caught_any}"
            )

    n_rows = len(structural_rows)
    n_same_cluster_control = sum(1 for r in structural_rows if r["prior_control_same_cluster"])
    n_same_cluster_caught = sum(1 for r in structural_rows if r["prior_control_same_cluster"] and r["caught_any_pass"])
    n_diff_cluster_control = n_rows - n_same_cluster_control
    print(
        f"\n  of {n_rows} cross-turn re-emissions: prior_accepted_answer_control was the SAME cluster "
        f"in {n_same_cluster_control} case(s) (of which {n_same_cluster_caught} were actually caught); "
        f"in the other {n_diff_cluster_control} case(s) the control value was a different cluster (or no "
        f"prior accepted answer yet) -- those are structurally invisible to stale_response_repeat no matter "
        f"how old or how textually close the resurfacing candidate is, because prior_accepted_answer() only "
        f"ever returns recent_turns[-1] / prior_accepted_answer_control, never a window."
    )

    # =====================================================================
    # PART 3 -- morning boilerplate cluster: last appearance + what displaced
    # it in recent_turns, verified against the dashboard traces' packet
    # snapshots AND a faithful fit_recent_turns/RECENT_TURNS_MAX_BYTES replay.
    # =====================================================================
    print("\n" + "=" * 100)
    print("PART 3: morning boilerplate cluster vs evening -- last appearance + displacement")
    print("=" * 100)

    boiler_needle = "fully local"
    boiler_cluster = None
    for idxs in cluster_list:
        texts = " ".join(records[i]["answer"].lower() for i in idxs)
        if "substrate gain" in texts and boiler_needle in texts:
            if boiler_cluster is None or len(idxs) > len(boiler_cluster):
                boiler_cluster = idxs
    if boiler_cluster:
        print(f"  boilerplate cluster size={len(boiler_cluster)}")
        for i in boiler_cluster:
            rec = records[i]
            print(f"    turn#{rec['turn_no']:>2} {rec['ts']}  decision={rec['receipt_decision']:7} prompt={rec['user_input']!r}")
            print(f"        answer={rec['answer']!r}")
        last = records[boiler_cluster[-1]]
        print(f"  LAST appearance of this cluster: turn#{last['turn_no']} {last['ts']} (decision={last['receipt_decision']})")
    else:
        print("  no cluster matched the 'fully local' + 'substrate gain' needle at >=0.6 jaccard")

    # Precise cluster-membership test for "does this stored/selected
    # recent_turns entry ACTUALLY carry the morning boilerplate cluster" --
    # using compute.stored_answer_carried itself (spec S10: threshold 0.5,
    # "because state._clip_text truncates it on write"), against the
    # cluster's own first (uncllipped) emission as the recurring_text. This
    # avoids false positives from unrelated answers that merely also contain
    # the phrase "fully local" (e.g. "this system operates fully local-only"
    # said about cloud services -- a different, unrelated answer).
    boiler_text = records[boiler_cluster[0]]["answer"] if boiler_cluster else ""

    # Cross-check against the dashboard traces' own packet.recent_turns
    # snapshots (companion-selected dialogue field for that turn).
    import glob as _glob

    dash_files = sorted(_glob.glob(str(LOGS / "dashboard" / "turns" / "*.json")))
    print("\n  dashboard trace packet.recent_turns snapshots (companion-selected field, per turn):")
    print("  (contains_morning_boilerplate = compute.stored_answer_carried(cluster1_text, packet.recent_turns))")
    for fp in dash_files:
        d = json.load(open(fp))
        rt = (d.get("packet") or {}).get("recent_turns") or []
        contains_boiler = stored_answer_carried(boiler_text, rt) if boiler_text else False
        print(f"    {d['turn_id']}  user_input={d['user_input']!r:40}  n_recent_turns_in_packet={len(rt)}  contains_morning_boilerplate={contains_boiler}")

    # Faithful replay of state.recent_turns() using the real fit_recent_turns/
    # RECENT_TURNS_MAX_BYTES ring logic, to find the turn at which the
    # morning boilerplate entries were structurally evicted from state (not
    # just selection-filtered out of one turn's packet).
    print(f"\n  faithful replay of state.recent_turns() ring (RECENT_TURNS_MAX_BYTES={RECENT_TURNS_MAX_BYTES}):")
    ring: list[dict] = []
    replay_log = []
    for turn_no, (t, h) in enumerate(zip(turns, turn_meta), start=1):
        final_c, final_r = t[-1]
        answer_text = str(final_c.get("answer") or "").strip()
        user_text = str(h.get("user_input") or "").strip()
        violations = list(final_r.get("violations") or [])
        poison = (
            "template_echo" in violations
            or "template_echo_evidence" in violations
            or "stale_response_repeat" in violations
            or is_template_echo_text(answer_text)
        )
        appended = False
        if final_r["decision"] == "accept" and answer_text and user_text and not poison:
            entry = {
                "user": _clip_text(user_text, RECENT_TURN_USER_MAX_CHARS),
                "answer": _clip_text(answer_text, RECENT_TURN_ANSWER_MAX_CHARS),
                "ts": h["ts"],
            }
            ring = ring + [entry]
            ring = fit_recent_turns(ring, max_bytes=RECENT_TURNS_MAX_BYTES)
            appended = True
        replay_log.append(
            {
                "turn_no": turn_no,
                "ts": h["ts"],
                "user_input": h["user_input"],
                "appended": appended,
                "ring_size": len(ring),
                "ring_bytes": recent_turns_byte_size(ring),
                "ring_contains_boilerplate": stored_answer_carried(boiler_text, ring) if boiler_text else False,
                "ring_users": [e["user"] for e in ring],
            }
        )
    # print every turn that actually mutated the ring (appended==True), so
    # the exact append that evicted the boilerplate cluster is visible.
    for row in replay_log:
        if row["appended"]:
            print(
                f"    turn#{row['turn_no']:>2} {row['ts']}  appended={row['appended']!s:5}  "
                f"ring_size={row['ring_size']} ring_bytes={row['ring_bytes']:>4}  "
                f"ring_contains_boilerplate={row['ring_contains_boilerplate']}  ring_users={row['ring_users']}"
            )

    # =====================================================================
    # PART 4 -- byte-identical candidate answers across DIFFERENT user inputs.
    # =====================================================================
    print("\n" + "=" * 100)
    print("PART 4: byte-identical candidate answers across different user inputs")
    print("=" * 100)

    by_answer: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_answer[rec["answer"]].append(rec)

    collisions = []
    for answer, recs in by_answer.items():
        if len(recs) < 2:
            continue
        distinct_inputs = {r["user_input"] for r in recs}
        if len(distinct_inputs) < 2:
            continue  # same answer to the same repeated user_input isn't a "collision" across inputs
        collisions.append((answer, recs))

    collisions.sort(key=lambda x: x[1][0]["turn_no"])
    for answer, recs in collisions:
        n_distinct = len({r["user_input"] for r in recs})
        print(f"\n  IDENTICAL ANSWER (byte-for-byte) across {len(recs)} candidate(s), {n_distinct} distinct user_input(s):")
        print(f"    answer={answer!r}")
        for r in recs:
            print(f"      turn#{r['turn_no']:>2} {r['ts']}  pass={r['pass_index']}  decision={r['receipt_decision']:7}  user_input={r['user_input']!r}")

    # =====================================================================
    # Dump structured JSON for the verifier.
    # =====================================================================
    out = {
        "n_candidates": n,
        "n_turns": len(turns),
        "cluster_threshold": CLUSTER_THRESHOLD,
        "n_clusters_total": len(cluster_list),
        "n_multi_member_clusters": len(multi),
        "n_singleton_clusters": len(singles),
        "n_pairs_jaccard_ge_0_6": edges,
        "genealogy": genealogy,
        "reemission_distance_analysis": reemission_rows,
        "distance_bucket_summary": dist_buckets,
        "structural_control_trace": structural_rows,
        "byte_identical_collisions": [
            {
                "answer": answer,
                "occurrences": [
                    {
                        "turn_no": r["turn_no"],
                        "ts": r["ts"],
                        "pass_index": r["pass_index"],
                        "user_input": r["user_input"],
                        "receipt_decision": r["receipt_decision"],
                    }
                    for r in recs
                ],
            }
            for answer, recs in collisions
        ],
    }
    out_path = OUT_DIR / "lens1_results.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n\nWrote structured results to {out_path}")


if __name__ == "__main__":
    main()
