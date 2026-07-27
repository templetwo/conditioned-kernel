"""RUN 00.6C.1 — durable receipt truth and artifact consistency.

Test-first: these tests open the on-disk receipt as audit-of-record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conditioned_kernel.continuity_events import (
    RECEIPT_SCHEMA_VERSION,
    canonical_json_bytes,
)
from conditioned_kernel.continuity_gate import (
    Decision,
    ExecutionScope,
    process_episode_a_candidate,
    verify_event_receipt_pair,
)
from conditioned_kernel.continuity_live import (
    run_episode_a_live,
    universe_from_task,
    valid_plumbing_candidate,
)
from conditioned_kernel.continuity_store import ContinuityStore
from conditioned_kernel.generate import InferenceResult, RunStatus


def _task() -> dict:
    return {
        "id": "live_plumbing_01",
        "continuity_universe": {
            "subject_ids": ["thread_gamma_receipt"],
            "object_ids": ["question_cold_start"],
            "relations": ["remains_open", "references"],
            "valid_combinations": [
                ["thread_gamma_receipt", "remains_open", "question_cold_start"],
            ],
            "forbidden_assertions": [],
        },
        "episode_a": {
            "objective": "Select a valid closed-set continuity relation.",
            "prompt": "Select a valid relation. JSON only.",
            "seed_state": {
                "goal": "Ship continuity cold-start receipt.",
                "threads": [{"id": "thread_gamma_receipt", "title": "receipt"}],
                "facts": ["This system is fully local."],
            },
        },
        "episode_b": {"prompt": "What relation is accepted?"},
    }


def _completed(text: str) -> InferenceResult:
    return InferenceResult(
        status=RunStatus.COMPLETED,
        output=text,
        error=None,
        elapsed_seconds=0.1,
        timeout_seconds=90.0,
        thinking_chars=0,
        final_response_chars=len(text),
    )


def _disk_accept_receipt(store: ContinuityStore) -> dict:
    paths = sorted(store.receipts_dir.glob("*.json"))
    assert paths, "no receipt files on disk"
    # Prefer accept_* or event-id receipt containing decision accepted
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("decision") == "accepted":
            return data
    return json.loads(paths[0].read_text(encoding="utf-8"))


def _disk_reject_receipt(store: ContinuityStore) -> dict:
    for p in sorted(store.receipts_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("decision") == "rejected":
            return data
    raise AssertionError("no rejection receipt on disk")


# ---------------------------------------------------------------------------
# 1–2 Live-plumbing accept/reject on disk
# ---------------------------------------------------------------------------


def test_accepted_live_plumbing_receipt_on_disk(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    store = ContinuityStore.open(r.store_path)
    disk = _disk_accept_receipt(store)
    assert disk["execution_scope"] == ExecutionScope.LIVE_PLUMBING.value
    assert disk["scientific_completion"] is False
    assert disk["decision"] == Decision.ACCEPTED.value
    assert disk["event_id"]
    assert disk.get("receipt_schema_version") == RECEIPT_SCHEMA_VERSION


def test_rejected_live_plumbing_receipt_on_disk(tmp_path: Path):
    task = _task()
    bad = json.dumps(
        {
            "continuity_assertions": [
                {
                    "subject_id": "ghost",
                    "relation": "remains_open",
                    "object_id": "question_cold_start",
                }
            ]
        }
    )
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(bad),
    )
    store = ContinuityStore.open(r.store_path)
    disk = _disk_reject_receipt(store)
    assert disk["execution_scope"] == ExecutionScope.LIVE_PLUMBING.value
    assert disk["scientific_completion"] is False
    assert disk["decision"] == Decision.REJECTED.value
    assert disk["event_id"] is None


# ---------------------------------------------------------------------------
# 3–5 Disk parse, byte-equivalence, no post-persist patch
# ---------------------------------------------------------------------------


def test_returned_receipt_byte_equivalent_to_disk(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    assert r.gate is not None
    disk = _disk_accept_receipt(ContinuityStore.open(r.store_path))
    # Returned receipt must match persisted bytes under canonical JSON
    assert canonical_json_bytes(r.gate.receipt) == canonical_json_bytes(disk)


def test_no_post_persistence_scientific_completion_patch(tmp_path: Path):
    """Regression: disk must already say false before any return-object rewrite."""
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    r = run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    disk = _disk_accept_receipt(ContinuityStore.open(store_root))
    # Disk truth
    assert disk["scientific_completion"] is False
    assert disk["execution_scope"] == "live_plumbing"
    # Returned object must not be the only place that is correct
    assert r.gate is not None
    assert r.gate.receipt["scientific_completion"] is False
    assert r.gate.scientific_completion is False


# ---------------------------------------------------------------------------
# 6–9 Event/receipt agreement
# ---------------------------------------------------------------------------


def test_event_receipt_agree_on_candidate_hash_event_id_scope_hashes(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    store = ContinuityStore.open(r.store_path)
    ev = store.list_events()[0]
    rec = _disk_accept_receipt(store)
    assert ev["source_candidate_hash"] == rec["source_candidate_hash"]
    assert ev["event_id"] == rec["event_id"]
    assert ev["execution_scope"] == rec["execution_scope"]
    assert ev["parent_state_hash"] == rec["parent_state_hash"]
    assert ev["resulting_state_hash"] == rec["resulting_state_hash"]
    assert ev["episode_id"] == rec["episode_id"]
    verify_event_receipt_pair(ev, rec)  # no raise


# ---------------------------------------------------------------------------
# 10–11 Contradiction fails closed
# ---------------------------------------------------------------------------


def test_contradictory_event_receipt_pair_fails_verification():
    event = {
        "event_id": "e1",
        "source_candidate_hash": "abc",
        "execution_scope": "live_plumbing",
        "parent_state_hash": "p1",
        "resulting_state_hash": "r1",
        "episode_id": "episode_a",
    }
    receipt = {
        "decision": "accepted",
        "event_id": "e1",
        "source_candidate_hash": "DIFFERENT",
        "execution_scope": "live_plumbing",
        "scientific_completion": False,
        "parent_state_hash": "p1",
        "resulting_state_hash": "r1",
        "episode_id": "episode_a",
    }
    with pytest.raises(ValueError, match="source_candidate_hash"):
        verify_event_receipt_pair(event, receipt)


def test_live_plumbing_event_with_scientific_completion_true_fails():
    event = {
        "event_id": "e1",
        "source_candidate_hash": "abc",
        "execution_scope": "live_plumbing",
        "parent_state_hash": "p1",
        "resulting_state_hash": "r1",
        "episode_id": "episode_a",
    }
    receipt = {
        "decision": "accepted",
        "event_id": "e1",
        "source_candidate_hash": "abc",
        "execution_scope": "live_plumbing",
        "scientific_completion": True,  # illegal for live_plumbing
        "parent_state_hash": "p1",
        "resulting_state_hash": "r1",
        "episode_id": "episode_a",
    }
    with pytest.raises(ValueError, match="scientific_completion"):
        verify_event_receipt_pair(event, receipt)


# ---------------------------------------------------------------------------
# 12–13 run_continuity derives terminal facts from disk
# ---------------------------------------------------------------------------


def test_run_continuity_verifies_persisted_receipt(tmp_path: Path, monkeypatch):
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    path = root / "experiments" / "run_continuity.py"
    spec = importlib.util.spec_from_file_location("ck_rc_receipt", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    out = tmp_path / "report.json"
    store_base = tmp_path / "stores"
    # Use inject via run_live_plumbing API directly (same as CLI)
    from conditioned_kernel.edge import load_profile

    prof = load_profile()
    report = mod.run_live_plumbing(
        [task],
        model="fake",
        prof=prof,
        dry=False,
        out=out,
        store_base=store_base,
        invoke_episode_b_model=False,
        inject_final_response=cand,
    )
    assert report["scientific_completion_n"] == 0
    assert report["headline_eligible"] is False
    assert report["scientific_status"] == "live_plumbing_only"
    assert report["event"]["scientific_completion_n"] == 0
    # Terminal facts from disk
    assert "persisted_terminal_receipts" in report
    for rec in report["persisted_terminal_receipts"]:
        assert rec["scientific_completion"] is False
        assert rec["execution_scope"] == "live_plumbing"


# ---------------------------------------------------------------------------
# 14–16 Accepted != scientific; dry scope; no accidental scientific default
# ---------------------------------------------------------------------------


def test_accepted_lifecycle_with_scientific_completion_false(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    assert r.gate is not None
    assert r.gate.decision is Decision.ACCEPTED
    assert r.gate.scientific_completion is False
    disk = _disk_accept_receipt(ContinuityStore.open(r.store_path))
    assert disk["decision"] == "accepted"
    assert disk["scientific_completion"] is False


def test_dry_run_receipts_explicitly_scoped(tmp_path: Path):
    store = ContinuityStore.create(
        tmp_path / "store",
        genesis={"schema_version": "ck.genesis.v1", "task_id": "t", "seed_relations": []},
        universe={
            "subject_ids": ["s"],
            "object_ids": ["o"],
            "relations": ["remains_open"],
            "valid_combinations": [("s", "remains_open", "o")],
            "forbidden_assertions": [],
        },
    )
    raw = json.dumps(
        {"continuity_assertions": [{"subject_id": "s", "relation": "remains_open", "object_id": "o"}]}
    )
    r = process_episode_a_candidate(
        raw,
        store=store,
        episode_id="episode_a",
        dry_run=True,
        dry_store_root=tmp_path / "dry",
        execution_scope=ExecutionScope.DRY_RUN,
    )
    assert r.decision is Decision.ACCEPTED
    assert r.scientific_completion is False
    dry = ContinuityStore.open(tmp_path / "dry")
    disk = _disk_accept_receipt(dry)
    assert disk["execution_scope"] == "dry_run"
    assert disk["scientific_completion"] is False
    # Primary store untouched
    assert store.list_events() == []


def test_scientific_experiment_not_default_for_omitted_live_path(tmp_path: Path):
    """process_episode_a_candidate requires explicit scope; live path uses live_plumbing."""
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    disk = _disk_accept_receipt(ContinuityStore.open(r.store_path))
    assert disk["execution_scope"] != ExecutionScope.SCIENTIFIC_EXPERIMENT.value
    assert disk["execution_scope"] == ExecutionScope.LIVE_PLUMBING.value


def test_unknown_execution_scope_fails_closed(tmp_path: Path):
    store = ContinuityStore.create(
        tmp_path / "store",
        genesis={"schema_version": "ck.genesis.v1", "task_id": "t", "seed_relations": []},
        universe={
            "subject_ids": ["s"],
            "object_ids": ["o"],
            "relations": ["remains_open"],
            "valid_combinations": [("s", "remains_open", "o")],
            "forbidden_assertions": [],
        },
    )
    raw = json.dumps(
        {"continuity_assertions": [{"subject_id": "s", "relation": "remains_open", "object_id": "o"}]}
    )
    with pytest.raises(ValueError, match="execution_scope|unknown"):
        process_episode_a_candidate(
            raw,
            store=store,
            episode_id="episode_a",
            execution_scope="not_a_real_scope",
        )


def test_execution_scope_enum_is_closed():
    values = {s.value for s in ExecutionScope}
    assert values == {
        "offline_test",
        "dry_run",
        "live_plumbing",
        "scientific_experiment",
    }
