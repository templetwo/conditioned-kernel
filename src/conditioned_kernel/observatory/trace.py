"""TurnTrace / StageTrace: an observability layer wrapped around one real
call to `pipeline.run_turn`. It reports what the code did; it never infers
model psychology and it never changes what the pipeline does.

Reconstruction technique (see the pipeline cartography this package was
built from, RUN 00.9A dashboard handoff):

`TurnResult` only exposes the FINAL pass's packet/candidate/receipt in full;
earlier (repaired-away) passes are summarized in `TurnResult.passes` without
their raw text or packet. Two facts make full per-pass reconstruction
possible without touching pipeline.py:

1. Every pass's candidate and receipt are appended to
   ``logs/candidates.jsonl`` / ``logs/receipts.jsonl`` unconditionally,
   whether that pass repaired, accepted, or was rejected (repair-continue
   passes log directly in the loop; the terminal pass logs via
   `accept_candidate`). Snapshotting each file's line count immediately
   before the single `run_turn` call and reading only the newly appended
   lines afterward recovers the real, byte-exact candidate/receipt for
   every pass.
2. `compile.compile_turn` (and the packet/model-input builders under it) are
   pure functions of `(state, user_input, repair_plan, profile, ...)`. State
   is not mutated mid-turn — only `accept_candidate`, called once at the very
   end, ever writes to `state/`. So loading one read-only `SubstrateState`
   snapshot immediately before the real `run_turn` call and re-driving
   `compile_turn` with the *real, logged* receipt/candidate of each earlier
   pass (never a re-guessed one) reproduces every earlier pass's packet and
   model input functionally — everything except the non-deterministic
   `packet_id` / `created_at`, which `build_model_input` strips from the
   model input anyway and which this module documents rather than hides.

The **final** pass never needs reconstruction: `TurnResult.packet` /
`.candidate` / `.receipt` are the real objects the pipeline used, and this
module rebuilds only the model input for that one pass — a pure, exact
replay of `build_model_input` over the real packet (see cartography item 1).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from conditioned_kernel.authoritative_state import resolve_obligation
from conditioned_kernel.compile import build_arrival_packet, build_model_input, compile_turn
from conditioned_kernel.edge import EdgeProfile, load_profile
from conditioned_kernel.generate import OllamaClient
from conditioned_kernel.ids import make_id, utc_now_iso
from conditioned_kernel.observatory import compute
from conditioned_kernel.paths import default_logs_dir, default_state_dir
from conditioned_kernel.pipeline import TurnResult, run_turn
from conditioned_kernel.return_path.repair import build_repair_plan
from conditioned_kernel.state import SubstrateState

Mode = str


@dataclasses.dataclass
class StageTrace:
    """One of the 12 pipeline stages (spec §6), status/flag computed by
    `compute.derive_stage_status` / `derive_stage_flag` — never asserted."""

    index: int
    name: str
    source_module: str
    source_function: str
    source_line: int
    status: str
    flag: bool = False
    started_at: str | None = None
    completed_at: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    raw_input: Any = None
    raw_output: Any = None
    bytes_in: int | None = None
    bytes_out: int | None = None
    notes: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class PassTrace:
    """Spec §12 Export-shape core fields: pass_index, packet_id,
    candidate_id, receipt_id, answer, evidence_used, thread_touch,
    violations, advisories, decision, word_count, telemetry. `raw_text`,
    `packet`, `model_input`, `authoritative_kind`, `authoritative_fallback`,
    `checks`, `citation_audit`, `evidence_pool`
    are additions this trace layer needs to drive the per-stage panels the
    spec describes; they extend the exported shape, they do not replace any
    of its fields. `checks` / `citation_audit` / `evidence_pool` are the
    acceptance-criterion-8 fields (spec §7 stage 09 point 1): every named
    check `validate_candidate` can produce, individually, plus the citation
    and evidence-pool detail already built for the markdown debug brief —
    see `compute.derive_checks` / `compute.citation_audit` /
    `compute.labeled_evidence_pool`."""

    pass_index: int
    packet_id: str | None
    candidate_id: str | None
    receipt_id: str | None
    answer: str
    evidence_used: list[str]
    thread_touch: list[str]
    violations: list[str]
    advisories: list[str]
    decision: str | None
    word_count: int
    telemetry: dict[str, Any] | None
    raw_text: str | None = None
    packet: dict[str, Any] = dataclasses.field(default_factory=dict)
    model_input: dict[str, Any] = dataclasses.field(default_factory=dict)
    authoritative_kind: str | None = None
    authoritative_fallback: bool = False
    checks: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    citation_audit: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    evidence_pool: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class TurnTrace:
    """Spec §12 Export shape: turn_id, session_id, started_at, completed_at,
    user_input, runtime_config, stages[], context_share_bytes[], packet,
    packet_bytes, passes[], final_decision, persistence, observations[],
    operator. `error` and `notes` are additions (turn-level error string and
    honesty-contract disclosures about this trace's own reconstruction —
    never hidden from the object that carries the numbers)."""

    turn_id: str
    session_id: str
    started_at: str
    completed_at: str
    user_input: str
    runtime_config: dict[str, Any]
    stages: list[StageTrace]
    context_share_bytes: list[dict[str, Any]]
    packet: dict[str, Any]
    packet_bytes: int | None
    passes: list[PassTrace]
    final_decision: dict[str, Any]
    persistence: dict[str, Any]
    observations: list[dict[str, str]]
    operator: dict[str, Any]
    error: str | None = None
    notes: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------------------
# Log-line reconstruction helpers
# ---------------------------------------------------------------------------


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def _read_new_jsonl(path: Path, start_line: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < start_line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _patch_authoritative_fields(packet: dict[str, Any], receipt: dict[str, Any] | None) -> dict[str, Any]:
    """Fix the accept/reject packet asymmetry: on a rejected turn,
    `TurnResult.packet` is captured *before* pipeline.py's
    authoritative_enforced/fallback/reasons mutation, even though
    `accept_candidate` logged the mutated version. `receipt` carries these
    three fields unconditionally (set once per pass regardless of decision),
    so it is the reliable source either way."""
    if not receipt:
        return packet
    if receipt.get("authoritative_kind") is None and "authoritative_fallback" not in receipt:
        return packet
    out = dict(packet)
    out["authoritative_enforced"] = True
    out["authoritative_fallback"] = bool(receipt.get("authoritative_fallback"))
    out["authoritative_reasons"] = list(receipt.get("authoritative_reasons") or [])
    return out


# ---------------------------------------------------------------------------
# Traced turn runner
# ---------------------------------------------------------------------------


def run_traced_turn(
    user_input: str,
    *,
    turn_id: str | None = None,
    model: str | None = None,
    mode: Mode | None = None,
    state_dir: Path | None = None,
    logs_dir: Path | None = None,
    base_url: str = "http://127.0.0.1:11434",
    max_repair: int | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    profile: EdgeProfile | None = None,
    profile_id: str | None = None,
    client: OllamaClient | None = None,
    dry_candidate_text: str | None = None,
    acceptance_mode: str = "companion",
) -> TurnTrace:
    """Drive the existing pipeline path exactly once and assemble a full
    TurnTrace around it. `pipeline.run_turn` is called with the same
    keyword shape `cli.py` uses for `ck ask` / `ck chat` — this function
    never reimplements the turn, it observes one real run of it.

    Everything before and after the single `run_turn(...)` call below is
    read-only: a pre-turn state snapshot for shadow packet reconstruction,
    and post-turn reads of the log files `run_turn` itself already wrote.
    Nothing here is written back into `state/`.
    """
    prof = profile or load_profile(profile_id)
    state_root = Path(state_dir) if state_dir else default_state_dir()
    logs_root = Path(logs_dir) if logs_dir else default_logs_dir()

    use_model = model or prof.model
    use_mode: Mode = mode or prof.mode
    if use_mode not in ("chat_json", "generate_raw"):
        use_mode = "chat_json"
    resolved_temperature = prof.temperature if temperature is None else temperature
    resolved_seed = prof.seed if seed is None else seed
    resolved_num_ctx = prof.num_ctx if num_ctx is None else num_ctx
    resolved_keep_alive = prof.keep_alive if keep_alive is None else keep_alive
    resolved_think = bool(prof.think)

    # Read-only snapshot for shadow reconstruction only. State is not
    # mutated mid-turn (see module docstring), so this matches what the
    # real run_turn's own internal SubstrateState.load() sees a moment
    # later, barring a concurrent second turn against the same state dir.
    shadow_state = SubstrateState.load(state_dir=state_root, logs_dir=logs_root)
    session_id = str(shadow_state.current.get("session_id") or "sess_unknown")

    obligation = None
    if acceptance_mode == "companion":
        obligation = resolve_obligation(shadow_state, user_input, profile=prof, model=use_model)
    obligation_dict = obligation.to_dict() if obligation is not None else None

    candidates_path = logs_root / "candidates.jsonl"
    receipts_path = logs_root / "receipts.jsonl"
    cand_start = _line_count(candidates_path)
    rcpt_start = _line_count(receipts_path)

    resolved_turn_id = turn_id or make_id("turn")
    started_at = utc_now_iso()

    # ---- the one real call ----
    result: TurnResult = run_turn(
        user_input,
        model=model,
        mode=mode,
        state_dir=state_root,
        logs_dir=logs_root,
        base_url=base_url,
        max_repair=max_repair,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        keep_alive=keep_alive,
        profile=prof,
        profile_id=profile_id,
        client=client,
        dry_candidate_text=dry_candidate_text,
        acceptance_mode=acceptance_mode,
    )
    completed_at = utc_now_iso()

    notes: list[str] = []
    n_passes = len(result.passes)

    logged_candidates = _read_new_jsonl(candidates_path, cand_start)[:n_passes]
    logged_receipts = _read_new_jsonl(receipts_path, rcpt_start)[:n_passes]
    if len(logged_candidates) < n_passes or len(logged_receipts) < n_passes:
        notes.append(
            "logs/candidates.jsonl or logs/receipts.jsonl grew by fewer lines than this turn's "
            "pass count — another writer may be active against the same logs dir. Passes beyond "
            "what was logged fall back to TurnResult.passes summary data only."
        )

    def _logged(i: int, store: list[dict[str, Any]]) -> dict[str, Any]:
        return store[i] if i < len(store) else {}

    # ---- shadow-rebuild packets for every pass except the final one ----
    shadow_packets: list[dict[str, Any]] = []
    shadow_model_inputs: list[dict[str, Any]] = []
    repair_plan: dict[str, Any] | None = None
    for i in range(max(n_passes - 1, 0)):
        try:
            packet_i, model_input_i = compile_turn(
                shadow_state,
                user_input,
                model=use_model,
                mode=use_mode,
                repair_plan=repair_plan,
                temperature=temperature,
                seed=seed,
                num_ctx=num_ctx,
                keep_alive=keep_alive,
                profile=prof,
                acceptance_mode=acceptance_mode,
                authoritative_obligation=obligation_dict,
            )
        except Exception as e:  # noqa: BLE001 — shadow rebuild must never crash trace assembly
            notes.append(f"pass {i}: shadow packet reconstruction failed ({type(e).__name__}: {e})")
            packet_i, model_input_i = {}, {}
        shadow_packets.append(packet_i)
        shadow_model_inputs.append(model_input_i)
        rcpt_i = _logged(i, logged_receipts)
        cand_i = _logged(i, logged_candidates)
        repair_plan = build_repair_plan(rcpt_i, cand_i, packet_i)

    # ---- final pass: use the real packet the pipeline actually sent ----
    if result.packet:
        final_packet = _patch_authoritative_fields(dict(result.packet), result.receipt)
        final_model_input = build_model_input(
            final_packet,
            model=use_model,
            mode=use_mode,
            temperature=resolved_temperature,
            seed=resolved_seed,
            num_ctx=resolved_num_ctx,
            keep_alive=resolved_keep_alive,
            compact=True,
            think=resolved_think,
        )
    else:
        final_packet, final_model_input = {}, {}
        if result.error:
            notes.append(f"turn ended before a packet was produced: {result.error}")

    all_packets = shadow_packets + ([final_packet] if n_passes else [])
    all_model_inputs = shadow_model_inputs + ([final_model_input] if n_passes else [])
    if len(shadow_packets) > 0:
        notes.append(
            f"passes 0–{len(shadow_packets) - 1}: packet/model_input are reconstructed by "
            "re-driving compile.compile_turn against a pre-turn state snapshot and the real "
            "logged receipt/candidate of each prior pass — not the literal bytes sent, though "
            "content-identical except for the non-deterministic packet_id/created_at that "
            "build_model_input strips anyway."
        )

    # ---- assemble PassTrace list ----
    passes: list[PassTrace] = []
    for i in range(n_passes):
        result_pass = result.passes[i]
        cand = _logged(i, logged_candidates)
        rcpt = _logged(i, logged_receipts)
        next_state = cand.get("next_state") if isinstance(cand.get("next_state"), dict) else {}
        pass_packet = all_packets[i] if i < len(all_packets) else {}
        pass_evidence_used = list(cand.get("evidence_used") or [])
        passes.append(
            PassTrace(
                pass_index=i,
                packet_id=cand.get("packet_id"),
                candidate_id=cand.get("candidate_id") or result_pass.get("candidate_id"),
                receipt_id=rcpt.get("receipt_id"),
                answer=str(cand.get("answer") or ""),
                evidence_used=pass_evidence_used,
                thread_touch=list((next_state or {}).get("thread_touch") or []),
                violations=list(rcpt.get("violations") or result_pass.get("violations") or []),
                advisories=list(rcpt.get("advisories") or []),
                decision=rcpt.get("decision") or result_pass.get("decision"),
                word_count=int(rcpt.get("word_count") or 0),
                telemetry=result_pass.get("telemetry"),
                raw_text=cand.get("raw_text"),
                packet=pass_packet,
                model_input=all_model_inputs[i] if i < len(all_model_inputs) else {},
                authoritative_kind=result_pass.get("authoritative_kind"),
                authoritative_fallback=bool(result_pass.get("authoritative_fallback")),
                # Acceptance criterion 8 — every validate_candidate check
                # individually, plus the citation/evidence-pool detail the
                # markdown debug brief already builds (compute.citation_audit /
                # compute.labeled_evidence_pool), from this pass's own real
                # candidate/packet/receipt only.
                checks=compute.derive_checks(cand, pass_packet, rcpt),
                citation_audit=compute.citation_audit(pass_packet, pass_evidence_used),
                evidence_pool=compute.labeled_evidence_pool(pass_packet),
            )
        )

    final_pass = passes[-1] if passes else None

    # ---- context share (final pass) ----
    context_rows = (
        compute.context_share_bytes(final_packet, final_model_input) if final_packet else []
    )
    total_model_input_bytes = sum(r["bytes"] for r in context_rows)

    logged_bytes, recomputed_bytes, bytes_match = (
        compute.verify_packet_bytes(final_packet) if final_packet else (None, 0, True)
    )
    if not bytes_match:
        notes.append(
            f"packet_bytes mismatch: logged={logged_bytes} recomputed={recomputed_bytes} — "
            "the packet was mutated after edge.enforce_packet_budget ran."
        )
    packet_bytes = logged_bytes if logged_bytes is not None else recomputed_bytes

    # ---- budget diff (final pass, dropped facts) ----
    dropped_facts: list[str] = []
    if final_packet:
        try:
            pre_budget_packet = build_arrival_packet(
                shadow_state,
                user_input,
                repair_plan=repair_plan,
                profile=prof,
                enforce_budget=False,
                acceptance_mode=acceptance_mode,
                authoritative_obligation=obligation_dict,
            )
            pre_facts = list(pre_budget_packet.get("facts") or [])
            post_facts = list(final_packet.get("facts") or [])
            if len(pre_facts) > len(post_facts):
                dropped_facts = pre_facts[len(post_facts) :]
        except Exception as e:  # noqa: BLE001 — diagnostic only, never fatal
            notes.append(f"budget diff reconstruction failed ({type(e).__name__}: {e})")

    # ---- memory repetition + carried-forward (final pass) ----
    final_recent = final_packet.get("recent_turns") or [] if final_packet else []
    memory_rep = compute.memory_repetition(final_recent)
    stale = bool(final_pass and "stale_response_repeat" in final_pass.violations)
    carried_forward_pct = 0.0
    if final_pass is not None and final_recent:
        carried_forward_pct = max(
            (
                compute.jaccard_similarity(final_pass.answer, str(t.get("answer") or ""))
                for t in final_recent
                if isinstance(t, dict)
            ),
            default=0.0,
        )

    observations = compute.derive_observations(
        context_share_rows=context_rows,
        user_input_bytes=compute.bytes_len(user_input),
        stale_response_repeat=stale,
        budget_dropped_facts=dropped_facts,
        memory_rep=memory_rep,
        carried_forward_pct=carried_forward_pct,
        total_model_input_bytes=total_model_input_bytes,
    )
    advisory_obs = compute.derive_advisory_observation(final_pass.advisories if final_pass else [])
    if advisory_obs is not None:
        observations = [*observations, advisory_obs]

    # ---- stages ----
    applied_updates = list((result.outcome or {}).get("applied_updates") or [])
    final_violations = final_pass.violations if final_pass else []
    final_advisories = final_pass.advisories if final_pass else []
    user_share_pct = next(
        (r["share_pct"] for r in context_rows if r["source_id"] == "current_user_input"), 100.0
    )

    stages: list[StageTrace] = []
    for d in compute.stage_defs():
        status = compute.derive_stage_status(
            d["index"],
            final_violations=final_violations,
            final_advisories=final_advisories,
            pass_count=n_passes,
            final_decision=result.decision,
            applied_updates=applied_updates,
        )
        flag = compute.derive_stage_flag(
            d["index"],
            memory_repetition_detected=bool(memory_rep.get("detected")),
            user_share_pct=user_share_pct,
            budget_dropped_facts=bool(dropped_facts),
            final_violations=final_violations,
            final_advisories=final_advisories,
            final_decision=result.decision,
        )
        stage_notes: list[str] = []
        if d["index"] == 1:
            stage_notes.append(
                "the dashboard's POST /api/turn mirrors run_turn(...)'s own call shape rather "
                "than calling this stdin-blocking function directly."
            )
        if d["index"] == 5 and dropped_facts:
            stage_notes.append(f"edge.enforce_packet_budget dropped {len(dropped_facts)} fact slot(s).")
        if d["index"] == 7 and final_pass and final_pass.telemetry:
            think = final_pass.telemetry.get("thinking_chars")
            if think is not None:
                stage_notes.append(
                    "thinking channel disabled" if not think else f"thinking_chars={think}"
                )
        stages.append(
            StageTrace(
                index=d["index"],
                name=d["name"],
                source_module=d["source_module"],
                source_function=d["source_function"],
                source_line=d["source_line"],
                status=status,
                flag=flag,
                notes=stage_notes,
            )
        )

    decision_label = compute.derive_decision_label(
        result.decision,
        pass_count=n_passes,
        execution_status=(
            result.execution_outcome.status.value if result.execution_outcome else None
        ),
    )
    final_decision = {
        "decision": result.decision,
        "label": decision_label,
        "answer": result.answer if result.decision == "accept" else None,
        "violations": list(final_violations),
        "advisories": list(final_advisories),
    }

    persistence = {
        "applied_updates": applied_updates,
        "recent_turn_appended": "recent_turn_appended" in applied_updates,
        "outcome": result.outcome or {},
    }

    runtime_config = {
        "model": use_model,
        "mode": use_mode,
        "acceptance_mode": acceptance_mode,
        "temperature": resolved_temperature,
        "seed": resolved_seed,
        "num_ctx": resolved_num_ctx,
        "keep_alive": resolved_keep_alive,
        "think": resolved_think,
        "base_url": base_url,
        "profile": prof.to_dict(),
        "state_dir": str(state_root),
        "logs_dir": str(logs_root),
    }

    return TurnTrace(
        turn_id=resolved_turn_id,
        session_id=session_id,
        started_at=started_at,
        completed_at=completed_at,
        user_input=user_input,
        runtime_config=runtime_config,
        stages=stages,
        context_share_bytes=context_rows,
        packet=final_packet,
        packet_bytes=packet_bytes,
        passes=passes,
        final_decision=final_decision,
        persistence=persistence,
        observations=observations,
        operator={"marks": [], "note": ""},
        error=result.error,
        notes=notes,
    )


__all__ = ["StageTrace", "PassTrace", "TurnTrace", "run_traced_turn"]
