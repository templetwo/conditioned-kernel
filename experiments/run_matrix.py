#!/usr/bin/env python3
"""Minimal condition runner scaffold (M1+).

Conditions: bare | budget_matched_bare | ck_strict
This is a thin scaffold — full scoring lands with M1/M2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running without install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conditioned_kernel.edge import DEFAULT_PROFILE_ID  # noqa: E402
from conditioned_kernel.generate import OllamaClient, OllamaError  # noqa: E402
from conditioned_kernel.pipeline import run_turn  # noqa: E402
from conditioned_kernel.state import SubstrateState  # noqa: E402


def bare_generate(client: OllamaClient, model: str, prompt: str, *, num_ctx: int = 2048) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3, "seed": 42, "num_ctx": num_ctx},
    }
    r = client.generate({"mode": "chat_json", "payload": payload})
    return OllamaClient.extract_text(r, "chat_json")


def budget_matched_prompt(state: SubstrateState, user_input: str) -> str:
    """Unstructured dump of the same state mass (topology control)."""
    parts = [
        state.current.get("goal", ""),
        *(state.fact_list()),
        *[t.get("title", "") for t in state.open_threads()],
        user_input,
    ]
    return "\n".join(p for p in parts if p)


def main() -> int:
    p = argparse.ArgumentParser(description="Conditioned Kernel experiment matrix scaffold")
    p.add_argument("--model", default=None, help="Override profile model")
    p.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    p.add_argument("--probe", default="State the current design intent briefly.")
    p.add_argument(
        "--conditions",
        default="bare,budget_matched_bare,ck_strict",
        help="Comma-separated: bare,budget_matched_bare,ck_strict",
    )
    p.add_argument("--out", type=Path, default=ROOT / "experiments" / "runs" / "last_matrix.json")
    args = p.parse_args()

    from conditioned_kernel.edge import load_profile

    prof = load_profile(args.profile)
    model = args.model or prof.model

    client = OllamaClient(timeout=prof.timeout_s)
    try:
        client.heartbeat()
    except OllamaError as e:
        print(f"Ollama required for matrix: {e}", file=sys.stderr)
        return 2

    state = SubstrateState.load()
    results = []
    for cond in [c.strip() for c in args.conditions.split(",") if c.strip()]:
        row = {
            "condition": cond,
            "model": model,
            "profile": prof.profile_id,
            "num_ctx": prof.num_ctx,
            "probe": args.probe,
        }
        if cond == "bare":
            text = bare_generate(client, model, args.probe, num_ctx=prof.num_ctx)
            row["raw"] = text
            row["decision"] = "n/a_bare"
        elif cond == "budget_matched_bare":
            text = bare_generate(
                client,
                model,
                budget_matched_prompt(state, args.probe),
                num_ctx=prof.num_ctx,
            )
            row["raw"] = text
            row["decision"] = "n/a_budget_matched"
        elif cond == "ck_strict":
            tr = run_turn(args.probe, model=model, client=client, profile=prof)
            row["raw"] = tr.answer
            row["decision"] = tr.decision
            row["violations"] = (tr.receipt or {}).get("violations")
            row["ok"] = tr.ok
            row["packet_bytes"] = (tr.packet.get("_edge") or {}).get("packet_bytes")
        else:
            row["error"] = f"unknown_condition:{cond}"
        results.append(row)
        print(f"[{cond}] decision={row.get('decision')} chars={len(row.get('raw') or '')}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
