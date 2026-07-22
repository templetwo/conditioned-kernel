import json
from pathlib import Path

from conditioned_kernel.pipeline import run_turn


def test_dry_accept_writes_receipt(tmp_path: Path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    # minimal state
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model.",
                "active_profile": "ck_v0",
                "session_id": "sess_test",
                "receipt_count_24h": 0,
                "flags": {"sensors": False, "tools": False, "cloud": False, "max_repair_passes": 1},
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

    dry = json.dumps(
        {
            "answer": (
                "Design intent: demonstrate conditioned-kernel substrate gain "
                "over bare generation on a small local model."
            ),
            "evidence_used": [
                "This system is fully local.",
                "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model.",
            ],
            "next_state": {"thread_touch": ["thread_min_model"], "proposed_note": "test"},
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
    assert (logs_dir / "receipts.jsonl").exists()
    assert (logs_dir / "history.jsonl").exists()
    text = (logs_dir / "receipts.jsonl").read_text(encoding="utf-8")
    assert "accept" in text
