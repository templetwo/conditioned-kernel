"""Live Episode A → fresh Episode B continuity plumbing (RUN 00.6C).

Uses the verified candidate-atomic gate and store. Scientific completion
is never claimed by this module (plumbing only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from conditioned_kernel.continuity_events import (
    ALLOWED_RELATIONS,
    canonical_json_bytes,
    sha256_hex,
)
from conditioned_kernel.continuity_gate import (
    EpisodeAResult,
    episode_b_packet_relations,
    process_episode_a_candidate,
)
from conditioned_kernel.continuity_replay import ReplayError, replay_store
from conditioned_kernel.continuity_store import ContinuityStore
from conditioned_kernel.generate import InferenceResult, OllamaClient, RunStatus

# Ollama format= schema for continuity_assertions only.
CONTINUITY_ASSERTIONS_FORMAT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "continuity_assertions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_id": {"type": "string"},
                    "relation": {"type": "string"},
                    "object_id": {"type": "string"},
                },
                "required": ["subject_id", "relation", "object_id"],
            },
        }
    },
    "required": ["continuity_assertions"],
}

LIVE_PLUMBING_POLICY: dict[str, Any] = {
    "scientific_status": "live_plumbing_only",
    "headline_eligible": False,
    "headline_ineligible_reason": "controls_and_scoring_not_yet_ratified",
}


def live_plumbing_headline_policy() -> dict[str, Any]:
    return dict(LIVE_PLUMBING_POLICY)


def universe_from_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """Closed-set universe: prefer explicit task.continuity_universe."""
    explicit = task.get("continuity_universe")
    if isinstance(explicit, dict) and explicit.get("subject_ids"):
        rels = list(explicit.get("relations") or sorted(ALLOWED_RELATIONS))
        return {
            "subject_ids": list(explicit["subject_ids"]),
            "object_ids": list(explicit.get("object_ids") or []),
            "relations": [r for r in rels if r in ALLOWED_RELATIONS],
            "valid_combinations": [
                tuple(c) if not isinstance(c, tuple) else c
                for c in (explicit.get("valid_combinations") or [])
            ],
            "forbidden_assertions": list(explicit.get("forbidden_assertions") or []),
        }
    # Derive a minimal closed set from seed threads/facts (no gold triple).
    seed = (task.get("episode_a") or {}).get("seed_state") or {}
    threads = seed.get("threads") or []
    facts = seed.get("facts") or []
    subjects = [str(t.get("id")) for t in threads if isinstance(t, dict) and t.get("id")]
    objects = [f"obj_{i}" for i in range(len(facts))]
    if not objects:
        objects = ["obj_0"]
    if not subjects:
        subjects = ["subject_0"]
    combos = [
        (subjects[0], "remains_open", objects[0]),
        (subjects[0], "references", objects[0]),
    ]
    return {
        "subject_ids": subjects,
        "object_ids": objects,
        "relations": ["remains_open", "references", "depends_on"],
        "valid_combinations": combos,
        "forbidden_assertions": [],
    }


def genesis_from_task(task: Mapping[str, Any]) -> dict[str, Any]:
    seed = (task.get("episode_a") or {}).get("seed_state") or {}
    return {
        "schema_version": "ck.genesis.v1",
        "task_id": str(task.get("id") or "task"),
        "goal": str(seed.get("goal") or ""),
        "seed_facts": list(seed.get("facts") or []),
        "seed_threads": list(seed.get("threads") or []),
        "seed_relations": [],
    }


def compile_episode_a_packet(
    task: Mapping[str, Any],
    universe: Mapping[str, Any],
) -> dict[str, Any]:
    """Bounded Episode A packet — no gold assertion, no archive dump."""
    seed = (task.get("episode_a") or {}).get("seed_state") or {}
    objective = str(
        (task.get("episode_a") or {}).get("objective")
        or (task.get("episode_a") or {}).get("prompt")
        or "Select a valid closed-set continuity relation."
    )
    # Facts required to choose — not the answer key.
    facts = list(seed.get("facts") or [])
    packet = {
        "packet_kind": "episode_a_continuity",
        "objective": objective,
        "subject_ids": list(universe["subject_ids"]),
        "object_ids": list(universe["object_ids"]),
        "allowed_relations": list(universe["relations"]),
        "task_facts": facts,
        "output_schema": {
            "type": "object",
            "required": ["continuity_assertions"],
            "properties": {
                "continuity_assertions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["subject_id", "relation", "object_id"],
                        "properties": {
                            "subject_id": {"type": "string"},
                            "relation": {"type": "string"},
                            "object_id": {"type": "string"},
                        },
                    },
                }
            },
        },
        "instructions": (
            "Return ONLY valid JSON with key continuity_assertions. "
            "Use only subject_ids, object_ids, and allowed_relations from this packet. "
            "Do not invent identifiers. Do not include free-form answer prose as authority. "
            "If you cannot form a valid closed-set assertion, return "
            '{"continuity_assertions":[]} which will be rejected as incomplete.'
        ),
    }
    return packet


def packet_hash(packet: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(dict(packet)))


def build_episode_a_model_input(
    packet: Mapping[str, Any],
    *,
    model: str,
    num_ctx: int = 2048,
    temperature: float = 0.3,
    seed: int = 42,
) -> dict[str, Any]:
    serialized = json.dumps(packet, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    system = (
        "Local conditioned-kernel continuity aperture. "
        "Return ONLY JSON with continuity_assertions. "
        "Use only closed-set identifiers from the packet. No tools, cloud, or free-form memory."
    )
    return {
        "schema_version": "ck.v0",
        "mode": "chat_json",
        "model": model,
        "payload": {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": "Packet:\n" + serialized},
            ],
            "format": CONTINUITY_ASSERTIONS_FORMAT,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_ctx": num_ctx,
            },
        },
        "packet_hash": packet_hash(packet),
    }


def compile_episode_b_packet(
    task: Mapping[str, Any],
    store: ContinuityStore,
) -> dict[str, Any]:
    """Compile Episode B only from verified replay + frozen task facts."""
    st = replay_store(store)
    relations = episode_b_packet_relations(store)
    seed = (task.get("episode_b") or {})
    genesis = store.load_genesis()
    packet = {
        "packet_kind": "episode_b_continuity",
        "task_id": genesis.get("task_id"),
        "goal": genesis.get("goal"),
        "seed_facts": list(genesis.get("seed_facts") or []),
        "accepted_relations": relations,
        "state_hash": st.state_hash,
        "prompt": str(seed.get("prompt") or "Resume from reconstructed continuity state."),
        "instructions": (
            "Continuity state was reconstructed by verified event replay. "
            "Use accepted_relations and seed_facts only. Return JSON if required by the task."
        ),
    }
    return packet


@dataclass
class LiveEpisodeAResult:
    inference: dict[str, Any] | None
    inference_status: str
    final_response: str | None
    gate: EpisodeAResult | None
    packet: dict[str, Any]
    packet_hash: str
    store_path: str
    events_n: int
    rejection_receipts_n: int
    gate_invocations: int = 1
    error: str | None = None
    dry_run: bool = False
    scientific_completion: bool = False  # always false for live plumbing


@dataclass
class LiveEpisodeBResult:
    replay_ok: bool
    state_hash: str | None
    packet: dict[str, Any] | None
    packet_hash: str | None
    relation_count: int
    accepted_relations: list[dict[str, str]]
    inference: dict[str, Any] | None = None
    inference_status: str | None = None
    error: str | None = None
    dry_run: bool = False
    scientific_completion: bool = False
    used_episode_a_memory: bool = False  # must remain false


def run_episode_a_live(
    task: Mapping[str, Any],
    *,
    store_root: Path | str,
    model: str,
    timeout_s: float = 90.0,
    num_ctx: int = 2048,
    dry: bool = False,
    dry_candidate_text: str | None = None,
    inject_inference: InferenceResult | None = None,
    client: OllamaClient | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> LiveEpisodeAResult:
    """Episode A: compile → typed inference → gate once → persist.

    inject_inference / dry_candidate_text allow offline tests without Ollama.
    """
    store_path = Path(store_root)
    universe = universe_from_task(task)
    genesis = genesis_from_task(task)
    if store_path.exists() and (store_path / "genesis.json").exists():
        store = ContinuityStore.open(store_path)
    else:
        store = ContinuityStore.create(store_path, genesis=genesis, universe=universe)

    packet = compile_episode_a_packet(task, universe)
    ph = packet_hash(packet)
    gate_invocations = 0

    if dry and dry_candidate_text is None:
        # Pure dry: no inference, no gate accept of model output
        return LiveEpisodeAResult(
            inference=None,
            inference_status="dry_run_only",
            final_response=None,
            gate=None,
            packet=packet,
            packet_hash=ph,
            store_path=str(store.root),
            events_n=len(store.list_events()),
            rejection_receipts_n=len(store.rejection_receipts()),
            gate_invocations=0,
            dry_run=True,
            scientific_completion=False,
        )

    inference: InferenceResult | None = inject_inference
    if inference is None and dry_candidate_text is not None:
        inference = InferenceResult(
            status=RunStatus.COMPLETED,
            output=dry_candidate_text,
            error=None,
            elapsed_seconds=0.0,
            timeout_seconds=float(timeout_s),
            thinking_chars=0,
            final_response_chars=len(dry_candidate_text),
        )
    if inference is None:
        mi = build_episode_a_model_input(
            packet, model=model, num_ctx=num_ctx
        )
        ollama = client or OllamaClient(timeout=timeout_s)
        inference = ollama.run(mi)

    # Operational failures: no gate on missing final
    if inference.status is not RunStatus.COMPLETED or inference.output is None:
        return LiveEpisodeAResult(
            inference=inference.to_dict(),
            inference_status=inference.status.value,
            final_response=None,
            gate=None,
            packet=packet,
            packet_hash=ph,
            store_path=str(store.root),
            events_n=len(store.list_events()),
            rejection_receipts_n=len(store.rejection_receipts()),
            gate_invocations=0,
            error=inference.error or inference.status.value,
            dry_run=dry,
            scientific_completion=False,
        )

    final = inference.output  # may be ""
    gate_invocations = 1
    gate = process_episode_a_candidate(
        final,
        store=store,
        episode_id="episode_a",
        dry_run=False,  # write to the live store path (tests use temp dirs)
        provenance={
            **dict(provenance or {}),
            "model": model,
            "packet_hash": ph,
            "live_plumbing": True,
        },
    )
    # Plumbing never claims scientific completion at the experiment layer.
    if gate.scientific_completion:
        # Force incomplete for live plumbing policy (gate may mark lifecycle ok).
        gate = EpisodeAResult(
            decision=gate.decision,
            reason_code=gate.reason_code,
            reason_codes=gate.reason_codes,
            candidate_hash=gate.candidate_hash,
            events=gate.events,
            receipt={**gate.receipt, "scientific_completion": False, "live_plumbing": True},
            dry_run=gate.dry_run,
            scientific_completion=False,
            assertions=gate.assertions,
        )

    return LiveEpisodeAResult(
        inference=inference.to_dict(),
        inference_status=inference.status.value,
        final_response=final,
        gate=gate,
        packet=packet,
        packet_hash=ph,
        store_path=str(store.root),
        events_n=len(store.list_events()),
        rejection_receipts_n=len(store.rejection_receipts()),
        gate_invocations=gate_invocations,
        dry_run=dry,
        scientific_completion=False,
    )


def run_episode_b_live(
    task: Mapping[str, Any],
    *,
    store_root: Path | str,
    model: str | None = None,
    timeout_s: float = 90.0,
    num_ctx: int = 2048,
    dry: bool = False,
    invoke_model: bool = False,
    client: OllamaClient | None = None,
    inject_inference: InferenceResult | None = None,
) -> LiveEpisodeBResult:
    """Episode B: fresh load of store only — no Episode A objects."""
    store = ContinuityStore.open(store_root)
    try:
        st = replay_store(store)
    except ReplayError as e:
        return LiveEpisodeBResult(
            replay_ok=False,
            state_hash=None,
            packet=None,
            packet_hash=None,
            relation_count=0,
            accepted_relations=[],
            error=f"REPLAY_FAILED:{e}",
            dry_run=dry,
            scientific_completion=False,
            used_episode_a_memory=False,
        )

    packet = compile_episode_b_packet(task, store)
    ph = packet_hash(packet)
    relations = list(packet.get("accepted_relations") or [])

    result = LiveEpisodeBResult(
        replay_ok=True,
        state_hash=st.state_hash,
        packet=packet,
        packet_hash=ph,
        relation_count=len(relations),
        accepted_relations=relations,
        dry_run=dry,
        scientific_completion=False,
        used_episode_a_memory=False,
    )

    if dry or not invoke_model:
        result.inference_status = "dry_run_only" if dry else "not_invoked"
        return result

    inference = inject_inference
    if inference is None:
        # Minimal model invoke for authorized smoke only
        serialized = json.dumps(packet, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        mi = {
            "schema_version": "ck.v0",
            "mode": "chat_json",
            "model": model or "unknown",
            "payload": {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Local continuity resume. Answer briefly from accepted_relations "
                            "and seed_facts only. JSON optional."
                        ),
                    },
                    {"role": "user", "content": "Packet:\n" + serialized},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "seed": 42, "num_ctx": num_ctx},
            },
        }
        ollama = client or OllamaClient(timeout=timeout_s)
        inference = ollama.run(mi)

    result.inference = inference.to_dict()
    result.inference_status = inference.status.value
    return result


def valid_plumbing_candidate(universe: Mapping[str, Any]) -> str:
    """Build a known-valid candidate for offline tests from the first valid combo."""
    combos = list(universe.get("valid_combinations") or [])
    if not combos:
        raise ValueError("universe has no valid_combinations")
    s, r, o = combos[0]
    return json.dumps(
        {
            "continuity_assertions": [
                {"subject_id": s, "relation": r, "object_id": o}
            ]
        },
        separators=(",", ":"),
    )
