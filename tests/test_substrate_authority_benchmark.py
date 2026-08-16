"""Benchmark: Substrate Authority Matrix (edge companion path).

Not a multi-turn narrative. This expands the substrate surface the first
chat-pipeline bench did not center:

  - obligation taxonomy under adversarial phrasing
  - when the substrate must own the answer vs keep model phrasing
  - goal_echo discipline (paraphrase vs near-paste)
  - speaker integrity on recall (never bare user-line as answer)
  - interleaved generative controls that must not fire obligations
  - packet budget + recent_turns fitting under mixed authority pressure

Thesis alignment
  The model supplies linguistic possibility; the substrate determines what
  becomes an answer. This bench measures whether that separation holds on a
  lean edge profile (orin_nano_8gb), offline-first for headless Jetson CI.

Cells ≥ 21. Each cell is independent in intent; state accumulates only so
recent_turns / threads are realistic under fitting pressure.

Run:
    pytest tests/test_substrate_authority_benchmark.py -q -s
    python tests/test_substrate_authority_benchmark.py
"""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

from conditioned_kernel.authoritative_state import (
    classify_state_question,
    resolve_obligation,
)
from conditioned_kernel.compile import build_arrival_packet
from conditioned_kernel.edge import load_profile, packet_byte_size
from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.state import (
    DEFAULT_DESIGN_INTENT,
    RECENT_TURNS_MAX_BYTES,
    SubstrateState,
    recent_turns_byte_size,
)

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)

# Distinctive value used only in recall cells — not the spine of the bench.
RECALL_VALUE = "AETHER-7-KITE"

ExpectedOutcome = Literal[
    "accept_model",       # model phrasing kept; no authoritative fallback
    "accept_fallback",    # substrate rendered the answer
    "reject",             # hard reject (e.g. goal_echo on near-paste)
    "accept_any",         # accept either model or fallback is fine
]


@dataclass(frozen=True)
class AuthorityCell:
    id: str
    user: str
    dry_answer: str
    expected: ExpectedOutcome
    # Optional classifiers / content guards
    expect_kind: str | None = None  # goal | design_intent | edge_or_model | cloud_policy | open_threads | recent_recall | None
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    # Speaker integrity: accepted answer must not be a near-copy of a user line
    forbid_user_paste: bool = False
    evidence: tuple[str, ...] = (
        "This system is fully local.",
        "Edge target: jetson_orin_nano_8gb (one model at a time).",
    )
    thread_touch: tuple[str, ...] = ()
    notes: str = ""


def _dry(
    answer: str,
    *,
    evidence: tuple[str, ...] | None = None,
    thread_touch: tuple[str, ...] = (),
) -> str:
    return json.dumps(
        {
            "answer": answer,
            "evidence_used": list(
                evidence
                or (
                    "This system is fully local.",
                    "Edge target: jetson_orin_nano_8gb (one model at a time).",
                )
            ),
            "next_state": {"thread_touch": list(thread_touch)},
        }
    )


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": GOAL,
                "design_intent": DEFAULT_DESIGN_INTENT,
                "operator": {
                    "name": "Anthony",
                    "durable_facts": [
                        "Operator of this Conditioned Kernel instance",
                        "Prefers fully local operation",
                    ],
                },
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_authority_bench",
                "receipt_count_24h": 0,
                "recent_turns": [],
                "flags": {
                    "sensors": False,
                    "tools": False,
                    "cloud": False,
                    "max_repair_passes": 1,
                    "edge_target": "jetson_orin_nano_8gb",
                    "one_model_only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text(
        json.dumps(
            [
                {
                    "id": "thread_min_model",
                    "status": "open",
                    "title": "What is the minimum viable model size on Jetson Orin Nano 8GB?",
                },
                {
                    "id": "thread_authority",
                    "status": "open",
                    "title": "Which claims does the substrate own vs the kernel?",
                },
            ]
        ),
        encoding="utf-8",
    )
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    return state_dir, logs_dir


