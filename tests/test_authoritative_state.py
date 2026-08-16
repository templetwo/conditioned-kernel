"""Studio authoritative-state path. No Ollama. Measurement mode untouched."""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.authoritative_state import (
    classify_state_question,
    resolve_obligation,
)
from conditioned_kernel.edge import load_profile
from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.state import DEFAULT_DESIGN_INTENT, SubstrateState


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
                "design_intent": DEFAULT_DESIGN_INTENT,
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_auth",
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
                },
                {
                    "id": "thread_compile_order",
                    "status": "open",
                    "title": "Which compile ordering maximizes state-faithfulness?",
                },
            ]
        ),
        encoding="utf-8",
    )
    (sd / "methods.json").write_text("[]", encoding="utf-8")
    return sd, ld


def test_classify_live_shapes():
    assert classify_state_question("What is the goal we're working toward?") == "goal"
    assert classify_state_question("Name the primary research goal.") == "goal"
    assert (
        classify_state_question("In plain language, what is the design intent right now?")
        == "design_intent"
    )
    assert classify_state_question("What are we building?") == "design_intent"
    assert classify_state_question("What are we working toward?") == "design_intent"
    assert (
        classify_state_question("Which model or edge target are we using?")
        == "edge_or_model"
    )
    assert classify_state_question("Are cloud services allowed?") == "cloud_policy"
    assert classify_state_question("What are the current open threads?") == "open_threads"
    assert classify_state_question("What was the codeword?") == "recent_recall"
    # Store imperatives are open-generative, not recall
    assert classify_state_question("Remember the codeword FALCON-9-DELTA.") is None
    # Mere mention of Orin is not an edge-state question
    assert (
        classify_state_question("What should we try first tonight on the Orin?") is None
    )
    assert classify_state_question("Write a haiku about rivers") is None


