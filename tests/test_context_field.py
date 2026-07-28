"""Structural tests for companion context-field selection.

Assert architecture, not exact model wording.
"""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.compile import build_arrival_packet, compile_turn
from conditioned_kernel.context_field import detect_intents
from conditioned_kernel.state import SubstrateState


def _boot(tmp_path: Path) -> SubstrateState:
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "current.json").write_text(
        json.dumps(
            {
                "goal": (
                    "Demonstrate conditioned-kernel substrate gain over bare generation "
                    "on a small local model under Jetson Orin Nano 8GB edge budgets."
                ),
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_cf",
                "receipt_count_24h": 0,
                "recent_turns": [
                    {
                        "user": "what does the room feel like",
                        "answer": (
                            "The room feels still under Jetson Orin Nano with "
                            "conditioned-kernel local inference and sensors out of scope "
                            "for substrate gain demonstration."
                        ),
                    }
                ],
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
    return SubstrateState.load(state_dir=sd, logs_dir=tmp_path / "logs")


def _selected_ids(packet: dict) -> set[str]:
    field = packet.get("context_field") or {}
    return set(field.get("selected_ids") or [])


def test_social_greeting_withholds_project_state(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(st, "suuppp", acceptance_mode="companion")
    ids = _selected_ids(packet)
    assert "input.current" in ids
    # Must not auto-select hardware / goal / threads / repair budget
    assert "state.edge.target" not in ids
    assert "state.goal" not in ids
    assert "state.runtime.repair_budget" not in ids
    assert not any(i.startswith("state.thread.") for i in ids)
    assert packet["facts"] == []
    assert packet["open_threads"] == []


def test_emotional_statement_withholds_hardware(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(
        st, "man i really don't like AI", acceptance_mode="companion"
    )
    ids = _selected_ids(packet)
    assert "state.edge.target" not in ids
    assert "state.goal" not in ids


def test_purpose_question_selects_concise_purpose(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(
        st, "what does this system do?", acceptance_mode="companion"
    )
    ids = _selected_ids(packet)
    assert "state.identity" in ids or "state.goal" in ids
    assert "state.policy.local" in ids or "state.identity" in ids
    # Not every open experimental thread by default
    assert "state.runtime.repair_budget" not in ids


def test_runtime_question_selects_model(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(st, "what model is this", acceptance_mode="companion")
    ids = _selected_ids(packet)
    assert "state.runtime.model" in ids


def test_hardware_question_selects_edge(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(st, "what is a Jetson", acceptance_mode="companion")
    ids = _selected_ids(packet)
    assert "state.edge.target" in ids


def test_topic_change_does_not_force_stale_assistant(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(
        st, "what is your favorite flower?", acceptance_mode="companion"
    )
    # Boilerplate prior assistant monologue should be omitted on topic change
    field = packet.get("context_field") or {}
    omitted_reasons = [
        r.get("reason")
        for r in (field.get("selection_records") or [])
        if not r.get("selected")
    ]
    assert any(
        "boilerplate" in (r or "") or "not_relevant" in (r or "") or "social" in (r or "")
        for r in omitted_reasons
    )


def test_measurement_mode_keeps_full_fact_list(tmp_path: Path):
    st = _boot(tmp_path)
    packet = build_arrival_packet(st, "suuppp", acceptance_mode="measurement")
    assert len(packet["facts"]) >= 5
    assert any("Jetson" in f or "jetson" in f.lower() or "Edge target" in f for f in packet["facts"])
    assert packet["context_field"].get("mode") == "measurement_full"


def test_companion_model_input_anchors_current_message(tmp_path: Path):
    st = _boot(tmp_path)
    packet, mi = compile_turn(st, "hello friend", acceptance_mode="companion")
    msgs = mi["payload"]["messages"]
    user = [m for m in msgs if m["role"] == "user"][0]["content"]
    assert "## Current human message" in user
    assert "hello friend" in user
    # Current message appears after selected context block
    assert user.index("## Selected context") < user.index("## Current human message")


def test_tracing_off_same_compile(tmp_path: Path):
    st = _boot(tmp_path)
    a = build_arrival_packet(st, "what model is this", acceptance_mode="companion")
    b = build_arrival_packet(st, "what model is this", acceptance_mode="companion")
    # strip volatile ids
    for p in (a, b):
        p.pop("packet_id", None)
        p.pop("created_at", None)
        if p.get("_edge"):
            p["_edge"] = {k: v for k, v in p["_edge"].items() if k != "packet_bytes"}
    # intents and selected facts should match
    assert a["intents"] == b["intents"]
    assert a["facts"] == b["facts"]
    assert a["context_field"]["selected_ids"] == b["context_field"]["selected_ids"]


def test_detect_intents_not_exact_prompt_table():
    assert "social" in detect_intents("suuppp")
    assert "purpose" in detect_intents("what does this system do?")
    assert "runtime" in detect_intents("what model is this")
    assert "edge" in detect_intents("tell me about the Jetson board")
