"""Parse raw model text into a candidate object."""

from __future__ import annotations

import json
import re
from typing import Any

from conditioned_kernel.ids import candidate_id, utc_now_iso


def _extract_json_blob(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    # Direct parse first
    if text.startswith("{") and text.endswith("}"):
        return text
    # Fenced block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    # First balanced-ish object
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def parse_candidate(
    raw_text: str,
    *,
    packet_id: str,
    pass_index: int = 0,
) -> dict[str, Any]:
    """Return a candidate object. status is model-proposed, not trusted."""
    cid = candidate_id()
    base: dict[str, Any] = {
        "candidate_id": cid,
        "packet_id": packet_id,
        "pass_index": pass_index,
        "status": "proposed",
        "raw_text": raw_text,
        "parsed_at": utc_now_iso(),
        "parse_ok": False,
        "answer": "",
        "evidence_used": [],
        "next_state": {},
        "self_report": {},
        "parse_error": None,
    }

    blob = _extract_json_blob(raw_text)
    if blob is None:
        base["parse_error"] = "no_json_object_found"
        base["answer"] = raw_text.strip()
        return base

    try:
        data = json.loads(blob)
    except json.JSONDecodeError as e:
        base["parse_error"] = f"json_decode_error:{e.msg}"
        base["answer"] = raw_text.strip()
        return base

    if not isinstance(data, dict):
        base["parse_error"] = "json_root_not_object"
        return base

    base["parse_ok"] = True
    base["answer"] = str(data.get("answer") or "")
    evidence = data.get("evidence_used") or []
    if isinstance(evidence, list):
        base["evidence_used"] = [str(x) for x in evidence]
    else:
        base["evidence_used"] = []
        base["parse_error"] = "evidence_used_not_array"
        base["parse_ok"] = False

    next_state = data.get("next_state") or {}
    if isinstance(next_state, dict):
        base["next_state"] = next_state
    else:
        base["next_state"] = {}
        base["parse_error"] = "next_state_not_object"
        base["parse_ok"] = False

    # Optional untrusted fields
    if "self_report" in data and isinstance(data["self_report"], dict):
        base["self_report"] = data["self_report"]
    # Accept alternate shapes some small models emit
    if not base["answer"] and isinstance(data.get("response"), str):
        base["answer"] = data["response"]

    return base
