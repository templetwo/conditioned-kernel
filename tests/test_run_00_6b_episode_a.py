"""RUN 00.6B — Episode A external continuity lifecycle.

Test-first: these tests define the contract. No live model. No M0.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from conditioned_kernel.continuity_events import (
    EVENT_SCHEMA_VERSION,
    VALIDATOR_VERSION,
    materialize_state,
)
from conditioned_kernel.continuity_gate import (
    Decision,
    process_episode_a_candidate,
)
from conditioned_kernel.continuity_replay import ReplayError, replay_store
from conditioned_kernel.continuity_store import ContinuityStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        # Frozen task truth: contradictions against these fail closed.
        "forbidden_assertions": [
            {"subject_id": "thread_2", "relation": "is_answered", "object_id": "question_4"},
        ],
    }


def _valid_raw() -> str:
    return json.dumps(
        {
            "continuity_assertions": [
                {
                    "subject_id": "thread_2",
                    "relation": "remains_open",
                    "object_id": "question_4",
                }
            ]
        },
        separators=(",", ":"),
    )


def _store(tmp_path: Path) -> ContinuityStore:
    genesis = {
        "schema_version": "ck.genesis.v1",
        "task_id": "task_epA_01",
        "goal": "Demonstrate external continuity under closed-set assertions.",
        "seed_relations": [],
    }
    return ContinuityStore.create(tmp_path / "store", genesis=genesis, universe=_universe())


# ---------------------------------------------------------------------------
# 1–5 Accept path
# ---------------------------------------------------------------------------


def test_valid_assertion_is_accepted(tmp_path: Path):
    store = _store(tmp_path)
    result = process_episode_a_candidate(
        _valid_raw(),
        store=store,
        episode_id="episode_a",
    )
    assert result.decision is Decision.ACCEPTED
    assert result.reason_code == "ACCEPTED"
    assert len(result.events) == 1


def test_accepted_assertion_appends_one_event(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    events = store.list_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["schema_version"] == EVENT_SCHEMA_VERSION
    assert ev["subject_id"] == "thread_2"
    assert ev["relation"] == "remains_open"
    assert ev["object_id"] == "question_4"
    assert ev["validator_version"] == VALIDATOR_VERSION
    assert ev["parent_state_hash"]
    assert ev["resulting_state_hash"]
    assert ev["parent_state_hash"] != ev["resulting_state_hash"]
    assert ev["source_candidate_hash"]


def test_accepted_assertion_changes_canonical_state_hash(tmp_path: Path):
    store = _store(tmp_path)
    before = store.current_state_hash()
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    after = store.current_state_hash()
    assert before != after
    # Materialized accepted relation present
    state = materialize_state(store.load_genesis(), store.list_events())
    assert {
        "subject_id": "thread_2",
        "relation": "remains_open",
        "object_id": "question_4",
    } in state["accepted_relations"]


def test_fresh_process_reconstructs_changed_state(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    expected_hash = store.current_state_hash()
    store_path = str(store.root)

    # Fresh interpreter boundary (new process).
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / "src")!r})
        from conditioned_kernel.continuity_store import ContinuityStore
        from conditioned_kernel.continuity_replay import replay_store
        s = ContinuityStore.open({store_path!r})
        st = replay_store(s)
        print(json.dumps({{"hash": st.state_hash, "rels": st.state["accepted_relations"]}}))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["hash"] == expected_hash
    assert any(
        r["subject_id"] == "thread_2" and r["relation"] == "remains_open"
        for r in payload["rels"]
    )


def test_episode_b_packet_contains_reconstructed_relation(tmp_path: Path):
    from conditioned_kernel.continuity_gate import episode_b_packet_relations

    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    # Simulate process exit + fresh load
    store2 = ContinuityStore.open(store.root)
    rels = episode_b_packet_relations(store2)
    assert any(
        r["subject_id"] == "thread_2"
        and r["relation"] == "remains_open"
        and r["object_id"] == "question_4"
        for r in rels
    )


# ---------------------------------------------------------------------------
# 6–7 Reject path
# ---------------------------------------------------------------------------


def test_rejected_assertion_appends_no_continuity_event(tmp_path: Path):
    store = _store(tmp_path)
    bad = json.dumps(
        {
            "continuity_assertions": [
                {
                    "subject_id": "unknown_subject",
                    "relation": "remains_open",
                    "object_id": "question_4",
                }
            ]
        }
    )
    result = process_episode_a_candidate(bad, store=store, episode_id="episode_a")
    assert result.decision is Decision.REJECTED
    assert store.list_events() == []
    assert store.rejection_receipts()  # audit trail remains


def test_rejected_assertion_leaves_state_hash_unchanged(tmp_path: Path):
    store = _store(tmp_path)
    before = store.current_state_hash()
    bad = json.dumps(
        {
            "continuity_assertions": [
                {
                    "subject_id": "thread_2",
                    "relation": "is_answered",  # forbidden by frozen truth
                    "object_id": "question_4",
                }
            ]
        }
    )
    process_episode_a_candidate(bad, store=store, episode_id="episode_a")
    assert store.current_state_hash() == before


def test_fresh_process_sees_no_rejected_mutation(tmp_path: Path):
    store = _store(tmp_path)
    before = store.current_state_hash()
    bad = json.dumps(
        {
            "continuity_assertions": [
                {
                    "subject_id": "nope",
                    "relation": "remains_open",
                    "object_id": "question_4",
                }
            ]
        }
    )
    process_episode_a_candidate(bad, store=store, episode_id="episode_a")
    store_path = str(store.root)
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / "src")!r})
        from conditioned_kernel.continuity_store import ContinuityStore
        from conditioned_kernel.continuity_replay import replay_store
        s = ContinuityStore.open({store_path!r})
        st = replay_store(s)
        print(json.dumps({{"hash": st.state_hash, "n_events": len(s.list_events())}}))
        """
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["n_events"] == 0
    assert payload["hash"] == before


