from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.validate import validate_candidate

PACKET = {
    "packet_id": "pkt_test",
    "state_digest": {
        "goal": "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model."
    },
    "facts": [
        "This system is fully local.",
        "Sensors are out of scope for v0.",
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


def test_valid_candidate_accepts():
    raw = """{
      "answer": "Intent is to demonstrate conditioned-kernel substrate gain over bare generation on a small local model, fully local.",
      "evidence_used": ["This system is fully local.", "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model."],
      "next_state": {"thread_touch": ["thread_min_model"], "proposed_note": "ok"}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    receipt = assess(receipt, pass_index=0)
    assert receipt["valid_schema"] is True
    assert receipt["state_faithful"] is True
    assert receipt["decision"] == "accept"


def test_bad_evidence_repairs():
    raw = """{
      "answer": "Something about substrate gain and conditioned-kernel on a local model.",
      "evidence_used": ["I invented this fact"],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    receipt = assess(receipt, pass_index=0)
    assert receipt["decision"] == "repair"
    assert any("evidence_not_in_packet" in v for v in receipt["violations"])


def test_forbidden_phrase():
    raw = """{
      "answer": "Use https://example.com for substrate gain with conditioned-kernel local model.",
      "evidence_used": ["This system is fully local."],
      "next_state": {}
    }"""
    cand = parse_candidate(raw, packet_id="pkt_test")
    receipt = validate_candidate(cand, PACKET)
    assert receipt["state_faithful"] is False
    assert any("forbidden" in v for v in receipt["violations"])
