#!/usr/bin/env python3
"""M1 experiment matrix: bare vs budget-matched bare vs CK under edge profile.

Default profile: orin_nano_8gb.
Scores structural + semantic proxies; reports substrate gain.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conditioned_kernel.edge import DEFAULT_PROFILE_ID, load_profile  # noqa: E402
from conditioned_kernel.generate import OllamaClient, OllamaError  # noqa: E402
from conditioned_kernel.pipeline import run_turn  # noqa: E402
from conditioned_kernel.score import (  # noqa: E402
    aggregate_condition,
    score_ck_result,
    score_free_text,
    substrate_gain,
)
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
        "STATE DUMP (unordered):",
        state.current.get("goal", ""),
        *(state.fact_list()),
        *[f"{t.get('id')}: {t.get('title', '')}" for t in state.open_threads()],
        "QUESTION:",
        user_input,
    ]
    return "\n".join(p for p in parts if p)


def load_probes(path: Path | None) -> list[dict]:
    if path and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data)
    return [
        {
            "id": "probe_intent",
            "category": "state_faithfulness",
            "prompt": "State the current design intent in two sentences. Cite the goal.",
        }
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="Conditioned Kernel M1 matrix (edge-default)")
    p.add_argument("--model", default=None, help="Override profile model")
    p.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    p.add_argument(
        "--probes",
        type=Path,
        default=ROOT / "experiments" / "probes" / "v0_probes.json",
    )
    p.add_argument(
        "--conditions",
        default="bare,budget_matched_bare,ck_strict",
        help="Comma-separated conditions",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default experiments/runs/matrix_<ts>.json)",
    )
    p.add_argument("--limit", type=int, default=0, help="Limit probe count (0=all)")
    args = p.parse_args()

    prof = load_profile(args.profile)
    model = args.model or prof.model
    probes = load_probes(args.probes)
    if args.limit and args.limit > 0:
        probes = probes[: args.limit]

    client = OllamaClient(timeout=prof.timeout_s)
    try:
        client.heartbeat()
    except OllamaError as e:
        print(f"Ollama required for matrix: {e}", file=sys.stderr)
        return 2

    state = SubstrateState.load()
    goal = str(state.current.get("goal") or "")
    facts = state.fact_list()
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]

    rows: list[dict] = []
    by_cond: dict[str, list] = {c: [] for c in conditions}

    print(
        f"matrix profile={prof.profile_id} model={model} ctx={prof.num_ctx} "
        f"probes={len(probes)} conditions={conditions}"
    )

    for probe in probes:
        prompt = probe.get("prompt") or ""
        pid = probe.get("id") or "probe"
        for cond in conditions:
            row: dict = {
                "probe_id": pid,
                "category": probe.get("category"),
                "condition": cond,
                "model": model,
                "profile": prof.profile_id,
                "num_ctx": prof.num_ctx,
                "prompt": prompt,
            }
            try:
                if cond == "bare":
                    text = bare_generate(client, model, prompt, num_ctx=prof.num_ctx)
                    row["raw"] = text
                    row["decision"] = "n/a_bare"
                    row["scores"] = score_free_text(
                        text,
                        goal=goal,
                        facts=facts,
                        max_words=prof.max_answer_words,
                    )
                elif cond == "budget_matched_bare":
                    text = bare_generate(
                        client,
                        model,
                        budget_matched_prompt(state, prompt),
                        num_ctx=prof.num_ctx,
                    )
                    row["raw"] = text
                    row["decision"] = "n/a_budget_matched"
                    row["scores"] = score_free_text(
                        text,
                        goal=goal,
                        facts=facts,
                        max_words=prof.max_answer_words,
                    )
                elif cond == "ck_strict":
                    tr = run_turn(prompt, model=model, client=client, profile=prof)
                    row["raw"] = tr.answer
                    row["decision"] = tr.decision
                    row["ok"] = tr.ok
                    row["passes"] = tr.passes
                    row["scores"] = score_ck_result(
                        ok=tr.ok,
                        decision=tr.decision,
                        answer=tr.answer,
                        packet=tr.packet,
                        candidate=tr.candidate,
                        receipt=tr.receipt,
                        passes=tr.passes,
                    )
                else:
                    row["error"] = f"unknown_condition:{cond}"
                    row["scores"] = {}
            except Exception as e:  # noqa: BLE001 — matrix continues
                row["error"] = str(e)
                row["scores"] = {}

            rows.append(row)
            by_cond.setdefault(cond, []).append(row)
            sc = row.get("scores") or {}
            print(
                f"  [{cond}] {pid} decision={row.get('decision')} "
                f"struct={sc.get('structural_score', 0):.2f} "
                f"sem={sc.get('semantic_score', 0):.2f} "
                f"accept={sc.get('accept', False)}"
            )

    aggregates = {c: aggregate_condition(by_cond.get(c, [])) for c in conditions}
    gains = {}
    if "ck_strict" in aggregates and "bare" in aggregates:
        gains["vs_bare"] = substrate_gain(aggregates["ck_strict"], aggregates["bare"])
    if "ck_strict" in aggregates and "budget_matched_bare" in aggregates:
        gains["vs_budget_matched_bare"] = substrate_gain(
            aggregates["ck_strict"], aggregates["budget_matched_bare"]
        )

    report = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "profile": prof.profile_id,
        "model": model,
        "num_ctx": prof.num_ctx,
        "probe_count": len(probes),
        "conditions": conditions,
        "aggregates": aggregates,
        "substrate_gain": gains,
        "rows": rows,
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or (ROOT / "experiments" / "runs" / f"matrix_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # also write last_matrix.json pointer
    last = ROOT / "experiments" / "runs" / "last_matrix.json"
    last.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n=== aggregates ===")
    print(json.dumps(aggregates, indent=2))
    print("=== substrate_gain ===")
    print(json.dumps(gains, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
