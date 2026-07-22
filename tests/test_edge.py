import json
from pathlib import Path

import pytest

from conditioned_kernel.compile import build_arrival_packet, compile_turn
from conditioned_kernel.edge import (
    BudgetError,
    DEFAULT_PROFILE_ID,
    enforce_packet_budget,
    load_profile,
    packet_byte_size,
)
from conditioned_kernel.state import SubstrateState


def _minimal_state(tmp_path: Path) -> SubstrateState:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model.",
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_edge",
                "flags": {"sensors": False, "tools": False, "cloud": False, "max_repair_passes": 1},
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text(
        json.dumps(
            [
                {"id": f"t{i}", "status": "open", "title": f"Thread number {i} " + ("x" * 80)}
                for i in range(12)
            ]
        ),
        encoding="utf-8",
    )
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    return SubstrateState.load(state_dir=state_dir, logs_dir=tmp_path / "logs")


def test_default_profile_is_orin_nano():
    assert DEFAULT_PROFILE_ID == "orin_nano_8gb"
    p = load_profile()
    assert p.profile_id == "orin_nano_8gb"
    assert p.num_ctx == 2048
    assert p.one_model_only is True
    assert p.stream is False
    assert p.cloud is False


def test_packet_trimmed_to_edge_bounds(tmp_path: Path):
    state = _minimal_state(tmp_path)
    prof = load_profile("orin_nano_tight")
    packet = build_arrival_packet(
        state,
        "hello",
        profile=prof,
        enforce_budget=True,
    )
    assert len(packet["open_threads"]) <= prof.max_open_threads
    assert len(packet["facts"]) <= prof.max_facts
    assert packet["_edge"]["packet_bytes"] <= prof.max_packet_bytes
    assert packet["constraints"]["max_words"] <= prof.max_answer_words


def test_compile_uses_edge_ctx_and_keep_alive(tmp_path: Path):
    state = _minimal_state(tmp_path)
    packet, mi = compile_turn(state, "summarize intent", profile_id="orin_nano_8gb")
    assert mi["payload"]["options"]["num_ctx"] == 2048
    assert mi["payload"]["keep_alive"] == "2m"
    assert mi["payload"]["stream"] is False
    # compact serialization (no pretty indent in user content)
    content = mi["payload"]["messages"][1]["content"]
    # Compact JSON: no pretty-printed 2-space indent blocks
    assert "\n  \"" not in content
    assert packet["_edge"]["profile_id"] == "orin_nano_8gb"


def test_budget_error_when_impossible():
    from dataclasses import replace

    prof = replace(load_profile("orin_nano_tight"), max_packet_bytes=80, max_facts=1, max_open_threads=1)
    huge = {
        "packet_id": "x" * 40,
        "facts": ["f" * 200],
        "open_threads": [{"id": "a", "title": "t" * 120}],
        "state_digest": {"goal": "g" * 240},
        "constraints": {"max_words": 80},
        "user_input": "u" * 800,
        "acceptance_contract": {"required_sections": ["answer", "evidence_used", "next_state"]},
    }
    with pytest.raises(BudgetError):
        enforce_packet_budget(huge, prof, strict=True)


def test_packet_byte_size_stable():
    p = {"a": 1, "b": ["x"]}
    assert packet_byte_size(p) == len(json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode())
