"""Acceptance decision from a validation receipt."""

from __future__ import annotations

from typing import Any, Literal

Decision = Literal["accept", "repair", "reject"]


def assess(receipt: dict[str, Any], *, pass_index: int = 0, max_repair: int = 1) -> dict[str, Any]:
    """Mutate/return receipt with final decision."""
    ok = bool(receipt.get("valid_schema")) and bool(receipt.get("state_faithful"))
    violations = list(receipt.get("violations") or [])

    if ok and not violations:
        decision: Decision = "accept"
    elif pass_index < max_repair and receipt.get("repairable", True):
        decision = "repair"
    else:
        decision = "reject"

    out = dict(receipt)
    out["decision"] = decision
    out["pass_index"] = pass_index
    return out