# ---------------------------------------------------------------------------
# Matrix (≥21 cells) — expands obligation surface, not chat length theater
# ---------------------------------------------------------------------------

CELLS: list[AuthorityCell] = [
    # ---- generative controls (must not fire obligations) ----
    AuthorityCell(
        id="gen_01_weather_noise",
        user="In one sentence, what does it mean for a system to be edge-first?",
        dry_answer=(
            "Edge-first means product decisions are made for constrained local "
            "hardware first, not deferred from a desktop prototype."
        ),
        expected="accept_model",
        expect_kind=None,
        must_contain=("edge",),
        notes="Open generative; no state question.",
    ),
    AuthorityCell(
        id="gen_02_metaphor",
        user="Offer a short metaphor for a replaceable transduction kernel.",
        dry_answer=(
            "Like a reed in a river: the reed shapes the sound, but the banks "
            "and the current decide what becomes music."
        ),
        expected="accept_model",
        expect_kind=None,
        notes="Phenomenological generative control.",
    ),
    AuthorityCell(
        id="gen_03_brief_ack",
        user="Understood — continue when ready.",
        dry_answer="Ready when you are.",
        expected="accept_model",
        expect_kind=None,
    ),
    # ---- goal obligation: paraphrase should accept; near-paste is design-reject ----
    AuthorityCell(
        id="goal_01_paraphrase",
        user="What is the current goal we are working toward?",
        dry_answer=(
            "We are working to show that a small local model becomes more "
            "coherent and continuous when the substrate, not the weights, "
            "carries state and constraints under Orin Nano budgets."
        ),
        expected="accept_any",
        expect_kind="goal",
        must_contain=("substrate", "orin"),
        notes="Paraphrase carries distinctive tokens without goal_echo paste.",
    ),
    AuthorityCell(
        id="goal_02_design_intent",
        user="In plain language, what is the design intent right now?",
        dry_answer=(
            "Put continuity and acceptance outside the model so a lean Jetson "
            "box can stay honest under a short context window."
        ),
        expected="accept_model",
        expect_kind="design_intent",
        must_contain=("jetson", "contin"),
        notes="Owned design-intent paraphrase keeps model phrasing; not the research goal.",
    ),
    AuthorityCell(
        id="goal_03_near_paste_expect_reject",
        user="Name the primary research goal.",
        dry_answer=GOAL,  # intentional near-paste
        expected="reject",
        expect_kind="goal",
        notes=(
            "Design call: goal_echo stays hard. Near-paste of the goal string "
            "must not accept unless authoritative fallback owns it. Under "
            "current rules this cell expects reject."
        ),
    ),
    AuthorityCell(
        id="goal_04_missing_claim_fallback",
        user="Which goal is active in substrate state?",
        dry_answer="Something about local models in general.",
        expected="accept_fallback",
        expect_kind="goal",
        must_contain=("goal",),
        notes="Weak answer should force substrate fallback for goal kind.",
    ),
    # ---- edge / model ----
    AuthorityCell(
        id="edge_01_device",
        user="What edge device is the default product target?",
        dry_answer=(
            "Default product target is the Jetson Orin Nano 8GB class, "
            "one model at a time."
        ),
        expected="accept_any",
        expect_kind="edge_or_model",
        must_contain=("orin", "nano"),
    ),
    AuthorityCell(
        id="edge_02_which_board",
        user="Which board are we running this on for the product path?",
        dry_answer="Product path targets jetson_orin_nano_8gb.",
        expected="accept_any",
        expect_kind="edge_or_model",
        must_contain=("orin",),
    ),
    AuthorityCell(
        id="edge_03_wrong_device_fallback",
        user="What is the edge target in the active profile?",
        dry_answer="We are targeting a high-end desktop GPU cluster.",
        expected="accept_fallback",
        expect_kind="edge_or_model",
        must_contain=("orin", "jetson"),
        must_not_contain=("desktop gpu cluster",),
        notes="Forbidden claim shape should yield substrate fallback.",
    ),
    # ---- cloud / local policy ----
    AuthorityCell(
        id="cloud_01_allowed",
        user="Are cloud APIs allowed in this configuration?",
        dry_answer=(
            "No. Cloud services are not allowed; this system operates fully local-only."
        ),
        expected="accept_any",
        expect_kind="cloud_policy",
        must_contain=("local",),
        must_not_contain=("cloud services are allowed",),
    ),
    AuthorityCell(
        id="cloud_02_fully_local",
        user="Is this a fully local operation only?",
        dry_answer="Yes — fully local-only, no cloud dependency.",
        expected="accept_any",
        expect_kind="cloud_policy",
        must_contain=("local",),
    ),
    AuthorityCell(
        id="cloud_03_false_allow_fallback",
        user="Can we use cloud services for this run?",
        dry_answer="Yes, cloud APIs are allowed for this session.",
        expected="accept_fallback",
        expect_kind="cloud_policy",
        must_not_contain=("cloud services are allowed", "yes, cloud"),
        notes="Asserted cloud allowance must be overridden by substrate.",
    ),
    # ---- open threads ----
    AuthorityCell(
        id="threads_01_list",
        user="List the current open threads.",
        dry_answer=(
            "Open threads: thread_min_model (minimum viable model size on Orin) "
            "and thread_authority (substrate vs kernel ownership)."
        ),
        expected="accept_any",
        expect_kind="open_threads",
        must_contain=("thread_min_model",),
        thread_touch=("thread_authority",),
    ),
    AuthorityCell(
        id="threads_02_what_open",
        user="What open threads does the substrate currently hold?",
        dry_answer="thread_min_model and thread_authority are open.",
        expected="accept_any",
        expect_kind="open_threads",
        must_contain=("thread_",),
    ),
    AuthorityCell(
        id="threads_03_invented_fallback",
        user="Which threads are open right now?",
        dry_answer="Open threads include thread_cloud_bridge and thread_sensors.",
        expected="accept_fallback",
        expect_kind="open_threads",
        must_not_contain=("thread_cloud_bridge", "thread_sensors"),
        notes="Invented thread ids must not survive; substrate owns the list.",
    ),
    # ---- recent_recall: inject value, then probe under pressure ----
    AuthorityCell(
        id="recall_00_inject",
        user=f"Remember the session token {RECALL_VALUE} as a continuity anchor.",
        dry_answer=f"Noted. Continuity anchor stored as {RECALL_VALUE}.",
        expected="accept_model",
        expect_kind=None,  # store imperative, not recall
        must_contain=(RECALL_VALUE,),
        notes="Injection only; classifier should not treat as recent_recall.",
    ),
    AuthorityCell(
        id="recall_01_direct",
        user="What session token did I ask you to remember?",
        dry_answer=f"The session token is {RECALL_VALUE}.",
        expected="accept_any",
        expect_kind="recent_recall",
        must_contain=(RECALL_VALUE,),
        forbid_user_paste=True,
    ),
    AuthorityCell(
        id="recall_02_rephrase",
        user="Remind me of the continuity anchor from earlier.",
        dry_answer=f"Continuity anchor: {RECALL_VALUE}.",
        expected="accept_any",
        expect_kind="recent_recall",
        must_contain=(RECALL_VALUE,),
        forbid_user_paste=True,
    ),
    AuthorityCell(
        id="recall_03_cue_only_user_line_must_not_win",
        user="Confirm the session token one more time before we continue.",
        dry_answer=f"Confirmed: {RECALL_VALUE}.",
        expected="accept_any",
        expect_kind="recent_recall",
        must_contain=(RECALL_VALUE,),
        forbid_user_paste=True,
        notes=(
            "After A+B+C: cue-only user lines must not become the answer. "
            "Kernel line with the value must be kept, or fallback must state the value."
        ),
    ),
    AuthorityCell(
        id="recall_04_wrong_value_fallback",
        user="What was the session token again?",
        dry_answer="The session token is ORBIT-0-NULL.",
        expected="accept_fallback",
        expect_kind="recent_recall",
        must_contain=(RECALL_VALUE,),
        must_not_contain=("ORBIT-0-NULL",),
        forbid_user_paste=True,
        notes="Wrong value must yield substrate fallback carrying the real token.",
    ),
    # ---- mixed pressure / integrity ----
    AuthorityCell(
        id="mix_01_generative_between",
        user="One sentence on why streaming tokens to the terminal is out of scope for v0.",
        dry_answer=(
            "v0 buffers the full candidate before acceptance so the substrate, "
            "not the stream, decides what becomes an answer."
        ),
        expected="accept_model",
        expect_kind=None,
        must_contain=("accept",),
    ),
    AuthorityCell(
        id="mix_02_goal_again_paraphrase",
        user="Restate the active goal without copying it verbatim.",
        dry_answer=(
            "Active aim: measure substrate gain on a small local model under "
            "Jetson Orin Nano budgets, with continuity held outside the weights."
        ),
        expected="accept_any",
        expect_kind="goal",
        must_contain=("substrate", "orin"),
    ),
    AuthorityCell(
        id="mix_03_local_policy_again",
        user="Quick check: are we allowed to call external cloud services?",
        dry_answer="No external cloud services — local only.",
        expected="accept_any",
        expect_kind="cloud_policy",
        must_contain=("local",),
    ),
    AuthorityCell(
        id="mix_04_edge_again",
        user="Which edge target and posture are in force?",
        dry_answer=(
            "Edge target jetson_orin_nano_8gb, one model at a time, fully local."
        ),
        expected="accept_any",
        expect_kind="edge_or_model",
        must_contain=("orin",),
    ),
]


