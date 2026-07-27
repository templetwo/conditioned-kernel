"""Deterministic replay of append-only continuity events. No model invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from conditioned_kernel.continuity_events import (
    EVENT_SCHEMA_VERSION,
    canonical_state_hash,
    materialize_state,
    sha256_hex,
    canonical_json_bytes,
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
        "subject_id",
        "relation",
        "object_id",
        "source_candidate_hash",
        "validator_version",
        "acceptance_reason_code",
        "timestamp",
        "repo_commit",
        "provenance",
    }
    unknown = set(event.keys()) - allowed
    if unknown:
        raise ReplayError(f"unknown event fields: {sorted(unknown)}")


def replay_events(
    genesis: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> ReconstructedState:
    """Replay genesis + ordered events; fail closed on any integrity break."""
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

        # Apply this event's relation atom only (not free-form fields)
        applied.append(
            {
                "subject_id": ev["subject_id"],
                "relation": ev["relation"],
                "object_id": ev["object_id"],
                "event_id": event_id,
                "sequence": ev.get("sequence"),
                "parent_state_hash": ev["parent_state_hash"],
                "resulting_state_hash": ev["resulting_state_hash"],
                "schema_version": ev["schema_version"],
                "source_candidate_hash": ev.get("source_candidate_hash"),
                "validator_version": ev.get("validator_version"),
                "acceptance_reason_code": ev.get("acceptance_reason_code"),
                "timestamp": ev.get("timestamp"),
                "repo_commit": ev.get("repo_commit"),
                "provenance": ev.get("provenance") or {},
                "episode_id": ev.get("episode_id"),
            }
        )
        # Recompute expected resulting hash from genesis + applied events so far
        expected = canonical_state_hash(genesis, applied)
        claimed = ev.get("resulting_state_hash")
        if claimed != expected:
            raise ReplayError(
                f"mutated or inconsistent event payload at {event_id}: "
                f"claimed resulting hash {claimed}, recomputed {expected}"
            )
        current_hash = expected

    state = materialize_state(genesis, applied)
    # Double-check materialization hash
    final = sha256_hex(canonical_json_bytes(state))
    if final != current_hash:
        raise ReplayError("materialized state hash mismatch after replay")
    return ReconstructedState(state=state, state_hash=final, event_count=len(applied))


def replay_store(store: ContinuityStore) -> ReconstructedState:
    store.quarantine_partials()
    return replay_events(store.load_genesis(), store.list_events())
