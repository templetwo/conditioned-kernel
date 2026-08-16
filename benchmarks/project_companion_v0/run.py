#!/usr/bin/env python3
"""Project Companion Benchmark v0 — runner.

Two arms, same twelve user lines, same order, same seed fixture:

  bare : raw Ollama /api/chat, short preamble built from the same fixture
         fields (name, intent, local-only, edge). No packet, no validate,
         no repair, no authoritative fallback, no recent_turns file.
  ck   : full companion path via conditioned_kernel.pipeline.run_turn on a
         COPY of the fixture state (live state/ is never touched).

Usage (device):
  python benchmarks/project_companion_v0/run.py --model qwen3.5:0.8b --host jetson
Usage (CI, offline):
  python benchmarks/project_companion_v0/run.py --dry

Writes one receipt JSON per run under receipts/ (FIXTURE.md §8).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

import score as S  # noqa: E402

try:  # httpx is a project dependency; fall back to urllib so bare arm never needs CK
    import httpx  # type: ignore
except Exception:  # noqa: BLE001
    httpx = None
import urllib.request  # noqa: E402

DEFAULT_MODEL = "qwen3.5:0.8b"
PROFILE_ID = "orin_nano_8gb"


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


def load_probes() -> dict[str, Any]:
    return json.loads((HERE / "probes.json").read_text(encoding="utf-8"))


def load_fixture_state() -> dict[str, Any]:
    return json.loads((HERE / "state" / "current.json").read_text(encoding="utf-8"))


def load_profile_knobs() -> dict[str, Any]:
    p = json.loads((ROOT / "configs" / "edge" / f"{PROFILE_ID}.json").read_text(encoding="utf-8"))
    return {
        "num_ctx": int(p.get("num_ctx", 2048)),
        "temperature": float(p.get("temperature", 0.3)),
        "seed": int(p.get("seed", 42)),
        "keep_alive": str(p.get("keep_alive", "2m")),
        "timeout_s": float(p.get("timeout_s", 90)),
        "max_packet_bytes": int(p.get("max_packet_bytes", 6000)),
        "think": bool(p.get("think", False)),
    }


def bare_preamble(fx: dict[str, Any]) -> str:
    op = fx.get("operator") or {}
    facts = "; ".join(op.get("durable_facts") or [])
    flags = fx.get("flags") or {}
    return (
        "You are a small local assistant running fully offline on a "
        f"{flags.get('edge_target', 'jetson_orin_nano_8gb')} device. "
        f"Operator: {op.get('name', 'the operator')} ({facts}). "
        f"Design intent: {fx.get('design_intent', '')} "
        f"Research goal: {fx.get('goal', '')} "
        "No cloud, no sensors, no tools. Answer briefly."
    )


# ---------------------------------------------------------------------------
# ollama helpers (bare arm + telemetry)
# ---------------------------------------------------------------------------


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    if httpx is not None:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=payload)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            return r.json()
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.load(resp)


def _get_json(url: str, timeout: float = 5.0) -> dict[str, Any] | None:
    try:
        if httpx is not None:
            with httpx.Client(timeout=timeout) as c:
                r = c.get(url)
                return r.json() if r.status_code < 400 else None
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return json.load(resp)
    except Exception:  # noqa: BLE001
        return None


def ollama_ps_size_mb(base_url: str) -> float | None:
    d = _get_json(f"{base_url}/api/ps")
    if not d:
        return None
    sizes = [m.get("size_vram") or m.get("size") or 0 for m in d.get("models", [])]
    return round(max(sizes) / 1e6, 1) if sizes else 0.0


def meminfo_memfree_mb() -> float | None:
    try:
        for line in open("/proc/meminfo", encoding="utf-8"):
            if line.startswith("MemFree:"):
                return round(int(line.split()[1]) / 1024, 1)
    except Exception:  # noqa: BLE001
        return None
    return None


def bare_chat(base_url: str, model: str, messages: list[dict[str, str]], knobs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": knobs["keep_alive"],
        "think": knobs["think"],
        "options": {
            "temperature": knobs["temperature"],
            "repeat_penalty": 1.1,
            "seed": knobs["seed"],
            "num_ctx": knobs["num_ctx"],
        },
    }
    t0 = time.time()
    d = _post_json(f"{base_url}/api/chat", payload, knobs["timeout_s"])
    wall = time.time() - t0
    msg = d.get("message") or {}
    text = (msg.get("content") or "").strip()
    ev, ed = d.get("eval_count"), d.get("eval_duration")
    tps = round(ev / (ed / 1e9), 2) if ev and ed else None
    return text, {"latency_s": round(wall, 3), "tokens_per_s": tps, "eval_count": ev, "thinking_len": len(msg.get("thinking") or "")}


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------


def run_bare_arm(probes: dict[str, Any], fx: dict[str, Any], *, model: str, base_url: str, knobs: dict[str, Any], dry: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    res: dict[str, Any] = {"latencies": [], "tps": [], "vram_mb": []}
    preamble = bare_preamble(fx)
    messages: list[dict[str, str]] = [{"role": "system", "content": preamble}]

    def _turn(user: str, dry_text: str | None) -> tuple[str, dict[str, Any]]:
        messages.append({"role": "user", "content": user})
        if dry:
            text, tele = (dry_text or ""), {"latency_s": 0.0, "tokens_per_s": None}
        else:
            text, tele = bare_chat(base_url, model, messages, knobs)
            v = ollama_ps_size_mb(base_url)
            if v is not None:
                res["vram_mb"].append(v)
        messages.append({"role": "assistant", "content": text})
        res["latencies"].append(tele.get("latency_s") or 0.0)
        if tele.get("tokens_per_s"):
            res["tps"].append(tele["tokens_per_s"])
        return text, tele

    for cell in probes["cells"]:
        if cell.get("context") == "reset":
            messages = [{"role": "system", "content": preamble}]
        for prior in cell.get("prior") or []:
            _turn(prior, "Noted." if dry else None)
        text, tele = _turn(cell["user"], cell.get("dry_bare") if dry else None)
        st, snote = S.structural_pass("bare", text, None)
        ctx = {"goal": fx.get("goal", ""), "design_intent": fx.get("design_intent", ""), "arm": "bare"}
        cp, cnote = S.companion_pass(cell["rule"], text, ctx)
        rows.append({
            "id": cell["id"], "arm": "bare", "group": cell["group"],
            "structural": st, "companion": cp, "cell_pass": st and cp,
            "notes": f"{snote}; {cnote}", "answer": text[:400], "telemetry": tele,
        })
    return rows, res


def run_ck_arm(probes: dict[str, Any], fx: dict[str, Any], *, model: str, base_url: str, knobs: dict[str, Any], dry: bool) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    from conditioned_kernel.edge import load_profile, packet_byte_size  # noqa: PLC0415
    from conditioned_kernel.pipeline import run_turn  # noqa: PLC0415
    from conditioned_kernel.state import RECENT_TURNS_MAX_BYTES, SubstrateState, recent_turns_byte_size  # noqa: PLC0415

    rows: list[dict[str, Any]] = []
    res: dict[str, Any] = {"latencies": [], "vram_mb": [], "packet_bytes": [], "recent_bytes": []}
    violations: list[str] = []
    profile = load_profile(PROFILE_ID)

    tmp = Path(tempfile.mkdtemp(prefix="pcb_v0_ck_"))
    state_dir, logs_dir = tmp / "state", tmp / "logs"
    shutil.copytree(HERE / "state", state_dir)
    logs_dir.mkdir()

    def _reset_dialogue() -> None:
        st = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
        st.current["recent_turns"] = []
        st.save_current()

    def _packet_bytes(result: Any) -> int | None:
        pkt = getattr(result, "packet", None) or {}
        pb = (pkt.get("_edge") or {}).get("packet_bytes")
        if pb is None and pkt:
            body = {k: v for k, v in pkt.items() if not str(k).startswith("_")}
            try:
                pb = packet_byte_size(body)
            except Exception:  # noqa: BLE001
                pb = None
        return pb

    def _turn(user: str, dry_cand: dict[str, Any] | None) -> tuple[Any, dict[str, Any]]:
        t0 = time.time()
        result = run_turn(
            user,
            model=model,
            state_dir=state_dir,
            logs_dir=logs_dir,
            base_url=base_url,
            profile=profile,
            profile_id=PROFILE_ID,
            dry_candidate_text=json.dumps(dry_cand) if (dry and dry_cand is not None) else None,
            acceptance_mode="companion",
        )
        wall = time.time() - t0
        res["latencies"].append(round(wall, 3))
        if not dry:
            v = ollama_ps_size_mb(base_url)
            if v is not None:
                res["vram_mb"].append(v)
        pb = _packet_bytes(result)
        if pb is not None:
            res["packet_bytes"].append(pb)
        st = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
        rb = recent_turns_byte_size(st.recent_turns())
        res["recent_bytes"].append(rb)
        return result, {"latency_s": round(wall, 3), "packet_bytes": pb, "recent_bytes": rb}

    for cell in probes["cells"]:
        if cell.get("context") == "reset":
            _reset_dialogue()
        for prior in cell.get("prior") or []:
            _turn(prior, {"answer": "Noted.", "evidence_used": [], "next_state": {}} if dry else None)
        result, tele = _turn(cell["user"], cell.get("dry_ck") if dry else None)
        answer = getattr(result, "answer", "") or ""
        ckinfo = {"decision": getattr(result, "decision", None), "error": getattr(result, "error", None)}
        st, snote = S.structural_pass("ck", answer, ckinfo)
        packet_ok = tele["packet_bytes"] is None or tele["packet_bytes"] <= knobs["max_packet_bytes"]
        recent_ok = tele["recent_bytes"] <= RECENT_TURNS_MAX_BYTES
        if not packet_ok:
            violations.append(f"{cell['id']}: packet_bytes {tele['packet_bytes']} > {knobs['max_packet_bytes']}")
        if not recent_ok:
            violations.append(f"{cell['id']}: recent_turns {tele['recent_bytes']} > {RECENT_TURNS_MAX_BYTES}")
        ctx = {"goal": fx.get("goal", ""), "design_intent": fx.get("design_intent", ""), "arm": "ck", "packet_ok": packet_ok, "recent_ok": recent_ok}
        cp, cnote = S.companion_pass(cell["rule"], answer, ctx)
        rec = getattr(result, "receipt", None) or {}
        rows.append({
            "id": cell["id"], "arm": "ck", "group": cell["group"],
            "structural": st, "companion": cp, "cell_pass": st and cp,
            "notes": f"{snote}; {cnote}", "answer": answer[:400], "telemetry": tele,
            "ck": {"decision": ckinfo["decision"], "pass_index": rec.get("pass_index"),
                    "authoritative_kind": rec.get("authoritative_kind"),
                    "authoritative_fallback": rec.get("authoritative_fallback"),
                    "violations": rec.get("violations")},
        })

    shutil.rmtree(tmp, ignore_errors=True)
    return rows, res, violations


# ---------------------------------------------------------------------------
# receipt
# ---------------------------------------------------------------------------


def _model_meta(base_url: str, model: str, dry: bool) -> dict[str, Any]:
    if dry:
        return {"digest": None, "quant": None}
    d = _get_json(f"{base_url}/api/tags")
    if not d:
        return {"digest": None, "quant": None}
    for m in d.get("models", []):
        if m.get("name") == model or m.get("model") == model:
            det = m.get("details") or {}
            return {"digest": (m.get("digest") or "")[:12] or None, "quant": det.get("quantization_level"), "params": det.get("parameter_size")}
    return {"digest": None, "quant": None}


def build_receipt(*, model: str, host: str, dry: bool, base_url: str, rows: list[dict[str, Any]], bare_res: dict[str, Any], ck_res: dict[str, Any], violations: list[str], wall_s: float, knobs: dict[str, Any]) -> dict[str, Any]:
    scored = S.score_run(rows, violations)
    meta = _model_meta(base_url, model, dry)
    lat = bare_res.get("latencies", []) + ck_res.get("latencies", [])
    vram = bare_res.get("vram_mb", []) + ck_res.get("vram_mb", [])
    tps = bare_res.get("tps", [])
    return {
        "benchmark": S.BENCHMARK,
        "version": "0",
        "model": model,
        "quant": meta.get("quant"),
        "digest": meta.get("digest"),
        "params": meta.get("params"),
        "think": "off",
        "profile": PROFILE_ID,
        "host": host,
        "mode": "dry" if dry else "live",
        "arms": ["bare", "ck"],
        "knobs": knobs,
        "per_cell": [{k: r[k] for k in ("id", "arm", "group", "structural", "companion", "cell_pass", "notes", "answer")} | ({"ck": r["ck"]} if "ck" in r else {}) for r in rows],
        "rates": scored["rates"],
        "delta": scored["delta"],
        "budget": {
            "ck_packet_max": max(ck_res.get("packet_bytes") or [0]),
            "ck_packet_budget": knobs["max_packet_bytes"],
            "ck_recent_max": max(ck_res.get("recent_bytes") or [0]),
            "ck_recent_cap": 1200,
            "violations": violations,
        },
        "resource": {
            "vram_peak_mb": max(vram) if vram else None,
            "memfree_end_mb": meminfo_memfree_mb(),
            "latency_s": {"bare_mean": round(sum(bare_res.get("latencies", [])) / max(1, len(bare_res.get("latencies", []))), 3), "ck_mean": round(sum(ck_res.get("latencies", [])) / max(1, len(ck_res.get("latencies", []))), 3), "max": max(lat) if lat else 0.0},
            "tokens_per_s_bare_mean": round(sum(tps) / len(tps), 2) if tps else None,
            "wall_s": round(wall_s, 1),
            "platform": platform.platform(),
        },
        "verdict": scored["verdict"],
        "shakedown": bool(os.environ.get("PCB_SHAKEDOWN")),
    }


def run(*, model: str, host: str, dry: bool, base_url: str, out_dir: Path | None) -> dict[str, Any]:
    probes = load_probes()
    fx = load_fixture_state()
    knobs = load_profile_knobs()
    t0 = time.time()
    bare_rows, bare_res = run_bare_arm(probes, fx, model=model, base_url=base_url, knobs=knobs, dry=dry)
    ck_rows, ck_res, violations = run_ck_arm(probes, fx, model=model, base_url=base_url, knobs=knobs, dry=dry)
    rows = bare_rows + ck_rows
    receipt = build_receipt(model=model, host=host, dry=dry, base_url=base_url, rows=rows, bare_res=bare_res, ck_res=ck_res, violations=violations, wall_s=time.time() - t0, knobs=knobs)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
        p = out_dir / f"{safe}__{host}__{'dry' if dry else 'live'}__{stamp}.json"
        p.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        receipt["_receipt_path"] = str(p)
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Project Companion Benchmark v0")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--host", default="jetson" if platform.machine() in ("aarch64", "arm64") and sys.platform.startswith("linux") else "desktop-sim")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--dry", action="store_true", help="offline: canned answers, exercises the instrument only")
    ap.add_argument("--out", default=str(HERE / "receipts"))
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    r = run(model=a.model, host=a.host, dry=a.dry, base_url=a.base_url, out_dir=None if a.no_write else Path(a.out))
    summary = {k: r[k] for k in ("benchmark", "model", "host", "mode", "rates", "delta", "budget", "verdict")}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    for row in r["per_cell"]:
        flag = "PASS" if row["cell_pass"] else "FAIL"
        print(f"  {row['arm']:4} {row['id']:3} {flag}  {row['notes'][:70]}")
    if r.get("_receipt_path"):
        print(f"receipt: {r['_receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
