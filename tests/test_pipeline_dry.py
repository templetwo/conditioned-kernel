import json
from pathlib import Path

from conditioned_kernel.pipeline import run_turn


def test_dry_accept_writes_receipt(tmp_path: Path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": (
                    "Demonstrate conditioned-kernel substrate gain over bare generation "
                    "on a small local model under Jetson Orin Nano 8GB edge budgets."
                ),
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

    # Non-echo answer that is responsive to "Summarize design intent"
    dry = json.dumps(
        {
            "answer": (
                "Design intent is edge-first substrate conditioning: keep models small "
                "and local, put continuity in files, measure gain under Jetson budgets."
            ),
            "evidence_used": [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": ["thread_min_model"]},
        }
    )

    result = run_turn(
        "Summarize design intent.",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert result.ok is True
    assert result.decision == "accept"
    assert "goal_echo" not in (result.receipt.get("violations") or [])
    assert (logs_dir / "receipts.jsonl").exists()


def test_dry_goal_echo_rejected(tmp_path: Path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    goal = (
        "Demonstrate conditioned-kernel substrate gain over bare generation "
        "on a small local model under Jetson Orin Nano 8GB edge budgets."
    )
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": goal,
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_test",
                "flags": {
                    "sensors": False,
                    "cloud": False,
                    "edge_target": "jetson_orin_nano_8gb",
                    "one_model_only": True,
                    "max_repair_passes": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text("[]", encoding="utf-8")
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")

    dry = json.dumps(
        {
            "answer": goal,
            "evidence_used": ["This system is fully local."],
            "next_state": {},
        }
    )
    result = run_turn(
        "State the design intent.",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert result.ok is False
    assert "goal_echo" in (result.receipt.get("violations") or [])