def test_goal_fallback_on_question_echo(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    # Model just echoes the question — substrate must not accept that.
    dry = json.dumps(
        {
            "answer": "What is the goal we're working toward?",
            "evidence_used": [],
            "next_state": {},
        }
    )
    r = run_turn(
        "What is the goal we're working toward?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
        acceptance_mode="companion",
    )
    assert r.ok, r.receipt.get("violations")
    assert "substrate" in r.answer.lower() or "goal" in r.answer.lower()
    assert "demonstrate" in r.answer.lower() or "conditioned" in r.answer.lower()
    assert r.candidate.get("authoritative_fallback") is True
    assert r.answer.lower() != "what is the goal we're working toward?"


def test_edge_target_not_substituted_for_goal(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    dry = json.dumps(
        {
            "answer": "The goal is jetson_orin_nano_8gb.",
            "evidence_used": [],
            "next_state": {},
        }
    )
    r = run_turn(
        "What is the goal we are working toward?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert r.ok
    # Must include real goal content, not only edge id
    assert "jetson_orin_nano_8gb" not in r.answer or "substrate" in r.answer.lower()
    assert any(
        tok in r.answer.lower()
        for tok in ("substrate", "demonstrate", "conditioned", "generation")
    )


def test_cloud_false_cannot_become_yes(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    dry = json.dumps(
        {
            "answer": "Yes, cloud services are allowed.",
            "evidence_used": [],
            "next_state": {},
        }
    )
    r = run_turn(
        "Are cloud services allowed?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert r.ok
    assert "not allowed" in r.answer.lower() or "local" in r.answer.lower()
    assert "are allowed" not in r.answer.lower() or "not" in r.answer.lower()
    assert r.candidate.get("authoritative_fallback") is True


def test_open_threads_from_state(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    dry = json.dumps({"answer": "I don't know.", "evidence_used": [], "next_state": {}})
    r = run_turn(
        "What are the current open threads?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert r.ok
    assert "thread_min_model" in r.answer
    assert "thread_compile_order" in r.answer


def test_codeword_recall_after_dialogue(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    # Turn 1: open-generative remember (not authoritative)
    dry1 = json.dumps(
        {
            "answer": "Got it — I'll remember FALCON-9-DELTA for this session.",
            "evidence_used": ["This system is fully local."],
            "next_state": {},
        }
    )
    r1 = run_turn(
        "Remember the codeword FALCON-9-DELTA.",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry1,
        max_repair=0,
    )
    assert r1.ok, r1.receipt.get("violations")
    state = SubstrateState.load(state_dir=sd, logs_dir=ld)
    assert any("FALCON" in str(t) for t in state.recent_turns())

    # Turn 2: open generative filler (must remain responsive for companion accept)
    dry2 = json.dumps(
        {
            "answer": "Ready — standing by for the next step on the local edge path.",
            "evidence_used": ["This system is fully local."],
            "next_state": {},
        }
    )
    r2 = run_turn(
        "Stay ready for the next step.",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry2,
        max_repair=0,
    )
    assert r2.ok, r2.receipt.get("violations")

    # Turn 3: recall — even if model fails, substrate answers from recent_turns
    dry3 = json.dumps(
        {
            "answer": "What was the codeword?",
            "evidence_used": [],
            "next_state": {},
        }
    )
    r3 = run_turn(
        "What was the codeword?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry3,
        max_repair=0,
    )
    assert r3.ok, r3.receipt.get("violations")
    assert "FALCON-9-DELTA" in r3.answer


def test_measurement_mode_skips_authoritative(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    dry = json.dumps(
        {
            "answer": "Yes, cloud services are allowed.",
            "evidence_used": [],
            "next_state": {},
        }
    )
    r = run_turn(
        "Are cloud services allowed?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
        acceptance_mode="measurement",
    )
    # Measurement still fails empty evidence — no companion authoritative rescue
    assert r.ok is False
    assert "evidence_used_empty" in (r.receipt.get("violations") or [])


def test_model_phrasing_kept_when_claims_present(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    dry = json.dumps(
        {
            "answer": (
                "Cloud services are not allowed; this stack is fully local-only."
            ),
            "evidence_used": [],
            "next_state": {},
        }
    )
    r = run_turn(
        "Are cloud services allowed?",
        state_dir=sd,
        logs_dir=ld,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert r.ok
    assert r.candidate.get("authoritative_fallback") is False
    assert "local" in r.answer.lower()


def test_resolve_obligation_fields(tmp_path: Path):
    sd, ld = _boot(tmp_path)
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    prof = load_profile("orin_nano_8gb")
    ob = resolve_obligation(
        st, "Which board are we running it on?", profile=prof, model=prof.model
    )
    assert ob is not None
    assert ob.kind == "edge_or_model"
    assert "jetson_orin_nano_8gb" in " ".join(ob.required_substrings)


def test_recent_recall_skips_cue_probe_and_keeps_correct_kernel_answer(tmp_path: Path):
    """Turn-15 shape: later 'codeword' probes must not override a correct kernel.

    History has the injection plus cue-only user lines (confirm / later).
    A kernel answer that only carries the codeword must be kept; the fallback
    must not paste an unlabeled user probe.
    """
    from conditioned_kernel.authoritative_state import (
        check_obligation,
        enforce_authoritative_candidate,
        resolve_obligation,
    )

    sd, ld = _boot(tmp_path)
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    st.current["recent_turns"] = [
        {
            "user": "Remember the session codeword FALCON-9-DELTA. Confirm you have it.",
            "answer": "Codeword noted: FALCON-9-DELTA. I will treat it as a continuity anchor.",
        },
        {
            "user": "Confirm the codeword one more time before we continue.",
            "answer": "Confirmed: FALCON-9-DELTA.",
        },
        {
            "user": "If I ask about the codeword later, what should you answer?",
            "answer": "",
        },
    ]
    st.save_current()
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)

    q = "If I ask about the codeword later, what should you answer?"
    ob = resolve_obligation(st, q, profile=load_profile("orin_nano_8gb"))
    assert ob is not None
    assert ob.kind == "recent_recall"
    assert "falcon-9-delta" in ob.required_substrings
    assert "confirm the codeword" not in ob.fallback_answer.lower()
    assert "FALCON-9-DELTA" in ob.fallback_answer
    assert "From earlier in this session:" not in ob.fallback_answer

    kernel = "The session codeword is FALCON-9-DELTA."
    assert check_obligation(kernel, ob, q) == []

    cand = {
        "parse_ok": True,
        "answer": kernel,
        "evidence_used": [],
        "pass_index": 0,
    }
    out, reasons = enforce_authoritative_candidate(
        cand, ob, user_input=q, packet_id="pkt_test"
    )
    assert reasons == []
    assert out.get("authoritative_fallback") is False
    assert out["answer"] == kernel


def test_recent_recall_fallback_uses_value_not_bare_user_cue(tmp_path: Path):
    """If the kernel fails, fallback answers with the value, not a cue line."""
    from conditioned_kernel.authoritative_state import (
        enforce_authoritative_candidate,
        resolve_obligation,
    )

    sd, ld = _boot(tmp_path)
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    st.current["recent_turns"] = [
        {
            "user": "Remember the session codeword FALCON-9-DELTA.",
            "answer": "Got it.",
        },
        {
            "user": "Confirm the codeword one more time before we continue.",
            "answer": "Standing by.",
        },
    ]
    st.save_current()
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)

    q = "What was the codeword?"
    ob = resolve_obligation(st, q, profile=load_profile("orin_nano_8gb"))
    assert ob is not None
    cand = {
        "parse_ok": True,
        "answer": "What was the codeword?",
        "evidence_used": [],
        "pass_index": 0,
    }
    out, reasons = enforce_authoritative_candidate(
        cand, ob, user_input=q, packet_id="pkt_test"
    )
    assert reasons
    assert out.get("authoritative_fallback") is True
    assert "FALCON-9-DELTA" in out["answer"]
    assert "Confirm the codeword" not in out["answer"]


def test_design_intent_paraphrase_keeps_model_phrasing(tmp_path: Path):
    """Owned-fact paraphrase must not be replaced for missing lexicon."""
    from conditioned_kernel.authoritative_state import (
        check_obligation,
        enforce_authoritative_candidate,
        resolve_obligation,
    )

    sd, ld = _boot(tmp_path)
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    q = "In plain language, what is the design intent right now?"
    ob = resolve_obligation(st, q, profile=load_profile("orin_nano_8gb"))
    assert ob is not None
    assert ob.kind == "design_intent"
    paraphrase = (
        "Put continuity and acceptance outside the model so a lean Jetson "
        "box can stay honest under a short context window."
    )
    assert check_obligation(paraphrase, ob, q) == []
    cand = {"parse_ok": True, "answer": paraphrase, "evidence_used": [], "pass_index": 0}
    out, reasons = enforce_authoritative_candidate(
        cand, ob, user_input=q, packet_id="pkt_intent"
    )
    assert reasons == []
    assert out.get("authoritative_fallback") is False
    assert out["answer"] == paraphrase


def test_design_intent_research_goal_paste_falls_back(tmp_path: Path):
    """Answering 'what are we building?' with the experiment abstract is wrong."""
    from conditioned_kernel.authoritative_state import (
        enforce_authoritative_candidate,
        resolve_obligation,
    )

    sd, ld = _boot(tmp_path)
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    q = "What are we building?"
    ob = resolve_obligation(st, q, profile=load_profile("orin_nano_8gb"))
    assert ob is not None
    assert ob.kind == "design_intent"
    goal = str(st.current["goal"])
    cand = {"parse_ok": True, "answer": goal, "evidence_used": [], "pass_index": 0}
    out, reasons = enforce_authoritative_candidate(
        cand, ob, user_input=q, packet_id="pkt_intent"
    )
    assert "authoritative_wrong_claim" in reasons
    assert out.get("authoritative_fallback") is True
    assert "companion" in out["answer"].lower() or "riverbed" in out["answer"].lower()
    assert "The current goal is:" not in out["answer"]


def test_design_intent_empty_and_echo_fall_back(tmp_path: Path):
    from conditioned_kernel.authoritative_state import (
        check_obligation,
        resolve_obligation,
    )

    sd, ld = _boot(tmp_path)
    st = SubstrateState.load(state_dir=sd, logs_dir=ld)
    q = "What is the design intent?"
    ob = resolve_obligation(st, q, profile=load_profile("orin_nano_8gb"))
    assert ob is not None
    assert "authoritative_empty_answer" in check_obligation("", ob, q)
    assert "authoritative_question_echo" in check_obligation(q, ob, q)
    miss = "Something about local models in general."
    assert "authoritative_missing_claim" in check_obligation(miss, ob, q)
