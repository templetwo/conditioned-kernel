"""Shared loaders for Lens 3 (validation forensics) analysis scripts.

READ-ONLY against /Users/vaquez/conditioned-kernel/logs and /state.
Uses the pipeline's own conditioned_kernel.observatory.compute and
conditioned_kernel.return_path.validate helpers wherever a rule already
exists there, rather than re-deriving thresholds locally.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LOGS_DIR = Path("/Users/vaquez/conditioned-kernel/logs")
STATE_DIR = Path("/Users/vaquez/conditioned-kernel/state")
DASHBOARD_DIR = LOGS_DIR / "dashboard" / "turns"

# Make the real package importable.
sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def load_candidates() -> list[dict]:
    return load_jsonl(LOGS_DIR / "candidates.jsonl")


def load_receipts() -> list[dict]:
    return load_jsonl(LOGS_DIR / "receipts.jsonl")


def load_history() -> list[dict]:
    return load_jsonl(LOGS_DIR / "history.jsonl")


def load_dashboard_turns() -> list[dict]:
    files = sorted(DASHBOARD_DIR.glob("*.json"))
    out = []
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            d = json.load(f)
        d["_file"] = fp.name
        out.append(d)
    return out


def load_current_state() -> dict:
    with (STATE_DIR / "current.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def group_turns(candidates: list[dict], receipts: list[dict]) -> list[list[tuple[dict, dict]]]:
    """Group the 1:1 (candidate, receipt) line pairs into logical turns.

    Turn boundary rule (verified against the data): pass_index resets to 0
    at the start of every new logical turn; a turn ends at the first pass
    whose receipt.decision is 'accept' or 'reject' (terminal). 'repair'
    always continues to pass_index+1 within the same turn. Confirmed
    structurally: candidates.jsonl has exactly 93 lines = 58 turns
    (23 single-pass + 35 two-pass), matching history.jsonl's 58 terminal
    entries exactly.
    """
    assert len(candidates) == len(receipts)
    turns: list[list[tuple[dict, dict]]] = []
    current: list[tuple[dict, dict]] = []
    for c, r in zip(candidates, receipts):
        if c["pass_index"] == 0 and current:
            turns.append(current)
            current = []
        current.append((c, r))
        if r.get("decision") in ("accept", "reject"):
            turns.append(current)
            current = []
    if current:
        turns.append(current)
    return turns


def turn_user_input(turn: list[tuple[dict, dict]], history_by_candidate: dict[str, dict]) -> str | None:
    """Every pass within one logical turn answers the same user_input (the
    packet is rebuilt on repair with the same user_input + an updated repair
    plan). Recovered from history.jsonl's terminal-pass record (the only
    place user_input is logged for non-dashboard turns) and applied to every
    pass in the turn, including repair passes that never reached history
    directly.
    """
    for c, r in turn:
        h = history_by_candidate.get(c["candidate_id"])
        if h is not None:
            return h.get("user_input")
    return None


def base_check_name(violation_or_advisory: str) -> str:
    """Strip the ':<detail>' suffix validate.py appends to some violation
    strings (e.g. 'unknown_thread_touch:orin_nano_8gb' -> 'unknown_thread_touch',
    'max_words_exceeded:190>180' -> 'max_words_exceeded')."""
    return violation_or_advisory.split(":", 1)[0]


if __name__ == "__main__":
    cands = load_candidates()
    rcpts = load_receipts()
    hist = load_history()
    dash = load_dashboard_turns()
    turns = group_turns(cands, rcpts)
    print(f"candidates={len(cands)} receipts={len(rcpts)} history={len(hist)} "
          f"dashboard_turns={len(dash)} grouped_turns={len(turns)}")
    sizes = {}
    for t in turns:
        sizes[len(t)] = sizes.get(len(t), 0) + 1
    print("turn pass-count distribution:", sizes)