# ---------------------------------------------------------------------------
# 8–12 Fail closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,code_prefix",
    [
        (
            {
                "continuity_assertions": [
                    {
                        "subject_id": "ghost",
                        "relation": "remains_open",
                        "object_id": "question_4",
                    }
                ]
            },
            "UNKNOWN_SUBJECT",
        ),
        (
            {
                "continuity_assertions": [
                    {
                        "subject_id": "thread_2",
                        "relation": "remains_open",
                        "object_id": "ghost_obj",
                    }
                ]
            },
            "UNKNOWN_OBJECT",
        ),
        (
            {
                "continuity_assertions": [
                    {
                        "subject_id": "thread_2",
                        "relation": "teleports_to",
                        "object_id": "question_4",
                    }
                ]
            },
            "UNKNOWN_RELATION",
        ),
        (
            {
                "continuity_assertions": [
                    {
                        "subject_id": "goal_1",
                        "relation": "remains_open",
                        "object_id": "question_4",
                    }
                ]
            },
            "INVALID_COMBINATION",
        ),
        (
            {
                "continuity_assertions": [
                    {
                        "subject_id": "thread_2",
                        "relation": "is_answered",
                        "object_id": "question_4",
                    }
                ]
            },
            "CONTRADICTION",
        ),
    ],
)
def test_unknown_and_invalid_assertions_fail_closed(tmp_path: Path, raw, code_prefix):
    store = _store(tmp_path)
    result = process_episode_a_candidate(
        json.dumps(raw), store=store, episode_id="episode_a"
    )
    assert result.decision is Decision.REJECTED
    assert any(code_prefix in c for c in result.reason_codes)
    assert store.list_events() == []


# ---------------------------------------------------------------------------
# 13 Duplicate handling
# ---------------------------------------------------------------------------


def test_duplicate_event_handling_is_deterministic(tmp_path: Path):
    store = _store(tmp_path)
    r1 = process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    assert r1.decision is Decision.ACCEPTED
    r2 = process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    # Second identical assertion: deterministic reject (not a second event)
    assert r2.decision is Decision.REJECTED
    assert any("DUPLICATE" in c for c in r2.reason_codes)
    assert len(store.list_events()) == 1


# ---------------------------------------------------------------------------
# 14–17 Tamper / partial / version
# ---------------------------------------------------------------------------


def test_mutated_historical_event_breaks_replay(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    # Mutate on disk
    path = next(store.events_dir.glob("*.json"))
    data = json.loads(path.read_text())
    data["object_id"] = "tampered"
    path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ReplayError):
        replay_store(store)


def test_broken_parent_state_hash_breaks_replay(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    path = next(store.events_dir.glob("*.json"))
    data = json.loads(path.read_text())
    data["parent_state_hash"] = "0" * 64
    path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ReplayError) as ei:
        replay_store(store)
    assert "parent" in str(ei.value).lower() or "chain" in str(ei.value).lower()


def test_unknown_event_schema_version_breaks_replay(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    path = next(store.events_dir.glob("*.json"))
    data = json.loads(path.read_text())
    data["schema_version"] = "ck.continuity_event.v999"
    # Keep hashes consistent with content so version check is the fail point
    path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ReplayError) as ei:
        replay_store(store)
    assert "version" in str(ei.value).lower() or "schema" in str(ei.value).lower()


def test_partial_append_cannot_replay_as_accepted(tmp_path: Path):
    store = _store(tmp_path)
    # Leave a .tmp partial file — must not count as accepted event
    partial = store.events_dir / "000001_evt_partial.json.tmp"
    partial.write_text('{"schema_version":"ck.continuity_event.v1","broken":true}\n')
    events = store.list_events()
    assert events == []
    # Quarantine before/during replay; partials never become accepted history
    moved = store.quarantine_partials()
    assert moved
    assert not partial.exists()
    assert any(store.quarantine_dir.iterdir())
    st = replay_store(store)
    assert st.state["accepted_relations"] == []
    assert store.list_events() == []


