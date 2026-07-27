"""Parse → closed-set validate → accept/reject → persist continuity assertions.

The model proposes; the substrate decides. Raw prose never becomes state.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from conditioned_kernel.continuity_events import (
    ALLOWED_RELATIONS,
    VALIDATOR_VERSION,
    build_event,
    candidate_hash,
    canonical_state_hash,
    materialize_state,
    relation_atom,
)
from conditioned_kernel.continuity_replay import replay_store
from conditioned_kernel.continuity_store import ContinuityStore
from conditioned_kernel.ids import make_id, utc_now_iso


class Decision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ContinuityAssertion:
    subject_id: str
    relation: str
    object_id: str

    def as_atom(self) -> dict[str, str]:
        return relation_atom(self.subject_id, self.relation, self.object_id)


@dataclass
class EpisodeAResult:
    decision: Decision
    reason_code: str
    reason_codes: tuple[str, ...]
    candidate_hash: str
    events: list[dict[str, Any]] = field(default_factory=list)
    receipt: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
    scientific_completion: bool = False
    assertions: list[ContinuityAssertion] = field(default_factory=list)


def _repo_commit() -> str | None:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%h"],
            capture_output=True,
            text=True,
            check=False,
        )
        return (r.stdout or "").strip() or None
    except Exception:
        return None


def parse_continuity_candidate(
    raw: str,
) -> tuple[list[ContinuityAssertion] | None, list[str], str]:
    """Parse raw candidate text.

    Returns (assertions_or_None, reason_codes, candidate_hash).
    PARSE_* vs SCHEMA_* are distinct.
    """
    ch = candidate_hash(raw)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, [f"PARSE_FAILED:{e.msg}"], ch
    except TypeError as e:
        return None, [f"PARSE_FAILED:{e}"], ch

    if not isinstance(obj, dict):
        return None, ["SCHEMA_FAILED:root_not_object"], ch

    # Unknown top-level keys are ignored for authority (only continuity_assertions matter)
    # but hidden authority fields inside assertions are rejected at validation.
    if "continuity_assertions" not in obj:
        return None, ["SCHEMA_FAILED:missing_continuity_assertions"], ch

    cas = obj["continuity_assertions"]
    if not isinstance(cas, list):
        return None, ["SCHEMA_FAILED:continuity_assertions_not_list"], ch
    if len(cas) == 0:
        return None, ["SCHEMA_FAILED:empty_continuity_assertions"], ch

    assertions: list[ContinuityAssertion] = []
    for i, item in enumerate(cas):
        if not isinstance(item, dict):
            return None, [f"SCHEMA_FAILED:assertion_{i}_not_object"], ch
        unknown = set(item.keys()) - {"subject_id", "relation", "object_id"}
        if unknown:
            return None, [f"SCHEMA_FAILED:unknown_fields:{sorted(unknown)}"], ch
        for key in ("subject_id", "relation", "object_id"):
            if key not in item:
                return None, [f"SCHEMA_FAILED:missing_{key}"], ch
            if not isinstance(item[key], str) or not item[key].strip():
                return None, [f"SCHEMA_FAILED:{key}_not_nonempty_string"], ch
        assertions.append(
            ContinuityAssertion(
                subject_id=item["subject_id"].strip(),
                relation=item["relation"].strip(),
                object_id=item["object_id"].strip(),
            )
        )
    return assertions, [], ch


def validate_assertions(
    assertions: Sequence[ContinuityAssertion],
    universe: Mapping[str, Any],
    *,
    existing_atoms: Sequence[Mapping[str, str]] | None = None,
) -> list[str]:
    """Return reason codes; empty list means valid."""
    codes: list[str] = []
    subjects = set(universe.get("subject_ids") or [])
    objects = set(universe.get("object_ids") or [])
    rels = set(universe.get("relations") or []) & ALLOWED_RELATIONS
    if not rels:
        # Universe may list relations; if empty, fall back to global allowlist
        rels = set(ALLOWED_RELATIONS)
    combos = {
        (str(a), str(b), str(c))
        for a, b, c in (universe.get("valid_combinations") or [])
    }
    forbidden = {
        (
            str(f.get("subject_id")),
            str(f.get("relation")),
            str(f.get("object_id")),
        )
        for f in (universe.get("forbidden_assertions") or [])
        if isinstance(f, Mapping)
    }
    existing = {
        (str(a["subject_id"]), str(a["relation"]), str(a["object_id"]))
        for a in (existing_atoms or [])
    }

    for a in assertions:
        if a.subject_id not in subjects:
            codes.append(f"UNKNOWN_SUBJECT:{a.subject_id}")
            continue
        if a.object_id not in objects:
            codes.append(f"UNKNOWN_OBJECT:{a.object_id}")
            continue
        if a.relation not in ALLOWED_RELATIONS or a.relation not in rels:
            codes.append(f"UNKNOWN_RELATION:{a.relation}")
            continue
        triple = (a.subject_id, a.relation, a.object_id)
        if combos and triple not in combos:
            codes.append(
                f"INVALID_COMBINATION:{a.subject_id}/{a.relation}/{a.object_id}"
            )
            continue
        if triple in forbidden:
            codes.append(
                f"CONTRADICTION:{a.subject_id}/{a.relation}/{a.object_id}"
            )
            continue
        if triple in existing:
            codes.append(
                f"DUPLICATE_ASSERTION:{a.subject_id}/{a.relation}/{a.object_id}"
            )
            continue
    return codes


def process_episode_a_candidate(
    raw: str,
    *,
    store: ContinuityStore,
    episode_id: str,
    dry_run: bool = False,
    dry_store_root: Path | str | None = None,
    provenance: Mapping[str, Any] | None = None,
    repo_commit: str | None = None,
) -> EpisodeAResult:
    """Full Episode A gate for one candidate string.

    dry_run=True writes only to an isolated temporary store and never marks
    scientific completion.
    """
    active = store
    if dry_run:
        if dry_store_root is None:
            raise ValueError("dry_run requires dry_store_root")
        active = ContinuityStore.create(
            dry_store_root,
            genesis=store.load_genesis(),
            universe=store.load_universe(),
        )

    assertions, parse_codes, ch = parse_continuity_candidate(raw)
    if assertions is None:
        receipt = _reject_receipt(
            ch, parse_codes, episode_id, dry_run=dry_run, provenance=provenance
        )
        active.append_rejection_receipt(receipt)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=parse_codes[0],
            reason_codes=tuple(parse_codes),
            candidate_hash=ch,
            receipt=receipt,
            dry_run=dry_run,
            scientific_completion=False,
        )

    # Existing accepted atoms from durable store (or dry store after prior accepts)
    existing_state = materialize_state(active.load_genesis(), active.list_events())
    existing_atoms = existing_state.get("accepted_relations") or []
    v_codes = validate_assertions(
        assertions,
        active.load_universe(),
        existing_atoms=existing_atoms,
    )
    if v_codes:
        receipt = _reject_receipt(
            ch, v_codes, episode_id, dry_run=dry_run, provenance=provenance
        )
        active.append_rejection_receipt(receipt)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=v_codes[0],
            reason_codes=tuple(v_codes),
            candidate_hash=ch,
            receipt=receipt,
            dry_run=dry_run,
            scientific_completion=False,
            assertions=list(assertions),
        )

    # Accept: one event per assertion in candidate (typically one)
    commit = repo_commit if repo_commit is not None else _repo_commit()
    ts = utc_now_iso()
    events_out: list[dict[str, Any]] = []
    parent = active.current_state_hash()
    applied_so_far = list(active.list_events())

    for a in assertions:
        seq = active.next_sequence()
        event_id = make_id("cevt")
        prospective = applied_so_far + [
            {
                "subject_id": a.subject_id,
                "relation": a.relation,
                "object_id": a.object_id,
            }
        ]
        resulting = canonical_state_hash(active.load_genesis(), prospective)
        event = build_event(
            event_id=event_id,
            sequence=seq,
            parent_state_hash=parent,
            resulting_state_hash=resulting,
            episode_id=episode_id,
            subject_id=a.subject_id,
            relation=a.relation,
            object_id=a.object_id,
            source_candidate_hash=ch,
            acceptance_reason_code="ACCEPTED",
            timestamp=ts,
            repo_commit=commit,
            provenance=provenance or {},
        )
        receipt = {
            "receipt_id": make_id("crec"),
            "decision": Decision.ACCEPTED.value,
            "reason_code": "ACCEPTED",
            "reason_codes": ["ACCEPTED"],
            "source_candidate_hash": ch,
            "event_id": event_id,
            "episode_id": episode_id,
            "validator_version": VALIDATOR_VERSION,
            "timestamp": ts,
            "dry_run": dry_run,
            "scientific_completion": False if dry_run else True,
            "provenance": dict(provenance or {}),
        }
        active.append_event_and_receipt(event, receipt)
        events_out.append(event)
        applied_so_far = prospective
        parent = resulting

    # Primary scientific_completion for Episode A persistence is true only when
    # not dry and at least one event was committed. M0 headline remains NO-GO
    # at the experiment layer (policy elsewhere).
    return EpisodeAResult(
        decision=Decision.ACCEPTED,
        reason_code="ACCEPTED",
        reason_codes=("ACCEPTED",),
        candidate_hash=ch,
        events=events_out,
        receipt={
            "decision": Decision.ACCEPTED.value,
            "reason_code": "ACCEPTED",
            "source_candidate_hash": ch,
            "event_ids": [e["event_id"] for e in events_out],
            "dry_run": dry_run,
            "scientific_completion": (not dry_run) and bool(events_out),
        },
        dry_run=dry_run,
        scientific_completion=(not dry_run) and bool(events_out),
        assertions=list(assertions),
    )


def _reject_receipt(
    ch: str,
    codes: Sequence[str],
    episode_id: str,
    *,
    dry_run: bool,
    provenance: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "receipt_id": make_id("crec"),
        "decision": Decision.REJECTED.value,
        "reason_code": codes[0] if codes else "REJECTED",
        "reason_codes": list(codes),
        "source_candidate_hash": ch,
        "episode_id": episode_id,
        "validator_version": VALIDATOR_VERSION,
        "timestamp": utc_now_iso(),
        "dry_run": dry_run,
        "scientific_completion": False,
        "provenance": dict(provenance or {}),
    }


def episode_b_packet_relations(store: ContinuityStore) -> list[dict[str, str]]:
    """Relations for Episode B packet compilation from reconstructed state only."""
    st = replay_store(store)
    return list(st.state.get("accepted_relations") or [])
