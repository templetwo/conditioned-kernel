"""Step 0 executable authority — kernel decides where truth is mechanical.

MODEL produces candidates. KERNEL owns deterministic gates.
Disagreement is evidence. It is never accepted system truth.

Gate version: step0-gate-v1
Compile policy: static-v0 (until adaptive compile is earned)
"""

from __future__ import annotations

import re
from typing import Any

COMPILE_POLICY_VERSION = "static-v0"
GATE_VERSION = "step0-gate-v1"


def policy_stamp(
    *,
    compile_policy: str | None = None,
    gate_version: str | None = None,
) -> dict[str, str]:
    return {
        "compile_policy": compile_policy or COMPILE_POLICY_VERSION,
        "gate_version": gate_version or GATE_VERSION,
    }


def extract_coverage_claim(text: str) -> str | None:
    """Return PASS|FAIL|CANNOT_EVALUATE if the prose claims a classification."""
    u = (text or "").upper()
    if re.search(r"RESULT\s*[:=]\s*PASS", u) or re.search(
        r"CLASSIFICATION\s*[:=]\s*PASS", u
    ):
        return "PASS"
    if re.search(r"RESULT\s*[:=]\s*FAIL", u) or re.search(
        r"CLASSIFICATION\s*[:=]\s*FAIL", u
    ):
        return "FAIL"
    if re.search(r"CANNOT[_\s-]*EVALUATE", u):
        return "CANNOT_EVALUATE"
    # bare FAIL preferred over bare PASS when both appear
    if re.search(r"\bFAIL\b", u) and not re.search(r"RESULT\s*[:=]\s*PASS", u):
        if re.search(r"\bPASS\b", u):
            # first explicit stance
            pi, fi = u.find("PASS"), u.find("FAIL")
            if pi >= 0 and (fi < 0 or pi < fi):
                return "PASS"
            return "FAIL"
        return "FAIL"
    if re.search(r"\bPASS\b", u):
        return "PASS"
    return None


def coverage_threshold_gate(
    *,
    coverage: float,
    threshold: float = 0.80,
    exclusions_documented: bool = True,
    cannot_evaluate_count: int = 0,
    instrument_silence: bool = False,
) -> dict[str, Any]:
    """Job 04 lesson — numeric threshold is not negotiable by prose."""
    if instrument_silence:
        result = "CANNOT_EVALUATE"
        reason = "instrument_silence_on_required_metric"
    elif not exclusions_documented or coverage < threshold:
        result = "FAIL"
        if not exclusions_documented:
            reason = "exclusions_documented is false"
        else:
            reason = f"coverage {coverage} < required {threshold}"
    elif cannot_evaluate_count > 1:
        result = "FAIL"
        reason = f"cannot_evaluate_count {cannot_evaluate_count} > 1"
    else:
        result = "PASS"
        reason = f"coverage {coverage} >= {threshold} and exclusions documented"
    return {
        "gate_id": "coverage_threshold",
        "gate_version": GATE_VERSION,
        "result": result,
        "reason": reason,
        "inputs": {
            "coverage": coverage,
            "threshold": threshold,
            "exclusions_documented": exclusions_documented,
            "cannot_evaluate_count": cannot_evaluate_count,
            "instrument_silence": instrument_silence,
        },
    }


