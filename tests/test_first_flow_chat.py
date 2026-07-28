"""Studio first-flow: recent_turns + chat surface. No Ollama required."""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.cli import build_parser
from conditioned_kernel.compile import build_arrival_packet
from conditioned_kernel.edge import load_profile, packet_byte_size
from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.state import (
    RECENT_TURNS_MAX_BYTES,
    SubstrateState,
    fit_recent_turns,
    recent_turns_byte_size,
)


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": (
                    "Demonstrate conditioned-kernel substrate gain over bare generation "
                    "on a small local model under Jetson Orin Nano 8GB edge budgets."
                ),
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_test",
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


def _dry_candidate(answer: str) -> str:
    return json.dumps(
        {
            "answer": answer,
            "evidence_used": [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": ["thread_min_model"]},
        }
    )


def test_chat_command_registered():
    p = build_parser()
    for a in p._actions:
        if getattr(a, "choices", None) and isinstance(a.choices, dict):
            assert "chat" in a.choices
            return
    raise AssertionError("chat subcommand missing")


def test_fit_recent_turns_byte_cap_drops_oldest():
    long_ans = "x" * 400
    turns = [
        {"user": f"q{i}", "answer": long_ans, "ts": f"t{i}"} for i in range(10)
    ]
    fitted = fit_recent_turns(turns, max_bytes=RECENT_TURNS_MAX_BYTES)
    assert recent_turns_byte_size(fitted) <= RECENT_TURNS_MAX_BYTES
    assert len(fitted) < len(turns)
    # newest retained
    if fitted:
        assert fitted[-1]["user"] == "q9"


def test_single_huge_turn_cannot_exceed_budget():
    huge = "Z" * 50_000
    fitted = fit_recent_turns(
        [{"user": huge, "answer": huge}],
        max_bytes=RECENT_TURNS_MAX_BYTES,
    )
    assert recent_turns_byte_size(fitted) <= RECENT_TURNS_MAX_BYTES


def test_accept_appends_recent_turn(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    dry = _dry_candidate(
        "Design intent is edge-first substrate conditioning under Jetson budgets "
        "with local models and file continuity."
    )
    r1 = run_turn(
        "Summarize design intent for tonight.",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert r1.ok
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    turns = state.recent_turns()
    assert len(turns) == 1
    assert "Summarize design intent" in turns[0]["user"]
    assert "edge-first" in turns[0]["answer"].lower()


def test_turn_two_packet_includes_turn_one(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    dry1 = _dry_candidate(
        "Tonight we prove substrate gain on a small local model under Orin budgets."
    )
    r1 = run_turn(
        "What should we try first tonight on the Orin?",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry1,
        max_repair=0,
    )
    assert r1.ok

    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    packet = build_arrival_packet(
        state,
        "What did I just decide to try first?",
        profile=load_profile("orin_nano_8gb"),
    )
    assert packet.get("recent_turns")
    assert any(
        "Orin" in str(t.get("answer") or "") or "substrate" in str(t.get("answer") or "").lower()
        for t in packet["recent_turns"]
    )
    # Stay under edge packet budget
    size = packet_byte_size(
        {k: v for k, v in packet.items() if not str(k).startswith("_")}
    )
    assert size <= load_profile("orin_nano_8gb").max_packet_bytes


def test_new_session_clears_recent_turns(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    state.append_recent_turn("hello", "world remembered")
    assert state.recent_turns()
    old = state.current["session_id"]
    new_id = state.begin_new_session()
    state2 = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    assert state2.recent_turns() == []
    assert state2.current["session_id"] == new_id
    assert new_id != old


def test_companion_accepts_empty_evidence_with_substrate_supply(tmp_path: Path):
    """Earned Studio fix: Laboratory evidence demand must not block conversation."""
    state_dir, logs_dir = _bootstrap(tmp_path)
    # Model returned JSON but empty evidence_used — the live failure mode.
    dry = json.dumps(
        {
            "answer": (
                "The goal is demonstrating substrate gain on a small local model "
                "under Jetson Orin edge budgets."
            ),
            "evidence_used": [],
            "next_state": {},
        }
    )
    result = run_turn(
        "What is the goal we are working toward?",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        max_repair=0,
        acceptance_mode="companion",
    )
    assert result.ok is True, result.receipt.get("violations")
    assert result.decision == "accept"
    assert result.candidate.get("evidence_source") == "substrate_supplied"
    assert result.candidate.get("evidence_used")
    # recent_turns only appends on accept — B can engage
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    assert len(state.recent_turns()) == 1


def test_measurement_still_rejects_empty_evidence(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    dry = json.dumps(
        {
            "answer": (
                "The goal is demonstrating substrate gain on a small local model "
                "under Jetson Orin edge budgets."
            ),
            "evidence_used": [],
            "next_state": {},
        }
    )
    result = run_turn(
        "What is the goal we are working toward?",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        max_repair=0,
        acceptance_mode="measurement",
    )
    assert result.ok is False
    assert "evidence_used_empty" in (result.receipt.get("violations") or [])


def test_many_long_turns_still_compile_under_budget(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    for i in range(20):
        state.append_recent_turn(
            "Q" * 300 + str(i),
            "A" * 500 + f" turn {i} substrate jetson orin kernel",
        )
    assert recent_turns_byte_size(state.recent_turns()) <= RECENT_TURNS_MAX_BYTES
    packet = build_arrival_packet(
        state,
        "Continue from earlier.",
        profile=load_profile("orin_nano_8gb"),
        enforce_budget=True,
    )
    size = packet["_edge"]["packet_bytes"]
    assert size <= load_profile("orin_nano_8gb").max_packet_bytes
