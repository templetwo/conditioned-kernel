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


# ---------------------------------------------------------------------------
# Context-share buckets sum to the model-input total
# ---------------------------------------------------------------------------


def test_context_share_buckets_are_six_sources_summing_to_the_total(tmp_path):
    packet, model_input = _real_packet_and_model_input(tmp_path)
    rows = compute.context_share_bytes(packet, model_input)
    assert len(rows) == 6
    assert [r["source_id"] for r in rows] == [
        "current_user_input",
        "recent_dialogue",
        "durable_state",
        "system_instructions",
        "output_schema",
        "constraints",
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
