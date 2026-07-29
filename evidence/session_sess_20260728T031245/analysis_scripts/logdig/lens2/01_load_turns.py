#!/usr/bin/env python3
"""Lens 2: load the 19 dashboard TurnTraces in chronological (filename) order
and dump the fields needed for the substrate-composition-dynamics analysis.

Read-only against /Users/vaquez/conditioned-kernel/logs/dashboard/turns/*.json.
"""
import json
import sys
from pathlib import Path

TURNS_DIR = Path("/Users/vaquez/conditioned-kernel/logs/dashboard/turns")
OUT_DIR = Path("/Users/vaquez/.claude/jobs/4855c88d/tmp/logdig/lens2")


def load_all():
    files = sorted(TURNS_DIR.glob("turn_*.json"))
    turns = []
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            d = json.load(f)
        turns.append((fp.name, d))
    return turns


def main():
    turns = load_all()
    print(f"Loaded {len(turns)} turn files from {TURNS_DIR}")
    rows = []
    for fname, d in turns:
        csb = {r["source_id"]: r for r in d.get("context_share_bytes", [])}
        total_model_input_bytes = sum(r["bytes"] for r in d.get("context_share_bytes", []))
        row = {
            "file": fname,
            "turn_id": d.get("turn_id"),
            "started_at": d.get("started_at"),
            "user_input": d.get("user_input"),
            "user_input_len_chars": len(d.get("user_input") or ""),
            "decision": (d.get("final_decision") or {}).get("decision"),
            "label": (d.get("final_decision") or {}).get("label"),
            "violations": (d.get("final_decision") or {}).get("violations"),
            "advisories": (d.get("final_decision") or {}).get("advisories"),
            "packet_bytes": d.get("packet_bytes"),
            "total_model_input_bytes": total_model_input_bytes,
            "context_share_bytes": csb,
            "n_recent_turns": len((d.get("packet") or {}).get("recent_turns") or []),
            "n_facts": len((d.get("packet") or {}).get("facts") or []),
            "n_open_threads": len((d.get("packet") or {}).get("open_threads") or []),
            "n_passes": len(d.get("passes") or []),
        }
        rows.append(row)

    out_path = OUT_DIR / "turns_summary.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote {out_path}")

    for r in rows:
        cs = r["context_share_bytes"]
        user_pct = cs.get("current_user_input", {}).get("share_pct")
        user_bytes = cs.get("current_user_input", {}).get("bytes")
        print(
            f"{r['started_at']}  {r['file'][:40]:40s}  decision={r['decision']:8s}  "
            f"user_input={r['user_input']!r:25.25s}  user_bytes={user_bytes:>5}  "
            f"user_pct={user_pct:>6}  total={r['total_model_input_bytes']:>5}  "
            f"packet_bytes={r['packet_bytes']:>5}  n_recent={r['n_recent_turns']}"
        )


if __name__ == "__main__":
    main()
