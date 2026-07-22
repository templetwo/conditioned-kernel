from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.validate import (
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