assert len(CELLS) >= 21, "authority matrix must contain at least 21 cells"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _is_near_user_paste(answer: str, recent: list[dict[str, Any]]) -> bool:
    """True if answer is essentially a prior user line (speaker collapse)."""
    a = re.sub(r"\s+", " ", (answer or "").strip().lower())
    if len(a) < 12:
        return False
    for t in recent:
        u = re.sub(r"\s+", " ", str(t.get("user") or "").strip().lower())
        if not u or len(u) < 12:
            continue
        if a == u:
            return True
        if u in a and len(a) <= len(u) + 24:
            return True
        if a in u and len(a) >= max(20, int(0.75 * len(u))):
            return True
    return False


def run_authority_matrix(
    state_dir: Path,
    logs_dir: Path,
    *,
    profile_id: str = "orin_nano_8gb",
    max_repair: int = 0,
) -> dict[str, Any]:
    prof = load_profile(profile_id)
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for cell in CELLS:
        # Classification probe (pre-turn, for reporting)
        classified = classify_state_question(cell.user)

        turn_t0 = time.perf_counter()
        result = run_turn(
            cell.user,
            state_dir=state_dir,
            logs_dir=logs_dir,
            dry_candidate_text=_dry(
                cell.dry_answer,
                evidence=cell.evidence,
                thread_touch=cell.thread_touch,
            ),
            max_repair=max_repair,
            profile=prof,
            acceptance_mode="companion",
        )
        elapsed = time.perf_counter() - turn_t0

        state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
        recent = state.recent_turns()
        answer = result.answer or ""
        fallback = bool(result.candidate.get("authoritative_fallback"))
        kind = result.candidate.get("authoritative_kind") or classified

        pb = (result.packet.get("_edge") or {}).get("packet_bytes")
        if pb is None and result.packet:
            skip = {"context_field", "evidence_pool_selected", "intents"}
            body = {
                k: v
                for k, v in result.packet.items()
                if not str(k).startswith("_") and k not in skip
            }
            pb = packet_byte_size(body)

        # Content guards
        ans_l = answer.lower()
        missing = [s for s in cell.must_contain if s.lower() not in ans_l]
        forbidden_hits = [s for s in cell.must_not_contain if s.lower() in ans_l]
        user_paste = (
            _is_near_user_paste(answer, recent[:-1] if recent else [])
            if cell.forbid_user_paste and result.ok
            else False
        )

        # Outcome match
        if cell.expected == "accept_model":
            outcome_ok = result.ok and result.decision == "accept" and not fallback
        elif cell.expected == "accept_fallback":
            outcome_ok = result.ok and result.decision == "accept" and fallback
        elif cell.expected == "reject":
            outcome_ok = (not result.ok) and result.decision == "reject"
        else:  # accept_any
            outcome_ok = result.ok and result.decision == "accept"

        content_ok = not missing and not forbidden_hits and not user_paste
        cell_pass = outcome_ok and content_ok

        # Kind match (informational when expect_kind set)
        kind_ok = True
        if cell.expect_kind is not None:
            kind_ok = (classified == cell.expect_kind) or (kind == cell.expect_kind)

        row = {
            "id": cell.id,
            "decision": result.decision,
            "ok": result.ok,
            "fallback": fallback,
            "classified": classified,
            "authoritative_kind": kind,
            "packet_bytes": pb,
            "recent_turns_n": len(recent),
            "recent_turns_bytes": recent_turns_byte_size(recent),
            "violations": list((result.receipt or {}).get("violations") or []),
            "elapsed_s": round(elapsed, 4),
            "expected": cell.expected,
            "outcome_ok": outcome_ok,
            "content_ok": content_ok,
            "kind_ok": kind_ok,
            "cell_pass": cell_pass,
            "missing_required": missing,
            "forbidden_hits": forbidden_hits,
            "user_paste": user_paste,
            "answer_preview": answer[:140],
            "notes": cell.notes,
        }
        rows.append(row)

    wall = time.perf_counter() - t0
    passed = [r for r in rows if r["cell_pass"]]
    failed = [r for r in rows if not r["cell_pass"]]

    by_expected: dict[str, dict[str, int]] = {}
    for r in rows:
        bucket = by_expected.setdefault(r["expected"], {"n": 0, "pass": 0})
        bucket["n"] += 1
        if r["cell_pass"]:
            bucket["pass"] += 1

    packet_sizes = [r["packet_bytes"] for r in rows if r["packet_bytes"] is not None]
    rt_bytes = [r["recent_turns_bytes"] for r in rows]

    # Post-matrix compile still under budget
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    post = build_arrival_packet(
        state,
        "Authority matrix complete — compile self-check.",
        profile=prof,
        enforce_budget=True,
    )
    post_bytes = post["_edge"]["packet_bytes"]

    summary = {
        "benchmark": "ck_substrate_authority_matrix",
        "cells": len(CELLS),
        "passed": len(passed),
        "failed": len(failed),
        "pass_rate": round(len(passed) / len(rows), 4) if rows else 0.0,
        "wall_seconds": round(wall, 3),
        "by_expected": by_expected,
        "packet_bytes": {
            "min": min(packet_sizes) if packet_sizes else None,
            "max": max(packet_sizes) if packet_sizes else None,
            "mean": round(statistics.mean(packet_sizes), 1) if packet_sizes else None,
            "budget": prof.max_packet_bytes,
            "any_over_budget": any((p or 0) > prof.max_packet_bytes for p in packet_sizes),
            "post_matrix": post_bytes,
        },
        "recent_turns": {
            "final_n": rows[-1]["recent_turns_n"] if rows else 0,
            "final_bytes": rows[-1]["recent_turns_bytes"] if rows else 0,
            "max_bytes": max(rt_bytes) if rt_bytes else 0,
            "cap_bytes": RECENT_TURNS_MAX_BYTES,
            "any_over_cap": any(b > RECENT_TURNS_MAX_BYTES for b in rt_bytes),
        },
        "speaker_integrity": {
            "user_paste_failures": sum(1 for r in rows if r["user_paste"]),
        },
        "profile_id": prof.profile_id,
        "failed_ids": [r["id"] for r in failed],
        "rows": rows,
    }
    return summary


