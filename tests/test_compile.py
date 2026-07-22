import json
from pathlib import Path

from conditioned_kernel.compile import build_arrival_packet, build_model_input, packet_hash
from conditioned_kernel.state import SubstrateState


def test_compile_packet_shape(tmp_path: Path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": "Demo goal",
                "active_profile": "ck_v0",
                "session_id": "sess_x",
                "flags": {"sensors": False, "max_repair_passes": 1},
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text("[]", encoding="utf-8")
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")

    state = SubstrateState.load(state_dir=state_dir, logs_dir=tmp_path / "logs")
    packet = build_arrival_packet(state, "hello")
    assert packet["user_input"] == "hello"
    assert "packet_id" in packet
    assert "facts" in packet
    assert packet["acceptance_contract"]["must_reference_goal"] is True

    mi = build_model_input(packet, model="qwen2.5:0.5b", mode="chat_json")
    assert mi["mode"] == "chat_json"
    assert mi["payload"]["stream"] is False
    assert mi["packet_hash"] == packet_hash(packet)

    raw = build_model_input(packet, model="qwen2.5:0.5b", mode="generate_raw")
    assert raw["payload"]["raw"] is True


def test_model_input_is_reproducible_across_builds(tmp_path: Path):
    """Same state + same input must yield a byte-identical prompt.

    packet_id and created_at change on every build. While they were serialized
    into the model input, generation could not be reproduced even at fixed
    temperature and seed, because the prompt itself differed run to run — the
    matrix headline flipped sign between two back-to-back runs.
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps({"goal": "Test goal for reproducibility.", "flags": {}})
    )
    (state_dir / "threads.json").write_text(json.dumps([]))
    state = SubstrateState.load(state_dir=state_dir, logs_dir=tmp_path / "logs")

    a = build_arrival_packet(state, "Same question?")
    b = build_arrival_packet(state, "Same question?")
    # The packets differ by construction...
    assert a["packet_id"] != b["packet_id"]
    # ...but what reaches the model must not.
    ma = build_model_input(a, model="m", num_ctx=2048)
    mb = build_model_input(b, model="m", num_ctx=2048)
    assert ma["payload"] == mb["payload"]
