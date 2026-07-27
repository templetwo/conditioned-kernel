"""RUN 00.9A — static anti-copy / anti-leak analysis over model-visible packets.

No model invocation. Canonical relation-aware checks, not sentinel-only grep.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from conditioned_kernel.relational_scorer import RelationTriple, canonical_json_bytes


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


def gold_derivable_from_control(
    *,
    control_visible: Mapping[str, Any] | str | bytes,
    gold: Sequence[Mapping[str, Any]],
    permitted_combinations: Sequence[Any] | None = None,
) -> bool:
    """True if control exposes gold triples or only-possible complete recipe."""
    text = packet_bytes_from_visible(control_visible)
    if gold_visible_in_text(text, gold):
        return True
    # Mechanically complete recipe: permitted_combinations == gold only
    if permitted_combinations is not None:
        combos = []
        for c in permitted_combinations:
            if isinstance(c, (list, tuple)) and len(c) == 3:
                combos.append(RelationTriple(str(c[0]), str(c[1]), str(c[2])))
            elif isinstance(c, Mapping):
                combos.append(_triple(c))
        gold_set = {_triple(g) for g in gold}
        if combos and set(combos) == gold_set:
            return True
    # operational state fields that dump accepted_relations
    if isinstance(control_visible, Mapping):
        for key in (
            "accepted_relations",
            "expected_relations",
            "gold_relations",
            "output_ready_triples",
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
    """C3 contains exact scorer triples under the output schema key."""
    if not isinstance(treatment_visible, Mapping):
        text = packet_bytes_from_visible(treatment_visible)
        return bool(gold_visible_in_text(text, gold)) and output_schema_key in text
    if output_schema_key in treatment_visible:
        try:
            items = treatment_visible[output_schema_key]
            if isinstance(items, list) and items:
                got = {_triple(x) for x in items if isinstance(x, Mapping)}
                if got == {_triple(g) for g in gold}:
                    return True
        except (KeyError, TypeError):
            pass
    # accepted_relations that are identical to required output form
    ar = treatment_visible.get("accepted_relations")
    if isinstance(ar, list) and ar:
        try:
            got = {_triple(x) for x in ar if isinstance(x, Mapping)}
            if got == {_triple(g) for g in gold}:
                # structured state that is byte-identical to output triples
                return True
        except (KeyError, TypeError):
            pass
    return False


def condition_identity_visible(visible: Mapping[str, Any] | str | bytes) -> bool:
    text = packet_bytes_from_visible(visible)
    # model-visible condition labels (supersession: forbidden outside metadata)
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


def analyze_condition_packets(
    *,
    gold: Sequence[Mapping[str, Any]],
    packets: Mapping[str, Mapping[str, Any] | str | bytes],
    permitted_combinations: Sequence[Any] | None = None,
    c3_allows_structured_state: bool = True,
) -> dict[str, Any]:
    """Return leakage reasons per condition and aggregate exclusion reasons."""
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
                permitted_combinations=permitted_combinations,
            ):
                cr.append("GOLD_DERIVABLE_FROM_CONTROL")
        if cond in ("C3", "C3_static_ck"):
            if treatment_is_output_ready(treatment_visible=vis, gold=gold):
                if not c3_allows_structured_state:
                    cr.append("GOLD_OUTPUT_READY_IN_TREATMENT")
                else:
                    # Prefer structured state representation marker
                    if isinstance(vis, Mapping) and vis.get("continuity_assertions"):
                        cr.append("GOLD_OUTPUT_READY_IN_TREATMENT")
                    elif isinstance(vis, Mapping) and vis.get(
                        "structured_state_not_output_schema"
                    ):
                        pass  # OK: treatment is structured non-output form
                    elif isinstance(vis, Mapping) and "accepted_relations" in vis:
                        # accepted_relations identical to gold is still leaky if
                        # format matches output — flag when only field is triples
                        if treatment_is_output_ready(treatment_visible=vis, gold=gold):
                            if vis.get("representation") != "structured_state_v1":
                                cr.append("GOLD_OUTPUT_READY_IN_TREATMENT")
        per[cond] = cr
        reasons.extend(cr)

    return {
        "per_condition": per,
        "exclusion_reasons": sorted(set(reasons)),
        "leakage_detected": bool(reasons),
    }
