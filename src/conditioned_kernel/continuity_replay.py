"""Deterministic replay of append-only continuity events. No model invocation.

RUN 00.6B.1: events carry a candidate-level assertion batch (schema v2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from conditioned_kernel.continuity_events import (
    ALLOWED_RELATIONS,
    EVENT_SCHEMA_VERSION,
    canonical_json_bytes,
    canonical_state_hash,
    event_assertion_atoms,
    materialize_state,
    normalize_relations,
    sha256_hex,
)
from conditioned_kernel.continuity_store import ContinuityStore


class ReplayError(ValueError):
    """Broken chain, unknown version, tamper, or non-deterministic history."""


@dataclass(frozen=True)
class ReconstructedState:
    state: dict[str, Any]
    state_hash: str
    event_count: int


def _verify_event_content_integrity(event: Mapping[str, Any]) -> None:
    """Reject events with unknown keys that could carry hidden authority."""
    allowed = {
        "schema_version",
        "event_id",
        "sequence",
        "parent_state_hash",
        "resulting_state_hash",
        "episode_id",
        "assertions",
        "source_candidate_hash",
        "validator_version",
        "acceptance_reason_code",
        "timestamp",
        "repo_commit",
        "execution_scope",
        "provenance",
    }
    unknown = set(event.keys()) - allowed
    if unknown:
        raise ReplayError(f"unknown event fields: {sorted(unknown)}")


def _validate_event_assertions(
    event: Mapping[str, Any],
    universe: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    """Validate batch assertions; fail closed on duplicates or invalid atoms."""
    try:
        atoms = event_assertion_atoms(event)
    except ValueError as e:
        raise ReplayError(str(e)) from e

    triples = [(a["subject_id"], a["relation"], a["object_id"]) for a in atoms]
    if len(triples) != len(set(triples)):
        raise ReplayError("duplicate assertions inside persisted event")

    # Canonical order required
    if atoms != normalize_relations(atoms):
        raise ReplayError("assertions not in canonical order")

    if universe is not None:
        subjects = set(universe.get("subject_ids") or [])
        objects = set(universe.get("object_ids") or [])
        rels = set(universe.get("relations") or []) & ALLOWED_RELATIONS
        if not rels:
            rels = set(ALLOWED_RELATIONS)
        combos = {
            (str(a), str(b), str(c))
            for a, b, c in (universe.get("valid_combinations") or [])
        }
        for a in atoms:
            if a["subject_id"] not in subjects:
                raise ReplayError(f"invalid assertion subject: {a['subject_id']}")
            if a["object_id"] not in objects:
                raise ReplayError(f"invalid assertion object: {a['object_id']}")
            if a["relation"] not in ALLOWED_RELATIONS or a["relation"] not in rels:
                raise ReplayError(f"invalid assertion relation: {a['relation']}")
            triple = (a["subject_id"], a["relation"], a["object_id"])
            if combos and triple not in combos:
                raise ReplayError(f"invalid assertion combination: {triple}")
    else:
        for a in atoms:
            if a["relation"] not in ALLOWED_RELATIONS:
                raise ReplayError(f"invalid assertion relation: {a['relation']}")
            for key in ("subject_id", "relation", "object_id"):
                if not a.get(key):
                    raise ReplayError(f"invalid assertion missing {key}")

    return atoms


def replay_events(
    genesis: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    universe: Mapping[str, Any] | None = None,
) -> ReconstructedState:
    """Replay genesis + ordered candidate-batch events; fail closed on integrity breaks."""
    seen_ids: set[str] = set()
    applied: list[dict[str, Any]] = []
    current_hash = canonical_state_hash(genesis, [])

    for ev in events:
        _verify_event_content_integrity(ev)
        version = ev.get("schema_version")
        if version != EVENT_SCHEMA_VERSION:
            raise ReplayError(f"unknown event schema version: {version!r}")

        event_id = str(ev.get("event_id") or "")
        if not event_id:
            raise ReplayError("missing event_id")
        if event_id in seen_ids:
            raise ReplayError(f"duplicate event_id: {event_id}")
        seen_ids.add(event_id)

        parent = ev.get("parent_state_hash")
        if parent != current_hash:
            raise ReplayError(
                f"broken parent hash chain at {event_id}: "
                f"expected {current_hash}, got {parent}"
            )

        atoms = _validate_event_assertions(ev, universe)

        # Apply complete batch atomically as one event record
        batch_event = {
            "schema_version": ev["schema_version"],
            "event_id": event_id,
            "sequence": ev.get("sequence"),
            "parent_state_hash": ev["parent_state_hash"],
            "resulting_state_hash": ev["resulting_state_hash"],
            "episode_id": ev.get("episode_id"),
            "assertions": atoms,
            "source_candidate_hash": ev.get("source_candidate_hash"),
            "validator_version": ev.get("validator_version"),
            "acceptance_reason_code": ev.get("acceptance_reason_code"),
            "timestamp": ev.get("timestamp"),
            "repo_commit": ev.get("repo_commit"),
            "provenance": ev.get("provenance") or {},
        }
        applied.append(batch_event)

        expected = canonical_state_hash(genesis, applied)
        claimed = ev.get("resulting_state_hash")
        if claimed != expected:
            raise ReplayError(
                f"mutated or inconsistent event payload at {event_id}: "
                f"claimed resulting hash {claimed}, recomputed {expected}"
            )
        current_hash = expected

    state = materialize_state(genesis, applied)
    final = sha256_hex(canonical_json_bytes(state))
    if final != current_hash:
        raise ReplayError("materialized state hash mismatch after replay")
    return ReconstructedState(state=state, state_hash=final, event_count=len(applied))


def replay_store(store: ContinuityStore) -> ReconstructedState:
    store.quarantine_partials()
    universe = None
    try:
        universe = store.load_universe()
    except Exception:
        universe = None
    return replay_events(
        store.load_genesis(),
        store.list_events(),
        universe=universe,
    )
