"""Tests for the per-check validation table — acceptance criterion 8

("Every validation result is visible individually", design_handoff_interior_
view/README.md §7 stage 09 point 1 / §14). Covers `compute.derive_checks`
and the `PassTrace.checks` / `.citation_audit` / `.evidence_pool` fields
`trace.run_traced_turn` attaches to every pass.

No live Ollama required: uses the repo's established offline-stub pattern
(`dry_candidate_text` injection into `pipeline.run_turn` /
`observatory.trace.run_traced_turn` — see tests/test_pipeline_dry.py,
tests/test_observatory_trace.py).
"""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.observatory.trace import PassTrace, run_traced_turn
from conditioned_kernel.return_path.validate import _evidence_ok, _packet_evidence_pool
from conditioned_kernel.state import DEFAULT_DESIGN_INTENT, SubstrateState

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)

ACCEPT_ANSWER = (
    "Design intent is edge-first substrate conditioning: keep models small "
    "and local, put continuity in files, measure gain under Jetson budgets."
)

# The exact, authoritative check names/order this table must produce —
# return_path/validate.py's own append order, reconciled against
# design_handoff_interior_view/README.md §7 stage 09's named list (which
# calls the "missing_answer" violation "nonempty_answer" and the "forbidden"
# violation "forbidden_content" — the display names this table uses, not
# validate.py's raw violation strings).
EXPECTED_CHECK_NAMES = [
    "parse_ok",
    "nonempty_answer",
    "template_echo",
    "template_echo_evidence",
    "goal_echo",
    "intent_echo",
    "not_responsive",
    "stale_response_repeat",
    "required_section:answer",
    "required_section:evidence_used",
    "required_section:next_state",
    "max_words",
    "evidence_used_empty",
    "evidence_too_short",
    "evidence_not_in_packet",
    "goal_not_referenced",
    "forbidden_content",
    "contradicts_facts",
    "unknown_thread_touch",
    "authoritative_obligation",
]

_STATUS_VOCAB = {"PASS", "FAIL", "ADVISORY", "SKIP"}

# Maps a violation string's prefix (the part before the first ":", or the
# whole string when there is no ":") to the check name it corresponds to.
# Two entries ("required_section:*") are looked up by the *whole* violation
# string instead, since validate.py folds the section name into the
# violation itself and derive_checks mirrors that as the check's own name.
_PREFIX_TO_CHECK = {
    "parse_failed": "parse_ok",
    "missing_answer": "nonempty_answer",
    "template_echo": "template_echo",
    "template_echo_evidence": "template_echo_evidence",
    "goal_echo": "goal_echo",
    "intent_echo": "intent_echo",
    "not_responsive": "not_responsive",
    "stale_response_repeat": "stale_response_repeat",
    "max_words_exceeded": "max_words",
    "evidence_used_empty": "evidence_used_empty",
    "evidence_too_short": "evidence_too_short",
    "evidence_not_in_packet": "evidence_not_in_packet",
    "goal_not_referenced": "goal_not_referenced",
    "forbidden": "forbidden_content",
    "contradicts_facts": "contradicts_facts",
    "unknown_thread_touch": "unknown_thread_touch",
}


def _violation_to_check_name(v: str) -> str:
    if v.startswith("required_section:"):
        return v
    return _PREFIX_TO_CHECK[v.split(":", 1)[0]]


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": GOAL,
                "design_intent": DEFAULT_DESIGN_INTENT,
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_test",
                "receipt_count_24h": 0,
                "flags": {
                    "sensors": False,
                    "tools": False,
                    "cloud": False,
                    "max_repair_passes": 1,
                    "edge_target": "jetson_orin_nano_8gb",
                    "one_model_only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text(
        json.dumps(
            [
                {
                    "id": "thread_min_model",
                    "status": "open",
                    "title": "What is the minimum viable model size on Jetson Orin Nano 8GB?",
                }
            ]
        ),
        encoding="utf-8",
    )
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    return state_dir, logs_dir


