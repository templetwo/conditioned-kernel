#!/usr/bin/env python3
"""Lens 2 item 4: concrete packet-level diff, one morning-rejected turn vs
one evening-accepted turn of matched user-input length (both 11 chars).

morning: turn_20260728T190222Z_d25ed1.json  user_input='dont reject'   (11 chars, 27 B)
evening: turn_20260728T203813Z_40ba91.json  user_input='hello there'   (11 chars, 11 B)

Every value below is read straight out of the two TurnTrace files'
`packet` field -- the real, logged arrival packet each turn's final pass
actually sent (see trace.py: `packet=final_packet`, which for the final
pass is `result.packet`, the literal object pipeline.py built and passed
to build_model_input, not a reconstruction).
"""
import json
from pathlib import Path

TURNS_DIR = Path("/Users/vaquez/conditioned-kernel/logs/dashboard/turns")

MORNING = TURNS_DIR / "turn_20260728T190222Z_d25ed1.json"
EVENING = TURNS_DIR / "turn_20260728T203813Z_40ba91.json"


def load(fp):
    with fp.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    m = load(MORNING)
    e = load(EVENING)

    print(f"morning: {MORNING.name}  user_input={m['user_input']!r} ({len(m['user_input'])} chars) "
          f"decision={m['final_decision']['decision']}")
    print(f"evening: {EVENING.name}  user_input={e['user_input']!r} ({len(e['user_input'])} chars) "
          f"decision={e['final_decision']['decision']}")
    print()

    mp, ep = m["packet"], e["packet"]
    print("=" * 100)
    print("top-level packet key sets")
    print("=" * 100)
    mk, ek = set(mp.keys()), set(ep.keys())
    print("keys only in MORNING packet:", sorted(mk - ek))
    print("keys only in EVENING packet:", sorted(ek - mk))
    print("keys in both:               ", sorted(mk & ek))

    print()
    print("=" * 100)
    print("acceptance_mode / runtime_config")
    print("=" * 100)
    print("morning runtime_config.acceptance_mode:", m["runtime_config"]["acceptance_mode"])
    print("evening runtime_config.acceptance_mode:", e["runtime_config"]["acceptance_mode"])
    print("morning packet.acceptance_contract:", mp.get("acceptance_contract"))
    print("evening packet.acceptance_contract:", ep.get("acceptance_contract"))

    print()
    print("=" * 100)
    print("facts")
    print("=" * 100)
    print(f"morning: {len(mp.get('facts') or [])} fact lines")
    for f in mp.get("facts") or []:
        print("   -", f)
    print(f"evening: {len(ep.get('facts') or [])} fact lines")
    for f in ep.get("facts") or []:
        print("   -", f)

    print()
    print("=" * 100)
    print("open_threads")
    print("=" * 100)
    print("morning:", mp.get("open_threads"))
    print("evening:", ep.get("open_threads"))

    print()
    print("=" * 100)
    print("recent_turns (as shipped in the packet)")
    print("=" * 100)
    print(f"morning: {len(mp.get('recent_turns') or [])} entries")
    for t in mp.get("recent_turns") or []:
        print("   -", {"user": t.get("user"), "answer": (t.get("answer") or "")[:60] + "...", "ts": t.get("ts")})
    print(f"evening: {len(ep.get('recent_turns') or [])} entries")
    for t in ep.get("recent_turns") or []:
        print("   -", t)

    print()
    print("=" * 100)
    print("state_digest")
    print("=" * 100)
    print("morning:", mp.get("state_digest"))
    print("evening:", ep.get("state_digest"))

    print()
    print("=" * 100)
    print("constraints")
    print("=" * 100)
    print("morning:", mp.get("constraints"))
    print("evening:", ep.get("constraints"))

    print()
    print("=" * 100)
    print("context_field (companion selection map) -- morning has none")
    print("=" * 100)
    mcf = mp.get("context_field")
    ecf = ep.get("context_field")
    print("morning packet.context_field present?", mcf is not None)
    if ecf is not None:
        print("evening context_field.available_count:", ecf["available_count"])
        print("evening context_field.selected_count:", ecf["selected_count"])
        print("evening context_field.omitted_count:", ecf["omitted_count"])
        print("evening context_field.selected contribution ids:", ecf["selected_ids"])
        print("evening selected content:")
        for c in ecf["selected"]:
            print("   -", c["contribution_id"], c["kind"], c.get("content"))

    print()
    print("=" * 100)
    print("_edge (edge-budget accounting)")
    print("=" * 100)
    print("morning:", mp.get("_edge"))
    print("evening:", ep.get("_edge"))

    print()
    print("=" * 100)
    print("final_decision")
    print("=" * 100)
    print("morning:", m["final_decision"])
    print("evening:", e["final_decision"])

    print()
    print("=" * 100)
    print("context_share_bytes side-by-side")
    print("=" * 100)
    mrows = {r["source_id"]: r for r in m["context_share_bytes"]}
    erows = {r["source_id"]: r for r in e["context_share_bytes"]}
    all_src = sorted(set(mrows) | set(erows))
    print(f"{'source':22} {'morning B':>10} {'morning %':>10}   {'evening B':>10} {'evening %':>10}")
    for s in all_src:
        mr = mrows.get(s, {"bytes": 0, "share_pct": 0.0})
        er = erows.get(s, {"bytes": 0, "share_pct": 0.0})
        print(f"{s:22} {mr['bytes']:>10} {mr['share_pct']:>9.2f}%   {er['bytes']:>10} {er['share_pct']:>9.2f}%")
    mtotal = sum(r["bytes"] for r in m["context_share_bytes"])
    etotal = sum(r["bytes"] for r in e["context_share_bytes"])
    print(f"{'TOTAL':22} {mtotal:>10}            {etotal:>10}")

    print()
    print("=" * 100)
    print("system prompt text actually sent (from final pass model_input)")
    print("=" * 100)
    def system_text(trace):
        mi = trace["passes"][-1]["model_input"]
        for msg in (mi.get("payload") or {}).get("messages") or []:
            if msg.get("role") == "system":
                return msg.get("content")
        return None
    print("morning system text:")
    print(" ", system_text(m))
    print("evening system text:")
    print(" ", system_text(e))

    print()
    print("=" * 100)
    print("user message content actually sent (from final pass model_input)")
    print("=" * 100)
    def user_text(trace):
        mi = trace["passes"][-1]["model_input"]
        for msg in (mi.get("payload") or {}).get("messages") or []:
            if msg.get("role") == "user":
                return msg.get("content")
        return None
    print("morning user message:")
    print(" ", user_text(m))
    print()
    print("evening user message:")
    print(" ", user_text(e))


if __name__ == "__main__":
    main()
