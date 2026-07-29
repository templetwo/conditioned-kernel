#!/usr/bin/env python3
"""Lens 2 item 1+2: full user-share series (table + sparkline) and six-source
ranking per turn, morning-rejected vs evening-accepted regime comparison.

All numbers come straight from each TurnTrace's own `context_share_bytes`
field (computed once, at trace-assembly time, by
`conditioned_kernel.observatory.compute.context_share_bytes`). Nothing here
re-derives byte shares independently -- item 5's script does that
cross-check separately.
"""
import json
import statistics as stats
from pathlib import Path

TURNS_DIR = Path("/Users/vaquez/conditioned-kernel/logs/dashboard/turns")

SOURCES = [
    "current_user_input",
    "recent_dialogue",
    "durable_state",
    "system_instructions",
    "output_schema",
    "constraints",
]

SPARK_CHARS = " ▁▂▃▄▅▆▇█"


def spark(values, vmin=None, vmax=None):
    vmin = min(values) if vmin is None else vmin
    vmax = max(values) if vmax is None else vmax
    span = (vmax - vmin) or 1.0
    out = []
    for v in values:
        idx = int(round((v - vmin) / span * (len(SPARK_CHARS) - 1)))
        idx = max(0, min(len(SPARK_CHARS) - 1, idx))
        out.append(SPARK_CHARS[idx])
    return "".join(out)


def load_turns():
    files = sorted(TURNS_DIR.glob("turn_*.json"))
    out = []
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            out.append((fp.name, json.load(f)))
    return out


def main():
    turns = load_turns()
    print(f"{len(turns)} turns loaded\n")

    print("=" * 100)
    print("ITEM 1 — user-input share of total model-input bytes, every turn in order")
    print("=" * 100)
    series = []
    header = f"{'#':>2} {'started_at':20} {'regime':9} {'decision':8} {'user_input':32} {'bytes':>6} {'total':>6} {'pct':>7}"
    print(header)
    print("-" * len(header))
    for i, (fname, d) in enumerate(turns, 1):
        csb = {r["source_id"]: r for r in d["context_share_bytes"]}
        total = sum(r["bytes"] for r in d["context_share_bytes"])
        u = csb.get("current_user_input", {})
        regime = "morning" if d["started_at"] < "2026-07-28T20:00:00Z" else "evening"
        pct = u.get("share_pct", 0.0)
        series.append(pct)
        print(
            f"{i:>2} {d['started_at']:20} {regime:9} {d['final_decision']['decision']:8} "
            f"{d['user_input']!r:32.32} {u.get('bytes', 0):>6} {total:>6} {pct:>6.2f}%"
        )

    print()
    print("ASCII sparkline of current_user_input share_pct across all 19 turns (chrono order):")
    print(" ", spark(series), f"  min={min(series):.2f}% max={max(series):.2f}%")
    print(
        "  scale: each glyph is one turn, height mapped linearly between the series' own"
        f" min ({min(series):.2f}%) and max ({max(series):.2f}%)"
    )
    lo_i = series.index(min(series))
    hi_i = series.index(max(series))
    print(
        f"  min turn: #{lo_i+1} {turns[lo_i][1]['started_at']} {turns[lo_i][1]['user_input']!r} "
        f"= {series[lo_i]:.2f}%"
    )
    print(
        f"  max turn: #{hi_i+1} {turns[hi_i][1]['started_at']} {turns[hi_i][1]['user_input']!r} "
        f"= {series[hi_i]:.2f}%"
    )

    print()
    print("=" * 100)
    print("ITEM 2a — per-turn six-source ranking (source with rank=1 is the largest share)")
    print("=" * 100)
    rank1_counts = {}
    for i, (fname, d) in enumerate(turns, 1):
        rows = sorted(d["context_share_bytes"], key=lambda r: -r["bytes"])
        regime = "morning" if d["started_at"] < "2026-07-28T20:00:00Z" else "evening"
        top = rows[0]
        rank1_counts[top["source_id"]] = rank1_counts.get(top["source_id"], 0) + 1
        ranking = ", ".join(f"{r['source_id']}={r['share_pct']:.1f}%" for r in rows)
        print(f"{i:>2} [{regime}] {d['user_input']!r:28.28} -> {ranking}")

    print()
    print("rank-1 (dominant source) frequency across all 19 turns:")
    for k, v in sorted(rank1_counts.items(), key=lambda kv: -kv[1]):
        print(f"   {k:22} {v:>2} turns")

    print()
    print("=" * 100)
    print("ITEM 2b — mean share_pct per source, morning-rejected (n=3) vs evening-accepted (n=16)")
    print("=" * 100)
    morning = [d for _, d in turns if d["started_at"] < "2026-07-28T20:00:00Z"]
    evening = [d for _, d in turns if d["started_at"] >= "2026-07-28T20:00:00Z"]
    assert len(morning) == 3 and len(evening) == 16, (len(morning), len(evening))

    def means(group):
        out = {}
        for src in SOURCES:
            vals = []
            for d in group:
                row = next((r for r in d["context_share_bytes"] if r["source_id"] == src), None)
                if row:
                    vals.append(row["share_pct"])
            out[src] = (stats.mean(vals) if vals else 0.0, min(vals) if vals else 0.0, max(vals) if vals else 0.0)
        return out

    m_means = means(morning)
    e_means = means(evening)
    print(f"{'source':22} {'morning mean%':>14} {'morning range':>18}   {'evening mean%':>14} {'evening range':>18}")
    for src in SOURCES:
        mm, mlo, mhi = m_means[src]
        em, elo, ehi = e_means[src]
        print(
            f"{src:22} {mm:>13.2f}% [{mlo:5.2f},{mhi:5.2f}]   {em:>13.2f}% [{elo:5.2f},{ehi:5.2f}]"
        )

    # bytes too (absolute), not just pct, since totals differ turn to turn
    print()
    print("mean absolute bytes per source, morning vs evening")

    def bytes_means(group):
        out = {}
        for src in SOURCES:
            vals = []
            for d in group:
                row = next((r for r in d["context_share_bytes"] if r["source_id"] == src), None)
                if row:
                    vals.append(row["bytes"])
            out[src] = stats.mean(vals) if vals else 0.0
        return out

    mb = bytes_means(morning)
    eb = bytes_means(evening)
    print(f"{'source':22} {'morning mean B':>15} {'evening mean B':>15}")
    for src in SOURCES:
        print(f"{src:22} {mb[src]:>15.1f} {eb[src]:>15.1f}")
    mtotal = stats.mean([sum(r["bytes"] for r in d["context_share_bytes"]) for d in morning])
    etotal = stats.mean([sum(r["bytes"] for r in d["context_share_bytes"]) for d in evening])
    print(f"{'TOTAL model-input bytes':22} {mtotal:>15.1f} {etotal:>15.1f}")


if __name__ == "__main__":
    main()