# ---------------------------------------------------------------------------
# 18–19 Determinism / model replacement
# ---------------------------------------------------------------------------


def test_replay_byte_deterministic_across_fresh_processes(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    store_path = str(store.root)
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / "src")!r})
        from conditioned_kernel.continuity_store import ContinuityStore
        from conditioned_kernel.continuity_replay import replay_store
        from conditioned_kernel.continuity_events import canonical_json_bytes
        s = ContinuityStore.open({store_path!r})
        st = replay_store(s)
        print(st.state_hash)
        print(canonical_json_bytes(st.state).hex())
        """
    )
    hashes = []
    blobs = []
    for _ in range(3):
        proc = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln]
        hashes.append(lines[-2])
        blobs.append(lines[-1])
    assert len(set(hashes)) == 1
    assert len(set(blobs)) == 1


def test_replacement_model_identity_can_receive_reconstructed_state(tmp_path: Path):
    store = _store(tmp_path)
    process_episode_a_candidate(
        _valid_raw(),
        store=store,
        episode_id="episode_a",
        provenance={"model": "model_a:0.5b"},
    )
    # Fresh load as if a different model will consume Episode B
    store2 = ContinuityStore.open(store.root)
    st = replay_store(store2)
    from conditioned_kernel.continuity_gate import episode_b_packet_relations

    rels = episode_b_packet_relations(store2)
    assert rels
    # Provenance of original model is on the event; reconstructed state is model-agnostic
    ev = store2.list_events()[0]
    assert ev["provenance"]["model"] == "model_a:0.5b"
    assert st.state_hash == store.current_state_hash()


# ---------------------------------------------------------------------------
# 20–21 Authority boundaries
# ---------------------------------------------------------------------------


def test_raw_model_prose_never_in_authoritative_state(tmp_path: Path):
    store = _store(tmp_path)
    prose = (
        '{"continuity_assertions":[{"subject_id":"thread_2","relation":"remains_open",'
        '"object_id":"question_4"}],"answer":"SECRET FREEFORM MEMORY DUMP xyzzy"}'
    )
    process_episode_a_candidate(prose, store=store, episode_id="episode_a")
    st = replay_store(store)
    blob = json.dumps(st.state)
    assert "SECRET FREEFORM" not in blob
    assert "xyzzy" not in blob
    # Only closed-set relation atoms
    for rel in st.state["accepted_relations"]:
        assert set(rel.keys()) == {"subject_id", "relation", "object_id"}


def test_exactly_one_accept_or_reject_terminal_per_candidate(tmp_path: Path):
    store = _store(tmp_path)
    r = process_episode_a_candidate(_valid_raw(), store=store, episode_id="episode_a")
    assert r.decision in (Decision.ACCEPTED, Decision.REJECTED)
    # One receipt for this candidate hash
    receipts = store.all_receipts()
    cand_hash = r.candidate_hash
    matching = [x for x in receipts if x.get("source_candidate_hash") == cand_hash]
    assert len(matching) == 1
    assert matching[0]["decision"] == r.decision.value


def test_parse_failure_distinct_from_schema_failure(tmp_path: Path):
    store = _store(tmp_path)
    r_parse = process_episode_a_candidate("not json at all", store=store, episode_id="a")
    assert r_parse.decision is Decision.REJECTED
    assert any("PARSE" in c for c in r_parse.reason_codes)

    r_schema = process_episode_a_candidate(
        json.dumps({"continuity_assertions": "not-a-list"}),
        store=store,
        episode_id="a",
    )
    assert r_schema.decision is Decision.REJECTED
    assert any("SCHEMA" in c for c in r_schema.reason_codes)
    assert store.list_events() == []


def test_dry_run_isolated_store_not_scientific(tmp_path: Path):
    store = _store(tmp_path)
    dry_root = tmp_path / "dry_store"
    result = process_episode_a_candidate(
        _valid_raw(),
        store=store,
        episode_id="episode_a",
        dry_run=True,
        dry_store_root=dry_root,
    )
    assert result.decision is Decision.ACCEPTED
    assert result.dry_run is True
    assert result.scientific_completion is False
    # Primary store unchanged
    assert store.list_events() == []
    # Dry store has isolated event
    dry = ContinuityStore.open(dry_root)
    assert len(dry.list_events()) == 1


def test_model_cannot_directly_write_state_api(tmp_path: Path):
    """Trusted delta only: store has no public write from raw model dicts."""
    store = _store(tmp_path)
    assert not hasattr(store, "write_model_output")
    with pytest.raises(Exception):
        # No path that accepts arbitrary JSON as mutation
        store.append_raw_model_state({"anything": True})  # type: ignore[attr-defined]
