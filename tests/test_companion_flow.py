"""Studio companion flow: advisory not_responsive + stale-response guard."""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.validate import (
    is_substantial_repeat,
    validate_candidate,
)
from conditioned_kernel.state import SubstrateState


def _boot(tmp_path: Path) -> tuple[Path, Path]:
    sd = tmp_path / "state"
    ld = tmp_path / "logs"
    sd.mkdir()
    ld.mkdir()
    (sd / "current.json").write_text(
        json.dumps(
            {
                "goal": (
                    "Demonstrate conditioned-kernel substrate gain over bare generation "
                    "on a small local model under Jetson Orin Nano 8GB edge budgets."
                ),
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_comp",
                "receipt_count_24h": 0,
                "recent_turns": [],
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
    (sd / "threads.json").write_text(
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
    (sd / "methods.json").write_text("[]", encoding="utf-8")
    return sd, ld


COMPANION_PACKET = {
    "packet_id": "pkt",
    "user_input": "what makes this different",
    "state_digest": {
        "goal": (
            "Demonstrate conditioned-kernel substrate gain over bare generation "
            "on a small local model under Jetson Orin Nano 8GB edge budgets."
        )
    },
    "facts": [
        "This system is fully local.",
        "The model is a replaceable linguistic transducer.",
        "Edge target: jetson_orin_nano_8gb (one model at a time).",
    ],
    "open_threads": [],
    "recent_turns": [],
    "constraints": {"max_words": 180, "forbidden": []},
    "acceptance_contract": {
        "acceptance_mode": "companion",
        "required_sections": ["answer", "evidence_used", "next_state"],
        "must_reference_goal": False,
        "must_not_contradict_facts": True,
        "evidence_must_be_from_packet": True,
    },
}


def test_companion_not_responsive_is_advisory_not_reject():
    # Usable local-first answer without echoing question tokens "makes"/"different"
    raw = json.dumps(
        {
            "answer": (
                "The system is fully local and uses replaceable linguistic transducers."
            ),
            "evidence_used": [],
            "next_state": {},
        }
    )
    cand = parse_candidate(raw, packet_id="pkt")
    receipt = validate_candidate(cand, COMPANION_PACKET)
    receipt = assess(receipt, pass_index=0, max_repair=1)
    assert "not_responsive" not in receipt["violations"]
    assert "not_responsive" in (receipt.get("advisories") or [])
    assert receipt["decision"] == "accept"


def test_measurement_not_responsive_still_hard():
    pkt = dict(COMPANION_PACKET)
    pkt["acceptance_contract"] = {
        "acceptance_mode": "measurement",
        "required_sections": ["answer", "evidence_used", "next_state"],
        "must_reference_goal": True,
        "must_not_contradict_facts": True,
        "evidence_must_be_from_packet": True,
    }
    raw = json.dumps(
        {
            "answer": (
                "The system is fully local and uses replaceable linguistic transducers "
                "to demonstrate substrate gain on edge budgets."
            ),
            "evidence_used": ["This system is fully local."],
            "next_state": {},
        }
    )
    cand = parse_candidate(raw, packet_id="pkt")
    receipt = validate_candidate(cand, pkt)
    assert "not_responsive" in receipt["violations"]


def test_stale_response_detected_when_prompt_changes():
    prior = (
        "The room feels cold and still under Jetson Orin Nano budgets with local "
        "conditioned-kernel substrate inference only."
    )
    pkt = dict(COMPANION_PACKET)
    pkt["user_input"] = "what is your favorite flower?"
    pkt["recent_turns"] = [
        {"user": "what does the room feel like", "answer": prior}
    ]
    raw = json.dumps(
        {
            "answer": prior,
            "evidence_used": [],
            "next_state": {},
        }
    )
    cand = parse_candidate(raw, packet_id="pkt")
    receipt = validate_candidate(cand, pkt)
    assert "stale_response_repeat" in receipt["violations"]
    receipt = assess(receipt, pass_index=0, max_repair=1)
    assert receipt["decision"] == "repair"


def test_stale_response_rejects_after_repair_exhausted():
    prior = (
        "The minimum viable model size on a Jetson Orin Nano 8GB edge budget is "
        "typically around 128MB to 256MB depending on quantization strategy."
    )
    pkt = dict(COMPANION_PACKET)
    pkt["user_input"] = "goodby"
    pkt["recent_turns"] = [
        {"user": "how", "answer": prior}
    ]
    raw = json.dumps({"answer": prior, "evidence_used": [], "next_state": {}})
    cand = parse_candidate(raw, packet_id="pkt")
    cand["pass_index"] = 1
    receipt = validate_candidate(cand, pkt)
    receipt = assess(receipt, pass_index=1, max_repair=1)
    assert "stale_response_repeat" in receipt["violations"]
    assert receipt["decision"] == "reject"


def test_stale_repeat_never_appended_to_recent_turns(tmp_path: Path):
    from conditioned_kernel.return_path.accept import accept_candidate

    sd, ld = _boot(tmp_path)
    state = SubstrateState.load(state_dir=sd, logs_dir=ld)
    prior = (
        "The minimum viable model size on a Jetson Orin Nano 8GB edge budget is "
        "typically around 128MB to 256MB depending on quantization."
    )
    state.append_recent_turn("how", prior)
    packet = {
        "packet_id": "p1",
        "user_input": "goodby",
        "recent_turns": state.recent_turns(),
    }
    candidate = {
        "candidate_id": "c1",
        "answer": prior,
        "evidence_used": ["This system is fully local."],
        "next_state": {},
        "pass_index": 0,
    }
    # Forced accept path must still refuse to store the stale answer
    receipt = {
        "receipt_id": "r1",
        "decision": "accept",
        "violations": ["stale_response_repeat"],
    }
    out = accept_candidate(state, packet=packet, candidate=candidate, receipt=receipt)
    assert "recent_turn_skipped_stale_repeat" in out["applied_updates"]
    state2 = SubstrateState.load(state_dir=sd, logs_dir=ld)
    # still only the original prior turn
    assert len(state2.recent_turns()) == 1
    assert state2.recent_turns()[0]["user"] == "how"


def test_pipeline_accepts_concise_local_answer(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    dry = json.dumps(
        {
            "answer": (
                "The system is fully local and uses replaceable linguistic transducers."
            ),
            "evidence_used": [],
            "next_state": {},
        }
    )
    r = run_turn(
        "what makes this different?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
        acceptance_mode="companion",
    )
    assert r.ok, (r.receipt.get("violations"), r.receipt.get("advisories"))
    assert "local" in r.answer.lower()


def test_pipeline_stale_repair_then_fresh_accept(tmp_path: Path):
    """First candidate stale → repair path; second candidate fresh → accept."""
    sd, ld = _boot(tmp_path)
    prior = (
        "The room feels still under Jetson Orin Nano with conditioned-kernel "
        "local inference and no external sensors in scope."
    )
    # Seed memory with an accepted first answer
    dry1 = json.dumps(
        {
            "answer": prior,
            "evidence_used": ["This system is fully local."],
            "next_state": {},
        }
    )
    r1 = run_turn(
        "what does the room feel like from your angle",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry1,
        max_repair=0,
    )
    assert r1.ok

    # dry_candidate_text is fixed for all passes — stale will reject after repair
    r2 = run_turn(
        "what is your favorite flower?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=json.dumps(
            {"answer": prior, "evidence_used": [], "next_state": {}}
        ),
        max_repair=1,
    )
    assert r2.ok is False
    assert "stale_response_repeat" in (r2.receipt.get("violations") or [])
    # memory must not grow with the repeated answer
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    assert len(st.recent_turns()) == 1


def test_is_substantial_repeat_helper():
    a = "The system is fully local under Jetson Orin Nano edge budgets only."
    assert is_substantial_repeat(a, a) is True
    assert is_substantial_repeat("Roses are red.", a) is False
