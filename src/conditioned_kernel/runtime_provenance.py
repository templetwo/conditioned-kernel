"""RUN 00.8A — runtime provenance and generation-option enforcement.

Offline-capable. Model digest and runtime fields may be synthetic in
commissioning. Completeness is computed, never caller-attested.
"""

from __future__ import annotations

from typing import Any, Mapping

from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

COMMISSIONING_EXECUTION_SCOPE = "commissioning_validation"
SCIENTIFIC_STATUS = "commissioning_safety_only"

REQUIRED_PROVENANCE_FIELDS = (
    "model_tag",
    "resolved_model_digest",
    "runtime_version",
    "host_architecture",
    "requested_generation_options",
    "confirmed_generation_options",
    "packet_request_sha256",
    "raw_response_sha256",
    "started_at",
    "ended_at",
    "process_id",
)


class ProvenanceError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def compute_provenance_completeness(
    provenance: Mapping[str, Any] | None,
    *,
    require_confirmed_options: bool = True,
) -> tuple[bool, list[str]]:
    """Derive completeness from required fields. Never trust caller boolean."""
    missing: list[str] = []
    p = dict(provenance or {})
    field_to_reason = {
        "model_tag": "MODEL_TAG_MISSING",
        "resolved_model_digest": "MODEL_DIGEST_MISSING",
        "runtime_version": "RUNTIME_VERSION_MISSING",
        "host_architecture": "HOST_ARCHITECTURE_MISSING",
        "requested_generation_options": "GENERATION_OPTION_UNVERIFIED",
        "confirmed_generation_options": "GENERATION_OPTION_UNVERIFIED",
        "packet_request_sha256": "REQUEST_HASH_MISSING",
        "raw_response_sha256": "RESPONSE_HASH_MISSING",
        "started_at": "START_TIMESTAMP_MISSING",
        "ended_at": "END_TIMESTAMP_MISSING",
        "process_id": "PROCESS_ID_MISSING",
    }
    for f in REQUIRED_PROVENANCE_FIELDS:
        v = p.get(f)
        if v is None or v == "" or v == {}:
            missing.append(field_to_reason[f])

    req = p.get("requested_generation_options") or {}
    conf = p.get("confirmed_generation_options") or {}
    if require_confirmed_options and isinstance(req, Mapping) and isinstance(conf, Mapping):
        for key in ("temperature", "seed", "num_ctx"):
            if key in req and conf.get(key) != req.get(key):
                if "GENERATION_OPTION_UNVERIFIED" not in missing:
                    missing.append("GENERATION_OPTION_UNVERIFIED")
                if "RUNTIME_PROVENANCE_FAILURE" not in missing:
                    missing.append("RUNTIME_PROVENANCE_FAILURE")
                break
        if not conf and req:
            if "GENERATION_OPTION_UNVERIFIED" not in missing:
                missing.append("GENERATION_OPTION_UNVERIFIED")

    # Dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for m in missing:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return (len(out) == 0, out)


def build_runtime_provenance(
    *,
    model_tag: str,
    resolved_model_digest: str | None,
    runtime_version: str | None,
    host_architecture: str | None,
    requested_generation_options: Mapping[str, Any],
    confirmed_generation_options: Mapping[str, Any] | None,
    packet_request_sha256: str | None,
    raw_response_sha256: str | None,
    started_at: str | None,
    ended_at: str | None,
    process_id: int | str | None,
    tokenizer_metadata: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prov: dict[str, Any] = {
        "model_tag": model_tag,
        "resolved_model_digest": resolved_model_digest,
        "runtime_version": runtime_version,
        "host_architecture": host_architecture,
        "requested_generation_options": dict(requested_generation_options),
        "confirmed_generation_options": dict(confirmed_generation_options or {}),
        "packet_request_sha256": packet_request_sha256,
        "raw_response_sha256": raw_response_sha256,
        "started_at": started_at,
        "ended_at": ended_at,
        "process_id": process_id,
        "tokenizer_metadata": dict(tokenizer_metadata or {}),
    }
    if extra:
        prov.update(dict(extra))
    complete, missing = compute_provenance_completeness(prov)
    prov["provenance_complete"] = complete
    prov["provenance_missing_reasons"] = missing
    return prov


def options_honored(
    requested: Mapping[str, Any],
    confirmed: Mapping[str, Any] | None,
) -> tuple[bool, list[str]]:
    """Compare requested vs runtime-confirmed generation options."""
    if not confirmed:
        return False, ["GENERATION_OPTION_UNVERIFIED"]
    reasons: list[str] = []
    for key in sorted(requested.keys()):
        if key not in confirmed:
            reasons.append(f"OPTION_UNCONFIRMED:{key}")
        elif confirmed[key] != requested[key]:
            reasons.append(f"OPTION_MISMATCH:{key}")
    if reasons:
        return False, reasons
    return True, []


def synthetic_model_digest(model_tag: str, *, salt: str = "commissioning") -> str:
    """Deterministic offline digest for synthetic adapters (not a real model)."""
    return "sha256:" + sha256_hex(
        canonical_json_bytes({"model_tag": model_tag, "salt": salt})
    )