# ---------------------------------------------------------------------------
# Pytest
# ---------------------------------------------------------------------------


def test_substrate_authority_matrix_ge_21(tmp_path: Path):
    """Primary: ≥21 authority cells; edge budgets hold; speaker integrity holds."""
    state_dir, logs_dir = _bootstrap(tmp_path)
    summary = run_authority_matrix(state_dir, logs_dir)

    assert summary["cells"] >= 21
    assert summary["packet_bytes"]["any_over_budget"] is False
    assert summary["recent_turns"]["any_over_cap"] is False
    assert summary["speaker_integrity"]["user_paste_failures"] == 0
    assert summary["packet_bytes"]["post_matrix"] <= load_profile("orin_nano_8gb").max_packet_bytes

    # Design-call cell must still reject near-paste of the goal
    paste_row = next(r for r in summary["rows"] if r["id"] == "goal_03_near_paste_expect_reject")
    assert paste_row["decision"] == "reject"
    assert "goal_echo" in (paste_row["violations"] or [])

    # Recall value must survive probes without user-line paste
    recall_rows = [r for r in summary["rows"] if r["id"].startswith("recall_0") and r["id"] != "recall_00_inject"]
    assert recall_rows
    assert all(r["cell_pass"] for r in recall_rows), [
        (r["id"], r["decision"], r["missing_required"], r["user_paste"], r["answer_preview"])
        for r in recall_rows
        if not r["cell_pass"]
    ]

    # Overall: allow only the intentional design-reject cell to fail content/outcome
    # if something else fails, surface it clearly
    unexpected = [
        r
        for r in summary["rows"]
        if not r["cell_pass"] and r["id"] != "goal_03_near_paste_expect_reject"
    ]
    assert not unexpected, [
        (r["id"], r["expected"], r["decision"], r["fallback"], r["missing_required"], r["forbidden_hits"], r["answer_preview"])
        for r in unexpected
    ]

    print(
        f"\n[ck authority matrix] cells={summary['cells']} "
        f"pass={summary['passed']}/{summary['cells']} "
        f"pkt_max={summary['packet_bytes']['max']}/{summary['packet_bytes']['budget']} "
        f"rt={summary['recent_turns']['final_n']}t/"
        f"{summary['recent_turns']['final_bytes']}B "
        f"user_paste_fail={summary['speaker_integrity']['user_paste_failures']} "
        f"wall={summary['wall_seconds']}s "
        f"failed={summary['failed_ids']}"
    )


