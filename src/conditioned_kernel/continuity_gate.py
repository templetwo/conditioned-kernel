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


class ExecutionScope(str, Enum):
    """Closed execution-scope vocabulary (RUN 00.6C.1).

    Scientific completion is never inferred from ACCEPTED alone; it is a
    function of scope (and only scientific_experiment may be true).
    """

    OFFLINE_TEST = "offline_test"
    DRY_RUN = "dry_run"
    LIVE_PLUMBING = "live_plumbing"
    SCIENTIFIC_EXPERIMENT = "scientific_experiment"


def parse_execution_scope(value: ExecutionScope | str) -> ExecutionScope:
    if isinstance(value, ExecutionScope):
        return value
    try:
        return ExecutionScope(str(value))
    except ValueError as e:
        raise ValueError(f"unknown execution_scope: {value!r}") from e


def scientific_completion_for(
    scope: ExecutionScope, *, accepted: bool
) -> bool:
    """Only scientific_experiment + ACCEPTED may claim scientific completion."""
    return accepted and scope is ExecutionScope.SCIENTIFIC_EXPERIMENT


def verify_event_receipt_pair(
    event: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    """Fail closed if event and terminal receipt contradict each other."""
    pairs = (
        ("source_candidate_hash", "source_candidate_hash"),
        ("event_id", "event_id"),
        ("execution_scope", "execution_scope"),
        ("parent_state_hash", "parent_state_hash"),
        ("resulting_state_hash", "resulting_state_hash"),
        ("episode_id", "episode_id"),
    )
    for ek, rk in pairs:
        if ek not in event and rk not in receipt:
            continue
        if event.get(ek) != receipt.get(rk):
            raise ValueError(
                f"event/receipt mismatch on {ek}: "
                f"event={event.get(ek)!r} receipt={receipt.get(rk)!r}"
            )
    # Live plumbing / dry / offline may never claim scientific completion.
    scope = str(receipt.get("execution_scope") or event.get("execution_scope") or "")
    if scope in {
        ExecutionScope.LIVE_PLUMBING.value,
        ExecutionScope.DRY_RUN.value,
        ExecutionScope.OFFLINE_TEST.value,
    }:
        if receipt.get("scientific_completion") is True:
            raise ValueError(
                f"scientific_completion cannot be true for execution_scope={scope}"
            )
    if receipt.get("decision") == Decision.ACCEPTED.value:
        if not receipt.get("event_id"):
            raise ValueError("accepted receipt requires event_id")
        if event.get("event_id") != receipt.get("event_id"):
            raise ValueError("accepted event_id mismatch")


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
    execution_scope: ExecutionScope | str = ExecutionScope.OFFLINE_TEST,
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

    Durable receipt truth (00.6C.1):
    - execution_scope is resolved before any write
    - scientific_completion is derived from scope, never from ACCEPTED alone
    - returned receipt is the same object that was persisted
    """
    scope = parse_execution_scope(execution_scope)
    if dry_run:
        # Dry path may only use dry_run (or offline_test callers that set dry_run).
        if scope is ExecutionScope.SCIENTIFIC_EXPERIMENT:
            raise ValueError("scientific_experiment cannot use dry_run storage")
        if scope is ExecutionScope.LIVE_PLUMBING:
            # Allow dry live-plumbing tests only if explicitly dry_run scope.
            pass
        if scope not in (ExecutionScope.DRY_RUN, ExecutionScope.OFFLINE_TEST, ExecutionScope.LIVE_PLUMBING):
            raise ValueError(f"dry_run incompatible with execution_scope={scope.value}")
        if scope is not ExecutionScope.DRY_RUN and dry_run:
            # Canonical dry persistence scope.
            scope = ExecutionScope.DRY_RUN

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
            execution_scope=scope,
        )
        active.append_terminal_receipt(receipt)
        disk = _load_persisted_receipt(active, event_id=None, candidate_hash=ch)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=parse_codes[0],
            reason_codes=tuple(parse_codes),
            candidate_hash=ch,
            receipt=disk,
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
            execution_scope=scope,
            duplicate_triple=dup_triple,
        )
        active.append_terminal_receipt(receipt)
        disk = _load_persisted_receipt(active, event_id=None, candidate_hash=ch)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=dup_codes[0],
            reason_codes=tuple(dup_codes),
            candidate_hash=ch,
            receipt=disk,
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
            execution_scope=scope,
        )
        active.append_terminal_receipt(receipt)
        disk = _load_persisted_receipt(active, event_id=None, candidate_hash=ch)
        return EpisodeAResult(
            decision=Decision.REJECTED,
            reason_code=v_codes[0],
            reason_codes=tuple(v_codes),
            candidate_hash=ch,
            receipt=disk,
            dry_run=dry_run,
            scientific_completion=False,
            assertions=list(assertions),
        )

    # B — One event per accepted candidate (canonical ordered batch)
    sci = scientific_completion_for(scope, accepted=True)
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
        execution_scope=scope.value,
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
        "execution_scope": scope.value,
        "scientific_completion": sci,
        "provenance": dict(provenance or {}),
    }
    # Consistency before durable write
    verify_event_receipt_pair(event, receipt)
    active.append_event_and_receipt(event, receipt)
    # Re-read from disk as audit-of-record and return that object.
    disk_receipt = _load_persisted_receipt(active, event_id=event_id, candidate_hash=ch)
    verify_event_receipt_pair(event, disk_receipt)

    return EpisodeAResult(
        decision=Decision.ACCEPTED,
        reason_code="ACCEPTED",
        reason_codes=("ACCEPTED",),
        candidate_hash=ch,
        events=[event],
        receipt=disk_receipt,
        dry_run=dry_run,
        scientific_completion=bool(disk_receipt.get("scientific_completion")),
        assertions=list(assertions),
    )


def _load_persisted_receipt(
    store: ContinuityStore,
    *,
    event_id: str | None,
    candidate_hash: str,
) -> dict[str, Any]:
    """Load the terminal receipt that was just written for this candidate."""
    for rec in store.terminal_receipts():
        if rec.get("source_candidate_hash") == candidate_hash:
            if event_id is None or rec.get("event_id") == event_id:
                return rec
    # Fallback: read event-id named file
    if event_id:
        path = store.receipts_dir / f"{event_id}.json"
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        f"persisted receipt not found for candidate {candidate_hash[:12]}…"
    )


def _reject_receipt(
    ch: str,
    codes: Sequence[str],
    episode_id: str,
    *,
    dry_run: bool,
    provenance: Mapping[str, Any] | None,
    state_hash: str,
    execution_scope: ExecutionScope,
    duplicate_triple: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    sci = scientific_completion_for(execution_scope, accepted=False)
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
        "execution_scope": execution_scope.value,
        "scientific_completion": sci,
        "provenance": dict(provenance or {}),
    }
    if duplicate_triple is not None:
        rec["duplicate_triple"] = dict(duplicate_triple)
    return rec


def episode_b_packet_relations(store: ContinuityStore) -> list[dict[str, str]]:
    """Relations for Episode B packet compilation from reconstructed state only."""
    st = replay_store(store)
    return list(st.state.get("accepted_relations") or [])
