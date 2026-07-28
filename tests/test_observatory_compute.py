"""Tests for observatory.compute — the honesty-contract computed values
(design_handoff_interior_view/README.md §10).

Covers the handoff task's item 3: context-share buckets sum to the
model-input total; evidence matching agrees with
`return_path.validate._evidence_ok` on shared cases; the symmetric-Jaccard
property `sim(a, b) == sim(b, a)`; and the repetition gate requiring two or
more stored memory entries (byte share alone cannot measure repetition —
one stored turn always holds ~100% of the list).

No live Ollama required: packets are built with the real `compile.py`
functions against a hand-written temp state dir, the same pattern
tests/test_first_flow_chat.py already uses for packet-shape assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.compile import compile_turn
from conditioned_kernel.edge import load_profile
from conditioned_kernel.observatory import compute
from conditioned_kernel.return_path.validate import _evidence_ok, _packet_evidence_pool
from conditioned_kernel.state import SubstrateState

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
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


def _real_packet_and_model_input(tmp_path: Path, user_input: str = "What model runs here?"):
    state_dir, logs_dir = _bootstrap(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    profile = load_profile("orin_nano_8gb")
    return compile_turn(state, user_input, profile=profile)


def _bootstrap_with_dialogue(tmp_path: Path) -> tuple[Path, Path]:
    """Like `_bootstrap`, but seeds one prior recent_turns entry so a
    companion turn can select both a dialogue contribution and a state
    (fact/runtime) contribution in the same pass — the exact mix the
    census over-count defect needed to reproduce (RUN 00.6F lens 2/3 log
    dig: durable_state's override counted the whole selected-context prose
    block while recent_dialogue and context_field separately re-counted
    the same selected text)."""
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
                "recent_turns": [
                    {
                        "user": "which model is active",
                        "answer": "The active model is qwen3.5 0.8b on the jetson orin nano board.",
                        "ts": "2026-07-28T00:00:00Z",
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
    (state_dir / "threads.json").write_text("[]", encoding="utf-8")
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    return state_dir, logs_dir


# ---------------------------------------------------------------------------
# Context-share buckets sum to the model-input total
# ---------------------------------------------------------------------------


def test_context_share_buckets_are_six_sources_summing_to_the_total(tmp_path):
    packet, model_input = _real_packet_and_model_input(tmp_path)
    rows = compute.context_share_bytes(packet, model_input)
    # Includes context_field selection census after the Studio structural cut
    assert len(rows) == 7
    assert [r["source_id"] for r in rows] == [
        "current_user_input",
        "recent_dialogue",
        "durable_state",
        "system_instructions",
        "output_schema",
        "constraints",
        "context_field",
    ]

    total_bytes = sum(r["bytes"] for r in rows)
    assert total_bytes > 0

    # share_pct is exactly the bucket's own bytes / total — the invariant
    # the buckets are defined by (spec §10: "labelled as share of
    # model-input bytes").
    for r in rows:
        assert r["share_pct"] == round((r["bytes"] / total_bytes) * 100, 2)

    # the shares sum to ~100% of the same total they were built from
    assert abs(sum(r["share_pct"] for r in rows) - 100.0) < 0.1

    # deterministic recomputation — no hidden state, never transcribed
    assert compute.context_share_bytes(packet, model_input) == rows


def test_context_share_user_input_bucket_reflects_the_literal_message(tmp_path):
    msg = "hello there, this is a distinctive test message for byte counting"
    packet, model_input = _real_packet_and_model_input(tmp_path, user_input=msg)
    rows = compute.context_share_bytes(packet, model_input)
    user_row = next(r for r in rows if r["source_id"] == "current_user_input")
    # the bucket must be at least as large as the raw utf-8 message bytes
    # (it also carries `"user_input":` key + JSON-quoting overhead)
    assert user_row["bytes"] >= compute.bytes_len(msg)
    assert packet["user_input"] == msg


# ---------------------------------------------------------------------------
# Companion (context_field.v1) census is a true byte partition — no bucket
# double-counts another bucket's bytes (RUN 00.6F Observatory census fix).
# ---------------------------------------------------------------------------


def test_context_share_companion_partition_covers_dialogue_and_state_with_no_double_count(tmp_path):
    """With both a selected recent-dialogue contribution and a selected
    state contribution present in the same turn, the buckets that partition
    the literal companion user message (current_user_input, recent_dialogue,
    durable_state, and the selection-framing share of the context_field
    bucket) must sum to exactly the message's own byte length — proving no
    byte was counted twice. This is the mix the durable_state-override bug
    needed to trigger: reproduces it, then asserts it can't reproduce."""
    state_dir, logs_dir = _bootstrap_with_dialogue(tmp_path)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    profile = load_profile("orin_nano_8gb")
    packet, model_input = compile_turn(
        state, "which model and jetson board should I use for this", profile=profile
    )

    # Sanity: this turn actually selected both kinds of contribution, or the
    # test below isn't exercising the bug it claims to guard against.
    assert packet["recent_turns"], "expected the prior turn to be selected into this packet"
    assert packet["facts"], "expected at least one state fact to be selected into this packet"

    user_message = compute._companion_user_message(model_input)
    assert user_message is not None

    rows = compute.context_share_bytes(packet, model_input)
    by_id = {r["source_id"]: r["bytes"] for r in rows}
    assert (
        by_id["current_user_input"]
        + by_id["recent_dialogue"]
        + by_id["durable_state"]
        + by_id["context_field"]
        == compute.bytes_len(user_message)
    )


