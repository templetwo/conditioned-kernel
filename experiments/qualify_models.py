#!/usr/bin/env python3
"""Model qualification gate for Conditioned Kernel (work order 22666f1).

Disqualifying checks before any experiment spends compute on a model.
Uses OllamaClient.run() — does not reimplement extraction.
Does not modify the frozen measurement layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conditioned_kernel.compile import CANDIDATE_FORMAT  # noqa: E402
from conditioned_kernel.edge import load_profile  # noqa: E402
from conditioned_kernel.generate import OllamaClient, OllamaError, RunStatus  # noqa: E402

DEFAULT_CANDIDATES = [
    "qwen2.5:0.5b",
    "gemma3:1b",
    "gemma3:4b",
    "granite4:350m",
    "functiongemma:270m",
    "qwen3.5:0.8b",
    "qwen3.5:2b",
    "gemma4:e2b",
    "gemma4:e4b",
]

PROBE = "Reply with the single word: ready"


def _now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def show_model(client: OllamaClient, model: str) -> dict[str, Any]:
    try:
        with __import__("httpx").Client(timeout=30.0) as http:
            r = http.post(f"{client.base_url}/api/show", json={"name": model})
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
            return {"ok": True, "body": r.json()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def model_installed(client: OllamaClient, model: str) -> bool:
    names = set(client.list_models())
    if model in names:
        return True
    # tag without digest variants
    return any(n == model or n.startswith(model + ":") or n.startswith(model.split(":")[0]) for n in names) and model in names


def parse_size_bytes(show: dict[str, Any]) -> int | None:
    body = show.get("body") or {}
    # details.parameter_size is human; model_info often has size
    for key in ("size", "modelsize"):
        if key in body and isinstance(body[key], (int, float)):
            return int(body[key])
    # filesize from modelfile details
    details = body.get("details") or {}
    # approximate from parameter_size string like "0.5B" not reliable for VRAM
    return None


def has_thinking_capability(show: dict[str, Any]) -> bool:
    body = show.get("body") or {}
    caps = body.get("capabilities") or []
    if isinstance(caps, list) and any(str(c).lower() == "thinking" for c in caps):
        return True
    # some builds put it in details
    details = body.get("details") or {}
    fam = str(details.get("family") or "") + str(details.get("families") or "")
    return "thinking" in fam.lower()


def chat_payload(
    model: str,
    *,
    content: str = PROBE,
    use_format: bool = False,
    think: bool | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "seed": 42, "num_ctx": 2048},
    }
    if use_format:
        payload["format"] = CANDIDATE_FORMAT
        payload["messages"] = [
            {
                "role": "system",
                "content": "Return only JSON with keys answer, evidence_used, next_state.",
            },
            {
                "role": "user",
                "content": (
                    'Return JSON: {"answer":"ready","evidence_used":["probe"],'
                    '"next_state":{"thread_touch":[]}}'
                ),
            },
        ]
    if think is not None:
        payload["think"] = think
    return {"mode": "chat_json", "model": model, "payload": payload}


def generate_raw_payload(model: str) -> dict[str, Any]:
    return {
        "mode": "generate_raw",
        "model": model,
        "payload": {
            "model": model,
            "prompt": PROBE + "\n",
            "raw": True,
            "stream": False,
            "options": {"temperature": 0.2, "seed": 42, "num_ctx": 512},
        },
    }


def answer_hash(text: str | None) -> str:
    if text is None:
        return "null"
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def qualify_one(
    client: OllamaClient,
    model: str,
    *,
    timeout_s: float,
    ram_budget_gb: float = 8.0,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "model": model,
        "checks": {},
        "evidence": {},
        "verdict": None,
        "disqualify_reasons": [],
    }

    # presence
    try:
        installed = model in set(client.list_models())
    except OllamaError as e:
        row["verdict"] = f"DISQUALIFIED: ollama unreachable ({e})"
        row["disqualify_reasons"].append("ollama_unreachable")
        return row

    if not installed:
        row["checks"]["installed"] = False
        row["verdict"] = "DISQUALIFIED: not installed on this host"
        row["disqualify_reasons"].append("not_installed")
        return row
    row["checks"]["installed"] = True

    show = show_model(client, model)
    row["evidence"]["show_ok"] = show.get("ok")
    caps = []
    if show.get("ok"):
        body = show["body"]
        caps = body.get("capabilities") or []
        row["evidence"]["capabilities"] = caps
        details = body.get("details") or {}
        row["evidence"]["details"] = {
            k: details.get(k) for k in ("parameter_size", "quantization_level", "family") if k in details
        }
        # size in bytes if present on model list via tags
    thinking_cap = has_thinking_capability(show) if show.get("ok") else False
    row["checks"]["1_capability_probe"] = bool(show.get("ok"))
    if not show.get("ok"):
        row["disqualify_reasons"].append(f"show_failed:{show.get('error')}")

    # size from tags API
    try:
        with __import__("httpx").Client(timeout=15.0) as http:
            tags = http.get(f"{client.base_url}/api/tags").json()
        size_b = None
        for m in tags.get("models") or []:
            if m.get("name") == model:
                size_b = m.get("size")
                break
        row["evidence"]["size_bytes"] = size_b
        if size_b is not None:
            size_gb = float(size_b) / (1024**3)
            row["evidence"]["size_gb"] = round(size_gb, 3)
            # leave headroom for OS + substrate (~1.5GB)
            fits = size_gb <= (ram_budget_gb - 1.5)
            row["checks"]["7_fits_memory"] = fits
            if not fits:
                row["disqualify_reasons"].append(
                    f"too_large:{size_gb:.2f}GB_on_{ram_budget_gb}GB_class"
                )
        else:
            row["checks"]["7_fits_memory"] = None
    except Exception as e:  # noqa: BLE001
        row["checks"]["7_fits_memory"] = None
        row["evidence"]["size_error"] = str(e)

    # 2+3 final response + thinking separation (default)
    r_default = client.run(chat_payload(model))
    row["evidence"]["default_run"] = r_default.to_dict()
    final_ok = r_default.status is RunStatus.COMPLETED and bool((r_default.output or "").strip())
    row["checks"]["2_final_response_observed"] = final_ok
    row["checks"]["3_reasoning_channel_separate"] = True  # always recorded on InferenceResult
    if r_default.status is RunStatus.NO_FINAL_RESPONSE:
        row["disqualify_reasons"].append(
            f"no_final_response:thinking_chars={r_default.thinking_chars}"
        )
    elif r_default.status is RunStatus.TIMEOUT:
        row["disqualify_reasons"].append("timeout_default")
    elif r_default.status is not RunStatus.COMPLETED:
        row["disqualify_reasons"].append(f"default_status:{r_default.status.value}")
    elif not final_ok:
        row["disqualify_reasons"].append("empty_final_response")

    # 4 think:false if thinking capable or if default produced thinking
    if thinking_cap or r_default.thinking_chars > 0:
        r_tf = client.run(chat_payload(model, think=False))
        row["evidence"]["think_false_run"] = r_tf.to_dict()
        tf_ok = r_tf.status is RunStatus.COMPLETED and bool((r_tf.output or "").strip())
        row["checks"]["4_think_false_honoured"] = tf_ok
        if not tf_ok:
            row["disqualify_reasons"].append(
                f"think_false_failed:status={r_tf.status.value}:thinking={r_tf.thinking_chars}"
            )
    else:
        row["checks"]["4_think_false_honoured"] = None  # N/A
        row["evidence"]["think_false_run"] = {"na": "no thinking capability observed"}

    # also record think:true explicitly for thinking models (kernel-compat question)
    if thinking_cap or r_default.thinking_chars > 0:
        r_tt = client.run(chat_payload(model, think=True))
        row["evidence"]["think_true_run"] = r_tt.to_dict()

    # 5 latency under budget (use default run elapsed)
    lat_ok = r_default.elapsed_seconds < timeout_s and r_default.status is not RunStatus.TIMEOUT
    # if final response ok, also require under budget
    if r_default.status is RunStatus.COMPLETED:
        lat_ok = r_default.elapsed_seconds < timeout_s
    row["checks"]["5_latency_under_budget"] = lat_ok
    row["evidence"]["latency_s"] = round(r_default.elapsed_seconds, 3)
    row["evidence"]["timeout_budget_s"] = timeout_s
    if not lat_ok:
        row["disqualify_reasons"].append(
            f"latency:{r_default.elapsed_seconds:.1f}s>={timeout_s}s"
        )

    # 6 schema compliance
    r_schema = client.run(chat_payload(model, use_format=True, think=False if thinking_cap else None))
    row["evidence"]["schema_run"] = r_schema.to_dict()
    schema_ok = False
    if r_schema.status is RunStatus.COMPLETED and r_schema.output:
        try:
            data = json.loads(r_schema.output)
            schema_ok = (
                isinstance(data, dict)
                and "answer" in data
                and "evidence_used" in data
                and "next_state" in data
            )
        except json.JSONDecodeError:
            # try extract blob
            text = r_schema.output
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start : end + 1])
                    schema_ok = (
                        isinstance(data, dict)
                        and "answer" in data
                        and "evidence_used" in data
                        and "next_state" in data
                    )
                except json.JSONDecodeError:
                    schema_ok = False
    row["checks"]["6_schema_compliance"] = schema_ok
    if not schema_ok:
        row["disqualify_reasons"].append("schema_fail")

    # 8 raw path note (not necessarily disqualifying — record only, disqualify if work order wants note)
    r_raw = client.run(generate_raw_payload(model))
    row["evidence"]["raw_path"] = r_raw.to_dict()
    raw_ok = r_raw.status is RunStatus.COMPLETED
    row["checks"]["8_raw_path_works"] = raw_ok
    # not added to disqualify_reasons by default — work order says "record whether"

    # 9 determinism class cold/warm (evict via keep_alive 0 then load)
    def one_ask(label: str) -> dict[str, Any]:
        res = client.run(chat_payload(model, content="Name the color of a clear sky in one word."))
        return {
            "label": label,
            "status": res.status.value,
            "hash": answer_hash(res.output),
            "output": (res.output or "")[:80],
            "elapsed_s": round(res.elapsed_seconds, 3),
        }

    # soft unload
    try:
        with __import__("httpx").Client(timeout=60.0) as http:
            http.post(
                f"{client.base_url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0, "stream": False},
            )
        time.sleep(1.0)
    except Exception as e:  # noqa: BLE001
        row["evidence"]["unload_error"] = str(e)

    cold1 = one_ask("cold_a")
    warm1 = one_ask("warm_a")
    warm2 = one_ask("warm_b")
    try:
        with __import__("httpx").Client(timeout=60.0) as http:
            http.post(
                f"{client.base_url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0, "stream": False},
            )
        time.sleep(1.0)
    except Exception:
        pass
    cold2 = one_ask("cold_b")
    det = {
        "cold_a": cold1,
        "warm_a": warm1,
        "warm_b": warm2,
        "cold_b": cold2,
        "cold_stable": cold1["hash"] == cold2["hash"],
        "warm_stable": warm1["hash"] == warm2["hash"],
        "cold_eq_warm": cold1["hash"] == warm1["hash"],
    }
    if det["cold_eq_warm"] and det["cold_stable"] and det["warm_stable"]:
        det_class = "stable"
    elif det["cold_stable"] and det["warm_stable"] and not det["cold_eq_warm"]:
        det_class = "bimodal_cold_warm"
    else:
        det_class = "unstable"
    row["evidence"]["determinism"] = det
    row["checks"]["9_determinism_class"] = det_class
    # determinism class is recorded; bimodal is not automatic disqualify (known Q4 issue)

    # Verdict: any explicit disqualify reason → DISQUALIFIED
    # Required pass: 1 show, 2 final, 5 latency, 6 schema, 7 fits if known
    required_fail = []
    if not row["checks"].get("1_capability_probe"):
        required_fail.append("capability_probe")
    if not row["checks"].get("2_final_response_observed"):
        required_fail.append("final_response")
    if row["checks"].get("4_think_false_honoured") is False:
        required_fail.append("think_false")
    if not row["checks"].get("5_latency_under_budget"):
        required_fail.append("latency")
    if not row["checks"].get("6_schema_compliance"):
        required_fail.append("schema")
    if row["checks"].get("7_fits_memory") is False:
        required_fail.append("memory")

    # merge
    for r in required_fail:
        if r not in row["disqualify_reasons"] and not any(r in x for x in row["disqualify_reasons"]):
            row["disqualify_reasons"].append(r)

    if row["disqualify_reasons"]:
        row["verdict"] = "DISQUALIFIED: " + "; ".join(row["disqualify_reasons"][:6])
    else:
        row["verdict"] = "QUALIFIED"
    return row


def render_markdown(rows: list[dict[str, Any]], *, host: str, profile: str) -> str:
    lines = [
        "# Model qualification",
        "",
        f"**Host:** {host}  ",
        f"**Profile budget:** {profile}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}  ",
        "",
        "Gate from `docs/WORK_ORDER_model_qualification.md`. Any failed required check is disqualifying.",
        "Do **not** treat these verdicts as continuity quality — only as kernel-compatibility.",
        "",
        "## Summary",
        "",
        "| model | verdict | final | schema | latency_s | size_GB | thinking | raw_path | determinism |",
        "|---|---|:---:|:---:|---:|---:|:---:|:---:|---|",
    ]
    for r in rows:
        ev = r.get("evidence") or {}
        ch = r.get("checks") or {}
        dr = ev.get("default_run") or {}
        lines.append(
            "| {model} | {verdict} | {final} | {schema} | {lat} | {size} | {think} | {raw} | {det} |".format(
                model=r.get("model"),
                verdict=r.get("verdict"),
                final="Y" if ch.get("2_final_response_observed") else "N",
                schema="Y" if ch.get("6_schema_compliance") else "N",
                lat=ev.get("latency_s", ""),
                size=ev.get("size_gb", ""),
                think="Y" if (dr.get("thinking_chars") or 0) > 0 else "N",
                raw="Y" if ch.get("8_raw_path_works") else "N",
                det=ch.get("9_determinism_class") or "",
            )
        )

    lines += [
        "",
        "## Stop using",
        "",
    ]
    stops = [r for r in rows if r.get("verdict", "").startswith("DISQUALIFIED")]
    if not stops:
        lines.append("_None on this host run._")
    else:
        for r in stops:
            lines.append(f"- **{r['model']}** — {r['verdict']}")

    lines += [
        "",
        "## Recommended default",
        "",
    ]
    qualified = [r for r in rows if r.get("verdict") == "QUALIFIED"]
    # Prefer gemma3:1b if qualified (ladder functional threshold), else smallest qualified
    rec = None
    for pref in ("gemma3:1b", "qwen2.5:0.5b", "granite4:350m"):
        for r in qualified:
            if r["model"] == pref:
                rec = r
                break
        if rec:
            break
    if not rec and qualified:
        rec = qualified[0]
    if rec:
        lines.append(
            f"**{rec['model']}** — only models with observed final responses, schema compliance, "
            f"and edge latency budget. gemma3:1b preferred when qualified (first ladder functional band). "
            f"qwen2.5:0.5b may qualify as a kernel but is below the functional continuity threshold."
        )
    else:
        lines.append("_No QUALIFIED models on this host run._")

    lines += [
        "",
        "## Notes",
        "",
        "- Check 3 always records thinking_chars separately via `OllamaClient.run()`.",
        "- Check 8 (raw path) is recorded; HTTP 500 on `/api/generate` is a note, not always disqualifying for chat-only harnesses.",
        "- Determinism class `bimodal_cold_warm` matches DETERMINISM.md; not automatic disqualification.",
        "- Models not installed are DISQUALIFIED for this host (re-run on Jetson for full candidate list).",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Conditioned Kernel model qualification gate")
    p.add_argument("--models", nargs="*", default=None, help="Override candidate list")
    p.add_argument("--profile", default="orin_nano_8gb")
    p.add_argument("--base-url", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=float, default=None, help="Override profile timeout_s")
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args()

    prof = load_profile(args.profile)
    timeout = float(args.timeout if args.timeout is not None else prof.timeout_s)
    models = args.models or DEFAULT_CANDIDATES
    client = OllamaClient(base_url=args.base_url, timeout=timeout)

    out_dir = args.out_dir or (ROOT / "experiments" / "runs" / f"qualification_{_now_slug()}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"qualify: profile={args.profile} timeout={timeout}s models={len(models)}")
    rows = []
    for m in models:
        print(f"  … {m}")
        row = qualify_one(client, m, timeout_s=timeout, ram_budget_gb=float(prof.ram_gb))
        rows.append(row)
        print(f"    {row['verdict']}")
        (out_dir / f"{m.replace(':','_').replace('/','_')}.json").write_text(
            json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "profile": args.profile,
        "timeout_s": timeout,
        "base_url": args.base_url,
        "rows": rows,
    }
    (out_dir / "qualification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    import platform

    host = platform.node() + " " + platform.machine()
    md = render_markdown(rows, host=host, profile=args.profile)
    md_path = ROOT / "experiments" / "MODEL_QUALIFICATION.md"
    md_path.write_text(md, encoding="utf-8")
    (out_dir / "MODEL_QUALIFICATION.md").write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
