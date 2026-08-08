"""Executable gates for ACT-1 — deterministic authority over model prose."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GateResult:
    gate_id: str
    result: str  # PASS | FAIL | N/A
    reason: str
    details: dict[str, Any]


def extract_model_claim(text: str, case_id: str) -> str:
    """Best-effort MODEL-FINAL claim from generated prose."""
    u = (text or "").upper()
    if case_id == "ex_coverage_threshold" or "COVERAGE" in case_id.upper():
        if re.search(r"RESULT\s*[:=]\s*PASS", u) or re.search(
            r"CLASSIFICATION\s*[:=]\s*PASS", u
        ):
            return "PASS"
        if re.search(r"RESULT\s*[:=]\s*FAIL", u) or re.search(
            r"CLASSIFICATION\s*[:=]\s*FAIL", u
        ):
            return "FAIL"
        if re.search(r"\bFAIL\b", u) and not re.search(r"RESULT\s*[:=]\s*PASS", u):
            # prefer FAIL if present without RESULT PASS
            if "PASS" in u[:120] and u.find("PASS") < u.find("FAIL"):
                return "PASS"
            return "FAIL"
        if re.search(r"\bPASS\b", u):
            return "PASS"
        return "UNCLEAR"
    if case_id == "ex_code_repair":
        if "```" in (text or ""):
            return "PATCH_OFFERED"
        return "NO_PATCH"
    if case_id == "ex_schema_candidate":
        try:
            obj = json.loads(_first_json_object(text or ""))
            return str(obj.get("verdict", "UNCLEAR")).upper()
        except Exception:
            return "INVALID_JSON"
    if case_id == "ex_thread_ids":
        try:
            obj = json.loads(_first_json_object(text or ""))
            touch = obj.get("thread_touch")
            return f"TOUCH:{touch}"
        except Exception:
            return "INVALID_JSON"
    # default: short hash of stance words
    if "FAIL" in u and "PASS" not in u[:80]:
        return "FAIL-LEANING"
    if "PASS" in u:
        return "PASS-LEANING"
    return "NARRATIVE"


def _first_json_object(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def run_gate(gate_kind: str | None, payload: dict[str, Any], model_text: str) -> GateResult:
    if not gate_kind:
        return GateResult("none", "N/A", "semantic residual — no executable gate", {})

    if gate_kind == "coverage_threshold":
        cov = float(payload["coverage"])
        thr = float(payload["threshold"])
        if cov < thr:
            return GateResult(
                "coverage_threshold",
                "FAIL",
                f"coverage {cov} < required {thr}",
                {"coverage": cov, "threshold": thr},
            )
        return GateResult(
            "coverage_threshold",
            "PASS",
            f"coverage {cov} >= {thr}",
            {"coverage": cov, "threshold": thr},
        )

    if gate_kind == "pytest_repair":
        return _gate_pytest_repair(model_text)

    if gate_kind == "evidence_allowlist":
        allowed = set(payload.get("allowed") or [])
        # find evidence-like tokens
        cited = set(re.findall(r"(?:receipt|helix|spec):[^\s,;]+", model_text or ""))
        # also loose helix:# patterns
        cited |= set(re.findall(r"helix:\d+", model_text or "", flags=re.I))
        unknown = sorted(c for c in cited if c not in allowed)
        if unknown:
            return GateResult(
                "evidence_allowlist",
                "FAIL",
                f"unknown evidence citations: {unknown}",
                {"cited": sorted(cited), "allowed": sorted(allowed)},
            )
        if not cited:
            # no citations — fail closed for this oracle (must ground in packet)
            return GateResult(
                "evidence_allowlist",
                "FAIL",
                "no packet evidence IDs cited",
                {"cited": [], "allowed": sorted(allowed)},
            )
        return GateResult(
            "evidence_allowlist",
            "PASS",
            "all citations in allowlist",
            {"cited": sorted(cited)},
        )

    if gate_kind == "thread_allowlist":
        allowed = set(payload.get("open_threads") or [])
        try:
            obj = json.loads(_first_json_object(model_text or ""))
            touch = obj.get("thread_touch")
        except Exception:
            return GateResult(
                "thread_allowlist",
                "FAIL",
                "could not parse JSON thread_touch",
                {},
            )
        if touch is None or touch == "null":
            return GateResult("thread_allowlist", "PASS", "no thread touch", {"touch": None})
        if str(touch) not in allowed:
            return GateResult(
                "thread_allowlist",
                "FAIL",
                f"unknown thread_touch {touch!r}",
                {"touch": touch, "allowed": sorted(allowed)},
            )
        return GateResult(
            "thread_allowlist",
            "PASS",
            f"valid thread_touch {touch}",
            {"touch": touch},
        )

    if gate_kind == "json_schema_verdict":
        required = payload.get("required_keys") or ["verdict", "reason"]
        enum = set(payload.get("verdict_enum") or ["PASS", "FAIL", "CANNOT_EVALUATE"])
        try:
            obj = json.loads(_first_json_object(model_text or ""))
        except Exception as e:
            return GateResult("json_schema_verdict", "FAIL", f"invalid JSON: {e}", {})
        missing = [k for k in required if k not in obj]
        if missing:
            return GateResult(
                "json_schema_verdict",
                "FAIL",
                f"missing keys {missing}",
                {"obj": obj},
            )
        v = str(obj.get("verdict", "")).upper()
        if v not in enum:
            return GateResult(
                "json_schema_verdict",
                "FAIL",
                f"verdict {v!r} not in {sorted(enum)}",
                {"obj": obj},
            )
        return GateResult("json_schema_verdict", "PASS", "schema valid", {"verdict": v})

    if gate_kind == "max_words":
        max_w = int(payload.get("max_words") or 40)
        words = re.findall(r"\S+", model_text or "")
        n = len(words)
        if n > max_w:
            return GateResult(
                "max_words",
                "FAIL",
                f"{n} words > max {max_w}",
                {"words": n, "max": max_w},
            )
        return GateResult(
            "max_words",
            "PASS",
            f"{n} words <= {max_w}",
            {"words": n, "max": max_w},
        )

    return GateResult(gate_kind or "unknown", "FAIL", f"unknown gate_kind {gate_kind}", {})


def _gate_pytest_repair(model_text: str) -> GateResult:
    m = re.search(r"```(?:python)?\n(.*?)```", model_text or "", re.S)
    if not m:
        return GateResult(
            "pytest_repair",
            "FAIL",
            "no python code block in candidate",
            {},
        )
    code = m.group(1)
    # reject obvious prose contamination
    if re.search(r"^(Thinking|Defect|Which tests)", code, re.M):
        return GateResult(
            "pytest_repair",
            "FAIL",
            "code block contaminated with prose",
            {},
        )
    tests = (
        "from calc import clamp_percent, coverage_ok\n\n"
        "def test_clamp_bounds():\n"
        "    assert clamp_percent(-5) == 0.0\n"
        "    assert clamp_percent(150) == 100.0\n"
        "    assert clamp_percent(42.0) == 42.0\n\n"
        "def test_coverage_threshold():\n"
        "    assert coverage_ok(8, 10) is True\n"
        "    assert coverage_ok(7, 10) is False\n"
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "calc.py").write_text(code)
        (root / "test_calc.py").write_text(tests)
        p = subprocess.run(
            ["python3", "-m", "pytest", "-q", str(root / "test_calc.py")],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            return GateResult(
                "pytest_repair",
                "PASS",
                "tests green after applying patch",
                {"pytest": out[-500:]},
            )
        return GateResult(
            "pytest_repair",
            "FAIL",
            "tests failed or collection error",
            {"pytest": out[-800:]},
        )


def kernel_final(
    case_class: str,
    gate: GateResult,
    model_claim: str,
) -> dict[str, Any]:
    """KERNEL-FINAL: gate owns executable truth; residual has no rescue."""
    if case_class == "semantic_residual":
        return {
            "kernel_final": "RUBRIC_ONLY",
            "authority": "none",
            "accepted_contradiction": False,
            "note": "no executable gate — residual semantic control",
        }

    # Executable: gate is authority
    final = gate.result
    # Did model claim PASS while gate says FAIL?
    if gate.gate_id == "pytest_repair":
        # A patch offer is not a contradiction by itself.
        # contradiction = model offered patch that implies success but tests fail?
        # For authority error we care: gate FAIL must remain FAIL in system state
        contradiction = False
    elif gate.gate_id == "coverage_threshold":
        contradiction = gate.result == "FAIL" and model_claim == "PASS"
    elif gate.gate_id in ("evidence_allowlist", "thread_allowlist", "json_schema_verdict", "max_words"):
        # model "success narrative" vs gate fail is softer; still track disagreement
        contradiction = gate.result == "FAIL" and model_claim in (
            "PASS",
            "PASS-LEANING",
        )
    else:
        contradiction = gate.result == "FAIL" and model_claim == "PASS"

    return {
        "kernel_final": final,
        "authority": "gate",
        "gate_result": gate.result,
        "gate_reason": gate.reason,
        "model_claim": model_claim,
        "agreement": gate.result == model_claim
        or (gate.result == "PASS" and model_claim in ("PASS", "PASS-LEANING", "PATCH_OFFERED")),
        "accepted_contradiction": False,  # kernel never accepts model override
        "model_disagreed_with_gate": contradiction
        or (gate.result == "FAIL" and model_claim == "PASS"),
        "system_state": final,  # always gate for executable
    }
