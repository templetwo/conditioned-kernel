"""RUN 00.6C — live Episode A → fresh Episode B integration tests.

Offline only except where inject_inference is used. No M0.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from conditioned_kernel.continuity_gate import Decision
from conditioned_kernel.continuity_live import (
    LIVE_PLUMBING_POLICY,
    compile_episode_a_packet,
    live_plumbing_headline_policy,
    run_episode_a_live,
    run_episode_b_live,
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
                ["thread_gamma_receipt", "references", "question_cold_start"],
            ],
            "forbidden_assertions": [],
        },
        "episode_a": {
            "objective": (
                "Select a valid closed-set continuity relation for "
                "thread_gamma_receipt about question_cold_start."
            ),
            "prompt": (
                "Select a valid closed-set continuity relation for "
                "thread_gamma_receipt about question_cold_start. JSON only."
            ),
            "seed_state": {
                "goal": "Ship the continuity cold-start receipt on the Orin board.",
                "threads": [
                    {
                        "id": "thread_gamma_receipt",
                        "title": "Wire cold-start receipt fields",
                    }
                ],
                "facts": [
                    "This system is fully local.",
                    "Deliverable is the continuity cold-start receipt on Orin.",
                ],
            },
        },
        "episode_b": {
            "prompt": "What continuity relation is accepted for thread_gamma_receipt?",
        },
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


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------


def test_run_continuity_exports_live_plumbing_entrypoints():
    root = Path(__file__).resolve().parents[1]
    path = root / "experiments" / "run_continuity.py"
    spec = importlib.util.spec_from_file_location("ck_rc_live", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    assert hasattr(mod, "episode_a_live")
    assert hasattr(mod, "episode_b_live")
    assert hasattr(mod, "live_plumbing_headline_policy")
    assert mod.live_plumbing_headline_policy()["scientific_status"] == "live_plumbing_only"


def test_episode_a_final_response_enters_gate_exactly_once(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    assert r.gate_invocations == 1
    assert r.gate is not None
    assert r.gate.decision is Decision.ACCEPTED


def test_accepted_episode_a_one_event_one_receipt(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    store = ContinuityStore.open(r.store_path)
    assert len(store.list_events()) == 1
    assert len(store.terminal_receipts()) == 1
    assert store.terminal_receipts()[0]["decision"] == "accepted"


def test_rejected_episode_a_zero_events_one_receipt(tmp_path: Path):
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
    assert r.gate is not None
    assert r.gate.decision is Decision.REJECTED
    assert store.list_events() == []
    assert len(store.terminal_receipts()) == 1


def test_episode_a_can_terminate_before_episode_b(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    r = run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    # Simulate process end: only store path remains
    assert Path(r.store_path).exists()
    # No Episode A result object required for B
    b = run_episode_b_live(task, store_root=store_root, dry=True)
    assert b.replay_ok
    assert b.used_episode_a_memory is False


def test_episode_b_fresh_process_reads_only_replay(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    store_path = str(store_root)
    src = str(Path(__file__).resolve().parents[1] / "src")
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {src!r})
        from conditioned_kernel.continuity_live import run_episode_b_live
        task = json.loads({json.dumps(task)!r})
        b = run_episode_b_live(task, store_root={store_path!r}, dry=True)
        print(json.dumps({{
            "replay_ok": b.replay_ok,
            "relation_count": b.relation_count,
            "used_memory": b.used_episode_a_memory,
            "rels": b.accepted_relations,
        }}))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["replay_ok"] is True
    assert payload["used_memory"] is False
    assert payload["relation_count"] >= 1
    assert any(r["subject_id"] == "thread_gamma_receipt" for r in payload["rels"])


def test_accepted_assertion_in_episode_b_packet(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    b = run_episode_b_live(task, store_root=store_root, dry=True)
    assert b.packet is not None
    assert any(
        r["subject_id"] == "thread_gamma_receipt"
        and r["relation"] == "remains_open"
        for r in b.packet["accepted_relations"]
    )


def test_rejected_assertion_absent_from_episode_b(tmp_path: Path):
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
    store_root = tmp_path / "store"
    run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(bad),
    )
    b = run_episode_b_live(task, store_root=store_root, dry=True)
    assert b.relation_count == 0
    assert b.accepted_relations == []


def test_raw_episode_a_prose_not_in_authoritative_state(tmp_path: Path):
    task = _task()
    prose = json.dumps(
        {
            "continuity_assertions": [
                {
                    "subject_id": "thread_gamma_receipt",
                    "relation": "remains_open",
                    "object_id": "question_cold_start",
                }
            ],
            "answer": "SECRET FREEFORM xyzzy should never persist",
        }
    )
    store_root = tmp_path / "store"
    run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(prose),
    )
    b = run_episode_b_live(task, store_root=store_root, dry=True)
    blob = json.dumps(b.packet)
    assert "SECRET FREEFORM" not in blob
    assert "xyzzy" not in blob


def test_episode_b_does_not_require_episode_a_memory(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    a = run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    del a  # drop Episode A object
    b = run_episode_b_live(task, store_root=store_root, dry=True)
    assert b.replay_ok
    assert b.used_episode_a_memory is False


def test_model_identity_swap_does_not_erase_continuity(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    run_episode_a_live(
        task,
        store_root=store_root,
        model="model_a:0.5b",
        inject_inference=_completed(cand),
        provenance={"model": "model_a:0.5b"},
    )
    # Episode B with different configured model — continuity from store only
    b = run_episode_b_live(
        task, store_root=store_root, model="model_b:1b", dry=True
    )
    assert b.relation_count >= 1
    store = ContinuityStore.open(store_root)
    assert store.list_events()[0]["provenance"]["model"] == "model_a:0.5b"


def test_invalid_replay_blocks_episode_b_generation(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    # Tamper event
    store = ContinuityStore.open(store_root)
    path = next(store.events_dir.glob("*.json"))
    data = json.loads(path.read_text())
    data["assertions"][0]["object_id"] = "tampered"
    path.write_text(json.dumps(data) + "\n")
    b = run_episode_b_live(task, store_root=store_root, dry=True, invoke_model=True)
    assert b.replay_ok is False
    assert b.packet is None
    assert b.error and "REPLAY_FAILED" in b.error


def test_dry_mode_isolated_and_incomplete(tmp_path: Path):
    task = _task()
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        dry=True,
    )
    assert r.dry_run is True
    assert r.scientific_completion is False
    assert r.gate_invocations == 0
    assert ContinuityStore.open(r.store_path).list_events() == []


def test_live_smoke_mode_scientifically_incomplete(tmp_path: Path):
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed(cand),
    )
    assert r.scientific_completion is False
    policy = live_plumbing_headline_policy()
    assert policy["headline_eligible"] is False
    assert policy["scientific_status"] == "live_plumbing_only"
    assert r.gate is not None and r.gate.scientific_completion is False


def test_no_final_response_creates_no_continuity_event(tmp_path: Path):
    task = _task()
    inf = InferenceResult(
        status=RunStatus.NO_FINAL_RESPONSE,
        output=None,
        error="thinking only",
        elapsed_seconds=1.0,
        timeout_seconds=90.0,
        thinking_chars=500,
        final_response_chars=0,
    )
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=inf,
    )
    assert r.gate_invocations == 0
    assert r.final_response is None
    assert ContinuityStore.open(r.store_path).list_events() == []


def test_timeout_creates_no_continuity_event(tmp_path: Path):
    task = _task()
    inf = InferenceResult(
        status=RunStatus.TIMEOUT,
        output=None,
        error="timed out",
        elapsed_seconds=90.0,
        timeout_seconds=90.0,
    )
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=inf,
    )
    assert r.events_n == 0
    assert ContinuityStore.open(r.store_path).list_events() == []


def test_schema_invalid_candidate_creates_no_continuity_event(tmp_path: Path):
    task = _task()
    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        inject_inference=_completed('{"not_assertions": true}'),
    )
    assert r.gate is not None
    assert r.gate.decision is Decision.REJECTED
    assert ContinuityStore.open(r.store_path).list_events() == []


def test_episode_a_packet_omits_gold_assertion(tmp_path: Path):
    task = _task()
    u = universe_from_task(task)
    packet = compile_episode_a_packet(task, u)
    blob = json.dumps(packet)
    # Must not embed the expected triple as labeled gold
    assert "expected_assertion" not in blob
    assert "answer_key" not in blob
    assert "gold" not in blob.lower()
    assert "subject_ids" in packet
    assert "allowed_relations" in packet


def test_canonical_typed_path_used_for_live_episode_a(tmp_path: Path):
    """run_episode_a_live must use OllamaClient.run when no inject (spy client)."""
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    calls: list[str] = []

    class Spy:
        def run(self, model_input):
            calls.append("run")
            return _completed(cand)

        def generate(self, model_input):
            calls.append("generate")
            raise AssertionError("must not call generate()")

    r = run_episode_a_live(
        task,
        store_root=tmp_path / "store",
        model="fake",
        client=Spy(),  # type: ignore[arg-type]
    )
    assert calls == ["run"]
    assert r.gate is not None and r.gate.decision is Decision.ACCEPTED


def test_planned_passages_have_terminal_facts(tmp_path: Path):
    """Episode A + B produce structured diagnostic facts; sci completion 0."""
    task = _task()
    cand = valid_plumbing_candidate(universe_from_task(task))
    store_root = tmp_path / "store"
    a = run_episode_a_live(
        task,
        store_root=store_root,
        model="fake",
        inject_inference=_completed(cand),
    )
    b = run_episode_b_live(task, store_root=store_root, dry=True)
    assert a.scientific_completion is False
    assert b.scientific_completion is False
    assert a.inference_status == "completed"
    assert b.replay_ok is True
    facts = {
        "episode_a_inference": a.inference_status,
        "events_n": a.events_n,
        "rejection_n": a.rejection_receipts_n,
        "episode_b_relations": b.relation_count,
        "scientific_completion_n": 0,
        **LIVE_PLUMBING_POLICY,
    }
    assert facts["scientific_completion_n"] == 0
    assert facts["headline_eligible"] is False