def test_partition_companion_user_message_is_an_exact_byte_partition_with_all_line_kinds():
    """Unit-level check of `_partition_companion_user_message` against a
    hand-built literal message covering every ctx_lines prefix
    compile.build_model_input emits (fact, thread, prior dialogue, must-
    preserve claim, repair) — independent of compile.py's own behavior."""
    user_content = (
        "## Selected context\n"
        "- This system is fully local.\n"
        "- thread thread_min_model: What is the minimum viable model size?\n"
        "- prior: user=what model is this | assistant=The active model is qwen.\n"
        "- [must preserve] The system is fully local.\n"
        "- repair: Previous output failed validation. Return corrected JSON only. hints=[]\n\n"
        "## Current human message\n"
        "which model and jetson board should I use\n"
    )
    parts = compute._partition_companion_user_message(user_content)
    assert sum(parts.values()) == compute.bytes_len(user_content)
    assert parts["current_user_input"] == compute.bytes_len(
        "which model and jetson board should I use"
    )
    assert parts["recent_dialogue"] > 0
    assert parts["durable_state"] > 0  # fact + thread + must-preserve lines
    assert parts["system_instructions"] > 0  # repair line
    assert parts["selection_framing"] > 0  # headers + line joiners


def test_partition_companion_user_message_empty_selection_placeholder():
    user_content = (
        "## Selected context\n"
        "(no selected substrate prose)\n\n"
        "## Current human message\n"
        "hello there\n"
    )
    parts = compute._partition_companion_user_message(user_content)
    assert sum(parts.values()) == compute.bytes_len(user_content)
    assert parts["current_user_input"] == compute.bytes_len("hello there")
    assert parts["recent_dialogue"] == 0
    assert parts["durable_state"] == 0
    assert parts["system_instructions"] == 0


def test_partition_companion_user_message_shape_mismatch_falls_back_to_framing():
    """A message that doesn't match compile.build_model_input's fixed
    companion template attributes its whole byte length to
    selection_framing rather than guessing at a split that isn't there."""
    weird = 'Packet:\n{"user_input": "hi"}'
    parts = compute._partition_companion_user_message(weird)
    assert sum(parts.values()) == compute.bytes_len(weird)
    assert parts["selection_framing"] == compute.bytes_len(weird)
    assert parts["current_user_input"] == 0
    assert parts["recent_dialogue"] == 0
    assert parts["durable_state"] == 0


