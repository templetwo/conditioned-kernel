"""LENS 3, Q1: full check-outcome census.

Two layers, kept separate so nothing is a guess dressed as ground truth:

LAYER A (ground truth, 22 passes): the 19 dashboard TurnTraces carry the
real `checks[]` array the pipeline's own `compute.derive_checks` produced
for each pass (see observatory/trace.py PassTrace.checks). We just tabulate
what's already there. PASS/FAIL/ADVISORY/SKIP counts for these 22 passes
are exact.

LAYER B (all 93 passes, fired-only): receipts.jsonl records
`violations`/`advisories` for every one of the 93 logged passes (companion
and the 12 early measurement-mode passes alike). A violation/advisory
string is direct, unambiguous evidence that check fired for that pass. We
tabulate FAIL/ADVISORY fire-counts across all 93 this way — this answers
"which checks did all the work" and "which never fired all day" without
needing the packet body (which is not logged for the 71 non-dashboard
passes; there is no packets.jsonl/audit log in logs/, only packet_id +
packet_hash in history.jsonl).

What layer B deliberately does NOT claim: a full PASS-vs-SKIP split for
checks that did not fire on the 71 non-dashboard passes. That distinction
needs packet-level facts (state_digest.goal, acceptance_contract flags,
open_threads) that are not persisted outside the packet body, which is
only present in the 19 dashboard traces. Where the SKIP/PASS gate is
fully determined by candidate-only fields (already logged for all 93:
answer, evidence_used, next_state.thread_touch, receipt.authoritative_fallback)
we compute it and say so. Where it is not (goal_echo / not_responsive /
goal_not_referenced's "is there a goal / is must_reference_goal set"
gate), we rely on one documented, checked assumption: state_digest.goal
is a fixed system-level string ('Demonstrate conditioned-kernel substrate
gain over bare generation on a small local model under Jetson Orin Nano
8GB edge budgets.') that is identical and present in all 19 packets we DO
have full visibility into, and there is no companion-mode receipt anywhere
in the 93 whose violations show a state consistent with a missing goal.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from common import (
    base_check_name,
    load_candidates,
    load_dashboard_turns,
    load_history,
    load_receipts,
    group_turns,
    turn_user_input,
)

import sys
sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.return_path.validate import is_responsive, is_goal_echo  # noqa: E402

# Commit b385157 ("Studio: advisory not_responsive + stale-response guard",
# 2026-07-28T03:11:26Z) changed not_responsive in companion mode from a
# hard `violations` entry to an `advisories` entry. Confirmed against the
# receipts themselves (see q2_not_responsive.py): last companion-mode
# not_responsive VIOLATION at 03:09:34Z, first companion-mode
# not_responsive ADVISORY at 03:13:01Z. Applying *current* validate.py's
# companion-always-advisory branch to pre-fix passes would mislabel 34 real
# violations as PASS, so this gate is era-aware, not mode-aware alone.
NOT_RESPONSIVE_FIX_TS = "2026-07-28T03:11:26Z"

STATUSES = ("PASS", "FAIL", "ADVISORY", "SKIP")


def layer_a():
    dash = load_dashboard_turns()
    table = defaultdict(lambda: Counter())
    n_passes = 0
    per_pass_rows = []
    for d in dash:
        for p in d["passes"]:
            n_passes += 1
            for chk in p["checks"]:
                table[chk["name"]][chk["status"]] += 1
            per_pass_rows.append({
                "turn_file": d["_file"],
                "pass_index": p["pass_index"],
                "decision": p["decision"],
                "checks": {c["name"]: c["status"] for c in p["checks"]},
            })
    return n_passes, table, per_pass_rows


def layer_b():
    cands = load_candidates()
    rcpts = load_receipts()
    fail_counter = Counter()
    advisory_counter = Counter()
    fail_detail_examples = defaultdict(list)
    advisory_detail_examples = defaultdict(list)
    for c, r in zip(cands, rcpts):
        for v in r.get("violations") or []:
            name = base_check_name(v)
            fail_counter[name] += 1
            if len(fail_detail_examples[name]) < 5:
                fail_detail_examples[name].append(v)
        for a in r.get("advisories") or []:
            name = base_check_name(a)
            advisory_counter[name] += 1
            if len(advisory_detail_examples[name]) < 5:
                advisory_detail_examples[name].append(a)
    return len(cands), fail_counter, advisory_counter, fail_detail_examples, advisory_detail_examples


def layer_b_skip_pass_where_determinable():
    """For checks whose SKIP-gate is fully computable from candidate-only
    fields (already logged for all 93 passes), compute PASS vs SKIP vs FAIL
    across the full 93. Checks not listed here are left to layer A only.
    """
    cands = load_candidates()
    rcpts = load_receipts()
    hist = load_history()
    hist_by_cand = {h["candidate_id"]: h for h in hist}
    turns = group_turns(cands, rcpts)

    # Map candidate_id -> resolved user_input (propagated across repair passes
    # of the same logical turn via history.jsonl's terminal record).
    user_input_by_cand: dict[str, str | None] = {}
    for t in turns:
        ui = turn_user_input(t, hist_by_cand)
        for c, _r in t:
            user_input_by_cand[c["candidate_id"]] = ui

    GOAL = ("Demonstrate conditioned-kernel substrate gain over bare generation "
            "on a small local model under Jetson Orin Nano 8GB edge budgets.")

    out = defaultdict(lambda: Counter())
    unresolved_user_input = 0

    for c, r in zip(cands, rcpts):
        violations = [str(v) for v in (r.get("violations") or [])]
        advisories = [str(v) for v in (r.get("advisories") or [])]
        acceptance_mode = r.get("acceptance_mode") or "measurement"
        companion = acceptance_mode == "companion"
        answer = str(c.get("answer") or "").strip()
        evidence_used = list(c.get("evidence_used") or [])
        next_state = c.get("next_state") if isinstance(c.get("next_state"), dict) else {}
        thread_touch = list((next_state or {}).get("thread_touch") or [])
        fallback = bool(r.get("authoritative_fallback"))
        user_input = user_input_by_cand.get(c["candidate_id"])
        if user_input is None:
            unresolved_user_input += 1

        # template_echo_evidence: SKIP has no packet dependency at all — the
        # check only inspects evidence_used contents, but derive_checks
        # differentiates its PASS reason by "empty" vs "no placeholder".
        # It is never SKIP in validate_candidate (always evaluated), so no
        # SKIP bucket for this one, only PASS/FAIL — matches compute.py.
        name = "template_echo_evidence"
        out[name]["FAIL" if "template_echo_evidence" in violations else "PASS"] += 1

        # evidence_used_empty: always evaluated (PASS/FAIL, no SKIP).
        name = "evidence_used_empty"
        out[name]["FAIL" if "evidence_used_empty" in violations else "PASS"] += 1

        # evidence_too_short / evidence_not_in_packet: SKIP iff evidence_used
        # is empty (validate._evidence_ok short-circuits before its loop).
        for name, viol_prefix in (
            ("evidence_too_short", "evidence_too_short"),
            ("evidence_not_in_packet", "evidence_not_in_packet"),
        ):
            if not evidence_used:
                out[name]["SKIP"] += 1
            elif any(v.startswith(viol_prefix) for v in violations):
                out[name]["FAIL"] += 1
            else:
                out[name]["PASS"] += 1

        # unknown_thread_touch: SKIP iff next_state.thread_touch is empty.
        name = "unknown_thread_touch"
        if not thread_touch:
            out[name]["SKIP"] += 1
        elif any(v.startswith("unknown_thread_touch") for v in violations):
            out[name]["FAIL"] += 1
        else:
            out[name]["PASS"] += 1

        # nonempty_answer / parse_ok / max_words: always evaluated.
        out["nonempty_answer"]["FAIL" if "missing_answer" in violations else "PASS"] += 1
        out["parse_ok"]["FAIL" if any(v.startswith("parse_failed") for v in violations) else "PASS"] += 1
        out["max_words"]["FAIL" if any(v.startswith("max_words_exceeded") for v in violations) else "PASS"] += 1

        # required_section:answer/evidence_used/next_state — default contract,
        # always evaluated (no SKIP under the default required_sections list;
        # we cannot rule out a custom contract for non-dashboard turns, but
        # every dashboard packet we CAN see uses the default list, and no
        # receipt in the full 93 shows a required_section violation for a
        # section name outside {answer,evidence_used,next_state}).
        for sect in ("answer", "evidence_used", "next_state"):
            name = f"required_section:{sect}"
            fired = name in violations
            out[name]["FAIL" if fired else "PASS"] += 1

        # goal_echo: SKIP iff answer empty OR fallback (goal assumed present
        # per module docstring's documented check).
        name = "goal_echo"
        if not answer or fallback:
            out[name]["SKIP"] += 1
        elif "goal_echo" in violations:
            out[name]["FAIL"] += 1
        else:
            out[name]["PASS"] += 1

        # not_responsive: SKIP iff answer empty OR user_input empty/unknown OR
        # fallback. Severity is ADVISORY in companion mode *after* the
        # 03:11:26Z fix; before it, companion mode also hard-failed via
        # violations, identical to measurement mode (see module note above).
        name = "not_responsive"
        post_fix = r["created_at"] >= NOT_RESPONSIVE_FIX_TS
        companion_advisory_era = companion and post_fix
        if not answer or not user_input or fallback:
            out[name]["SKIP"] += 1
        else:
            if companion_advisory_era:
                fired = "not_responsive" in advisories
                sev = "ADVISORY"
            else:
                fired = "not_responsive" in violations
                sev = "FAIL"
            out[name][sev if fired else "PASS"] += 1

        # goal_not_referenced: gated on acceptance_contract.must_reference_goal
        # which defaults to `not companion` (we cannot see contract overrides
        # for the 71 non-dashboard passes, so this uses the documented
        # default — flagged in the report).
        name = "goal_not_referenced"
        must_goal = not companion
        if not (must_goal and answer):
            out[name]["SKIP"] += 1
        elif "goal_not_referenced" in violations:
            out[name]["FAIL"] += 1
        else:
            out[name]["PASS"] += 1

        # forbidden_content: always evaluated (constraints.forbidden unknown
        # for non-dashboard turns but PASS-if-empty and PASS-if-no-hit are
        # both PASS, so this collapses to PASS/FAIL regardless).
        name = "forbidden_content"
        out[name]["FAIL" if any(v.startswith("forbidden:") for v in violations) else "PASS"] += 1

        # contradicts_facts: gated on acceptance_contract.must_not_contradict_facts,
        # default False. We cannot see contract overrides for non-dashboard
        # turns; use default (documented assumption, flagged).
        name = "contradicts_facts"
        must_not_contradict = False  # default; see docstring
        if not must_not_contradict:
            out[name]["SKIP"] += 1
        elif any(v.startswith("contradicts_facts") for v in violations):
            out[name]["FAIL"] += 1
        else:
            out[name]["PASS"] += 1

        # stale_response_repeat: requires prior_accepted_answer(packet) and
        # user_prompt_changed(packet, user_input) — both packet-shaped
        # (recent_turns[-1]) and NOT recoverable for non-dashboard passes
        # from candidate/receipt/history alone. Left fully to layer A.

        # authoritative_obligation: gated on receipt.authoritative_kind,
        # which IS logged for all 93 receipts.
        name = "authoritative_obligation"
        kind = r.get("authoritative_kind")
        if kind is None:
            out[name]["SKIP"] += 1
        elif fallback:
            out[name]["FAIL"] += 1
        else:
            out[name]["PASS"] += 1

    return out, unresolved_user_input


def main():
    n_a, table_a, per_pass_a = layer_a()
    n_b, fail_b, adv_b, fail_ex, adv_ex = layer_b()
    table_c, unresolved = layer_b_skip_pass_where_determinable()

    # authoritative_obligation fires via receipt.authoritative_fallback, a
    # separate pipeline.py mechanism (enforce_authoritative_candidate) that
    # runs BEFORE validate_candidate and is never recorded as a
    # violations/advisories string — so it is invisible to the fail_b/adv_b
    # violation-text census above and must be counted directly here or it
    # would be wrongly reported as "never fired all day".
    cands_all = load_candidates()
    rcpts_all = load_receipts()
    authoritative_fallback_fires = sum(
        1 for r in rcpts_all if bool(r.get("authoritative_fallback"))
    )

    report = {
        "layer_a_ground_truth_22_passes": {
            "n_passes": n_a,
            "checks": {name: dict(counter) for name, counter in sorted(table_a.items())},
        },
        "layer_b_fired_only_93_passes": {
            "n_passes": n_b,
            "fail_counts": dict(sorted(fail_b.items(), key=lambda kv: -kv[1])),
            "advisory_counts": dict(sorted(adv_b.items(), key=lambda kv: -kv[1])),
            "fail_examples": {k: v for k, v in fail_ex.items()},
            "advisory_examples": {k: v for k, v in adv_ex.items()},
        },
        "layer_c_full_93_pass_skip_reconstruction": {
            "note": "PASS/SKIP/FAIL/ADVISORY per check, all 93 passes, using only "
                     "candidate-only + receipt-only fields (documented per-check gate "
                     "logic above). stale_response_repeat excluded (needs packet).",
            "unresolved_user_input_count": unresolved,
            "checks": {name: dict(counter) for name, counter in sorted(table_c.items())},
        },
        "authoritative_obligation_fallback_fires_93_passes": authoritative_fallback_fires,
        "never_fired_all_day": sorted(
            name for name in set(list(table_a.keys()) + list(table_c.keys()))
            if fail_b.get(name, 0) == 0
            and adv_b.get(name, 0) == 0
            and not (name == "authoritative_obligation" and authoritative_fallback_fires)
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
