"""Parse → closed-set validate → accept/reject → persist continuity assertions.

The candidate is the atomic acceptance and audit unit (RUN 00.6B.1).
One accepted candidate → one event + one terminal receipt.
One rejected candidate → zero events + one terminal receipt.
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
    RECEIPT_SCHEMA_VERSION,
    VALIDATOR_VERSION,
    build_event,
    candidate_hash,
    canonical_state_hash,
    materialize_state,
    normalize_relations,
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

    def as_triple(self) -> tuple[str, str, str]:
        return (self.subject_id, self.relation, self.object_id)


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


def detect_intra_candidate_duplicates(
    assertions: Sequence[ContinuityAssertion],
) -> tuple[list[str], dict[str, str] | None]:
    """Detect duplicate canonical triples within one candidate.

    Does not silently dedupe — returns DUPLICATE_ASSERTION reason codes and the
    first duplicated triple for diagnostics.
    """
    seen: set[tuple[str, str, str]] = set()
    for a in assertions:
        t = a.as_triple()
        if t in seen:
            atom = a.as_atom()
            return (
                [f"DUPLICATE_ASSERTION:{a.subject_id}/{a.relation}/{a.object_id}"],
                atom,
            )
        seen.add(t)
    return [], None


def validate_assertions(
    assertions: Sequence[ContinuityAssertion],
    universe: Mapping[str, Any],
    *,
    existing_atoms: Sequence[Mapping[str, str]] | None = None,
) -> list[str]:
    """Return reason codes; empty list means valid.

    Collects all failures for the candidate (all-or-nothing). Does not check
    intra-candidate duplicates — call detect_intra_candidate_duplicates first.
    """
    codes: list[str] = []
    subjects = set(universe.get("subject_ids") or [])
    objects = set(universe.get("object_ids") or [])
    rels = set(universe.get("relations") or []) & ALLOWED_RELATIONS
    if not rels:
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
        triple = a.as_triple()
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

    Candidate atomicity (00.6B.1):
    - ACCEPTED → exactly one continuity event + one terminal receipt
    - REJECTED → zero events + one terminal receipt
    - multi-assertion is all-or-nothing
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

    state_hash_before = active.current_state_hash()
    assertions, parse_codes, ch = parse_continuity_candidate(raw)
    if assertions is None:
        receipt = _reject_receipt(
            ch,
            parse_codes,
            episode_id,
            dry_run=dry_run,
            provenance=provenance,
            state_hash=state_hash_before,
        )
        active.append_terminal_receipt(receipt)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=parse_codes[0],
            reason_codes=tuple(parse_codes),
            candidate_hash=ch,
            receipt=receipt,
            dry_run=dry_run,
            scientific_completion=False,
        )

    # A — Intra-candidate duplicates (before durable-history validation)
    dup_codes, dup_triple = detect_intra_candidate_duplicates(assertions)
    if dup_codes:
        receipt = _reject_receipt(
            ch,
            dup_codes,
            episode_id,
            dry_run=dry_run,
            provenance=provenance,
            state_hash=state_hash_before,
            duplicate_triple=dup_triple,
        )
        active.append_terminal_receipt(receipt)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=dup_codes[0],
            reason_codes=tuple(dup_codes),
            candidate_hash=ch,
            receipt=receipt,
            dry_run=dry_run,
            scientific_completion=False,
            assertions=list(assertions),
        )

    existing_state = materialize_state(active.load_genesis(), active.list_events())
    existing_atoms = existing_state.get("accepted_relations") or []
    v_codes = validate_assertions(
        assertions,
        active.load_universe(),
        existing_atoms=existing_atoms,
    )
    if v_codes:
        # D — all-or-nothing: any failure rejects the complete candidate
        receipt = _reject_receipt(
            ch,
            v_codes,
            episode_id,
            dry_run=dry_run,
            provenance=provenance,
            state_hash=state_hash_before,
        )
        active.append_terminal_receipt(receipt)
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

    # B — One event per accepted candidate (canonical ordered batch)
    commit = repo_commit if repo_commit is not None else _repo_commit()
    ts = utc_now_iso()
    parent = state_hash_before
    ordered_atoms = normalize_relations([a.as_atom() for a in assertions])
    prospective_event = {"assertions": ordered_atoms}
    applied = list(active.list_events()) + [prospective_event]
    resulting = canonical_state_hash(active.load_genesis(), applied)

    seq = active.next_sequence()
    event_id = make_id("cevt")
    event = build_event(
        event_id=event_id,
        sequence=seq,
        parent_state_hash=parent,
        resulting_state_hash=resulting,
        episode_id=episode_id,
        assertions=ordered_atoms,
        source_candidate_hash=ch,
        acceptance_reason_code="ACCEPTED",
        timestamp=ts,
        repo_commit=commit,
        provenance=provenance or {},
    )
    receipt = {
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": make_id("crec"),
        "terminal": True,
        "decision": Decision.ACCEPTED.value,
        "reason_code": "ACCEPTED",
        "reason_codes": ["ACCEPTED"],
        "source_candidate_hash": ch,
        "event_id": event_id,
        "event_ids": [event_id],
        "accepted_assertion_count": len(ordered_atoms),
        "accepted_assertions": ordered_atoms,
        "parent_state_hash": parent,
        "resulting_state_hash": resulting,
        "episode_id": episode_id,
        "validator_version": VALIDATOR_VERSION,
        "timestamp": ts,
        "dry_run": dry_run,
        "scientific_completion": False if dry_run else True,
        "provenance": dict(provenance or {}),
    }
    active.append_event_and_receipt(event, receipt)

    return EpisodeAResult(
        decision=Decision.ACCEPTED,
        reason_code="ACCEPTED",
        reason_codes=("ACCEPTED",),
        candidate_hash=ch,
        events=[event],
        receipt=receipt,
        dry_run=dry_run,
        scientific_completion=(not dry_run),
        assertions=list(assertions),
    )


def _reject_receipt(
    ch: str,
    codes: Sequence[str],
    episode_id: str,
    *,
    dry_run: bool,
    provenance: Mapping[str, Any] | None,
    state_hash: str,
    duplicate_triple: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": make_id("crec"),
        "terminal": True,
        "decision": Decision.REJECTED.value,
        "reason_code": codes[0] if codes else "REJECTED",
        "reason_codes": list(codes),
        "source_candidate_hash": ch,
        "event_id": None,
        "event_ids": [],
        "accepted_assertion_count": 0,
        "accepted_assertions": [],
        "parent_state_hash": state_hash,
        "resulting_state_hash": state_hash,
        "episode_id": episode_id,
        "validator_version": VALIDATOR_VERSION,
        "timestamp": utc_now_iso(),
        "dry_run": dry_run,
        "scientific_completion": False,
        "provenance": dict(provenance or {}),
    }
    if duplicate_triple is not None:
        rec["duplicate_triple"] = dict(duplicate_triple)
    return rec


def episode_b_packet_relations(store: ContinuityStore) -> list[dict[str, str]]:
    """Relations for Episode B packet compilation from reconstructed state only."""
    st = replay_store(store)
    return list(st.state.get("accepted_relations") or [])
