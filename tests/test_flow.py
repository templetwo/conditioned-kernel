"""Studio Flow mode: field engine + turn path. No Ollama required.

Covers: field composition (current message primacy, byte-bounded live
elements, canonical state entering only when relevant), the flow prompt
(no schema, no evidence requirement), the no-accept/reject speech path
(every nonempty generation displayed; empty/transport-failure gets an
honest terminal message), post-hoc observations (repetition,
project-language dominance, low responsiveness, contradiction,
authoritative-topic disclosure -- all non-blocking), integration
(strengthen/create/decay/soften/carry), FlowTrace JSON-serializability,
and the `state/flow_field.json` / `current.json` / `threads.json`
isolation the hard rules require.
"""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.cli import build_parser
from conditioned_kernel.flow import (
    FLOW_EMPTY_MESSAGE,
    FLOW_TRANSPORT_MESSAGE,
    FieldBefore,
    FlowElement,
    FlowField,
    clear_flow_field,
    compose_field,
    flow_field_path,
    flow_trace_path,
    integrate_field,
    run_flow_turn,
)
from conditioned_kernel.generate import InferenceResult, RunStatus
from conditioned_kernel.state import SubstrateState

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": GOAL,
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


class FakeClient:
    def __init__(self, result: InferenceResult) -> None:
        self._result = result

    def run(self, model_input: dict) -> InferenceResult:  # noqa: ARG002 - fixture stub
        return self._result


# ---------------------------------------------------------------------------
# CLI wiring: no --mode flag collision, other subcommands unaffected.
# ---------------------------------------------------------------------------


def test_cli_chat_accepts_mode_flow_without_flag_conflict():
    p = build_parser()
    args = p.parse_args(["chat", "--mode", "flow", "--new-session"])
    assert args.mode == "flow"
    assert args.new_session is True


def test_cli_other_subcommands_mode_flag_unaffected():
    p = build_parser()
    assert p.parse_args(["ask", "hi", "--mode", "chat_json"]).mode == "chat_json"
    assert p.parse_args(["chat", "--mode", "chat_json"]).mode == "chat_json"
    assert p.parse_args(["chat", "--mode", "generate_raw"]).mode == "generate_raw"
    assert p.parse_args(["smoke", "--dry"]).mode is None


# ---------------------------------------------------------------------------
# State isolation: flow_field.json is the only file this path ever writes
# under state/; current.json and threads.json stay byte-identical.
# ---------------------------------------------------------------------------


