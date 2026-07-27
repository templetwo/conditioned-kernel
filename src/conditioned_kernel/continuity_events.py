"""Append-only continuity event schema and canonical state hashing.

RUN 00.6B / 00.6B.1: candidate is the atomic acceptance unit.
Event schema v2 carries a canonical ordered assertion batch per candidate.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

# v2 only — one event per accepted candidate with assertions[].
EVENT_SCHEMA_VERSION = "ck.continuity_event.v2"
GENESIS_SCHEMA_VERSION = "ck.genesis.v1"
VALIDATOR_VERSION = "ck.continuity_validator.v1"
# v2: execution_scope + scientific_completion are durable terminal fields
# set before persistence (never post-patched).
RECEIPT_SCHEMA_VERSION = "ck.continuity_receipt.v2"
RELATION_ATOM_KEYS = frozenset({"subject_id", "relation", "object_id"})

ALLOWED_RELATIONS = frozenset(
    {
        "remains_open",
        "is_answered",
        "depends_on",
        "blocked_by",
        "references",
    }
)


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON bytes (sorted keys, no insignificant whitespace)."""
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_hash(raw: str | bytes) -> str:
    if isinstance(raw, str):
        raw_b = raw.encode("utf-8")
    else:
        raw_b = raw
    return sha256_hex(raw_b)


def relation_atom(
    subject_id: str, relation: str, object_id: str
) -> dict[str, str]:
    return {
        "subject_id": subject_id,
        "relation": relation,
        "object_id": object_id,
    }


def normalize_relations(
    relations: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Sort relation atoms for deterministic materialization and event payload."""
    atoms: list[dict[str, str]] = []
    for r in relations:
        atoms.append(
            relation_atom(
                str(r["subject_id"]),
                str(r["relation"]),
                str(r["object_id"]),
            )
        )
    atoms.sort(key=lambda a: (a["subject_id"], a["relation"], a["object_id"]))
    return atoms


def event_assertion_atoms(event: Mapping[str, Any]) -> list[dict[str, str]]:
    """Extract assertion atoms from a v2 batch event."""
    if "assertions" not in event:
        raise ValueError("event missing assertions batch (v2 required)")
    raw = event["assertions"]
    if not isinstance(raw, list) or not raw:
        raise ValueError("event assertions must be a non-empty list")
    return normalize_relations(raw)


def materialize_state(
    genesis: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive canonical state from genesis + ordered accepted events.

    Each event contributes its full assertion batch. Free-form prose never enters
    accepted_relations.
    """
    rels: list[dict[str, str]] = []
    for seed in genesis.get("seed_relations") or []:
        if isinstance(seed, Mapping):
            rels.append(
                relation_atom(
                    str(seed["subject_id"]),
                    str(seed["relation"]),
                    str(seed["object_id"]),
                )
            )
    for ev in events:
        # Support internal prospective shapes that only carry assertions
        if "assertions" in ev:
            rels.extend(event_assertion_atoms(ev))
        elif all(k in ev for k in ("subject_id", "relation", "object_id")):
            # Prospective single-atom dict used only before packaging into a batch
            rels.append(
                relation_atom(
                    str(ev["subject_id"]),
                    str(ev["relation"]),
                    str(ev["object_id"]),
                )
            )
        else:
            raise ValueError("event lacks assertions batch")
    unique = {(a["subject_id"], a["relation"], a["object_id"]): a for a in rels}
    ordered = normalize_relations(list(unique.values()))
    return {
        "schema_version": "ck.materialized_state.v1",
        "genesis_hash": sha256_hex(canonical_json_bytes(dict(genesis))),
        "accepted_relations": ordered,
    }


def canonical_state_hash(
    genesis: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> str:
    return sha256_hex(canonical_json_bytes(materialize_state(genesis, events)))


def build_event(
    *,
    event_id: str,
    sequence: int,
    parent_state_hash: str,
    resulting_state_hash: str,
    episode_id: str,
    assertions: Sequence[Mapping[str, Any]],
    source_candidate_hash: str,
    acceptance_reason_code: str,
    timestamp: str,
    repo_commit: str | None,
    provenance: Mapping[str, Any] | None = None,
    execution_scope: str | None = None,
) -> dict[str, Any]:
    """Build one candidate-atomic continuity event with a canonical assertion batch.

    execution_scope is required for new events (live plumbing / offline / etc.).
    Kept as an additive field on schema v2 so event/receipt pairs can agree.
    """
    ordered = normalize_relations(assertions)
    if not ordered:
        raise ValueError("build_event requires a non-empty assertion batch")
    # Fail closed on internal duplicates (caller should already reject)
    triples = [(a["subject_id"], a["relation"], a["object_id"]) for a in ordered]
    if len(triples) != len(set(triples)):
        raise ValueError("build_event refuses duplicate assertions in batch")
    if not execution_scope:
        raise ValueError("build_event requires execution_scope")
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "sequence": sequence,
        "parent_state_hash": parent_state_hash,
        "resulting_state_hash": resulting_state_hash,
        "episode_id": episode_id,
        "assertions": ordered,
        "source_candidate_hash": source_candidate_hash,
        "validator_version": VALIDATOR_VERSION,
        "acceptance_reason_code": acceptance_reason_code,
        "timestamp": timestamp,
        "repo_commit": repo_commit,
        "execution_scope": str(execution_scope),
        "provenance": dict(provenance or {}),
    }
