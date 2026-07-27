"""RUN 00.9A.1 — fail-closed static anti-copy / anti-leak analysis.

No model invocation. Canonical relation-aware checks, not sentinel-only grep.

permitted_combinations is REQUIRED. Omitting it or passing None/empty never
returns a clean leakage_detected=false result (fail-closed).
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from conditioned_kernel.relational_scorer import RelationTriple, canonical_json_bytes

C3_REQUIRED_REPRESENTATION = "structured_state_v1"
OUTPUT_SCHEMA_KEYS = (
    "continuity_assertions",
    "continuity_assertions_v1",
    "output_ready_triples",
)


class LeakageAnalysisError(ValueError):
    """Fail-closed leakage analysis input/contract error."""

    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def _triple(m: Mapping[str, Any]) -> RelationTriple:
    return RelationTriple(
        str(m["subject_id"]), str(m["relation"]), str(m["object_id"])
    )


def _triple_signatures(t: RelationTriple) -> list[str]:
    """Canonical strings that would expose the gold triple in packet bytes."""
    return [
        json.dumps(t.as_dict(), sort_keys=True, separators=(",", ":")),
        f"{t.subject_id}|{t.relation}|{t.object_id}",
        f"{t.subject_id}/{t.relation}/{t.object_id}",
        f'"{t.subject_id}","{t.relation}","{t.object_id}"',
        f"{t.subject_id}{t.relation}{t.object_id}",
    ]


def packet_bytes_from_visible(visible: Mapping[str, Any] | str | bytes) -> str:
    if isinstance(visible, (bytes, bytearray)):
        return bytes(visible).decode("utf-8", errors="replace")
    if isinstance(visible, str):
        return visible
    return canonical_json_bytes(dict(visible)).decode("utf-8")


def gold_visible_in_text(text: str, gold: Sequence[Mapping[str, Any]]) -> list[str]:
    hits: list[str] = []
    for g in gold:
        t = _triple(g)
        for sig in _triple_signatures(t):
            if sig in text:
                hits.append(f"{t.subject_id}/{t.relation}/{t.object_id}")
                break
    return hits


def _parse_permitted(
    permitted_combinations: Sequence[Any],
) -> list[RelationTriple]:
    combos: list[RelationTriple] = []
    for c in permitted_combinations:
        if isinstance(c, (list, tuple)) and len(c) == 3:
            combos.append(RelationTriple(str(c[0]), str(c[1]), str(c[2])))
        elif isinstance(c, Mapping):
            combos.append(_triple(c))
        elif isinstance(c, RelationTriple):
            combos.append(c)
        else:
            raise LeakageAnalysisError(
                "LEAKAGE_ANALYSIS_INCOMPLETE",
                f"unparseable permitted combination: {c!r}",
            )
    return combos


def require_permitted_combinations(
    permitted_combinations: Sequence[Any] | None,
) -> list[RelationTriple]:
    """Fail-closed validation of the permitted universe for leakage analysis."""
    if permitted_combinations is None:
        raise LeakageAnalysisError("PERMITTED_COMBINATIONS_REQUIRED")
    try:
        items = list(permitted_combinations)
    except TypeError as exc:
        raise LeakageAnalysisError(
            "PERMITTED_COMBINATIONS_REQUIRED",
            "permitted_combinations must be a non-empty sequence",
        ) from exc
    if len(items) == 0:
        raise LeakageAnalysisError("PERMITTED_COMBINATIONS_EMPTY")
    return _parse_permitted(items)


def gold_derivable_from_control(
    *,
    control_visible: Mapping[str, Any] | str | bytes,
    gold: Sequence[Mapping[str, Any]],
    permitted_combinations: Sequence[Any],
) -> bool:
    """True if control exposes gold triples or only-possible complete recipe.

    permitted_combinations is required (no default). None/empty raise.
    """
    combos = require_permitted_combinations(permitted_combinations)
    text = packet_bytes_from_visible(control_visible)
    if gold_visible_in_text(text, gold):
        return True
    # Mechanically complete recipe: permitted universe equals gold only
    gold_set = {_triple(g) for g in gold}
    if set(combos) == gold_set:
        return True
    # operational state fields that dump accepted_relations
    if isinstance(control_visible, Mapping):
        for key in (
            "accepted_relations",
            "expected_relations",
            "gold_relations",
            "output_ready_triples",
            "continuity_assertions",
        ):
            if key in control_visible and control_visible[key]:
                try:
                    blob = packet_bytes_from_visible(control_visible[key])
                except Exception:  # noqa: BLE001
                    blob = str(control_visible[key])
                if gold_visible_in_text(blob, gold):
                    return True
    return False


def treatment_is_output_ready(
    *,
    treatment_visible: Mapping[str, Any] | str | bytes,
    gold: Sequence[Mapping[str, Any]],
    output_schema_key: str = "continuity_assertions",
) -> bool:
    """True when C3 contains exact scorer / output-ready gold triples.

    Hard invariant for M0-v2: output-ready treatment is never eligible.
    """
    gold_set = {_triple(g) for g in gold}
    if not isinstance(treatment_visible, Mapping):
        text = packet_bytes_from_visible(treatment_visible)
        return bool(gold_visible_in_text(text, gold)) and (
            output_schema_key in text or "continuity_assertions" in text
        )

    for key in OUTPUT_SCHEMA_KEYS:
        if key in treatment_visible:
            items = treatment_visible[key]
            if isinstance(items, list) and items:
                try:
                    got = {_triple(x) for x in items if isinstance(x, Mapping)}
                except (KeyError, TypeError):
                    got = set()
                if got == gold_set:
                    return True

    # Any field that is a complete scorer-triple rendering of gold is output-ready
    for key in (
        "accepted_relations",
        "expected_relations",
        "gold_relations",
        "output_ready_triples",
        "continuity_assertions",
    ):
        items = treatment_visible.get(key)
        if isinstance(items, list) and items:
            try:
                got = {_triple(x) for x in items if isinstance(x, Mapping)}
            except (KeyError, TypeError):
                continue
            if got == gold_set:
                return True

    # Canonical equivalence: whole visible object equals gold list
    if isinstance(treatment_visible, list):  # type: ignore[unreachable]
        try:
            got = {_triple(x) for x in treatment_visible if isinstance(x, Mapping)}
            if got == gold_set:
                return True
        except (KeyError, TypeError):
            pass

    return False


def c3_representation_valid(treatment_visible: Mapping[str, Any] | str | bytes) -> bool:
    """C3 must declare structured_state_v1 (or superseding structured non-output form)."""
    if not isinstance(treatment_visible, Mapping):
        return False
    rep = str(treatment_visible.get("representation") or "")
    if rep == C3_REQUIRED_REPRESENTATION:
        return True
    if treatment_visible.get("structured_state_not_output_schema") is True and rep:
        return True
    return False


def condition_identity_visible(visible: Mapping[str, Any] | str | bytes) -> bool:
    text = packet_bytes_from_visible(visible)
    patterns = [
        r'"condition"\s*:\s*"C[0-3]',
        r"C0_bare",
        r"C1_budget_matched",
        r"C2_instruction",
        r"C3_static",
        r"condition_id",
    ]
    return any(re.search(p, text) for p in patterns)


def information_match_check(
    *,
    c3_candidate_count: int,
    c1_candidate_count: int,
    c3_entity_mentions: int | None = None,
    c1_entity_mentions: int | None = None,
) -> list[str]:
    reasons: list[str] = []
    if c3_candidate_count != c1_candidate_count:
        reasons.append("CONTROL_PACKET_SEMANTIC_MISMATCH")
        reasons.append("INFORMATION_MATCHING_FAILED")
    if (
        c3_entity_mentions is not None
        and c1_entity_mentions is not None
        and c3_entity_mentions != c1_entity_mentions
    ):
        reasons.append("INFORMATION_MATCHING_FAILED")
    return reasons


def _incomplete_result(reason: str, extra: Sequence[str] = ()) -> dict[str, Any]:
    reasons = sorted(set([reason, "LEAKAGE_ANALYSIS_INCOMPLETE", *extra]))
    return {
        "per_condition": {},
        "exclusion_reasons": reasons,
        "leakage_detected": True,  # never false when incomplete
        "analysis_complete": False,
        "task_eligible": False,
    }


def analyze_condition_packets(
    *,
    gold: Sequence[Mapping[str, Any]],
    packets: Mapping[str, Mapping[str, Any] | str | bytes],
    permitted_combinations: Sequence[Any],
) -> dict[str, Any]:
    """Return leakage reasons per condition. Fail-closed on missing universe.

    permitted_combinations is required (no default). None/empty never yields a
    clean leakage_detected=false outcome.
    """
    if permitted_combinations is None:  # type: ignore[comparison-overlap]
        return _incomplete_result(
            "PERMITTED_COMBINATIONS_REQUIRED",
            ["CONTROL_DERIVABILITY_UNRESOLVED"],
        )
    try:
        combos = require_permitted_combinations(permitted_combinations)
    except LeakageAnalysisError as exc:
        return _incomplete_result(
            exc.reason_code,
            ["CONTROL_DERIVABILITY_UNRESOLVED"],
        )

    if not gold:
        return _incomplete_result("LEAKAGE_ANALYSIS_INCOMPLETE")

    reasons: list[str] = []
    per: dict[str, list[str]] = {}

    for cond, vis in packets.items():
        cr: list[str] = []
        text = packet_bytes_from_visible(vis)
        if condition_identity_visible(vis):
            cr.append("CONDITION_IDENTITY_MODEL_VISIBLE")
        if cond in ("C0", "C0_bare"):
            if gold_visible_in_text(text, gold):
                cr.append("GOLD_VISIBLE_IN_CONTROL")
        if cond in ("C1", "C1_budget_matched_bare", "C2", "C2_instruction_identical"):
            if gold_visible_in_text(text, gold):
                cr.append("GOLD_VISIBLE_IN_CONTROL")
            if gold_derivable_from_control(
                control_visible=vis,
                gold=gold,
                permitted_combinations=combos,
            ):
                cr.append("GOLD_DERIVABLE_FROM_CONTROL")
        if cond in ("C3", "C3_static_ck"):
            if treatment_is_output_ready(treatment_visible=vis, gold=gold):
                cr.append("GOLD_OUTPUT_READY_IN_TREATMENT")
            elif not c3_representation_valid(vis):
                # Missing structured non-output representation is incomplete/unsafe
                cr.append("GOLD_OUTPUT_READY_IN_TREATMENT")
        per[cond] = cr
        reasons.extend(cr)

    return {
        "per_condition": per,
        "exclusion_reasons": sorted(set(reasons)),
        "leakage_detected": bool(reasons),
        "analysis_complete": True,
        "task_eligible": len(reasons) == 0,
        "permitted_combination_n": len(combos),
    }