def test_flow_turn_never_touches_current_or_threads_json(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    before_current = (state_dir / "current.json").read_bytes()
    before_threads = (state_dir / "threads.json").read_bytes()

    result = run_flow_turn(
        "hello there",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Hey! Good to hear from you.",
    )
    assert result.ok is True
    assert (state_dir / "flow_field.json").exists()
    assert (state_dir / "current.json").read_bytes() == before_current
    assert (state_dir / "threads.json").read_bytes() == before_threads


def test_new_session_clears_only_flow_field(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    run_flow_turn("hello", state_dir=state_dir, logs_dir=logs_dir, dry_reply="hi!")
    assert flow_field_path(state_dir).exists()
    before_current = (state_dir / "current.json").read_bytes()
    before_threads = (state_dir / "threads.json").read_bytes()

    clear_flow_field(state_dir)

    assert not flow_field_path(state_dir).exists()
    assert (state_dir / "current.json").read_bytes() == before_current
    assert (state_dir / "threads.json").read_bytes() == before_threads

    # A fresh turn after clearing starts a fresh field (turn_count resets).
    run_flow_turn("hello again", state_dir=state_dir, logs_dir=logs_dir, dry_reply="hi again!")
    field = FlowField.load(flow_field_path(state_dir), session_id="sess_test")
    assert field.turn_count == 1


# ---------------------------------------------------------------------------
# Speech path: no accept/reject branch. Nonempty generation always
# displayed; empty / transport failure get an honest terminal message.
# ---------------------------------------------------------------------------


def test_nonempty_reply_always_displayed_verbatim(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    result = run_flow_turn(
        "what's on your mind",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Just thinking about how this conversation is unfolding.",
    )
    assert result.ok is True
    assert result.displayed_text == "Just thinking about how this conversation is unfolding."
    assert result.trace.raw_reply == result.displayed_text


def test_empty_reply_gets_honest_message_not_silence(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    result = run_flow_turn("...", state_dir=state_dir, logs_dir=logs_dir, dry_reply="")
    assert result.displayed_text == FLOW_EMPTY_MESSAGE
    assert result.trace.reply_status == "dry_run"


def test_transport_failure_gets_honest_message_not_silence(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    fake = FakeClient(
        InferenceResult(
            status=RunStatus.TRANSPORT_ERROR,
            output=None,
            error="Ollama unreachable at http://127.0.0.1:11434",
            elapsed_seconds=0.01,
            timeout_seconds=5.0,
        )
    )
    result = run_flow_turn("hello", state_dir=state_dir, logs_dir=logs_dir, client=fake)
    assert result.ok is False
    assert result.displayed_text == FLOW_TRANSPORT_MESSAGE.format(
        error="Ollama unreachable at http://127.0.0.1:11434"
    )
    assert result.trace.raw_reply is None
    assert result.trace.reply_status == "transport_error"


def test_flow_model_input_has_no_output_schema(tmp_path: Path):
    """Ask the kernel for ordinary language: no `format` key, no evidence
    requirement anywhere in the composed prompt."""
    state_dir, logs_dir = _bootstrap(tmp_path)
    result = run_flow_turn(
        "tell me something",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Sure, here's a thought.",
    )
    assert "format" not in result.trace.composed_prompt
    prompt_text = json.dumps(result.trace.composed_prompt)
    assert "evidence_used" not in prompt_text
    assert "candidate" not in prompt_text.lower()


# ---------------------------------------------------------------------------
# Field composition: current message primacy, canonical state relevance.
# ---------------------------------------------------------------------------


def test_canonical_state_absent_for_social_turn(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    field = FlowField.fresh("sess_test")
    before = compose_field(field, "hey, how's it going", state)
    assert before.relevant_canonical == []


def test_canonical_state_enters_when_relevant_to_message(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    field = FlowField.fresh("sess_test")
    before = compose_field(field, "what is our current goal here?", state)
    assert before.relevant_canonical  # goal contribution matched purpose intent
    kinds = {c["kind"] for c in before.relevant_canonical}
    assert "goal" in kinds


def test_open_thread_carried_at_low_salience_not_forced(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    field = FlowField.fresh("sess_test")
    # Neutral message with no strong topical competition -- the thread has
    # room to surface at its low carry salience without being forced.
    before = compose_field(field, "so what's next", state)
    # Not asserting presence (never forced) -- asserting it is eligible and
    # low-salience, i.e. it never dominates the field.
    thread_candidates = [e for e in before.selected if e["kind"] == "thread"]
    for t in thread_candidates:
        assert t["salience"] < 0.3


def test_current_message_never_counted_against_byte_budget(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    field = FlowField.fresh("sess_test")
    long_message = "tell me about the project. " * 200  # far over any element budget
    before = compose_field(field, long_message, state, byte_budget=200)
    assert before.current_message == long_message
    assert before.selected_bytes <= 200


# ---------------------------------------------------------------------------
# Integration: strengthen, create, decay, soften, bounded carry.
# ---------------------------------------------------------------------------


def test_integrate_creates_topic_elements_from_message_and_reply(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    run_flow_turn(
        "I've been thinking about garden irrigation systems lately",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Drip irrigation is efficient for that kind of setup.",
    )
    field = FlowField.load(flow_field_path(state_dir), session_id="sess_test")
    topic_sources = {e.source for e in field.elements if e.kind == "topic"}
    assert "human" in topic_sources


def test_integrate_strengthens_continued_element_across_turns(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    run_flow_turn(
        "let's talk about slow travel through mountain villages",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Slow travel through mountain villages sounds wonderful.",
    )
    field_after_1 = FlowField.load(flow_field_path(state_dir), session_id="sess_test")
    topic = next(e for e in field_after_1.elements if e.kind == "topic" and e.source == "human")
    salience_1 = topic.salience

    run_flow_turn(
        "yes, especially mountain villages with old stone paths",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Stone paths in mountain villages carry centuries of footsteps.",
    )
    field_after_2 = FlowField.load(flow_field_path(state_dir), session_id="sess_test")
    same_topic = field_after_2.find(topic.element_id)
    assert same_topic is not None
    assert same_topic.salience >= salience_1


def test_integrate_decays_unused_selected_element():
    field = FlowField.fresh("sess_x")
    el = FlowElement(
        element_id="topic:human:aaaa",
        kind="topic",
        content="a discussion about coral reef restoration projects",
        source="human",
        salience=0.6,
        momentum=0.1,
    )
    field.elements.append(el)
    before = FieldBefore(
        current_message="what's the weather like",
        intents=("open",),
        selected=[el.to_dict()],
        relevant_canonical=[],
        candidate_pool_size=1,
        live_element_count=1,
        byte_budget=1400,
        selected_bytes=el.bytes_len(),
    )
    integrate_field(
        field,
        field_before=before,
        current_message="what's the weather like",
        reply="It's sunny today.",
    )
    updated = field.find("topic:human:aaaa")
    assert updated is not None
    assert updated.salience < 0.6


def test_integrate_softens_verbatim_repeated_boilerplate():
    field = FlowField.fresh("sess_x")
    boilerplate = "This system is fully local and edge target is jetson orin nano."
    el = FlowElement(
        element_id="canonical:state.policy.local",
        kind="canonical",
        content=boilerplate,
        source="canonical",
        salience=0.6,
        momentum=0.1,
        repeat_streak=1,  # already repeated once before this turn
    )
    field.elements.append(el)
    before = FieldBefore(
        current_message="are we local only",
        intents=("policy",),
        selected=[el.to_dict()],
        relevant_canonical=[],
        candidate_pool_size=1,
        live_element_count=1,
        byte_budget=1400,
        selected_bytes=el.bytes_len(),
    )
    actions = integrate_field(
        field,
        field_before=before,
        current_message="are we local only",
        reply=boilerplate,  # model recited it verbatim again
    )
    softened = [a for a in actions if a.action == "softened"]
    assert softened
    updated = field.find("canonical:state.policy.local")
    assert updated is not None
    assert updated.salience < 0.6 * 0.5 + 1e-9


def test_bounded_carry_evicts_low_salience_elements_below_floor():
    field = FlowField.fresh("sess_x")
    field.elements.append(
        FlowElement(
            element_id="topic:human:zzzz",
            kind="topic",
            content="a very old faded topic nobody has mentioned in ages",
            source="human",
            salience=0.01,  # already below floor
            momentum=0.0,
        )
    )
    before = FieldBefore(
        current_message="hi",
        intents=("social",),
        selected=[],
        relevant_canonical=[],
        candidate_pool_size=0,
        live_element_count=1,
        byte_budget=1400,
        selected_bytes=0,
    )
    actions = integrate_field(field, field_before=before, current_message="hi", reply="Hi there!")
    assert field.find("topic:human:zzzz") is None
    assert any(a.action == "dropped" for a in actions)


# ---------------------------------------------------------------------------
# Observations: descriptive, never blocking.
# ---------------------------------------------------------------------------


def test_repetition_observation_flags_without_blocking(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    same_reply = "The quick brown fox jumps over the lazy dog near the river bend."
    run_flow_turn("say something", state_dir=state_dir, logs_dir=logs_dir, dry_reply=same_reply)
    second = run_flow_turn("say it again", state_dir=state_dir, logs_dir=logs_dir, dry_reply=same_reply)

    labels = {o["label"] for o in second.trace.observations}
    assert "Repetition" in labels
    # Non-blocking: the reply still travels through untouched.
    assert second.ok is True
    assert second.displayed_text == same_reply


def test_low_responsiveness_observation_is_signal_only(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    result = run_flow_turn(
        "what do you think about quantum entanglement experiments",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Okay.",
    )
    labels = {o["label"] for o in result.trace.observations}
    assert "Low responsiveness" in labels
    # Signal only -- never rejected, never altered.
    assert result.ok is True
    assert result.displayed_text == "Okay."


def test_authoritative_topic_disclosure_is_observation_only_never_enforced(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    result = run_flow_turn(
        "are we allowed to use cloud services",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="Sure, cloud services are totally fine to use whenever you like.",
    )
    labels = {o["label"] for o in result.trace.observations}
    assert "Authoritative-topic disclosure" in labels
    # Never substituted/enforced -- the model's own words still travel.
    assert result.displayed_text == "Sure, cloud services are totally fine to use whenever you like."


# ---------------------------------------------------------------------------
# FlowTrace: JSON-serializable, persisted under a dashboard-compatible path.
# ---------------------------------------------------------------------------


def test_flow_trace_is_json_serializable_and_has_required_shape(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    result = run_flow_turn(
        "what is this project for",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_reply="It's about keeping the model small and putting continuity in the substrate.",
    )
    data = result.trace.to_dict()
    reparsed = json.loads(json.dumps(data))  # round-trip
    for key in (
        "turn_id",
        "session_id",
        "started_at",
        "completed_at",
        "user_input",
        "field_before",
        "composed_prompt",
        "raw_reply",
        "reply_status",
        "displayed_text",
        "observations",
        "integration_actions",
        "field_after",
        "runtime_config",
    ):
        assert key in reparsed

    persisted_path = flow_trace_path(logs_dir, result.trace.turn_id)
    assert persisted_path.exists()
    on_disk = json.loads(persisted_path.read_text(encoding="utf-8"))
    assert on_disk["turn_id"] == result.trace.turn_id
    assert on_disk["displayed_text"] == result.displayed_text