def test_context_share_bytes_pre_context_field_path_byte_for_byte_unchanged():
    """Regression pin (spec: 'preserve the pre-context-field code path
    byte-for-byte unchanged'). A packet shaped like a morning-era,
    pre-context-field turn — no packet['context_field'] key at all,
    measurement-style acceptance_contract, repair present — must fall
    straight through the untouched `_keyed_bytes` formulas: the companion
    partition only ever engages when acceptance_mode == 'companion' AND
    context_field.schema == 'ck.context_field.v1', neither of which this
    packet has. Values pinned against the real function's own output."""
    packet = {
        "session_id": "sess_test",
        "user_input": "dont reject",
        "state_digest": {"goal": "Demonstrate substrate gain."},
        "facts": ["This system is fully local.", "Sensors are out of scope for v0."],
        "open_threads": [
            {"id": "thread_min_model", "title": "What is the minimum viable model size?"}
        ],
        "recent_turns": [
            {
                "user": "what model is this",
                "answer": "The system is fully local.",
                "ts": "2026-07-28T03:14:31Z",
            }
        ],
        "constraints": {"max_words": 120, "must_return_json": True, "forbidden": []},
        "acceptance_contract": {
            "acceptance_mode": "measurement",
            "required_sections": ["answer", "evidence_used", "next_state"],
        },
        "repair": {
            "pass_index": 1,
            "instruction": "Previous output failed validation. Return corrected JSON only.",
            "hints": ["FIX evidence_not_in_packet"],
        },
    }
    serialized = json.dumps(dict(packet), ensure_ascii=False, separators=(",", ":"))
    system_text = (
        "Local conditioned-kernel transducer. Return ONLY valid JSON with keys answer, "
        "evidence_used, next_state."
    )
    model_input = {
        "mode": "chat_json",
        "payload": {
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": "Packet:\n" + serialized},
            ],
            "format": {"type": "object", "properties": {}},
        },
    }

    rows = compute.context_share_bytes(packet, model_input)
    by_id = {r["source_id"]: r["bytes"] for r in rows}
    assert by_id == {
        "current_user_input": 27,
        "recent_dialogue": 113,
        "durable_state": 246,
        "system_instructions": 250,
        "output_schema": 33,
        "constraints": 187,
        "context_field": 0,
    }


def test_verify_packet_bytes_matches_logged_edge_packet_bytes(tmp_path):
    packet, _ = _real_packet_and_model_input(tmp_path)
    logged, recomputed, match = compute.verify_packet_bytes(packet)
    assert match is True
    assert logged == recomputed
    assert logged == (packet.get("_edge") or {}).get("packet_bytes")


# ---------------------------------------------------------------------------
# Evidence matching agrees with validate._evidence_ok on shared cases
# ---------------------------------------------------------------------------


def _synthetic_packet() -> dict:
    return {
        "facts": ["This system is fully local and runs on the edge."],
        "open_threads": [],
        "recent_turns": [],
        "state_digest": {},
    }


def test_citation_audit_status_agrees_with_evidence_ok_per_citation():
    packet = _synthetic_packet()
    pool = _packet_evidence_pool(packet)

    cases = [
        "This system is fully local and runs on the edge.",  # exact match
        "fully local and runs on the edge",  # substring match
        "totally unrelated citation text here",  # miss, long enough
        "short",  # too short (<12 chars floor in _evidence_ok)
    ]
    audit = compute.citation_audit(packet, cases)
    assert len(audit) == len(cases)

    for item, row in zip(cases, audit):
        ok, bad = _evidence_ok([item], pool)
        if ok:
            assert row["status"] == "MATCHED", (item, row)
        else:
            reason_token = bad[0] if bad else "evidence_not_in_packet"
            expected = "TOO_SHORT" if reason_token.startswith("evidence_too_short") else "MISS"
            assert row["status"] == expected, (item, row, reason_token)


