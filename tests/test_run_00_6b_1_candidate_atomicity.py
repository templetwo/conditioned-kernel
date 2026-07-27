"""RUN 00.6B.1 — candidate atomicity and receipt cardinality.

Test-first amendments for multi-assertion defects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conditioned_kernel.continuity_events import (
    EVENT_SCHEMA_VERSION,
    canonical_json_bytes,
    materialize_state,
    normalize_relations,
)
from conditioned_kernel.continuity_gate import Decision, process_episode_a_candidate
from conditioned_kernel.continuity_replay import ReplayError, replay_store
from conditioned_kernel.continuity_store import ContinuityStore


def _universe() -> dict:
    return {
        "subject_ids": ["thread_2", "thread_min_model", "goal_1"],
        "object_ids": ["question_4", "question_budget", "fact_local"],
        "relations": ["remains_open", "is_answered", "depends_on", "references"],
        "valid_combinations": [
            ("thread_2", "remains_open", "question_4"),
            ("thread_2", "is_answered", "question_4"),
            ("thread_min_model", "remains_open", "question_budget"),
            ("goal_1", "depends_on", "fact_local"),
            ("thread_2", "references", "fact_local"),
        ],
        "forbidden_assertions": [
            {"subject_id": "thread_2", "relation": "is_answered", "object_id": "question_4"},
        ],
    }


def _store(tmp_path: Path) -> ContinuityStore:
    return ContinuityStore.create(
        tmp_path / "store",
        genesis={
            "schema_version": "ck.genesis.v1",
            "task_id": "task_epA_01",
            "goal": "candidate atomicity",
            "seed_relations": [],
        },
        universe=_universe(),
    )


def _a(subject: str, relation: str, obj: str) -> dict:
    return {"subject_id": subject, "relation": relation, "object_id": obj}


def _raw(assertions: list[dict]) -> str:
    return json.dumps({"continuity_assertions": assertions}, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Finding 1 — intra-candidate duplicates
# ---------------------------------------------------------------------------


def test_intra_candidate_duplicate_is_rejected(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("thread_2", "remains_open", "question_4"),
        ]
    )
    r = process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    assert r.decision is Decision.REJECTED
    assert any("DUPLICATE_ASSERTION" in c for c in r.reason_codes)


def test_duplicate_candidate_appends_zero_events(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("thread_2", "remains_open", "question_4"),
        ]
    )
    process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    assert store.list_events() == []


def test_duplicate_candidate_leaves_state_hash_unchanged(tmp_path: Path):
    store = _store(tmp_path)
    before = store.current_state_hash()
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("thread_2", "remains_open", "question_4"),
        ]
    )
    process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    assert store.current_state_hash() == before


def test_duplicate_candidate_produces_exactly_one_rejection_receipt(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("thread_2", "remains_open", "question_4"),
        ]
    )
    r = process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    matching = [
        x
        for x in store.all_receipts()
        if x.get("source_candidate_hash") == r.candidate_hash
    ]
    assert len(matching) == 1
    assert matching[0]["decision"] == Decision.REJECTED.value
    # Diagnostics preserve the duplicated triple
    assert matching[0].get("duplicate_triple") == {
        "subject_id": "thread_2",
        "relation": "remains_open",
        "object_id": "question_4",
    }


# ---------------------------------------------------------------------------
# Finding 2 — one event / one receipt per multi-assertion candidate
# ---------------------------------------------------------------------------


def test_two_distinct_valid_assertions_one_accepted_event(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("goal_1", "depends_on", "fact_local"),
        ]
    )
    r = process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    assert r.decision is Decision.ACCEPTED
    assert len(r.events) == 1
    assert len(store.list_events()) == 1


def test_two_distinct_valid_assertions_one_terminal_receipt(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("goal_1", "depends_on", "fact_local"),
        ]
    )
    r = process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    matching = [
        x
        for x in store.all_receipts()
        if x.get("source_candidate_hash") == r.candidate_hash
    ]
    assert len(matching) == 1
    assert matching[0]["decision"] == Decision.ACCEPTED.value
    assert matching[0]["accepted_assertion_count"] == 2


def test_accepted_event_contains_both_assertions(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("goal_1", "depends_on", "fact_local"),
        ]
    )
    process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    ev = store.list_events()[0]
    assert "assertions" in ev
    triples = {
        (a["subject_id"], a["relation"], a["object_id"]) for a in ev["assertions"]
    }
    assert ("thread_2", "remains_open", "question_4") in triples
    assert ("goal_1", "depends_on", "fact_local") in triples
    # No top-level single-assertion fields in v2
    assert "subject_id" not in ev


def test_assertions_canonically_ordered_in_event(tmp_path: Path):
    store = _store(tmp_path)
    # Input order: goal first, thread second — canonical sort puts goal before thread
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),
            _a("goal_1", "depends_on", "fact_local"),
        ]
    )
    process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    assertions = store.list_events()[0]["assertions"]
    expected = normalize_relations(assertions)
    assert assertions == expected
    assert assertions[0]["subject_id"] == "goal_1"
    assert assertions[1]["subject_id"] == "thread_2"


def test_reversed_input_order_byte_equivalent_canonical_payload(tmp_path: Path):
    """Reversing assertion input order yields same assertions payload bytes."""
    store_a = _store(tmp_path / "a")
    store_b = _store(tmp_path / "b")
    a1 = _a("thread_2", "remains_open", "question_4")
    a2 = _a("goal_1", "depends_on", "fact_local")
    process_episode_a_candidate(
        _raw([a1, a2]), store=store_a, episode_id="episode_a", repo_commit="fixed"
    )
    process_episode_a_candidate(
        _raw([a2, a1]), store=store_b, episode_id="episode_a", repo_commit="fixed"
    )
    ea, eb = store_a.list_events()[0], store_b.list_events()[0]
    # Canonical assertion payload is byte-identical
    assert canonical_json_bytes(ea["assertions"]) == canonical_json_bytes(eb["assertions"])
    # Resulting state hash identical (variable: event_id, timestamp, candidate hash)
    assert ea["resulting_state_hash"] == eb["resulting_state_hash"]
    assert ea["parent_state_hash"] == eb["parent_state_hash"]


def test_multi_assertion_replay_reconstructs_both_relations(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw(
            [
                _a("thread_2", "remains_open", "question_4"),
                _a("goal_1", "depends_on", "fact_local"),
            ]
        ),
        store=store,
        episode_id="episode_a",
    )
    st = replay_store(store)
    triples = {
        (r["subject_id"], r["relation"], r["object_id"])
        for r in st.state["accepted_relations"]
    }
    assert ("thread_2", "remains_open", "question_4") in triples
    assert ("goal_1", "depends_on", "fact_local") in triples


def test_multi_assertion_replay_expected_resulting_hash(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw(
            [
                _a("thread_2", "remains_open", "question_4"),
                _a("goal_1", "depends_on", "fact_local"),
            ]
        ),
        store=store,
        episode_id="episode_a",
    )
    ev = store.list_events()[0]
    st = replay_store(store)
    assert st.state_hash == ev["resulting_state_hash"]
    assert st.state_hash == store.current_state_hash()


# ---------------------------------------------------------------------------
# All-or-nothing mixed validity
# ---------------------------------------------------------------------------


def test_one_invalid_plus_one_valid_rejects_entire_candidate(tmp_path: Path):
    store = _store(tmp_path)
    raw = _raw(
        [
            _a("thread_2", "remains_open", "question_4"),  # valid
            _a("ghost", "remains_open", "question_4"),  # invalid
        ]
    )
    r = process_episode_a_candidate(raw, store=store, episode_id="episode_a")
    assert r.decision is Decision.REJECTED
    assert any("UNKNOWN_SUBJECT" in c for c in r.reason_codes)


def test_mixed_validity_appends_zero_events(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw(
            [
                _a("thread_2", "remains_open", "question_4"),
                _a("ghost", "remains_open", "question_4"),
            ]
        ),
        store=store,
        episode_id="episode_a",
    )
    assert store.list_events() == []


def test_mixed_validity_zero_partial_state_mutation(tmp_path: Path):
    store = _store(tmp_path)
    before = store.current_state_hash()
    process_episode_a_candidate(
        _raw(
            [
                _a("thread_2", "remains_open", "question_4"),
                _a("ghost", "remains_open", "question_4"),
            ]
        ),
        store=store,
        episode_id="episode_a",
    )
    assert store.current_state_hash() == before
    st = materialize_state(store.load_genesis(), store.list_events())
    assert st["accepted_relations"] == []


# ---------------------------------------------------------------------------
# Replay fail-closed on bad persisted events
# ---------------------------------------------------------------------------


def test_persisted_event_with_duplicate_assertions_fails_replay(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw([_a("thread_2", "remains_open", "question_4")]),
        store=store,
        episode_id="episode_a",
    )
    path = next(store.events_dir.glob("*.json"))
    data = json.loads(path.read_text())
    # Inject duplicate assertions in stored event
    data["assertions"] = [
        _a("thread_2", "remains_open", "question_4"),
        _a("thread_2", "remains_open", "question_4"),
    ]
    path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ReplayError):
        replay_store(store)


def test_persisted_event_with_invalid_assertion_fails_replay(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw([_a("thread_2", "remains_open", "question_4")]),
        store=store,
        episode_id="episode_a",
    )
    path = next(store.events_dir.glob("*.json"))
    data = json.loads(path.read_text())
    data["assertions"] = [_a("ghost_subject", "remains_open", "question_4")]
    path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ReplayError):
        replay_store(store)


# ---------------------------------------------------------------------------
# Cardinality invariants
# ---------------------------------------------------------------------------


def test_event_count_equals_accepted_candidate_count_not_assertion_count(tmp_path: Path):
    store = _store(tmp_path)
    # Candidate 1: two assertions → 1 event
    process_episode_a_candidate(
        _raw(
            [
                _a("thread_2", "remains_open", "question_4"),
                _a("goal_1", "depends_on", "fact_local"),
            ]
        ),
        store=store,
        episode_id="episode_a",
    )
    # Candidate 2: one assertion → 1 event
    process_episode_a_candidate(
        _raw([_a("thread_min_model", "remains_open", "question_budget")]),
        store=store,
        episode_id="episode_a",
    )
    assert len(store.list_events()) == 2  # candidates, not 3 assertions


def test_terminal_receipt_count_equals_processed_candidate_count(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw(
            [
                _a("thread_2", "remains_open", "question_4"),
                _a("goal_1", "depends_on", "fact_local"),
            ]
        ),
        store=store,
        episode_id="episode_a",
    )
    process_episode_a_candidate(
        _raw([_a("ghost", "remains_open", "question_4")]),
        store=store,
        episode_id="episode_a",
    )
    # 1 accept + 1 reject = 2 terminal receipts
    assert len(store.terminal_receipts()) == 2


def test_every_candidate_hash_maps_to_exactly_one_terminal_receipt(tmp_path: Path):
    store = _store(tmp_path)
    results = []
    results.append(
        process_episode_a_candidate(
            _raw(
                [
                    _a("thread_2", "remains_open", "question_4"),
                    _a("goal_1", "depends_on", "fact_local"),
                ]
            ),
            store=store,
            episode_id="episode_a",
        )
    )
    results.append(
        process_episode_a_candidate(
            _raw([_a("thread_2", "remains_open", "question_4")]),  # duplicate of history
            store=store,
            episode_id="episode_a",
        )
    )
    by_hash: dict[str, list] = {}
    for rec in store.terminal_receipts():
        by_hash.setdefault(rec["source_candidate_hash"], []).append(rec)
    for r in results:
        assert len(by_hash[r.candidate_hash]) == 1


def test_event_schema_is_v2_batch(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _raw([_a("thread_2", "remains_open", "question_4")]),
        store=store,
        episode_id="episode_a",
    )
    assert store.list_events()[0]["schema_version"] == EVENT_SCHEMA_VERSION
    assert EVENT_SCHEMA_VERSION.endswith("v2")
