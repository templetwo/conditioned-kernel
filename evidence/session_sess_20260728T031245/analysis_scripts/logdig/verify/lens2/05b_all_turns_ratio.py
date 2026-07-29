#!/usr/bin/env python3
"""Independent extension of 05_crosscheck.py's method to ALL 19 dashboard
turns, to verify the claimed ratio range:
  evening: 1.17x-1.77x (mean ~1.5x)
  morning: 0.90x-0.91x

05_crosscheck.py itself only computes this for ONE turn (evening turn 2,
'im good...'). This script re-applies its exact same method (context_share
total / json.dumps(payload) compact bytes) to all 19 turns using the
pipeline's own compute.context_share_bytes, to see whether the claimed
range holds across the full turn set.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.observatory import compute  # noqa: E402

TURNS_DIR = Path("/Users/vaquez/conditioned-kernel/logs/dashboard/turns")


def main():
    files = sorted(TURNS_DIR.glob("turn_*.json"))
    print(f"{len(files)} turns\n")
    print(f"{'#':>2} {'started_at':20} {'regime':8} {'total_share':>12} {'payload_pretty':>15} {'payload_compact':>16} {'ratio(pretty)':>14} {'ratio(compact)':>15}")

    morning_ratios_pretty, morning_ratios_compact = [], []
    evening_ratios_pretty, evening_ratios_compact = [], []

    for i, fp in enumerate(files, 1):
        with fp.open() as f:
            d = json.load(f)
        packet = d["packet"]
        model_input = d["passes"][-1]["model_input"]
        rows = compute.context_share_bytes(packet, model_input)
        total_share = sum(r["bytes"] for r in rows)
        payload = model_input.get("payload") or {}
        payload_pretty = compute.bytes_len(json.dumps(payload, ensure_ascii=False))
        payload_compact = compute.bytes_len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        ratio_pretty = total_share / payload_pretty if payload_pretty else float("nan")
        ratio_compact = total_share / payload_compact if payload_compact else float("nan")
        regime = "morning" if d["started_at"] < "2026-07-28T20:00:00Z" else "evening"
        if regime == "morning":
            morning_ratios_pretty.append(ratio_pretty)
            morning_ratios_compact.append(ratio_compact)
        else:
            evening_ratios_pretty.append(ratio_pretty)
            evening_ratios_compact.append(ratio_compact)
        print(f"{i:>2} {d['started_at']:20} {regime:8} {total_share:>12} {payload_pretty:>15} {payload_compact:>16} {ratio_pretty:>13.3f}x {ratio_compact:>14.3f}x")

    print()
    print("morning (pretty)  min/max/mean:", min(morning_ratios_pretty), max(morning_ratios_pretty), sum(morning_ratios_pretty)/len(morning_ratios_pretty))
    print("morning (compact) min/max/mean:", min(morning_ratios_compact), max(morning_ratios_compact), sum(morning_ratios_compact)/len(morning_ratios_compact))
    print("evening (pretty)  min/max/mean:", min(evening_ratios_pretty), max(evening_ratios_pretty), sum(evening_ratios_pretty)/len(evening_ratios_pretty))
    print("evening (compact) min/max/mean:", min(evening_ratios_compact), max(evening_ratios_compact), sum(evening_ratios_compact)/len(evening_ratios_compact))


if __name__ == "__main__":
    main()
