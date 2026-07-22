"""Episode B scoring and arm construction.

Fixture tasks only. The real corpus (experiments/probes/continuity_tasks.json)
is the other seat's deliverable and is deliberately not touched here -- whoever
writes the tasks and the scorer together will unconsciously write tasks their
scorer passes.
"""

import json

from conditioned_kernel.continuity import (
    build_bare_serialized,
    build_broken_packet,
    context_hashes,
    extract_numeric_claims,
    grounding_violations,
    score_episode_b,
)

GOAL = "Demonstrate conditioned-kernel substrate gain on a small local model at the edge."

ARTIFACTS = {
    "state": {"goal": GOAL},
    "facts": ["This system is fully local.", "Sensors are out of scope for v0."],
    "threads": [
        {"id": "thread_min_model", "title": "What is the minimum viable model size?"},
        {"id": "thread_compile_order", "title": "Best compile ordering"},
    ],
    "episode_a_log": ["turn 1 accepted", "wrote thread_min_model"],
}

PACKET = {
    "packet_id": "pkt_cont",
    "user_input": "Resume the work. Which thread is unresolved and what is the next step?",
    "state_digest": {"goal": GOAL},
    "facts": ARTIFACTS["facts"],
    "open_threads": ARTIFACTS["threads"],
    "constraints": {"max_words": 120, "forbidden": []},
    "acceptance_contract": {"must_not_contradict_facts": True},
}

TASK = {
    "id": "fixture_resume_01",
    "category": "thread_resume",
    "known_failures": ["gave up and asked the user"],
    "episode_b": {
        "prompt": PACKET["user_input"],
        "answer_key": {"must_mention_any": [["thread_min_model", "minimum viable"]], "min_words": 6},
        "grounded_claims": {"forbidden_inventions": ["the answer is 2GB"]},
        "correct_next_action": {"accept_any_of": ["measure", "run the ladder", "test smaller"]},
        "progress_trace": {"accept_any_of": ["thread_min_model"]},
    },
}


# --- arm construction -------------------------------------------------------


def test_broken_packet_destroys_state_but_keeps_shape():
    """Floor control must be structurally intact so advantage can't be formatting."""
    broken = build_broken_packet(PACKET)
    assert set(broken).issuperset({"state_digest", "facts", "open_threads"})
    assert broken["state_digest"]["goal"] == "[REDACTED]"
    assert all(f == "[REDACTED]" for f in broken["facts"])
    assert all(t["id"] == "thread_redacted" for t in broken["open_threads"])
    # and the real state must be genuinely gone
    assert GOAL not in json.dumps(broken)
    assert "thread_min_model" not in json.dumps(broken)
    # original untouched
    assert PACKET["state_digest"]["goal"] == GOAL


def test_bare_serialized_respects_the_byte_budget():
    small = build_bare_serialized(ARTIFACTS, 40)
    assert len(small.encode("utf-8")) <= 40
    big = build_bare_serialized(ARTIFACTS, 10_000)
    assert GOAL in big
    assert "thread_min_model" in big


def test_context_hashes_report_budget_delta_rather_than_assuming_parity():
    bare = build_bare_serialized(ARTIFACTS, 200)
    h = context_hashes(PACKET, bare, build_broken_packet(PACKET))
    assert h["continuity_packet_hash"] != h["bare_context_hash"]
    assert "budget_delta_bytes" in h, "equal-budget must be reported, never assumed"


# --- grounding (dimension 5) ------------------------------------------------


def test_grounding_catches_the_observed_gemma3_fabrication():
    """The live failure: accepted while asserting an invented specific.

    gemma3:1b was ACCEPTED answering "The minimum viable model size on Jetson
    Orin Nano 8GB is 2GB" because the answer key only required the phrase
    "minimum viable" to appear. 2GB appears nowhere in the packet.
    """
    answer = "The minimum viable model size on Jetson Orin Nano 8GB is 2GB."
    viol = grounding_violations(answer, PACKET, ARTIFACTS)
    assert viol, "an invented numeric specific must be flagged"
    assert any("2gb" in v.lower() for v in viol)


def test_grounding_allows_numbers_that_are_actually_in_evidence():
    grounded = dict(ARTIFACTS)
    grounded["facts"] = ARTIFACTS["facts"] + ["Edge target has 8GB of memory."]
    answer = "The board has 8GB of memory, so the model must fit under that."
    assert grounding_violations(answer, PACKET, grounded) == []


def test_forbidden_inventions_are_per_task():
    answer = "I checked and the answer is 2GB."
    viol = grounding_violations(answer, PACKET, ARTIFACTS, ["the answer is 2GB"])
    assert any("forbidden_invention" in v for v in viol)


def test_extract_numeric_claims_finds_units():
    got = extract_numeric_claims("It is 2GB, about 8 GB, and 0.5b params.")
    assert any("2gb" in g for g in got)


# --- seven dimensions -------------------------------------------------------


def test_a_good_resume_scores_across_dimensions():
    answer = (
        "Resuming: the goal is to demonstrate conditioned-kernel substrate gain on a small "
        "local model at the edge. The unresolved thread is thread_min_model. Next step is to "
        "measure smaller models against it."
    )
    s = score_episode_b(answer, task=TASK, packet=PACKET, artifacts=ARTIFACTS)
    d = s["dimensions"]
    assert d["recovers_goal"]
    assert d["identifies_unresolved_state"]
    assert d["correct_next_action"]
    assert d["no_unsupported_invention"]
    assert s["key_ok"]
    assert s["continuity_score"] > 0.7


def test_a_fabricating_resume_loses_the_grounding_dimension_only():
    """Dimensions are independent: one failure must not silently sink the rest."""
    answer = (
        "Resuming: the goal is to demonstrate conditioned-kernel substrate gain on a small "
        "local model at the edge. thread_min_model is unresolved and the minimum viable "
        "model size is 2GB, so we should measure."
    )
    s = score_episode_b(answer, task=TASK, packet=PACKET, artifacts=ARTIFACTS)
    d = s["dimensions"]
    assert d["recovers_goal"], "goal recovery is unaffected by the fabrication"
    assert d["identifies_unresolved_state"]
    assert not d["no_unsupported_invention"], "the invented 2GB must be caught"
    assert 0.0 < s["continuity_score"] < 1.0


def test_an_empty_resume_scores_near_zero():
    s = score_episode_b("", task=TASK, packet=PACKET, artifacts=ARTIFACTS)
    assert s["continuity_score"] == 0.0
    assert not s["key_ok"]


def test_a_goal_echo_does_not_earn_continuity():
    """Echoing the goal recovers the goal but resumes nothing."""
    s = score_episode_b(GOAL, task=TASK, packet=PACKET, artifacts=ARTIFACTS)
    d = s["dimensions"]
    assert d["recovers_goal"]
    assert not d["identifies_unresolved_state"]
    assert not d["correct_next_action"]
    assert s["continuity_score"] < 0.6, "goal echo must not pass as continuity"
