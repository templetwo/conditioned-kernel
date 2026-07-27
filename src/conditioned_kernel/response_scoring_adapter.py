"""RUN 00.8A — ck.response_scoring_adapter.v1

Frozen route:
  raw model response bytes
    → typed inference outcome
    → approved structured-output parser
    → parsed continuity assertions
    → relational scorer

No prose inference. Deterministic mapping for empty/malformed/null cases.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping

from conditioned_kernel.m0_ledger_integration import M0TerminalClassification
from conditioned_kernel.relational_scorer import (
    SCORER_SCHEMA_VERSION,
    score_cell,
    score_record_hash,
    sha256_hex,
)

ADAPTER_SCHEMA_VERSION = "ck.response_scoring_adapter.v1"


class ParseKind(str, Enum):
    STRUCTURED_ASSERTIONS = "STRUCTURED_ASSERTIONS"
    EMPTY_FINAL_RESPONSE = "EMPTY_FINAL_RESPONSE"
    EMPTY_ASSERTION_LIST = "EMPTY_ASSERTION_LIST"
    MALFORMED_JSON = "MALFORMED_JSON"
    WRONG_SCHEMA_KEY = "WRONG_SCHEMA_KEY"
    PROSE_ONLY = "PROSE_ONLY"
    NULL_RESPONSE = "NULL_RESPONSE"
    PARSER_EXCEPTION = "PARSER_EXCEPTION"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    INFERENCE_TRANSPORT = "INFERENCE_TRANSPORT"
    INFERENCE_INVALID = "INFERENCE_INVALID"
    INFERENCE_NO_FINAL = "INFERENCE_NO_FINAL"


# Frozen mapping: one terminal classification per parse kind (no 0-vs-null fork).
_PARSE_TO_CLASS: dict[ParseKind, M0TerminalClassification] = {
    ParseKind.STRUCTURED_ASSERTIONS: M0TerminalClassification.SCORED,
    ParseKind.EMPTY_FINAL_RESPONSE: M0TerminalClassification.NO_FINAL_RESPONSE,
    ParseKind.EMPTY_ASSERTION_LIST: M0TerminalClassification.SCORED,  # scorer scores empty list
    ParseKind.MALFORMED_JSON: M0TerminalClassification.MALFORMED_ASSERTIONS,
    ParseKind.WRONG_SCHEMA_KEY: M0TerminalClassification.MALFORMED_ASSERTIONS,
    ParseKind.PROSE_ONLY: M0TerminalClassification.MALFORMED_ASSERTIONS,
    ParseKind.NULL_RESPONSE: M0TerminalClassification.NO_FINAL_RESPONSE,
    ParseKind.PARSER_EXCEPTION: M0TerminalClassification.MALFORMED_ASSERTIONS,
    ParseKind.INFERENCE_TIMEOUT: M0TerminalClassification.TIMEOUT,
    ParseKind.INFERENCE_TRANSPORT: M0TerminalClassification.TRANSPORT_ERROR,
    ParseKind.INFERENCE_INVALID: M0TerminalClassification.INVALID_RESPONSE,
    ParseKind.INFERENCE_NO_FINAL: M0TerminalClassification.NO_FINAL_RESPONSE,
}


def raw_response_evidence(raw: bytes | str | None) -> dict[str, Any]:
    if raw is None:
        data = b""
        channel = "null"
    elif isinstance(raw, str):
        data = raw.encode("utf-8")
        channel = "text"
    else:
        data = raw
        channel = "bytes"
    return {
        "raw_response_sha256": sha256_hex(data) if data else sha256_hex(b""),
        "raw_response_byte_length": len(data),
        "response_channel_status": channel if raw is not None else "null",
        "raw_response_bytes": data,
    }


def parse_structured_response(
    raw: bytes | str | None,
    *,
    inference_status: str = "completed",
) -> dict[str, Any]:
    """Parse raw response into assertions or a typed parse failure.

    Returns adapter record with parse_kind, classification, assertions|None,
    and evidence fields. Does not score.
    """
    ev = raw_response_evidence(raw)
    status = str(inference_status).lower()
    if status in ("timeout",):
        return _result(ParseKind.INFERENCE_TIMEOUT, None, ev, inference_status=status)
    if status in ("transport_error", "transport"):
        return _result(ParseKind.INFERENCE_TRANSPORT, None, ev, inference_status=status)
    if status in ("invalid_response", "invalid"):
        return _result(ParseKind.INFERENCE_INVALID, None, ev, inference_status=status)
    if status in ("no_final_response", "no_final"):
        return _result(ParseKind.INFERENCE_NO_FINAL, None, ev, inference_status=status)

    if raw is None:
        return _result(ParseKind.NULL_RESPONSE, None, ev)
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    if not text.strip():
        return _result(ParseKind.EMPTY_FINAL_RESPONSE, None, ev)

    stripped = text.strip()
    # Prose-only: no JSON object braces
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return _result(ParseKind.PROSE_ONLY, None, ev)

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return _result(ParseKind.MALFORMED_JSON, None, ev)
    except Exception:  # noqa: BLE001
        return _result(ParseKind.PARSER_EXCEPTION, None, ev)

    if not isinstance(obj, dict):
        return _result(ParseKind.WRONG_SCHEMA_KEY, None, ev)
    if "continuity_assertions" not in obj:
        return _result(ParseKind.WRONG_SCHEMA_KEY, None, ev)
    assertions = obj.get("continuity_assertions")
    if not isinstance(assertions, list):
        return _result(ParseKind.WRONG_SCHEMA_KEY, None, ev)
    if len(assertions) == 0:
        return _result(ParseKind.EMPTY_ASSERTION_LIST, [], ev)
    # Validate items are objects with required keys
    for item in assertions:
        if not isinstance(item, dict):
            return _result(ParseKind.MALFORMED_JSON, None, ev)
        if not all(k in item for k in ("subject_id", "relation", "object_id")):
            return _result(ParseKind.MALFORMED_JSON, None, ev)
    return _result(ParseKind.STRUCTURED_ASSERTIONS, assertions, ev)


def _result(
    kind: ParseKind,
    assertions: list[dict[str, Any]] | None,
    evidence: Mapping[str, Any],
    *,
    inference_status: str = "completed",
) -> dict[str, Any]:
    cls = _PARSE_TO_CLASS[kind]
    return {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "parse_kind": kind.value,
        "terminal_classification": cls.value,
        "assertions": assertions,
        "malformed": assertions is None
        and cls is M0TerminalClassification.MALFORMED_ASSERTIONS,
        "inference_status": inference_status,
        "raw_response_sha256": evidence["raw_response_sha256"],
        "raw_response_byte_length": evidence["raw_response_byte_length"],
        "response_channel_status": evidence["response_channel_status"],
        "scorer_schema_version": SCORER_SCHEMA_VERSION,
        "scientific_completion": False,
        "headline_eligible": False,
        "scientific_status": "commissioning_safety_only",
    }


def score_parsed_response(
    parse_result: Mapping[str, Any],
    *,
    planned_cell: Mapping[str, Any],
    gold: Mapping[str, Any],
    repo_commit: str | None = None,
) -> dict[str, Any]:
    """Run relational scorer when parse yields assertions; else null-score path.

    Empty assertion list is scored (deterministic 0.0 when expected_n > 0).
    Malformed / no-final paths produce null primary_score via scorer malformed flag
    or non-completed status — never an ad-hoc zero for those cases.
    """
    kind = ParseKind(str(parse_result["parse_kind"]))
    cls = M0TerminalClassification(str(parse_result["terminal_classification"]))
    base = {
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "parse_kind": kind.value,
        "terminal_classification": cls.value,
        "raw_response_sha256": parse_result["raw_response_sha256"],
        "raw_response_byte_length": parse_result["raw_response_byte_length"],
        "response_channel_status": parse_result["response_channel_status"],
        "scientific_completion": False,
        "headline_eligible": False,
    }

    if kind in (
        ParseKind.STRUCTURED_ASSERTIONS,
        ParseKind.EMPTY_ASSERTION_LIST,
    ):
        assertions = list(parse_result.get("assertions") or [])
        rec = score_cell(
            task_id=str(planned_cell["task_id"]),
            condition_id=str(planned_cell["condition_id"]),
            gold=gold,
            proposed_assertions=assertions,
            inference_status="completed",
            repo_commit=repo_commit,
            model_provenance={"model_tag": planned_cell.get("model_tag")},
            malformed=False,
        )
        # Bind planned expected hash — never overwrite planned with score-only view
        planned_exp = planned_cell.get("expected_relation_hash")
        if planned_exp and rec.get("expected_relation_hash") != planned_exp:
            # Gold mismatch against planned freeze
            return {
                **base,
                "terminal_classification": M0TerminalClassification.TASK_CONTRACT_ERROR.value,
                "score_record": None,
                "score_record_hash": None,
                "primary_score": None,
                "reason_codes": ["SCORE_EXPECTED_HASH_MISMATCH"],
            }
        return {
            **base,
            "terminal_classification": M0TerminalClassification.SCORED.value,
            "score_record": rec,
            "score_record_hash": score_record_hash(rec),
            "primary_score": rec.get("primary_score"),
            "reason_codes": [],
        }

    # Non-scored terminal paths: primary_score must be null (not zero)
    return {
        **base,
        "score_record": None,
        "score_record_hash": None,
        "primary_score": None,
        "reason_codes": [kind.value],
    }
