"""Tests for observatory.trace.run_traced_turn.

Covers the handoff task's item 1 (TurnTrace completeness: all 12 stages,
statuses derived per spec §6, byte fields present, JSON round-trip,
packet_bytes == edge.packet_byte_size of the compiled packet) and item 2
(criterion 20: observability does not change the model result).

Uses the repo's established offline-stub pattern for anything that would
otherwise touch Ollama: `dry_candidate_text` injection into
`pipeline.run_turn` / `observatory.trace.run_traced_turn` (see
tests/test_pipeline_dry.py, tests/test_first_flow_chat.py). No live Ollama
required.
"""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.edge import packet_byte_size
from conditioned_kernel.observatory.compute import stage_defs
from conditioned_kernel.observatory.trace import TurnTrace, run_traced_turn
from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.state import SubstrateState

_STAGE_STATUS_VOCAB = {
    "waiting",
    "active",
    "completed",
    "warning",
    "rejected",
    "repaired",
    "skipped",
}

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)

ACCEPT_ANSWER = (
    "Design intent is edge-first substrate conditioning: keep models small "
    "and local, put continuity in files, measure gain under Jetson budgets."
)


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": GOAL,
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_test",
                "receipt_count_24h": 0,
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
    # Empty thread_touch: companion field may withhold threads, and filtered
    # touches are advisories that would make stage 09 a warning on a "clean" accept.
    return json.dumps(
        {
            "answer": answer,
            "evidence_used": [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": []},
        }
    )


def _run(tmp_path: Path, prompt: str = "Summarize design intent.") -> tuple[TurnTrace, Path, Path]:
    state_dir, logs_dir = _bootstrap(tmp_path)
    trace = run_traced_turn(
        prompt,
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=_dry_candidate(ACCEPT_ANSWER),
        max_repair=0,
    )
    return trace, state_dir, logs_dir


# ---------------------------------------------------------------------------
# 1. TurnTrace completeness — all 12 stages
# ---------------------------------------------------------------------------


def test_traced_turn_has_all_12_stages_in_spec_order(tmp_path):
    trace, _, _ = _run(tmp_path)
    assert isinstance(trace, TurnTrace)
    assert len(trace.stages) == 12
    expected_names = [d["name"] for d in stage_defs()]
    assert [s.name for s in trace.stages] == expected_names
    assert [s.index for s in trace.stages] == list(range(1, 13))
    # every stage carries a resolved (non-hardcoded) source location
    for stage in trace.stages:
        assert stage.source_module
        assert stage.source_function
        assert isinstance(stage.source_line, int)


def test_stage_statuses_use_the_spec_6_vocabulary(tmp_path):
    trace, _, _ = _run(tmp_path)
    for stage in trace.stages:
        assert stage.status in _STAGE_STATUS_VOCAB, (stage.name, stage.status)


def test_stage_statuses_derived_per_spec_for_a_clean_single_pass_accept(tmp_path):
    """spec §6 status derivation: stages 01-08 completed on a finished turn;
    09 = bad if violations else warn if advisories else ok; 10 = fix if
    more than one pass else skip; 11 = fix if repaired-and-accepted, ok if
    accepted first pass, bad if rejected; 12 = ok if anything was applied.
    A clean single-pass accept (no violations/advisories, one pass,
    recent_turn_appended) exercises the "else" branch of every rule."""
    trace, _, _ = _run(tmp_path)
    assert trace.final_decision["decision"] == "accept"
    assert trace.final_decision["violations"] == []
    # Companion may record filtered thread_touch advisories; allow empty or filter-only
    adv = trace.final_decision.get("advisories") or []
    assert all(str(a).startswith("thread_touch_filtered:") for a in adv)
    assert len(trace.passes) == 1

    by_index = {s.index: s.status for s in trace.stages}
    for i in range(1, 9):
        assert by_index[i] == "completed", i
    assert by_index[9] == "completed"  # no violations, no advisories -> ok
    assert by_index[10] == "skipped"  # single pass -> repair not invoked
    assert by_index[11] == "completed"  # accepted first pass -> ok
    assert by_index[12] == "completed"  # recent_turn_appended is a real applied update


def test_stage_statuses_derived_per_spec_for_a_rejection(tmp_path):
    """A goal-echo rejection (see tests/test_pipeline_dry.py's
    test_dry_goal_echo_rejected for the same scenario against the plain
    pipeline) must land 09=rejected, 11=rejected, 12=warning (nothing
    applied on a reject)."""
    state_dir, logs_dir = _bootstrap(tmp_path)
    trace = run_traced_turn(
        "State the design intent.",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=_dry_candidate(GOAL),  # verbatim goal echo
        max_repair=0,
    )
    assert trace.final_decision["decision"] == "reject"
    assert "goal_echo" in trace.final_decision["violations"]

    by_index = {s.index: s.status for s in trace.stages}
    assert by_index[9] == "rejected"
    assert by_index[11] == "rejected"
    assert by_index[12] == "warning"

    by_index_flag = {s.index: s.flag for s in trace.stages}
    assert by_index_flag[9] is True  # any violation flags stage 09
    assert by_index_flag[11] is True  # rejection flags stage 11


def test_stage_dicts_carry_byte_fields(tmp_path):
    """StageTrace.to_dict() always carries bytes_in/bytes_out keys, and the
    turn-level byte fields (packet_bytes, context_share_bytes[].bytes) are
    populated — the shape the frontend and JSON export rely on."""
    trace, _, _ = _run(tmp_path)
    for stage in trace.stages:
        d = stage.to_dict()
        assert "bytes_in" in d
        assert "bytes_out" in d

    assert trace.packet_bytes is not None
    assert trace.packet_bytes > 0
    assert trace.context_share_bytes
    for row in trace.context_share_bytes:
        assert "bytes" in row and isinstance(row["bytes"], int)
        assert "share_pct" in row


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_turn_trace_json_round_trip(tmp_path):
    trace, _, _ = _run(tmp_path)
    as_dict = trace.to_dict()
    loaded = json.loads(trace.to_json())
    assert loaded == as_dict

    # the spec §12 export shape's field list, verbatim
    for field in (
        "turn_id",
        "session_id",
        "started_at",
        "completed_at",
        "user_input",
        "runtime_config",
        "stages",
        "context_share_bytes",
        "packet",
        "packet_bytes",
        "passes",
        "final_decision",
        "persistence",
        "observations",
        "operator",
    ):
        assert field in loaded, field

    assert len(loaded["stages"]) == 12
    assert len(loaded["passes"]) == 1
    pass0 = loaded["passes"][0]
    for field in (
        "pass_index",
        "packet_id",
        "candidate_id",
        "receipt_id",
        "answer",
        "evidence_used",
        "thread_touch",
        "violations",
        "advisories",
        "decision",
        "word_count",
        "telemetry",
    ):
        assert field in pass0, field


def test_turn_trace_json_round_trip_is_stable_across_two_serializations(tmp_path):
    trace, _, _ = _run(tmp_path)
    once = json.loads(trace.to_json())
    twice = json.loads(json.dumps(once, ensure_ascii=False))
    assert once == twice


# ---------------------------------------------------------------------------
# packet_bytes == edge.packet_byte_size of the compiled packet
# ---------------------------------------------------------------------------


def test_packet_bytes_equals_edge_packet_byte_size(tmp_path):
    """A prompt that does not classify as an authoritative-state question
    (see authoritative_state.classify_state_question) takes the plain
    compile -> budget -> generate path with no post-generation packet
    mutation, so the trace's packet_bytes must equal a fresh
    edge.packet_byte_size recompute of the exact packet object exposed as
    trace.packet — the core honesty-contract invariant (spec §10:
    "Verified: turn 1 computes 1440 B against a logged packet_bytes of
    1440")."""
    trace, _, _ = _run(tmp_path, prompt="Please continue and go deeper on that point.")
    assert trace.packet
    # packet_byte_size is inference-body only (observability maps excluded)
    recomputed = packet_byte_size(trace.packet)
    assert trace.packet_bytes == recomputed
    # and it must agree with what edge.enforce_packet_budget itself logged
    logged = (trace.packet.get("_edge") or {}).get("packet_bytes")
    assert logged is not None
    assert trace.packet_bytes == logged


def test_packet_bytes_mismatch_is_disclosed_not_hidden_for_authoritative_turns(tmp_path):
    """"Summarize design intent." classifies as an authoritative "goal"
    question (authoritative_state.classify_state_question). pipeline.py
    mutates the accepted packet in place afterwards — adding
    authoritative_enforced/authoritative_fallback/authoritative_reasons —
    *after* edge.enforce_packet_budget already computed and logged
    `_edge.packet_bytes`, so those three keys were never part of what was
    actually serialized and sent to the kernel. This is real, pre-existing
    pipeline.py behaviour (out of this build's scope), not a defect this
    package introduces. The honesty contract requires the trace to name a
    mismatch rather than silently pick a number (spec §10: "Where the
    trace cannot settle something, say so and name the value that
    would.") — verify that self-disclosure actually happens, and that
    trace.packet_bytes still reports the real, pre-mutation logged figure
    rather than the inflated recompute."""
    trace, _, _ = _run(tmp_path)  # default prompt: "Summarize design intent."
    assert trace.packet.get("authoritative_enforced") is True

    recomputed = packet_byte_size({k: v for k, v in trace.packet.items() if k != "_edge"})
    logged = (trace.packet.get("_edge") or {}).get("packet_bytes")
    assert logged is not None
    assert recomputed > logged  # the three post-hoc fields inflate the recompute

    # the trace reports the real, logged figure — not the inflated one —
    # and says so in its notes rather than staying silent about it.
    assert trace.packet_bytes == logged
    assert any("packet_bytes mismatch" in n for n in trace.notes), trace.notes


# ---------------------------------------------------------------------------
# 2. Criterion 20 — observability does not change the model result
# ---------------------------------------------------------------------------


def test_traced_and_untraced_runs_reach_identical_accept_decision(tmp_path):
    prompt = "Summarize design intent."
    dry = _dry_candidate(ACCEPT_ANSWER)

    state_a, logs_a = _bootstrap(tmp_path / "a")
    state_b, logs_b = _bootstrap(tmp_path / "b")

    plain = run_turn(
        prompt,
        state_dir=state_a,
        logs_dir=logs_a,
        dry_candidate_text=dry,
        max_repair=0,
    )
    traced = run_traced_turn(
        prompt,
        state_dir=state_b,
        logs_dir=logs_b,
        dry_candidate_text=dry,
        max_repair=0,
    )

    assert plain.decision == traced.final_decision["decision"] == "accept"
    assert plain.answer == traced.final_decision["answer"]
    assert (plain.receipt.get("violations") or []) == traced.final_decision["violations"]
    assert (plain.receipt.get("advisories") or []) == traced.final_decision["advisories"]
    assert plain.candidate.get("evidence_used") == traced.passes[-1].evidence_used
    assert (plain.candidate.get("next_state") or {}).get("thread_touch") == traced.passes[-1].thread_touch
    assert len(plain.passes) == len(traced.passes)

    plain_packet_bytes = (plain.packet.get("_edge") or {}).get("packet_bytes")
    assert plain_packet_bytes == traced.packet_bytes

    # identical durable-state effect, not just an identical in-memory result
    sa = SubstrateState.load(state_dir=state_a, logs_dir=logs_a)
    sb = SubstrateState.load(state_dir=state_b, logs_dir=logs_b)
    turns_a = [{"user": t["user"], "answer": t["answer"]} for t in sa.recent_turns()]
    turns_b = [{"user": t["user"], "answer": t["answer"]} for t in sb.recent_turns()]
    assert turns_a == turns_b


def test_traced_and_untraced_runs_agree_on_rejection(tmp_path):
    prompt = "State the design intent."
    dry = _dry_candidate(GOAL)  # echoes the goal verbatim -> goal_echo violation

    state_a, logs_a = _bootstrap(tmp_path / "a")
    state_b, logs_b = _bootstrap(tmp_path / "b")

    plain = run_turn(
        prompt,
        state_dir=state_a,
        logs_dir=logs_a,
        dry_candidate_text=dry,
        max_repair=0,
    )
    traced = run_traced_turn(
        prompt,
        state_dir=state_b,
        logs_dir=logs_b,
        dry_candidate_text=dry,
        max_repair=0,
    )

    assert plain.ok is False
    assert plain.decision == traced.final_decision["decision"] == "reject"
    assert "goal_echo" in (plain.receipt.get("violations") or [])
    assert "goal_echo" in traced.final_decision["violations"]
    assert sorted(plain.receipt.get("violations") or []) == sorted(traced.final_decision["violations"])
