#!/usr/bin/env python3
"""Lens 2 item 5: prove the context_share numbers are honest.

For one turn (evening turn 2, "im good...", 20:40:00Z -- has nonzero bytes
in every one of the 7 buckets, the richest case to check):

(1) Recompute `context_share_bytes` from scratch by calling the real,
    imported `conditioned_kernel.observatory.compute.context_share_bytes`
    against this turn's own logged `packet` and its final pass's own
    logged `model_input` -- and diff the result against the
    `context_share_bytes` array actually stored in the TurnTrace file.
    If they match exactly, the stored numbers were not hand-edited /
    fabricated; they are what this real function produces from this
    real packet+model_input, byte for byte.

(2) Independently measure the actual wire payload
    (`json.dumps(model_input['payload'])`) the Ollama client would have
    serialized, and compare it against the context_share sum, to show
    precisely what the census counts and what it does not (message-role
    JSON scaffolding, the outer {model, format, options, stream} envelope).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.observatory import compute  # noqa: E402

TURNS_DIR = Path("/Users/vaquez/conditioned-kernel/logs/dashboard/turns")
TARGET = TURNS_DIR / "turn_20260728T204000Z_1e9dfc.json"


def main():
    with TARGET.open("r", encoding="utf-8") as f:
        d = json.load(f)

    print(f"turn: {TARGET.name}  user_input={d['user_input']!r}  decision={d['final_decision']['decision']}")
    packet = d["packet"]
    model_input = d["passes"][-1]["model_input"]
    stored_rows = d["context_share_bytes"]

    print()
    print("=" * 100)
    print("(1) recompute compute.context_share_bytes(packet, model_input) from the logged objects")
    print("=" * 100)
    recomputed_rows = compute.context_share_bytes(packet, model_input)

    stored_by_id = {r["source_id"]: r for r in stored_rows}
    recomp_by_id = {r["source_id"]: r for r in recomputed_rows}
    all_ids = sorted(set(stored_by_id) | set(recomp_by_id))
    print(f"{'source_id':22} {'stored bytes':>13} {'recomputed bytes':>17} {'match':>7}   "
          f"{'stored pct':>11} {'recomputed pct':>15} {'match':>7}")
    all_match = True
    for sid in all_ids:
        s = stored_by_id.get(sid, {"bytes": None, "share_pct": None})
        r = recomp_by_id.get(sid, {"bytes": None, "share_pct": None})
        bmatch = s["bytes"] == r["bytes"]
        pmatch = s["share_pct"] == r["share_pct"]
        all_match = all_match and bmatch and pmatch
        print(
            f"{sid:22} {s['bytes']!s:>13} {r['bytes']!s:>17} {'OK' if bmatch else 'DIFF':>7}   "
            f"{s['share_pct']!s:>11} {r['share_pct']!s:>15} {'OK' if pmatch else 'DIFF':>7}"
        )
    print()
    print(f"FULL ROW-FOR-ROW MATCH: {all_match}")
    print(
        "(the TurnTrace's stored context_share_bytes is reproduced exactly by calling the "
        "real compute.context_share_bytes on this turn's own logged packet+model_input -- "
        "it is not a hand-typed or separately-fabricated number)"
    )

    print()
    print("=" * 100)
    print("(1b) independent verify_packet_bytes check (logged _edge.packet_bytes vs recomputed)")
    print("=" * 100)
    logged, recomputed, match = compute.verify_packet_bytes(packet)
    print(f"logged _edge.packet_bytes={logged}  recomputed edge.packet_byte_size(packet)={recomputed}  match={match}")

    print()
    print("=" * 100)
    print("(2) what the context_share sum counts vs the literal Ollama wire payload")
    print("=" * 100)
    total_context_share = sum(r["bytes"] for r in stored_rows)
    print(f"sum of all context_share_bytes rows (\"total_model_input_bytes\"): {total_context_share}")

    payload = model_input.get("payload") or {}
    payload_json_bytes = compute.bytes_len(json.dumps(payload, ensure_ascii=False))
    payload_compact_bytes = compute.bytes_len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    full_body_json_bytes = compute.bytes_len(json.dumps(model_input, ensure_ascii=False, separators=(",", ":")))

    # sum of just the message "content" strings (system + user), the actual
    # token-bearing substance of a chat_json call, no JSON scaffolding at all
    msg_content_bytes = sum(
        compute.bytes_len(str(m.get("content") or "")) for m in payload.get("messages") or []
    )

    print(f"raw bytes of json.dumps(payload) [pretty, default separators]: {payload_json_bytes}")
    print(f"raw bytes of json.dumps(payload) [compact separators]:         {payload_compact_bytes}")
    print(f"raw bytes of json.dumps(model_input) [the whole traced object, compact]: {full_body_json_bytes}")
    print(f"sum of message['content'] string bytes only (system + user, no JSON at all): {msg_content_bytes}")
    print()
    print("mode:", model_input.get("mode"))
    print("payload keys:", sorted(payload.keys()))
    print(
        "context_share sum vs raw message-content-only sum: "
        f"{total_context_share} vs {msg_content_bytes} "
        f"(diff={total_context_share - msg_content_bytes}; the census also folds in the schema's "
        "own serialized bytes -- format= is a separate payload key, not message content -- see "
        "'output_schema' row above)"
    )
    schema_row = recomp_by_id.get("output_schema", {})
    print(
        f"message-content-only sum + output_schema row bytes = "
        f"{msg_content_bytes} + {schema_row.get('bytes')} = {msg_content_bytes + schema_row.get('bytes', 0)} "
        f"vs context_share total {total_context_share}"
    )


if __name__ == "__main__":
    main()
