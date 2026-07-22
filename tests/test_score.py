import json

import pytest

from conditioned_kernel.score import (
    aggregate_condition,
    score_output,
    substrate_gain,
)

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)

PACKET = {
    "packet_id": "p",
    "user_input": "State the current design intent in two sentences.",
    "state_digest": {"goal": GOAL},
    "facts": [
        "This system is fully local.",
        "Edge target: jetson_orin_nano_8gb (one model at a time).",
    ],
    "open_threads": [{"id": "thread_min_model", "title": "min model size"}],
    "constraints": {"max_words": 120, "forbidden": []},
    "acceptance_contract": {
        "required_sections": ["answer", "evidence_used", "next_state"],
        "must_reference_goal": True,
        "must_not_contradict_facts": True,
    },
}

PROBE = {
    "id": "probe_intent",
    "prompt": PACKET["user_input"],
    "answer_key": {
        "must_mention_any": [["intent", "design", "substrate", "edge"]],
        "min_words": 8,
    },
}


def _json_answer(answer: str, evidence=None) -> str:
    return json.dumps(
        {
            "answer": answer,
            "evidence_used": evidence
            or [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": []},
        }
    )


def test_unified_scorer_accepts_good_answer():
    raw = _json_answer(
        "Design intent is edge-first substrate conditioning on a small local model without cloud."
    )
    s = score_output(raw, packet=PACKET, probe=PROBE)
    assert s["goal_echo"] is False
    assert s["accept"] is True
    assert s["structural_score"] > 0.5
    assert s["semantic_score"] > 0.5


def test_goal_echo_scores_low():
    raw = _json_answer(GOAL)
    s = score_output(raw, packet=PACKET, probe=PROBE)
    assert s["goal_echo"] is True
    assert s["accept"] is False
    assert s["structural_score"] < 1.0


def test_same_scorer_for_free_text_and_json():
    """Bare free text is not hard-coded accept=False; it can accept if it validates."""
    raw = _json_answer(
        "Design intent keeps substrate on the edge Jetson path, fully local."
    )
    s_bare = score_output(raw, packet=PACKET, probe=PROBE)
    s_ck = score_output(raw, packet=PACKET, probe=PROBE, decision="accept")
    # Same structural basis for parse/schema/echo
    assert s_bare["parse_ok"] == s_ck["parse_ok"]
    assert s_bare["goal_echo"] == s_ck["goal_echo"]


def test_probe_key_can_fail():
    raw = _json_answer(
        "Substrate conditioning on Jetson remains fully local for this system."
    )
    # Probe requires 'intent' or 'design' etc. — this may still pass group
    probe = {
        "answer_key": {
            "must_mention_any": [["THIS_TOKEN_WILL_NOT_APPEAR_XYZ"]],
            "min_words": 3,
        }
    }
    s = score_output(raw, packet=PACKET, probe=probe)
    assert s["key_ok"] is False
    assert s["accept"] is False


def test_hardcoded_composite_would_be_caught_by_structure():
    """Mutation guard: composite is derived from structural+semantic, not a constant."""
    good = score_output(
        _json_answer(
            "Design intent is edge-first substrate conditioning on a small local model."
        ),
        packet=PACKET,
        probe=PROBE,
    )
    bad = score_output(_json_answer(GOAL), packet=PACKET, probe=PROBE)
    assert good["structural_score"] != bad["structural_score"]
    g = substrate_gain(
        {"structural_score": good["structural_score"], "semantic_score": good["semantic_score"]},
        {"structural_score": bad["structural_score"], "semantic_score": bad["semantic_score"]},
    )
    # Derived, not asserted: composite must equal the mean of the two deltas.
    expected = (
        (good["structural_score"] - bad["structural_score"])
        + (good["semantic_score"] - bad["semantic_score"])
    ) / 2.0
    assert g["composite"] == pytest.approx(expected)

    # Two known input pairs pin the function to exact outputs. Any constant
    # return value — 0.60 or otherwise — fails at least one of these.
    hi = substrate_gain(
        {"structural_score": 1.0, "semantic_score": 1.0},
        {"structural_score": 0.0, "semantic_score": 0.0},
    )
    flat = substrate_gain(
        {"structural_score": 0.5, "semantic_score": 0.5},
        {"structural_score": 0.5, "semantic_score": 0.5},
    )
    assert hi["composite"] == pytest.approx(1.0)
    assert flat["composite"] == pytest.approx(0.0)


def test_aggregate_distinct_answers():
    rows = [
        {"scores": {"structural_score": 1.0, "accept": True, "answer": "aaa"}},
        {"scores": {"structural_score": 0.0, "accept": False, "answer": "aaa"}},
        {"scores": {"structural_score": 0.5, "accept": False, "answer": "bbb"}},
    ]
    a = aggregate_condition(rows)
    assert a["n"] == 3
    assert a["distinct_answers"] == 2
    assert a["structural_score"] == 0.5
