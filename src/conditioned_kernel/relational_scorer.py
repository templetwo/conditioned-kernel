"""Closed-set relational continuity scorer (RUN 00.6E).

Primary credit requires exact subject_id + relation + object_id equality.
Identifier mention alone never earns a true positive. Shotgunning cannot
improve primary_score. Offline only — no model invocation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

SCORER_SCHEMA_VERSION = "ck.relational_score.v1"
SCIENTIFIC_STATUS = "scorer_validation_only"
HEADLINE_INELIGIBLE_REASON = "m0_manifest_and_admission_contract_not_yet_ratified"


class ScoringStatus(str, Enum):
    SCORED = "SCORED"
    TIMEOUT = "TIMEOUT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    NO_FINAL_RESPONSE = "NO_FINAL_RESPONSE"
    MALFORMED_ASSERTIONS = "MALFORMED_ASSERTIONS"
    TASK_CONTRACT_ERROR = "TASK_CONTRACT_ERROR"
    SCORER_INTERNAL_ERROR = "SCORER_INTERNAL_ERROR"


class RelationClass(str, Enum):
    TRUE_POSITIVE = "TRUE_POSITIVE"
    WRONG_RELATION = "WRONG_RELATION"
    REVERSED_DIRECTION = "REVERSED_DIRECTION"
    UNSUPPORTED_ASSERTION = "UNSUPPORTED_ASSERTION"
    DUPLICATE_ASSERTION = "DUPLICATE_ASSERTION"
    OUT_OF_UNIVERSE_ASSERTION = "OUT_OF_UNIVERSE_ASSERTION"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"


class TaskContractError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


# ---------------------------------------------------------------------------
# Canonical triples
# ---------------------------------------------------------------------------


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, order=True)
class RelationTriple:
    subject_id: str
    relation: str
    object_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "subject_id": self.subject_id,
            "relation": self.relation,
            "object_id": self.object_id,
        }

    @staticmethod
    def from_mapping(m: Mapping[str, Any]) -> "RelationTriple":
        return RelationTriple(
            subject_id=str(m["subject_id"]),
            relation=str(m.get("relation") or m.get("predicate_id") or ""),
            object_id=str(m["object_id"]),
        )


def sort_triples(triples: Iterable[RelationTriple]) -> list[RelationTriple]:
    return sorted(
        triples,
        key=lambda t: (t.subject_id, t.relation, t.object_id),
    )


def triples_hash(triples: Iterable[RelationTriple]) -> str:
    payload = [t.as_dict() for t in sort_triples(triples)]
    return sha256_hex(canonical_json_bytes(payload))


# ---------------------------------------------------------------------------
# Task contract / gold
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationalGold:
    task_id: str
    contract_version: str
    subject_universe: frozenset[str]
    object_universe: frozenset[str]
    relation_universe: frozenset[str]
    expected_relations: frozenset[RelationTriple]
    symmetric_relations: frozenset[str] = frozenset()
    # Optional: allow empty expected only if explicitly permitted
    allow_empty_expected: bool = False

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "RelationalGold":
        task_id = str(data.get("task_id") or "")
        if not task_id:
            raise TaskContractError("MISSING_TASK_ID")
        contract_version = str(data.get("contract_version") or "")
        if not contract_version:
            raise TaskContractError("MISSING_CONTRACT_VERSION")

        subjects = frozenset(str(x) for x in (data.get("subject_universe") or []))
        objects = frozenset(str(x) for x in (data.get("object_universe") or []))
        relations = frozenset(str(x) for x in (data.get("relation_universe") or []))
        symmetric = frozenset(str(x) for x in (data.get("symmetric_relations") or []))

        raw_expected = list(data.get("expected_relations") or [])
        expected_list: list[RelationTriple] = []
        seen: set[RelationTriple] = set()
        for item in raw_expected:
            if not isinstance(item, Mapping):
                raise TaskContractError("MALFORMED_EXPECTED_RELATION")
            try:
                t = RelationTriple.from_mapping(item)
            except (KeyError, TypeError) as e:
                raise TaskContractError("MALFORMED_EXPECTED_RELATION") from e
            if not t.subject_id or not t.relation or not t.object_id:
                raise TaskContractError("MALFORMED_EXPECTED_RELATION")
            if t.subject_id not in subjects:
                raise TaskContractError(
                    "UNKNOWN_EXPECTED_SUBJECT", t.subject_id
                )
            if t.object_id not in objects:
                raise TaskContractError(
                    "UNKNOWN_EXPECTED_OBJECT", t.object_id
                )
            if t.relation not in relations:
                raise TaskContractError(
                    "UNKNOWN_EXPECTED_RELATION", t.relation
                )
            if t in seen:
                raise TaskContractError(
                    "DUPLICATE_EXPECTED_RELATION",
                    f"{t.subject_id}/{t.relation}/{t.object_id}",
                )
            seen.add(t)
            expected_list.append(t)

        allow_empty = bool(data.get("allow_empty_expected", False))
        if not expected_list and not allow_empty:
            raise TaskContractError("EMPTY_EXPECTED_RELATIONS")

        for s in symmetric:
            if s not in relations:
                raise TaskContractError("MALFORMED_SYMMETRY_METADATA", s)

        return RelationalGold(
            task_id=task_id,
            contract_version=contract_version,
            subject_universe=subjects,
            object_universe=objects,
            relation_universe=relations,
            expected_relations=frozenset(expected_list),
            symmetric_relations=symmetric,
            allow_empty_expected=allow_empty,
        )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _is_out_of_universe(t: RelationTriple, gold: RelationalGold) -> bool:
    return (
        t.subject_id not in gold.subject_universe
        or t.object_id not in gold.object_universe
        or t.relation not in gold.relation_universe
    )


def classify_proposal(
    proposed: RelationTriple,
    *,
    gold: RelationalGold,
    remaining_expected: set[RelationTriple],
    seen_unique: set[RelationTriple],
) -> RelationClass:
    """Assign exactly one primary relation-level class to a proposed triple.

    Precedence:
    1. DUPLICATE (if already seen as unique proposal)
    2. OUT_OF_UNIVERSE
    3. TRUE_POSITIVE (exact match remaining expected, or symmetric reverse)
    4. WRONG_RELATION (same subject+object, different relation vs some expected)
    5. REVERSED_DIRECTION (same relation, swapped ends vs some expected)
    6. UNSUPPORTED_ASSERTION
    """
    if proposed in seen_unique:
        return RelationClass.DUPLICATE_ASSERTION

    if _is_out_of_universe(proposed, gold):
        return RelationClass.OUT_OF_UNIVERSE_ASSERTION

    # Exact match
    if proposed in remaining_expected:
        return RelationClass.TRUE_POSITIVE

    # Symmetric: reverse counts as TP if relation is marked symmetric
    if proposed.relation in gold.symmetric_relations:
        rev = RelationTriple(
            proposed.object_id, proposed.relation, proposed.subject_id
        )
        if rev in remaining_expected:
            return RelationClass.TRUE_POSITIVE

    # Wrong relation: subject+object match an expected triple, relation differs
    for exp in gold.expected_relations:
        if (
            exp.subject_id == proposed.subject_id
            and exp.object_id == proposed.object_id
            and exp.relation != proposed.relation
        ):
            return RelationClass.WRONG_RELATION

    # Reversed direction: same relation, swapped subject/object (asymmetric)
    for exp in gold.expected_relations:
        if (
            exp.relation == proposed.relation
            and exp.subject_id == proposed.object_id
            and exp.object_id == proposed.subject_id
            and exp.relation not in gold.symmetric_relations
        ):
            return RelationClass.REVERSED_DIRECTION

    return RelationClass.UNSUPPORTED_ASSERTION


# ---------------------------------------------------------------------------
# Metrics / primary score
# ---------------------------------------------------------------------------


def primary_score_formula(
    *,
    true_positive_n: int,
    expected_n: int,
    wrong_relation_n: int,
    reversed_direction_n: int,
    unsupported_assertion_n: int,
    out_of_universe_assertion_n: int,
) -> tuple[float | None, str | None]:
    """Conservative primary score; shotgunning cannot improve it.

    primary_score = TP / (
        expected_n
        + wrong_relation_n
        + reversed_direction_n
        + unsupported_assertion_n
        + out_of_universe_assertion_n
    )

    Zero denominator → (None, reason). Score is always in [0, 1] when defined.
    Duplicates are excluded from the denominator by design (unique non-true
    classes only); FNs are represented via expected_n in the denominator.
    """
    denom = (
        expected_n
        + wrong_relation_n
        + reversed_direction_n
        + unsupported_assertion_n
        + out_of_universe_assertion_n
    )
    if denom <= 0:
        return None, "ZERO_DENOMINATOR"
    score = true_positive_n / denom
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0
    return score, None


def _precision_recall_f1(
    *,
    true_positive_n: int,
    expected_n: int,
    unique_scored_proposals: int,
) -> dict[str, Any]:
    """unique_scored_proposals = unique proposals excluding pure duplicates.

    precision = TP / unique_scored_proposals
    recall = TP / expected_n
    """
    if unique_scored_proposals <= 0:
        precision: float | None = None
        precision_reason: str | None = "ZERO_DENOMINATOR_PRECISION"
    else:
        precision = true_positive_n / unique_scored_proposals
        precision_reason = None

    if expected_n <= 0:
        recall: float | None = None
        recall_reason: str | None = "ZERO_DENOMINATOR_RECALL"
    else:
        recall = true_positive_n / expected_n
        recall_reason = None

    if precision is None or recall is None:
        f1: float | None = None
        f1_reason: str | None = "UNDEFINED_COMPONENT"
    elif precision + recall == 0:
        f1 = 0.0
        f1_reason = None
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
        f1_reason = None

    return {
        "precision": precision,
        "precision_undefined_reason": precision_reason,
        "recall": recall,
        "recall_undefined_reason": recall_reason,
        "f1": f1,
        "f1_undefined_reason": f1_reason,
    }


# ---------------------------------------------------------------------------
# Inference status → scoring status
# ---------------------------------------------------------------------------

_INFERENCE_TO_SCORING: dict[str, ScoringStatus] = {
    "timeout": ScoringStatus.TIMEOUT,
    "transport_error": ScoringStatus.TRANSPORT_ERROR,
    "invalid_response": ScoringStatus.INVALID_RESPONSE,
    "no_final_response": ScoringStatus.NO_FINAL_RESPONSE,
    "TIMEOUT": ScoringStatus.TIMEOUT,
    "TRANSPORT_ERROR": ScoringStatus.TRANSPORT_ERROR,
    "INVALID_RESPONSE": ScoringStatus.INVALID_RESPONSE,
    "NO_FINAL_RESPONSE": ScoringStatus.NO_FINAL_RESPONSE,
}


def score_cell(
    *,
    task_id: str,
    condition_id: str,
    gold: RelationalGold | Mapping[str, Any],
    proposed_assertions: Sequence[Mapping[str, Any]] | None,
    inference_status: str,
    model_provenance: Mapping[str, Any] | None = None,
    repo_commit: str | None = None,
    malformed: bool = False,
) -> dict[str, Any]:
    """Score one planned task-condition cell. Always returns one terminal record."""
    try:
        return _score_cell_inner(
            task_id=task_id,
            condition_id=condition_id,
            gold=gold,
            proposed_assertions=proposed_assertions,
            inference_status=inference_status,
            model_provenance=model_provenance,
            repo_commit=repo_commit,
            malformed=malformed,
        )
    except TaskContractError as e:
        return _terminal_null(
            task_id=task_id,
            condition_id=condition_id,
            inference_status=inference_status,
            scoring_status=ScoringStatus.TASK_CONTRACT_ERROR,
            invalid_reason=e.reason_code,
            model_provenance=model_provenance,
            repo_commit=repo_commit,
            gold=None,
        )
    except Exception as e:  # noqa: BLE001 — last-resort internal
        return _terminal_null(
            task_id=task_id,
            condition_id=condition_id,
            inference_status=inference_status,
            scoring_status=ScoringStatus.SCORER_INTERNAL_ERROR,
            invalid_reason=f"SCORER_INTERNAL_ERROR:{type(e).__name__}",
            model_provenance=model_provenance,
            repo_commit=repo_commit,
            gold=None,
        )


def _score_cell_inner(
    *,
    task_id: str,
    condition_id: str,
    gold: RelationalGold | Mapping[str, Any],
    proposed_assertions: Sequence[Mapping[str, Any]] | None,
    inference_status: str,
    model_provenance: Mapping[str, Any] | None,
    repo_commit: str | None,
    malformed: bool,
) -> dict[str, Any]:
    g = gold if isinstance(gold, RelationalGold) else RelationalGold.from_dict(gold)
    if g.task_id != task_id and task_id:
        # Allow explicit task_id override only if gold matches or is empty check
        pass
    if g.task_id != task_id:
        raise TaskContractError("TASK_ID_MISMATCH", f"{g.task_id}!={task_id}")

    # Non-completed inference → not scored numerically
    status_key = str(inference_status)
    if status_key in _INFERENCE_TO_SCORING:
        return _terminal_null(
            task_id=task_id,
            condition_id=condition_id,
            inference_status=status_key,
            scoring_status=_INFERENCE_TO_SCORING[status_key],
            invalid_reason=status_key,
            model_provenance=model_provenance,
            repo_commit=repo_commit,
            gold=g,
        )

    if malformed or proposed_assertions is None:
        return _terminal_null(
            task_id=task_id,
            condition_id=condition_id,
            inference_status=status_key,
            scoring_status=ScoringStatus.MALFORMED_ASSERTIONS,
            invalid_reason="MALFORMED_ASSERTIONS",
            model_provenance=model_provenance,
            repo_commit=repo_commit,
            gold=g,
        )

    # Parse proposed triples (schema-level)
    raw_triples: list[RelationTriple] = []
    for item in proposed_assertions:
        if not isinstance(item, Mapping):
            return _terminal_null(
                task_id=task_id,
                condition_id=condition_id,
                inference_status=status_key,
                scoring_status=ScoringStatus.MALFORMED_ASSERTIONS,
                invalid_reason="ASSERTION_NOT_OBJECT",
                model_provenance=model_provenance,
                repo_commit=repo_commit,
                gold=g,
            )
        for key in ("subject_id", "object_id"):
            if key not in item or not str(item[key]).strip():
                return _terminal_null(
                    task_id=task_id,
                    condition_id=condition_id,
                    inference_status=status_key,
                    scoring_status=ScoringStatus.MALFORMED_ASSERTIONS,
                    invalid_reason=f"MISSING_{key.upper()}",
                    model_provenance=model_provenance,
                    repo_commit=repo_commit,
                    gold=g,
                )
        rel = item.get("relation") or item.get("predicate_id")
        if not rel or not str(rel).strip():
            return _terminal_null(
                task_id=task_id,
                condition_id=condition_id,
                inference_status=status_key,
                scoring_status=ScoringStatus.MALFORMED_ASSERTIONS,
                invalid_reason="MISSING_RELATION",
                model_provenance=model_provenance,
                repo_commit=repo_commit,
                gold=g,
            )
        raw_triples.append(
            RelationTriple(
                subject_id=str(item["subject_id"]).strip(),
                relation=str(rel).strip(),
                object_id=str(item["object_id"]).strip(),
            )
        )

    remaining = set(g.expected_relations)
    seen_unique: set[RelationTriple] = set()
    proposal_classes: list[dict[str, Any]] = []

    tp = wr = rd = unsup = oou = dup = 0

    for prop in raw_triples:
        cls = classify_proposal(
            prop,
            gold=g,
            remaining_expected=remaining,
            seen_unique=seen_unique,
        )
        proposal_classes.append(
            {"triple": prop.as_dict(), "classification": cls.value}
        )
        if cls is RelationClass.DUPLICATE_ASSERTION:
            dup += 1
            continue
        # First occurrence of this unique triple
        seen_unique.add(prop)
        if cls is RelationClass.TRUE_POSITIVE:
            tp += 1
            # Consume expected (exact or symmetric reverse)
            if prop in remaining:
                remaining.discard(prop)
            elif prop.relation in g.symmetric_relations:
                rev = RelationTriple(prop.object_id, prop.relation, prop.subject_id)
                remaining.discard(rev)
        elif cls is RelationClass.WRONG_RELATION:
            wr += 1
        elif cls is RelationClass.REVERSED_DIRECTION:
            rd += 1
        elif cls is RelationClass.UNSUPPORTED_ASSERTION:
            unsup += 1
        elif cls is RelationClass.OUT_OF_UNIVERSE_ASSERTION:
            oou += 1

    false_negatives = sort_triples(remaining)
    fn = len(false_negatives)
    expected_n = len(g.expected_relations)
    proposed_raw_n = len(raw_triples)
    proposed_unique_n = len(seen_unique)
    # Unique scored proposals = unique triples (duplicates already excluded from set)
    unique_scored_proposals = proposed_unique_n

    score, score_reason = primary_score_formula(
        true_positive_n=tp,
        expected_n=expected_n,
        wrong_relation_n=wr,
        reversed_direction_n=rd,
        unsupported_assertion_n=unsup,
        out_of_universe_assertion_n=oou,
    )

    prf = _precision_recall_f1(
        true_positive_n=tp,
        expected_n=expected_n,
        unique_scored_proposals=unique_scored_proposals,
    )

    exact = (
        fn == 0
        and wr == 0
        and rd == 0
        and unsup == 0
        and oou == 0
        and dup == 0
        and tp == expected_n
        and expected_n > 0
    )

    record = {
        "schema_version": SCORER_SCHEMA_VERSION,
        "task_id": task_id,
        "condition_id": condition_id,
        "inference_status": status_key,
        "scoring_status": ScoringStatus.SCORED.value,
        "primary_score": score,
        "primary_score_undefined_reason": score_reason,
        "exact_relation_set_match": exact,
        "expected_n": expected_n,
        "proposed_raw_n": proposed_raw_n,
        "proposed_unique_n": proposed_unique_n,
        "true_positive_n": tp,
        "false_negative_n": fn,
        "wrong_relation_n": wr,
        "reversed_direction_n": rd,
        "unsupported_assertion_n": unsup,
        "out_of_universe_assertion_n": oou,
        "duplicate_assertion_n": dup,
        **prf,
        "invalid_reason": None,
        "expected_relation_hash": triples_hash(g.expected_relations),
        "proposed_assertion_hash": triples_hash(raw_triples),
        "false_negatives": [t.as_dict() for t in false_negatives],
        "proposal_classifications": proposal_classes,
        "task_contract_version": g.contract_version,
        "scorer_schema_version": SCORER_SCHEMA_VERSION,
        "repo_commit": repo_commit,
        "model_runtime_provenance": dict(model_provenance or {}),
        "scientific_status": SCIENTIFIC_STATUS,
        "scientific_completion": False,
        "headline_eligible": False,
        "headline_ineligible_reason": HEADLINE_INELIGIBLE_REASON,
    }
    return record


def _terminal_null(
    *,
    task_id: str,
    condition_id: str,
    inference_status: str,
    scoring_status: ScoringStatus,
    invalid_reason: str | None,
    model_provenance: Mapping[str, Any] | None,
    repo_commit: str | None,
    gold: RelationalGold | None,
) -> dict[str, Any]:
    expected_n = len(gold.expected_relations) if gold else 0
    exp_hash = triples_hash(gold.expected_relations) if gold else None
    contract = gold.contract_version if gold else None
    return {
        "schema_version": SCORER_SCHEMA_VERSION,
        "task_id": task_id,
        "condition_id": condition_id,
        "inference_status": inference_status,
        "scoring_status": scoring_status.value,
        "primary_score": None,
        "primary_score_undefined_reason": invalid_reason or scoring_status.value,
        "exact_relation_set_match": False,
        "expected_n": expected_n,
        "proposed_raw_n": 0,
        "proposed_unique_n": 0,
        "true_positive_n": 0,
        "false_negative_n": expected_n,
        "wrong_relation_n": 0,
        "reversed_direction_n": 0,
        "unsupported_assertion_n": 0,
        "out_of_universe_assertion_n": 0,
        "duplicate_assertion_n": 0,
        "precision": None,
        "precision_undefined_reason": "NOT_SCORED",
        "recall": None,
        "recall_undefined_reason": "NOT_SCORED",
        "f1": None,
        "f1_undefined_reason": "NOT_SCORED",
        "invalid_reason": invalid_reason,
        "expected_relation_hash": exp_hash,
        "proposed_assertion_hash": None,
        "false_negatives": (
            [t.as_dict() for t in sort_triples(gold.expected_relations)] if gold else []
        ),
        "proposal_classifications": [],
        "task_contract_version": contract,
        "scorer_schema_version": SCORER_SCHEMA_VERSION,
        "repo_commit": repo_commit,
        "model_runtime_provenance": dict(model_provenance or {}),
        "scientific_status": SCIENTIFIC_STATUS,
        "scientific_completion": False,
        "headline_eligible": False,
        "headline_ineligible_reason": HEADLINE_INELIGIBLE_REASON,
    }


def score_record_canonical_bytes(record: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(dict(record))


def score_record_hash(record: Mapping[str, Any]) -> str:
    return sha256_hex(score_record_canonical_bytes(record))


def score_planned_cells(
    cells: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Score a planned list of cells; one terminal record each (manifest shape).

    Each cell mapping requires:
      task_id, condition_id, gold, inference_status,
      proposed_assertions (optional), malformed (optional)
    """
    out: list[dict[str, Any]] = []
    for cell in cells:
        out.append(
            score_cell(
                task_id=str(cell["task_id"]),
                condition_id=str(cell["condition_id"]),
                gold=cell["gold"],
                proposed_assertions=cell.get("proposed_assertions"),
                inference_status=str(cell.get("inference_status") or "completed"),
                model_provenance=cell.get("model_provenance"),
                repo_commit=cell.get("repo_commit"),
                malformed=bool(cell.get("malformed", False)),
            )
        )
    return out