def _dry_candidate(answer: str, evidence: list[str] | None = None, thread_touch: list[str] | None = None) -> str:
    return json.dumps(
        {
            "answer": answer,
            "evidence_used": evidence
            if evidence is not None
            else [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": thread_touch or []},
        }
    )


def _run(
    tmp_path: Path,
    prompt: str = "Summarize design intent.",
    *,
    answer: str = ACCEPT_ANSWER,
    evidence: list[str] | None = None,
    thread_touch: list[str] | None = None,
    acceptance_mode: str = "companion",
):
    state_dir, logs_dir = _bootstrap(tmp_path)
    trace = run_traced_turn(
        prompt,
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=_dry_candidate(answer, evidence, thread_touch),
        max_repair=0,
        acceptance_mode=acceptance_mode,
    )
    return trace


# ---------------------------------------------------------------------------
# Full-coverage: every validate_candidate check exactly once, in order
# ---------------------------------------------------------------------------


def test_checks_cover_every_validate_candidate_check_exactly_once(tmp_path):
    trace = _run(tmp_path)
    pass0 = trace.passes[-1]
    assert isinstance(pass0, PassTrace)
    names = [c["name"] for c in pass0.checks]
    assert names == EXPECTED_CHECK_NAMES
    assert len(names) == len(set(names))  # exactly once each


def test_checks_have_required_fields(tmp_path):
    trace = _run(tmp_path)
    for c in trace.passes[-1].checks:
        assert set(c.keys()) == {"name", "status", "reason", "examined", "severity"}
        assert isinstance(c["reason"], str) and c["reason"]
        assert isinstance(c["examined"], str) and c["examined"]
        assert isinstance(c["severity"], str) and c["severity"]


def test_checks_serialize_on_the_pass_dict(tmp_path):
    trace = _run(tmp_path)
    d = trace.to_dict()
    pass0 = d["passes"][-1]
    assert "checks" in pass0 and len(pass0["checks"]) == len(EXPECTED_CHECK_NAMES)
    assert "citation_audit" in pass0
    assert "evidence_pool" in pass0
    reloaded = json.loads(trace.to_json())
    assert reloaded["passes"][-1]["checks"] == pass0["checks"]


# ---------------------------------------------------------------------------
# Statuses drawn only from {PASS, FAIL, ADVISORY, SKIP}
# ---------------------------------------------------------------------------


def test_check_statuses_use_only_the_four_status_vocabulary(tmp_path):
    trace = _run(tmp_path)
    for c in trace.passes[-1].checks:
        assert c["status"] in _STATUS_VOCAB, c


# ---------------------------------------------------------------------------
# FAIL/ADVISORY entries agree exactly with the pass's violations/advisories
# ---------------------------------------------------------------------------


def _assert_checks_agree_with_violations_and_advisories(pass_trace: PassTrace) -> None:
    expected_fail_names = {_violation_to_check_name(v) for v in pass_trace.violations}
    expected_advisory_names = {_violation_to_check_name(v) for v in pass_trace.advisories}
    # not_responsive is the only check that can land in either list; a given
    # pass only ever has it in one of the two, so no overlap is expected.
    assert not (expected_fail_names & expected_advisory_names)

    actual_fail_names = {c["name"] for c in pass_trace.checks if c["status"] == "FAIL"}
    actual_advisory_names = {c["name"] for c in pass_trace.checks if c["status"] == "ADVISORY"}

    assert actual_fail_names == expected_fail_names, (
        actual_fail_names, expected_fail_names, pass_trace.violations,
    )
    assert actual_advisory_names == expected_advisory_names, (
        actual_advisory_names, expected_advisory_names, pass_trace.advisories,
    )


def test_clean_accept_has_no_fail_or_advisory_checks(tmp_path):
    trace = _run(tmp_path)
    pass0 = trace.passes[-1]
    assert pass0.decision == "accept"
    assert pass0.violations == []
    assert pass0.advisories == []
    _assert_checks_agree_with_violations_and_advisories(pass0)
    assert all(c["status"] in ("PASS", "SKIP") for c in pass0.checks)


def test_goal_echo_rejection_checks_agree_with_violations(tmp_path):
    trace = _run(
        tmp_path,
        prompt="What is the current goal we are working toward?",
        answer=GOAL,
    )
    pass0 = trace.passes[-1]
    assert pass0.decision == "reject"
    assert "goal_echo" in pass0.violations
    _assert_checks_agree_with_violations_and_advisories(pass0)
    goal_echo = next(c for c in pass0.checks if c["name"] == "goal_echo")
    assert goal_echo["status"] == "FAIL"


def test_evidence_and_thread_touch_rejection_checks_agree_with_violations(tmp_path):
    # Measurement mode: unknown thread_touch remains a hard violation.
    # Companion mode filters unknown touches as advisory (withheld threads).
    trace = _run(
        tmp_path,
        evidence=["totally unrelated garbage citation text that matches nothing"],
        thread_touch=["bogus_thread_id"],
        acceptance_mode="measurement",
    )
    pass0 = trace.passes[-1]
    assert pass0.decision == "reject"
    assert "unknown_thread_touch:bogus_thread_id" in pass0.violations
    assert any(v.startswith("evidence_not_in_packet:") for v in pass0.violations)
    _assert_checks_agree_with_violations_and_advisories(pass0)

    evidence_check = next(c for c in pass0.checks if c["name"] == "evidence_not_in_packet")
    assert evidence_check["status"] == "FAIL"
    touch_check = next(c for c in pass0.checks if c["name"] == "unknown_thread_touch")
    assert touch_check["status"] == "FAIL"
    assert "bogus_thread_id" in touch_check["reason"]


def test_not_responsive_advisory_in_companion_mode_agrees_with_advisories(tmp_path):
    trace = _run(
        tmp_path,
        prompt="are you there",
        answer="Local edge substrate keeps continuity, files hold state, budgets bound the kernel fully.",
    )
    pass0 = trace.passes[-1]
    assert "not_responsive" in pass0.advisories
    assert "not_responsive" not in pass0.violations
    _assert_checks_agree_with_violations_and_advisories(pass0)
    nr = next(c for c in pass0.checks if c["name"] == "not_responsive")
    assert nr["status"] == "ADVISORY"
    assert nr["severity"] == "advisory"


def test_not_responsive_is_a_hard_violation_in_measurement_mode(tmp_path):
    trace = _run(
        tmp_path,
        prompt="What model runs here on the edge target?",
        answer="blah blah blah nothing relevant said here at all today",
        acceptance_mode="measurement",
    )
    pass0 = trace.passes[-1]
    assert "not_responsive" in pass0.violations
    assert "not_responsive" not in pass0.advisories
    _assert_checks_agree_with_violations_and_advisories(pass0)
    nr = next(c for c in pass0.checks if c["name"] == "not_responsive")
    assert nr["status"] == "FAIL"
    assert nr["severity"] == "violation"


def test_evidence_too_short_fires_in_measurement_mode(tmp_path):
    """Companion-mode grounding (validate.apply_companion_grounding) filters
    sub-12-char citations out of evidence_used before validate_candidate's
    per-item checks ever see them, so evidence_too_short can only be
    observed to fire under measurement mode (no grounding applied)."""
    trace = _run(
        tmp_path,
        evidence=["This system is fully local.", "short"],
        acceptance_mode="measurement",
    )
    pass0 = trace.passes[-1]
    assert any(v.startswith("evidence_too_short:") for v in pass0.violations)
    _assert_checks_agree_with_violations_and_advisories(pass0)
    too_short = next(c for c in pass0.checks if c["name"] == "evidence_too_short")
    assert too_short["status"] == "FAIL"
    assert "short" in too_short["reason"]


def test_stale_response_repeat_agrees_with_violations(tmp_path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    state.append_recent_turn("Tell me about edge budgets.", ACCEPT_ANSWER)
    state.save_current()
    trace = run_traced_turn(
        "What makes this different from a normal chatbot?",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=_dry_candidate(ACCEPT_ANSWER),
        max_repair=0,
    )
    pass0 = trace.passes[-1]
    assert "stale_response_repeat" in pass0.violations
    _assert_checks_agree_with_violations_and_advisories(pass0)
    stale = next(c for c in pass0.checks if c["name"] == "stale_response_repeat")
    assert stale["status"] == "FAIL"


# ---------------------------------------------------------------------------
# authoritative_obligation: SKIP when no obligation resolved, PASS/FAIL when one is
# ---------------------------------------------------------------------------


def test_authoritative_obligation_absent_turn_shows_skip(tmp_path):
    """"Explain how substrate conditioning helps." does not classify as a
    narrow state question (authoritative_state.classify_state_question
    returns None — unlike "Summarize design intent.", which resolves a
    "design_intent" obligation; see the tests below), so no obligation is resolved
    and the check must be SKIP, not PASS or FAIL — there is nothing for
    authoritative_state.check_obligation to have evaluated this pass."""
    trace = _run(tmp_path, prompt="Explain how substrate conditioning helps.")
    pass0 = trace.passes[-1]
    assert pass0.authoritative_kind is None
    auth = next(c for c in pass0.checks if c["name"] == "authoritative_obligation")
    assert auth["status"] == "SKIP"
    assert "not applicable" in auth["reason"]


def test_authoritative_obligation_resolved_and_preserved_shows_pass(tmp_path):
    """"What is the current goal?" classifies as an authoritative "goal"
    question; a candidate that plainly states the goal preserves the
    required claims, so authoritative_state.check_obligation finds nothing
    wrong and no substrate fallback is substituted."""
    trace = _run(tmp_path, prompt="What is the current goal?")
    pass0 = trace.passes[-1]
    assert pass0.authoritative_kind == "goal"
    assert pass0.authoritative_fallback is False
    auth = next(c for c in pass0.checks if c["name"] == "authoritative_obligation")
    assert auth["status"] == "PASS"


def test_authoritative_obligation_resolved_and_failed_shows_fail(tmp_path):
    """A candidate that merely echoes the question fails
    authoritative_state.check_obligation (authoritative_question_echo), so
    the substrate substitutes its own fallback answer — the turn itself
    still accepts (the fallback answer clears validate_candidate cleanly),
    but authoritative_obligation must report FAIL: a check this table
    exists specifically to make visible even when it never lands in
    receipt["violations"]."""
    trace = _run(tmp_path, prompt="What is the current goal?", answer="What is the current goal?")
    pass0 = trace.passes[-1]
    assert pass0.authoritative_kind == "goal"
    assert pass0.authoritative_fallback is True
    assert pass0.violations == []  # the substituted fallback clears validate_candidate
    auth = next(c for c in pass0.checks if c["name"] == "authoritative_obligation")
    assert auth["status"] == "FAIL"
    assert "authoritative_question_echo" in auth["reason"] or "authoritative" in auth["reason"]


# ---------------------------------------------------------------------------
# citation_audit agrees with validate._evidence_ok on each citation
# ---------------------------------------------------------------------------


def test_citation_audit_agrees_with_evidence_ok_on_a_clean_accept(tmp_path):
    trace = _run(tmp_path)
    pass0 = trace.passes[-1]
    pool = _packet_evidence_pool(pass0.packet)
    assert len(pass0.citation_audit) == len(pass0.evidence_used)
    for citation, row in zip(pass0.evidence_used, pass0.citation_audit):
        ok, bad = _evidence_ok([citation], pool)
        if ok:
            assert row["status"] == "MATCHED", (citation, row)
        else:
            reason_token = bad[0] if bad else "evidence_not_in_packet"
            expected = "TOO_SHORT" if reason_token.startswith("evidence_too_short") else "MISS"
            assert row["status"] == expected, (citation, row, reason_token)


def test_citation_audit_agrees_with_evidence_ok_on_mixed_citations(tmp_path):
    trace = _run(
        tmp_path,
        evidence=[
            "This system is fully local.",  # matches
            "totally unrelated garbage citation text that matches nothing",  # miss
        ],
        acceptance_mode="measurement",
    )
    pass0 = trace.passes[-1]
    pool = _packet_evidence_pool(pass0.packet)
    assert len(pass0.citation_audit) == len(pass0.evidence_used) == 2
    for citation, row in zip(pass0.evidence_used, pass0.citation_audit):
        ok, bad = _evidence_ok([citation], pool)
        if ok:
            assert row["status"] == "MATCHED", (citation, row)
        else:
            reason_token = bad[0] if bad else "evidence_not_in_packet"
            expected = "TOO_SHORT" if reason_token.startswith("evidence_too_short") else "MISS"
            assert row["status"] == expected, (citation, row, reason_token)


def test_evidence_pool_field_matches_compute_labeled_evidence_pool(tmp_path):
    from conditioned_kernel.observatory import compute

    trace = _run(tmp_path)
    pass0 = trace.passes[-1]
    assert pass0.evidence_pool == compute.labeled_evidence_pool(pass0.packet)
    assert len(pass0.evidence_pool) > 0
    for entry in pass0.evidence_pool:
        assert set(entry.keys()) == {"source_key", "value", "length"}
