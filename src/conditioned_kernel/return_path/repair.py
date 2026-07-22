"""Build repair annotations for a second compile pass."""

from __future__ import annotations

from typing import Any


def build_repair_annotations(
    receipt: dict[str, Any],
    candidate: dict[str, Any] | None = None,
) -> list[str]:
    notes = list(receipt.get("violations") or [])
    if candidate and candidate.get("parse_error"):
        notes.append(f"prior_parse_error:{candidate['parse_error']}")
    if candidate and candidate.get("answer"):
        notes.append("prior_answer_present_but_invalid_contract")
    # Deduplicate preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out
