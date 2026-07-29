"""The think flag must reach every Ollama payload, explicitly.

Wire-probed 2026-07-29 on qwen3.5:0.8b: with think=false the model answers a
one-sentence question in ~1s with zero thinking chars; with think=true, and
with the flag omitted (runtime default), it produced no response within 240s.
Losing this flag from any payload builder silences the companion. These tests
pin the flag's presence and honesty in both builders so a refactor cannot
drop it without failing loudly.
"""

from conditioned_kernel.compile import build_arrival_packet, build_model_input
from conditioned_kernel.flow import FieldBefore, build_flow_model_input
from conditioned_kernel.state import SubstrateState


def _minimal_packet(tmp_path) -> dict:
    state = SubstrateState.load(
        state_dir=tmp_path / "state", logs_dir=tmp_path / "logs"
    )
    return build_arrival_packet(state, "hello")


def _minimal_field() -> FieldBefore:
    return FieldBefore(
        current_message="hello",
        intents=(),
        selected=[],
        relevant_canonical=[],
        candidate_pool_size=0,
        live_element_count=0,
        byte_budget=1400,
        selected_bytes=0,
    )


def test_pipeline_payload_carries_explicit_think_false(tmp_path):
    payload = build_model_input(_minimal_packet(tmp_path), model="qwen3.5:0.8b")
    assert payload["think"] is False


def test_pipeline_payload_honors_profile_think_value(tmp_path):
    payload = build_model_input(
        _minimal_packet(tmp_path), model="qwen3.5:0.8b", think=True
    )
    assert payload["think"] is True


def test_flow_payload_carries_explicit_think_false():
    model_input = build_flow_model_input(
        _minimal_field(),
        model="qwen3.5:0.8b",
        keep_alive="2m",
        think=False,
        temperature=0.3,
        seed=42,
        num_ctx=2048,
    )
    payload = model_input["payload"]
    assert payload["think"] is False
    assert "format" not in payload
