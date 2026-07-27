"""RUN 00.8A — evidence-derived packet/control verification.

Caller-attested status strings are never trusted. Status is derived from
canonical receipt artifacts and their hashes.
"""

from __future__ import annotations

from typing import Any, Mapping

from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

PACKET_RECEIPT_SCHEMA = "ck.packet_receipt.v1"
CONTROL_RECEIPT_SCHEMA = "ck.control_receipt.v1"


class EvidenceError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def receipt_hash(receipt: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(dict(receipt)))


def make_packet_receipt(
    *,
    cell_id: str,
    task_id: str,
    condition_id: str,
    request_sha256: str,
    complete_byte_length: int,
    packet_contract_version: str,
    verdict: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    body = {
        "schema_version": PACKET_RECEIPT_SCHEMA,
        "cell_id": cell_id,
        "task_id": task_id,
        "condition_id": condition_id,
        "request_sha256": request_sha256,
        "complete_byte_length": complete_byte_length,
        "packet_contract_version": packet_contract_version,
        "verdict": verdict.upper(),
        "reason_codes": list(reason_codes or []),
        "scientific_completion": False,
        "headline_eligible": False,
        "scientific_status": "control_verification_only",
    }
    body["receipt_sha256"] = receipt_hash(
        {k: v for k, v in body.items() if k != "receipt_sha256"}
    )
    return body


def make_control_receipt(
    *,
    cell_id: str,
    task_id: str,
    condition_id: str,
    paired_cell_id: str | None,
    verdict: str,
    reason_codes: list[str] | None = None,
    left_hash: str | None = None,
    right_hash: str | None = None,
    byte_match: bool | None = None,
) -> dict[str, Any]:
    body = {
        "schema_version": CONTROL_RECEIPT_SCHEMA,
        "cell_id": cell_id,
        "task_id": task_id,
        "condition_id": condition_id,
        "paired_cell_id": paired_cell_id,
        "verdict": verdict.upper(),
        "reason_codes": list(reason_codes or []),
        "left_hash": left_hash,
        "right_hash": right_hash,
        "byte_match": byte_match,
        "scientific_completion": False,
        "headline_eligible": False,
        "scientific_status": "control_verification_only",
    }
    body["receipt_sha256"] = receipt_hash(
        {k: v for k, v in body.items() if k != "receipt_sha256"}
    )
    return body


def verify_packet_receipt(
    receipt: Mapping[str, Any] | None,
    *,
    cell_id: str,
    task_id: str,
    condition_id: str,
    claimed_hash: str | None = None,
) -> tuple[str, str | None, list[str]]:
    """Return (status, receipt_hash, reason_codes). status is pass|fail|missing."""
    if receipt is None:
        return "missing", None, ["PACKET_RECEIPT_MISSING"]
    reasons: list[str] = []
    if str(receipt.get("schema_version")) != PACKET_RECEIPT_SCHEMA:
        reasons.append("PACKET_RECEIPT_SCHEMA_MISMATCH")
    if str(receipt.get("cell_id")) != cell_id:
        reasons.append("PACKET_RECEIPT_CELL_MISMATCH")
    if str(receipt.get("task_id")) != task_id:
        reasons.append("PACKET_RECEIPT_TASK_MISMATCH")
    if str(receipt.get("condition_id")) != condition_id:
        reasons.append("PACKET_RECEIPT_CONDITION_MISMATCH")
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    computed = receipt_hash(body)
    embedded = str(receipt.get("receipt_sha256") or "")
    if embedded and embedded != computed:
        reasons.append("PACKET_RECEIPT_HASH_MISMATCH")
    if claimed_hash and claimed_hash != computed:
        reasons.append("PACKET_RECEIPT_CLAIMED_HASH_MISMATCH")
    if receipt.get("headline_eligible") is True:
        reasons.append("PACKET_RECEIPT_HEADLINE_LIE")
    if receipt.get("scientific_completion") is True:
        reasons.append("PACKET_RECEIPT_SCIENCE_LIE")
    verdict = str(receipt.get("verdict") or "").upper()
    if reasons:
        return "fail", computed, reasons
    if verdict == "PASS":
        return "pass", computed, []
    if verdict == "FAIL":
        return "fail", computed, list(receipt.get("reason_codes") or ["PACKET_VERDICT_FAIL"])
    return "fail", computed, ["PACKET_VERDICT_UNKNOWN"]


def verify_control_receipt(
    receipt: Mapping[str, Any] | None,
    *,
    cell_id: str,
    task_id: str,
    condition_id: str,
    claimed_hash: str | None = None,
) -> tuple[str, str | None, list[str]]:
    """Return (status, receipt_hash, reason_codes). Never trust caller 'pass' string."""
    if receipt is None:
        return "missing", None, ["CONTROL_RECEIPT_MISSING"]
    reasons: list[str] = []
    if str(receipt.get("schema_version")) != CONTROL_RECEIPT_SCHEMA:
        reasons.append("CONTROL_RECEIPT_SCHEMA_MISMATCH")
    if str(receipt.get("cell_id")) != cell_id:
        reasons.append("CONTROL_RECEIPT_CELL_MISMATCH")
    if str(receipt.get("task_id")) != task_id:
        reasons.append("CONTROL_RECEIPT_TASK_MISMATCH")
    if str(receipt.get("condition_id")) != condition_id:
        reasons.append("CONTROL_RECEIPT_CONDITION_MISMATCH")
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    computed = receipt_hash(body)
    embedded = str(receipt.get("receipt_sha256") or "")
    if embedded and embedded != computed:
        reasons.append("CONTROL_RECEIPT_HASH_MISMATCH")
    if claimed_hash and claimed_hash != computed:
        reasons.append("CONTROL_RECEIPT_CLAIMED_HASH_MISMATCH")
    if receipt.get("headline_eligible") is True:
        reasons.append("CONTROL_RECEIPT_HEADLINE_LIE")
    if receipt.get("scientific_completion") is True:
        reasons.append("CONTROL_RECEIPT_SCIENCE_LIE")
    verdict = str(receipt.get("verdict") or "").upper()
    if reasons:
        return "fail", computed, reasons
    if verdict == "PASS":
        return "pass", computed, []
    if verdict == "FAIL":
        return "fail", computed, list(receipt.get("reason_codes") or ["CONTROL_VERDICT_FAIL"])
    return "fail", computed, ["CONTROL_VERDICT_UNKNOWN"]