def apply_executable_authority(
    receipt: dict[str, Any],
    candidate: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    """Stamp policy versions and enforce executable gates on the receipt.

    If an executable gate says FAIL and the model claims PASS, the receipt
    decision is forced away from accept. The model may still explain later;
    it does not own the verdict.
    """
    out = dict(receipt)
    stamp = policy_stamp(
        compile_policy=(packet.get("compile_policy") or COMPILE_POLICY_VERSION),
        gate_version=(packet.get("gate_version") or GATE_VERSION),
    )
    out["compile_policy"] = stamp["compile_policy"]
    out["gate_version"] = stamp["gate_version"]

    auth = packet.get("executable_authority") or {}
    gates_run: list[dict[str, Any]] = []
    forced_reject = False
    disagreements: list[dict[str, Any]] = []

    # Coverage gate (Job 04 shape)
    cov_spec = auth.get("coverage") if isinstance(auth, dict) else None
    if isinstance(cov_spec, dict) and cov_spec.get("coverage") is not None:
        gate = coverage_threshold_gate(
            coverage=float(cov_spec["coverage"]),
            threshold=float(cov_spec.get("threshold") or 0.80),
            exclusions_documented=bool(cov_spec.get("exclusions_documented", True)),
            cannot_evaluate_count=int(cov_spec.get("cannot_evaluate_count") or 0),
            instrument_silence=bool(cov_spec.get("instrument_silence", False)),
        )
        answer = str(candidate.get("answer") or "")
        claim = extract_coverage_claim(answer)
        gate["model_claim"] = claim
        gate["agreement"] = claim is None or claim == gate["result"]
        if claim == "PASS" and gate["result"] == "FAIL":
            gate["model_disagreed"] = True
            disagreements.append(
                {
                    "gate_id": gate["gate_id"],
                    "model_claim": claim,
                    "gate_result": gate["result"],
                    "reason": gate["reason"],
                }
            )
            forced_reject = True
        else:
            gate["model_disagreed"] = False
        gates_run.append(gate)

    out["executable_gates"] = gates_run
    out["authority_disagreements"] = disagreements
    # Invariant: never accept when model PASS contradicts gate FAIL
    out["accepted_contradiction"] = False
    if forced_reject:
        violations = list(out.get("violations") or [])
        if "executable_authority_override" not in violations:
            violations.append("executable_authority_override")
        out["violations"] = violations
        # Force away from accept — assess will still run; we set decision after assess
        out["_force_reject_for_authority"] = True
        out["authority_note"] = (
            "gate FAIL outranks model PASS; system state remains FAIL"
        )

    return out


def finalize_authority_decision(receipt: dict[str, Any]) -> dict[str, Any]:
    """After assess(), ensure authority force cannot remain accept."""
    out = dict(receipt)
    if out.get("_force_reject_for_authority"):
        if out.get("decision") == "accept":
            out["decision"] = "reject"
            out["authority_overrode_accept"] = True
        out["accepted_contradiction"] = False
        # system_state for executable coverage gates
        for g in out.get("executable_gates") or []:
            if g.get("gate_id") == "coverage_threshold":
                out["system_state"] = g.get("result")
                out["kernel_final"] = g.get("result")
                out["model_final"] = g.get("model_claim")
    return out


def build_operating_point(
    *,
    profile: Any,
    model: str,
    think: bool,
    num_ctx: int,
    host: str | None = None,
    runtime_version: str | None = None,
    model_digest: str | None = None,
    tool_surface: str | None = None,
) -> dict[str, Any]:
    """Full OP tuple for receipts (Step 0 DoD D)."""
    think_profile = "deliberate" if think else "ordinary"
    # allow profile to declare preferred name
    if hasattr(profile, "think_profile") and not think:
        think_profile = getattr(profile, "think_profile", None) or "ordinary"
    if think:
        think_profile = "deliberate"

    return {
        "model": model,
        "base_model": getattr(profile, "base_model", None) or "",
        "quant": getattr(profile, "quant", None) or "",
        "digest_prefix": getattr(profile, "digest_prefix", None) or "",
        "model_digest": model_digest,
        "host": host or getattr(profile, "target_device", None) or "",
        "backend": getattr(profile, "backend", None) or "ollama",
        "runtime_version": runtime_version,
        "num_ctx": num_ctx,
        "think": bool(think),
        "think_profile": think_profile,
        "tool_surface": tool_surface
        or getattr(profile, "tool_surface", None)
        or "local_only",
        "profile_id": getattr(profile, "profile_id", None),
        "compile_policy": getattr(profile, "compile_policy", None)
        or COMPILE_POLICY_VERSION,
        "gate_version": getattr(profile, "gate_version", None) or GATE_VERSION,
    }
