#!/usr/bin/env python3
"""Lens 2 item 3: recent_turns byte-share evolution across the 16 accepted
evening turns, and whether state.RECENT_TURNS_MAX_BYTES (1200 B) ever fires.

Two independent measurements, both against the pipeline's own real code:

(A) What actually rode in the packet's `recent_turns` field each turn (the
    POST-SELECTION, companion-mode subset) -- read straight off each
    TurnTrace's packet.recent_turns, sized with the pipeline's own
    state.recent_turns_byte_size().

(B) What was AVAILABLE in durable state before selection each turn -- read
    off packet.context_field.available (the full dialogue-contribution
    inventory `context_field.py`'s collect_contributions() built from
    state.recent_turns() itself, before select_contributions() filtered
    it) -- this is the true count of what's sitting in state/current.json's
    recent_turns list at that moment, our best evidence for whether the
    1200 B ring ever had to drop an entry.

(C) An independent simulation: replay the real accepted (user, answer) pairs
    for this session, in order, through the pipeline's own
    state.fit_recent_turns() / state._clip_text() with the same
    RECENT_TURN_USER_MAX_CHARS/RECENT_TURN_ANSWER_MAX_CHARS/RECENT_TURNS_MAX_BYTES
    constants SubstrateState.append_recent_turn() uses, to see independently
    whether/when the 1200 B cap would engage over this exact session.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.state import (  # noqa: E402
    RECENT_TURNS_MAX_BYTES,
    RECENT_TURN_USER_MAX_CHARS,
    RECENT_TURN_ANSWER_MAX_CHARS,
    _clip_text,
    fit_recent_turns,
    recent_turns_byte_size,
)

TURNS_DIR = Path("/Users/vaquez/conditioned-kernel/logs/dashboard/turns")
CANDIDATES = Path("/Users/vaquez/conditioned-kernel/logs/candidates.jsonl")
HISTORY = Path("/Users/vaquez/conditioned-kernel/logs/history.jsonl")


def load_turns():
    files = sorted(TURNS_DIR.glob("turn_*.json"))
    out = []
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            d = json.load(f)
        if d["started_at"] >= "2026-07-28T20:00:00Z":
            out.append((fp.name, d))
    return out


def main():
    evening = load_turns()
    print(f"{len(evening)} evening (accepted) turns\n")

    print("=" * 118)
    print("(A) packet.recent_turns as actually shipped in the model input, each evening turn")
    print("=" * 118)
    hdr = (
        f"{'#':>2} {'started_at':20} {'user_input':30} {'n_in_packet':>11} "
        f"{'pkt.recent_turns bytes':>23} {'recent_dialogue bucket bytes':>29} {'bucket pct':>10}"
    )
    print(hdr)
    print("-" * len(hdr))
    for i, (fname, d) in enumerate(evening, 1):
        rt = (d.get("packet") or {}).get("recent_turns") or []
        b = recent_turns_byte_size(rt)
        csb = {r["source_id"]: r for r in d["context_share_bytes"]}
        bucket = csb.get("recent_dialogue", {})
        print(
            f"{i:>2} {d['started_at']:20} {d['user_input']!r:30.30} {len(rt):>11} "
            f"{b:>23} {bucket.get('bytes', 0):>29} {bucket.get('share_pct', 0):>9.2f}%"
        )

    print()
    print("=" * 118)
    print("(B) context_field.available -- true count of dialogue contributions sitting in state")
    print("    before per-turn selection filtering (== len(state.recent_turns()) at compile time)")
    print("=" * 118)
    hdr2 = (
        f"{'#':>2} {'started_at':20} {'user_input':30} {'available_count':>16} "
        f"{'avail. dialogue items':>22} {'selected_count':>15} {'selected dialogue items':>24}"
    )
    print(hdr2)
    print("-" * len(hdr2))
    for i, (fname, d) in enumerate(evening, 1):
        cf = (d.get("packet") or {}).get("context_field") or {}
        avail = cf.get("available") or []
        avail_dialogue = [a for a in avail if a.get("kind") == "recent_dialogue"]
        sel = cf.get("selected") or []
        sel_dialogue = [s for s in sel if s.get("kind") == "recent_dialogue"]
        print(
            f"{i:>2} {d['started_at']:20} {d['user_input']!r:30.30} {cf.get('available_count', 0):>16} "
            f"{len(avail_dialogue):>22} {cf.get('selected_count', 0):>15} {len(sel_dialogue):>24}"
        )

    print()
    print("=" * 118)
    print("(B2) selection reasons for every recent_dialogue contribution, each evening turn")
    print("=" * 118)
    for i, (fname, d) in enumerate(evening, 1):
        cf = (d.get("packet") or {}).get("context_field") or {}
        recs = cf.get("selection_records") or []
        dialogue_recs = [r for r in recs if r.get("kind") == "recent_dialogue"]
        if not dialogue_recs:
            continue
        print(f"#{i} {d['started_at']} {d['user_input']!r}")
        for r in dialogue_recs:
            print(f"     {r['contribution_id']:16} selected={r['selected']!s:5} reason={r['reason']}")

    print()
    print("=" * 118)
    print("(C) independent simulation of state.recent_turns growth via the real pipeline functions")
    print("    (state.fit_recent_turns / state._clip_text / RECENT_TURNS_MAX_BYTES=%d)" % RECENT_TURNS_MAX_BYTES)
    print("=" * 118)

    # Ground truth: (user_input, answer) for every ACCEPTED turn, in the
    # order they were actually persisted, taken from history.jsonl (final
    # pass of each turn) cross-referenced with candidates.jsonl for the
    # accepted candidate's own answer text.
    with CANDIDATES.open() as f:
        cand_by_id = {json.loads(l)["candidate_id"]: json.loads(l) for l in f if l.strip()}
    with HISTORY.open() as f:
        hist = [json.loads(l) for l in f if l.strip()]
    evening_hist = [h for h in hist if h["ts"] >= "2026-07-28T20:00:00Z" and h["decision"] == "accept"]

    # Starting condition: packet.recent_turns at the FIRST evening turn
    # ("hello there", 20:38:13) shows companion-mode selection filtered
    # recent_dialogue down to 0 selected -- but context_field.available for
    # that same turn lists 3 recent_dialogue contributions (dialogue.turn_0/1/2,
    # all rejected as "omitted_dialogue_not_relevant" / "omitted_stale_
    # assistant_boilerplate"), proving state.recent_turns() was NOT empty --
    # it still held the three morning-session exchanges from the 19:00-19:02
    # rejected turns' own recent_turns snapshot (03:13:01 / 03:14:31 / 03:15:35,
    # byte-identical to turn_20260728T190042Z_b47958.json's packet.recent_turns,
    # the last time this session's full recent_turns list is directly visible
    # in a packet). Seed the simulation with that real, logged list rather
    # than an assumed-empty one.
    with (TURNS_DIR / "turn_20260728T190042Z_b47958.json").open() as f:
        seed_packet = json.load(f)["packet"]
    sim_state_turns: list[dict] = list(seed_packet["recent_turns"])
    print(
        f"seed (state.recent_turns as of the last morning packet, 19:00:42Z): "
        f"{len(sim_state_turns)} entries, {recent_turns_byte_size(sim_state_turns)} bytes"
    )
    for t in sim_state_turns:
        print("  seed:", {"user": t["user"], "answer": t["answer"][:50] + "...", "ts": t["ts"]})
    print(f"{'#':>2} {'user_input':30} {'answer(clip)':30} {'sim state bytes':>16} {'sim n':>6} {'cap(1200) hit?':>15}")
    for i, h in enumerate(evening_hist, 1):
        cand = cand_by_id.get(h["candidate_id"], {})
        answer = str(cand.get("answer") or "")
        entry = {
            "user": _clip_text(str(h["user_input"]), RECENT_TURN_USER_MAX_CHARS),
            "answer": _clip_text(answer, RECENT_TURN_ANSWER_MAX_CHARS),
            "ts": h["ts"],
        }
        candidate_list = sim_state_turns + [entry]
        before_bytes = recent_turns_byte_size(candidate_list)
        fitted = fit_recent_turns(candidate_list, max_bytes=RECENT_TURNS_MAX_BYTES)
        cap_hit = len(fitted) < len(candidate_list) or before_bytes > RECENT_TURNS_MAX_BYTES
        sim_state_turns = fitted
        print(
            f"{i:>2} {h['user_input']!r:30.30} {answer[:30]!r:30} "
            f"{recent_turns_byte_size(sim_state_turns):>16} {len(sim_state_turns):>6} "
            f"{('YES dropped ' + str(len(candidate_list) - len(fitted)) + ' oldest') if cap_hit else 'no':>15}"
        )

    print()
    print("Final simulated state.recent_turns after all 16 evening turns:")
    for t in sim_state_turns:
        print("  ", t)
    print(f"  total bytes = {recent_turns_byte_size(sim_state_turns)} (cap = {RECENT_TURNS_MAX_BYTES})")


if __name__ == "__main__":
    main()
