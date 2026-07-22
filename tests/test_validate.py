from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.validate import (
    _fact_contradictions,
    is_goal_echo,
    validate_candidate,
)

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)

PACKET = {
    "packet_id": "pkt_test",
    "user_input": "State the current design intent in two sentences. Cite the goal.",
    "state_digest": {"goal": GOAL},
    "facts": [
        "This system is fully local.",
        "Sensors are out of scope for v0.",
        "Edge target: jetson_orin_nano_8gb (one model at a time).",
    ],
    "open_threads": [
        {"id": "thread_min_model", "title": "What is the minimum viable model size?"}
    ],
    "constraints": {
        "max_words": 180,
        "forbidden": ["https://", "tool_calls"],
    },
    "acceptance_contract": {
        "required_sections": ["answer", "evidence_used", "next_state"],
        "must_reference_goal": True,
        "must_not_contradict_facts": True,
        "evidence_must_be_from_packet": True,
    },
}


def test_valid_candidate_accepts_non_echo():
    raw = """{
      "answer": "Design intent is edge-first substrate conditioning on a small local model, measuring gain without cloud.",
      "evidence_used": ["This system is fully local.", "Edge target: jetson_orin_nano_8gb (one model at a time)."],
      "next_state": {"thread_touch": ["thread_min_model"]}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    receipt = assess(receipt, pass_index=0)
    assert "goal_echo" not in receipt["violations"]
    assert receipt["valid_schema"] is True
    assert receipt["state_faithful"] is True
    assert receipt["decision"] == "accept"


def test_goal_echo_rejected():
    raw = {
        "answer": GOAL,
        "evidence_used": ["This system is fully local."],
        "next_state": {},
    }
    import json

    cand = parse_candidate(json.dumps(raw), packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    assert "goal_echo" in receipt["violations"]
    assert is_goal_echo(GOAL, GOAL) is True


def test_goal_echo_helper_near_copy():
    assert is_goal_echo(GOAL + ".", GOAL) is True
    assert is_goal_echo(
        "Design intent is different: measure continuity from files only on edge.",
        GOAL,
    ) is False


def test_not_responsive_capital():
    pkt = dict(PACKET)
    pkt["user_input"] = "What is the capital of France?"
    raw = """{
      "answer": "Edge substrate conditioning on Jetson keeps models local.",
      "evidence_used": ["This system is fully local."],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, pkt)
    assert "not_responsive" in receipt["violations"]


def test_contradicts_facts():
    raw = """{
      "answer": "Yes, this system routinely calls cloud APIs and uses sensors for data.",
      "evidence_used": ["This system is fully local."],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    assert any(v.startswith("contradicts_facts") for v in receipt["violations"])


def test_evidence_too_short():
    raw = """{
      "answer": "Design intent covers substrate gain on edge Jetson local models.",
      "evidence_used": ["e"],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    assert any("evidence_too_short" in v for v in receipt["violations"])


def test_bad_evidence_repairs():
    raw = """{
      "answer": "Something about substrate gain and conditioned-kernel on a local edge model for design intent.",
      "evidence_used": ["I invented this fact that is long enough"],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    receipt = assess(receipt, pass_index=0)
    assert receipt["decision"] == "repair"
    assert any("evidence_not_in_packet" in v for v in receipt["violations"])


def test_forbidden_phrase():
    raw = """{
      "answer": "Use https://example.com for substrate gain with conditioned-kernel local model design intent.",
      "evidence_used": ["This system is fully local."],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    assert receipt["state_faithful"] is False
    assert any("forbidden" in v for v in receipt["violations"])


# --- polarity of the contradiction check -------------------------------------
# Both directions are pinned deliberately. The original bug was topic-matching
# (any mention of a forbidden capability flagged, even a denial). The obvious
# fix — ignore anything near a negation — regresses the other way, so the
# assertions below must stay paired: denials clean, assertions still caught.

CONSTRAINT_PACKET = {
    **PACKET,
    "user_input": "Is this system allowed to call cloud APIs or use sensors in v0? Answer briefly.",
}


def _contradictions(answer: str, packet: dict = CONSTRAINT_PACKET) -> list[str]:
    return _fact_contradictions(answer, packet)


def test_denial_mentioning_forbidden_capability_is_not_a_contradiction():
    """Answering a question about cloud/sensors requires naming them."""
    for answer in [
        "No. Cloud APIs and sensors are out of scope for v0.",
        "This system does not call cloud APIs.",
        "Cloud APIs are forbidden in v0; the system is fully local.",
        "No cloud API access and no sensor data are permitted.",
        "Cloud APIs cannot be called and sensors are disabled.",
    ]:
        assert _contradictions(answer) == [], f"false positive on denial: {answer!r}"


def test_assertion_of_forbidden_capability_is_still_flagged():
    for answer in [
        "This system routinely calls cloud APIs and streams sensor data.",
        "Yes, cloud APIs are available in v0.",
        "The kernel uses cloud inference for long prompts.",
        "It reads sensor data from the camera.",
    ]:
        assert _contradictions(answer), f"missed real contradiction: {answer!r}"


def test_negation_does_not_leak_across_clauses():
    """A denial in one sentence must not excuse an assertion in the next."""
    answer = "The system is not a toy. It calls cloud APIs on every request."
    assert _contradictions(answer)


def test_constraint_probe_is_answerable_end_to_end():
    """Regression for the not_responsive / contradicts_facts catch-22.

    A correct answer had to both contain 'cloud API' (to be responsive) and
    not contain it (to avoid contradicts_facts). It was unpassable.
    """
    raw = """{
      "answer": "No. Cloud APIs and sensors are out of scope for v0; the goal is demonstrating substrate gain on a small local model at the edge.",
      "evidence_used": ["This system is fully local.", "Sensors are out of scope for v0."],
      "next_state": {"thread_touch": []}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, CONSTRAINT_PACKET)
    assert receipt["violations"] == []
    assert receipt["valid_schema"] is True
    assert receipt["state_faithful"] is True