def test_substrate_authority_matrix_report_shape(tmp_path: Path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    summary = run_authority_matrix(state_dir, logs_dir)
    required = {
        "benchmark",
        "cells",
        "passed",
        "failed",
        "pass_rate",
        "by_expected",
        "packet_bytes",
        "recent_turns",
        "speaker_integrity",
        "rows",
    }
    assert required.issubset(summary.keys())
    blob = json.dumps(summary, ensure_ascii=False)
    assert "ck_substrate_authority_matrix" in blob


def test_classify_does_not_treat_store_imperative_as_recall():
    """Injection language must not classify as recent_recall."""
    q = f"Remember the session token {RECALL_VALUE} as a continuity anchor."
    assert classify_state_question(q) is None


def test_classify_goal_and_cloud_smoke():
    assert classify_state_question("What is the current goal we are working toward?") == "goal"
    assert classify_state_question("Are cloud APIs allowed in this configuration?") == "cloud_policy"
    assert classify_state_question("What edge device is the default product target?") == "edge_or_model"


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory(prefix="ck_auth_bench_") as td:
        root = Path(td)
        sd, ld = _bootstrap(root)
        report = run_authority_matrix(sd, ld)
        slim = {k: v for k, v in report.items() if k != "rows"}
        print(json.dumps(slim, indent=2))
        print(f"\nfailed_ids={report['failed_ids']}")
        print(f"pass_rate={report['pass_rate']}")
