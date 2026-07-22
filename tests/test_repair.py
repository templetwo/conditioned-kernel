from conditioned_kernel.return_path.repair import build_repair_plan
from conditioned_kernel.return_path.validate import validate_candidate
from conditioned_kernel.return_path.parse import parse_candidate

PACKET = {
    "packet_id": "pkt_r",
    "state_digest": {
        "goal": "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model under Jetson Orin Nano 8GB edge budgets."
    },
    "facts": [
        "This system is fully local.",
        "Edge target: jetson_orin_nano_8gb (one model at a time).",
    ],
    "open_threads": [
        {"id": "thread_min_model", "title": "What is the minimum viable model size?"}
    ],
    "constraints": {"max_words": 120, "forbidden": ["https://"]},
    "acceptance_contract": {
        "required_sections": ["answer", "evidence_used", "next_state"],
        "must_reference_goal": True,
    },
}


def test_repair_plan_has_actionable_hints():
    raw = '{"answer":"hello only","evidence_used":["invented"],"next_state":{"thread_touch":["ids used"]}}'
    cand = parse_candidate(raw, packet_id="pkt_r")
    receipt = validate_candidate(cand, PACKET)
    plan = build_repair_plan(receipt, cand, PACKET)
    assert plan["allowed_thread_ids"] == ["thread_min_model"]
    assert plan["goal_snippet"]
    assert any("goal_not_referenced" in h or "FIX goal" in h for h in plan["hints"])
    assert any("evidence" in h.lower() for h in plan["hints"])
    # junk thread_touch should not appear as unknown_thread_touch
    assert not any(v.startswith("unknown_thread_touch") for v in receipt["violations"])


def test_junk_thread_touch_ignored():
    raw = (
        '{"answer":"Demonstrate conditioned-kernel substrate gain on Jetson Orin Nano edge budgets.",'
        '"evidence_used":["This system is fully local."],'
        '"next_state":{"thread_touch":["ids used"]}}'
    )
    cand = parse_candidate(raw, packet_id="pkt_r")
    receipt = validate_candidate(cand, PACKET)
    assert receipt["state_faithful"] is True or "goal_not_referenced" not in str(
        receipt.get("violations")
    )
    # at least no unknown_thread_touch for junk
    assert not any("unknown_thread_touch" in v for v in receipt["violations"])


def test_normalized_thread_touch_with_prefix():
    raw = (
        '{"answer":"Demonstrate conditioned-kernel substrate gain on Jetson Orin Nano edge budgets.",'
        '"evidence_used":["This system is fully local."],'
        '"next_state":{"thread_touch":["[0] thread_min_model"]}}'
    )
    cand = parse_candidate(raw, packet_id="pkt_r")
    receipt = validate_candidate(cand, PACKET)
    assert not any("unknown_thread_touch" in v for v in receipt["violations"])


def test_template_echo_rejected():
    raw = (
        '{"answer":"(short reply that mentions: Demonstrate conditioned-kernel)",'
        '"evidence_used":["STRING_FROM_FACTS"],'
        '"next_state":{"thread_touch":[]}}'
    )
    cand = parse_candidate(raw, packet_id="pkt_r")
    receipt = validate_candidate(cand, PACKET)
    assert "template_echo" in receipt["violations"] or "template_echo_evidence" in receipt[
        "violations"
    ]