def test_citation_audit_empty_evidence_used_produces_no_rows():
    packet = _synthetic_packet()
    assert compute.citation_audit(packet, []) == []


def test_evidence_pool_is_the_real_validate_function_not_a_copy():
    packet = _synthetic_packet()
    assert compute.evidence_pool(packet) == _packet_evidence_pool(packet)


# ---------------------------------------------------------------------------
# Symmetric Jaccard: sim(a, b) == sim(b, a)
# ---------------------------------------------------------------------------


def test_jaccard_similarity_is_symmetric_across_varied_pairs():
    pairs = [
        ("the quick brown fox jumps", "the quick brown dog jumps"),
        ("edge conditioning substrate kernel", "kernel substrate edge conditioning"),
        ("completely different words here", "totally unrelated other content"),
        ("", "nonempty text with words"),
        ("", ""),
        ("same text repeated exactly", "same text repeated exactly"),
        ("a", "ab"),  # both below the 4-char token floor
    ]
    for a, b in pairs:
        assert compute.jaccard_similarity(a, b) == compute.jaccard_similarity(b, a), (a, b)


def test_jaccard_similarity_bounds_and_identity():
    assert compute.jaccard_similarity("", "") == 0.0
    same = "edge conditioning substrate kernel words"
    assert compute.jaccard_similarity(same, same) == 1.0
    assert compute.jaccard_similarity("aaaa bbbb", "cccc dddd") == 0.0


def test_jaccard_is_not_fooled_by_asymmetric_containment():
    """spec §10: "Asymmetric containment scores 1.0 for any long answer that
    merely recites the same boilerplate, which is wrong." A long answer
    that contains a short boilerplate phrase verbatim must not score 1.0
    under Jaccard, and the score must still be symmetric."""
    boilerplate = "short helpful reply grounded in the packet"
    long_answer = boilerplate + " " + (
        "extra words that pad this candidate out far beyond the boilerplate alone "
    ) * 3
    sim_ab = compute.jaccard_similarity(boilerplate, long_answer)
    sim_ba = compute.jaccard_similarity(long_answer, boilerplate)
    assert sim_ab == sim_ba
    assert sim_ab < 1.0


# ---------------------------------------------------------------------------
# Repetition gate requires >= 2 entries
# ---------------------------------------------------------------------------


def test_memory_repetition_with_zero_entries():
    rep = compute.memory_repetition([])
    assert rep["entries"] == 0
    assert rep["detected"] is False
    assert rep["pair"] is None


def test_memory_repetition_with_one_entry_never_detected():
    """spec §10: "Byte share cannot measure it: one stored turn always holds
    ~100% of the list." A single entry can never trigger the repetition
    gate, regardless of its own content."""
    single = [{"user": "q", "answer": "the same repeated answer text over and over again"}]
    rep = compute.memory_repetition(single)
    assert rep["entries"] == 1
    assert rep["detected"] is False


def test_memory_repetition_detects_two_similar_entries():
    turns = [
        {"user": "q1", "answer": "the design intent is edge first substrate conditioning kernel"},
        {"user": "q2", "answer": "the design intent is edge first substrate conditioning system"},
    ]
    rep = compute.memory_repetition(turns)
    assert rep["entries"] == 2
    assert rep["pair"] == (0, 1)
    assert rep["detected"] is True
    assert rep["pairwise_max"] >= rep["threshold"]


def test_memory_repetition_two_dissimilar_entries_not_detected():
    turns = [
        {"user": "q1", "answer": "completely unrelated first answer about jetson budgets"},
        {"user": "q2", "answer": "an entirely different second answer about linguistic transducers"},
    ]
    rep = compute.memory_repetition(turns)
    assert rep["entries"] == 2
    assert rep["detected"] is False
    assert rep["pairwise_max"] < rep["threshold"]
