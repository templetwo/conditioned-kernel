"""Benchmark: ck chat inference pipeline under multi-turn load (≥21 turns).

Exercises the full companion path used by `ck chat`:

    compile(arrival packet) → generate (dry or live) → parse → validate
    → assess → accept | repair | reject → recent_turns update + receipts

Designed for offline CI (dry candidates) while remaining live-capable.

Metrics collected per turn and summarized at the end:

  - decision (accept / reject / error)
  - packet_bytes (edge body)
  - recent_turns count + UTF-8 byte size after accept
  - repair passes used
  - violations
  - continuity probes (codeword / goal reference survival under fitting)

Run offline:
    pytest tests/test_chat_pipeline_benchmark.py -q -s

Or as a module:
    python -m pytest tests/test_chat_pipeline_benchmark.py -q -s
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

import pytest

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
# Fixture / bootstrap (mirrors test_first_flow_chat)
# ---------------------------------------------------------------------------

CODEWORD = "FALCON-9-DELTA"
GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
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
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_bench_chat",
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
                    "id": "thread_continuity",
                    "status": "open",
                    "title": "Does recent_turns preserve continuity under byte cap?",
                },
            ]
        ),
        encoding="utf-8",
    )
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    return state_dir, logs_dir


def _dry_candidate(
    answer: str,
    *,
    evidence: list[str] | None = None,
    thread_touch: list[str] | None = None,
) -> str:
    """Valid companion-mode candidate JSON."""
    return json.dumps(
        {
            "answer": answer,
            "evidence_used": evidence
            or [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": thread_touch or ["thread_min_model"]},
        }
    )


# ---------------------------------------------------------------------------
# Scripted conversation (≥21 turns)
# ---------------------------------------------------------------------------

# 24 turns: mix of setup, continuity probes, length pressure, and short
# clarifying exchanges. Dry answers are crafted so acceptance is expected
# under companion mode while still stressing the packet / recent_turns path.
TURN_SCRIPT: list[dict[str, Any]] = [
    # 1–5  setup + codeword injection
    {
        "user": "Summarize the current design intent in one short paragraph.",
        "dry": _dry_candidate(
            "Design intent is edge-first substrate conditioning: keep the model "
            "small and local, put continuity in the substrate, and measure gain "
            "under Jetson Orin Nano budgets without cloud or sensors."
        ),
    },
    {
        "user": f"Remember the session codeword {CODEWORD}. Confirm you have it.",
        "dry": _dry_candidate(
            f"Codeword noted: {CODEWORD}. I will treat it as a continuity anchor "
            "for this session under the local substrate."
        ),
    },
    {
        "user": "What edge device is the default product target?",
        "dry": _dry_candidate(
            "Default product target is Jetson Orin Nano 8GB class, one model at a time."
        ),
    },
    {
        "user": "Is the system allowed to call cloud APIs or use sensors in v0?",
        "dry": _dry_candidate(
            "No. v0 is fully local: no cloud dependency and sensors are out of scope."
        ),
    },
    {
        "user": "Name the primary research goal we are working toward.",
        "dry": _dry_candidate(
            "Primary goal: demonstrate conditioned-kernel substrate gain over bare "
            "generation on a small local model under Jetson Orin Nano 8GB edge budgets."
        ),
        "expect_goal_echo": True,
        "notes": "Design call: goal_echo stays hard on a near-paste of the claim.",
    },
    # 6–10  continuity + length pressure
    {
        "user": "What codeword did I give you earlier?",
        "dry": _dry_candidate(
            f"The session codeword is {CODEWORD}."
        ),
        "expect_codeword": True,
    },
    {
        "user": "Give a slightly longer answer about why the model is treated as a replaceable kernel.",
        "dry": _dry_candidate(
            "The language model is a replaceable text-transduction kernel. Once it "
            "crosses a minimum linguistic threshold, substrate design (state, compiled "
            "arrival packet, validation, repair, acceptance) should predict system "
            "behavior more strongly than model identity. Continuity and constraint "
            "obedience live outside any single model instance."
        ),
    },
    {
        "user": "Touch the continuity thread and restate why recent_turns matter.",
        "dry": _dry_candidate(
            "recent_turns is the byte-capped dialogue ring that carries prior "
            "exchanges into the next arrival packet so the substrate, not the model "
            "weights, holds session continuity under edge budgets.",
            thread_touch=["thread_continuity"],
        ),
    },
    {
        "user": "In two sentences, how does the packet budget interact with recent_turns?",
        "dry": _dry_candidate(
            "Arrival packets are compiled under a hard byte budget for the edge "
            "profile. recent_turns is itself byte-capped and oldest-first fitted so "
            "prior dialogue cannot blow the packet budget."
        ),
    },
    {
        "user": "Confirm the codeword one more time before we continue.",
        "dry": _dry_candidate(f"Confirmed: {CODEWORD}."),
        "expect_codeword": True,
    },
    # 11–16  mid-session pressure
    {
        "user": "What is the maximum repair passes allowed by the default flags?",
        "dry": _dry_candidate(
            "Default flags allow one repair pass (max_repair_passes=1)."
        ),
    },
    {
        "user": "Does acceptance require the model to invent evidence, or can the substrate supply it?",
        "dry": _dry_candidate(
            "In companion mode the substrate can supply authoritative evidence when "
            "the model returns empty evidence_used, so conversation is not blocked "
            "by laboratory-style evidence demands."
        ),
    },
    {
        "user": "List the open threads you currently know about.",
        "dry": _dry_candidate(
            "Open threads include thread_min_model (minimum viable model size on "
            "Orin Nano) and thread_continuity (recent_turns under byte cap)."
        ),
    },
    {
        "user": "Repeat the design goal without inventing new claims.",
        "dry": _dry_candidate(
            "Goal remains: demonstrate conditioned-kernel substrate gain over bare "
            "generation on a small local model under Jetson Orin Nano 8GB edge budgets."
        ),
        "expect_goal_echo": True,
        "notes": "Design call: goal_echo stays hard.",
    },
    {
        "user": "If I ask about the codeword later, what should you answer?",
        "dry": _dry_candidate(
            f"I should answer with the session codeword {CODEWORD}."
        ),
        "expect_codeword": True,
    },
    {
        "user": "Short status: are we still on the edge product path?",
        "dry": _dry_candidate(
            "Yes. Product path remains edge-first on Jetson Orin Nano 8GB class."
        ),
    },
    # 17–24  late session / fitting stress
    {
        "user": "What happens when recent_turns exceeds the byte cap?",
        "dry": _dry_candidate(
            "Oldest turns are dropped first until the serialized recent_turns list "
            "fits under the RECENT_TURNS_MAX_BYTES cap; single oversized turns are "
            "hard-clipped."
        ),
    },
    {
        "user": "Give a longer reflection on substrate gain vs model identity (keep it coherent).",
        "dry": _dry_candidate(
            "Substrate gain is the claim that the same small local model becomes more "
            "coherent, state-faithful, continuous, and repairable when run through the "
            "compiled packet, validation, and one repair loop than when run bare. Those "
            "gains should survive a model swap within the tested size band because "
            "behavior is relocated into the substrate rather than into weights."
        ),
    },
    {
        "user": f"Final continuity check: what is the codeword and the edge target?",
        "dry": _dry_candidate(
            f"Codeword {CODEWORD}; edge target Jetson Orin Nano 8GB (one model at a time)."
        ),
        "expect_codeword": True,
    },
    {
        "user": "One sentence on why streaming is out of scope for v0 terminal.",
        "dry": _dry_candidate(
            "v0 does not stream model tokens to the terminal; the substrate buffers "
            "the full candidate before acceptance."
        ),
    },
    {
        "user": "Acknowledge that this is turn pressure for the benchmark and stay brief.",
        "dry": _dry_candidate(
            "Acknowledged. Staying brief under multi-turn packet and recent_turns pressure."
        ),
    },
    {
        "user": "Reaffirm the primary goal one last time.",
        "dry": _dry_candidate(
            "Primary goal: demonstrate conditioned-kernel substrate gain over bare "
            "generation on a small local model under Jetson Orin Nano 8GB edge budgets."
        ),
        "expect_goal_echo": True,
        "notes": "Design call: goal_echo stays hard.",
    },
    {
        "user": "Close the loop: name the codeword and confirm local-only posture.",
        "dry": _dry_candidate(
            f"Codeword {CODEWORD}. Posture remains fully local: no cloud, no sensors, "
            "one model at a time on the Orin Nano edge path."
        ),
        "expect_codeword": True,
    },
    {
        "user": "End-of-session status: still under edge packet budget?",
        "dry": _dry_candidate(
            "Yes. Arrival packets continue to compile under the orin_nano_8gb byte budget."
        ),
    },
]


assert len(TURN_SCRIPT) >= 21, "script must contain at least 21 turns"


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def run_chat_pipeline_benchmark(
    state_dir: Path,
    logs_dir: Path,
    *,
    profile_id: str = "orin_nano_8gb",
    max_repair: int = 0,
    acceptance_mode: str = "companion",
) -> dict[str, Any]:
    """Execute the scripted multi-turn chat pipeline and collect metrics."""
    prof = load_profile(profile_id)
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for i, step in enumerate(TURN_SCRIPT, start=1):
        user = step["user"]
        dry = step["dry"]
        expect_cw = bool(step.get("expect_codeword"))
        expect_goal_echo = bool(step.get("expect_goal_echo"))

        turn_t0 = time.perf_counter()
        result = run_turn(
            user,
            state_dir=state_dir,
            logs_dir=logs_dir,
            dry_candidate_text=dry,
            max_repair=max_repair,
            profile=prof,
            acceptance_mode=acceptance_mode,
        )
        turn_elapsed = time.perf_counter() - turn_t0

        state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
        turns = state.recent_turns()
        rt_bytes = recent_turns_byte_size(turns)

        # Packet size for the just-compiled turn (from result)
        pb = (result.packet.get("_edge") or {}).get("packet_bytes")
        if pb is None and result.packet:
            skip = {"context_field", "evidence_pool_selected", "intents"}
            body = {
                k: v
                for k, v in result.packet.items()
                if not str(k).startswith("_") and k not in skip
            }
            pb = packet_byte_size(body)

        # Continuity probe: does the accepted answer still carry the codeword
        # when we asked for it? (Under dry this is always true if the dry
        # string contains it; the probe still exercises the accept path.)
        answer = result.answer or ""
        codeword_present = CODEWORD in answer if expect_cw else None

        row = {
            "turn": i,
            "user_len": len(user),
            "decision": result.decision,
            "ok": result.ok,
            "expect_goal_echo": expect_goal_echo,
            "packet_bytes": pb,
            "recent_turns_n": len(turns),
            "recent_turns_bytes": rt_bytes,
            "passes": len(result.passes),
            "violations": list((result.receipt or {}).get("violations") or []),
            "elapsed_s": round(turn_elapsed, 4),
            "expect_codeword": expect_cw,
            "codeword_present": codeword_present,
            "answer_preview": answer[:120],
        }
        rows.append(row)

    wall = time.perf_counter() - t0
    accepted = [r for r in rows if r["decision"] == "accept"]
    rejected = [r for r in rows if r["decision"] == "reject"]
    errors = [r for r in rows if r["decision"] == "error"]

    packet_sizes = [r["packet_bytes"] for r in rows if r["packet_bytes"] is not None]
    rt_sizes = [r["recent_turns_bytes"] for r in rows]
    rt_ns = [r["recent_turns_n"] for r in rows]

    codeword_checks = [r for r in rows if r["expect_codeword"]]
    codeword_hits = sum(1 for r in codeword_checks if r["codeword_present"])

    summary = {
        "benchmark": "ck_chat_inference_pipeline",
        "turns_scripted": len(TURN_SCRIPT),
        "turns_executed": len(rows),
        "accepted_n": len(accepted),
        "rejected_n": len(rejected),
        "error_n": len(errors),
        "accept_rate": round(len(accepted) / len(rows), 4) if rows else 0.0,
        "wall_seconds": round(wall, 3),
        "packet_bytes": {
            "min": min(packet_sizes) if packet_sizes else None,
            "max": max(packet_sizes) if packet_sizes else None,
            "mean": round(statistics.mean(packet_sizes), 1) if packet_sizes else None,
            "budget": prof.max_packet_bytes,
            "any_over_budget": any(
                (p or 0) > prof.max_packet_bytes for p in packet_sizes
            ),
        },
        "recent_turns": {
            "final_n": rt_ns[-1] if rt_ns else 0,
            "final_bytes": rt_sizes[-1] if rt_sizes else 0,
            "max_n": max(rt_ns) if rt_ns else 0,
            "max_bytes": max(rt_sizes) if rt_sizes else 0,
            "cap_bytes": RECENT_TURNS_MAX_BYTES,
            "any_over_cap": any(b > RECENT_TURNS_MAX_BYTES for b in rt_sizes),
        },
        "continuity": {
            "codeword_probes": len(codeword_checks),
            "codeword_hits": codeword_hits,
            "codeword_hit_rate": (
                round(codeword_hits / len(codeword_checks), 4)
                if codeword_checks
                else None
            ),
        },
        "profile_id": prof.profile_id,
        "acceptance_mode": acceptance_mode,
        "max_repair": max_repair,
        "rows": rows,
    }
    return summary


# ---------------------------------------------------------------------------
# Pytest entry
# ---------------------------------------------------------------------------


def test_chat_pipeline_benchmark_ge_21_turns(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Primary benchmark: ≥21 sequential conditioned turns under edge budget."""
    state_dir, logs_dir = _bootstrap(tmp_path)
    summary = run_chat_pipeline_benchmark(state_dir, logs_dir)

    # --- hard invariants ---
    assert summary["turns_executed"] >= 21
    echo_rows = [r for r in summary["rows"] if r.get("expect_goal_echo")]
    unexpected_reject = [
        r
        for r in summary["rows"]
        if r["decision"] != "accept" and not r.get("expect_goal_echo")
    ]
    assert not unexpected_reject, [
        (r["turn"], r["decision"], r.get("violations"), r["answer_preview"])
        for r in unexpected_reject
    ]
    assert echo_rows, "script must keep at least one intentional goal_echo reject"
    assert all("goal_echo" in (r.get("violations") or []) for r in echo_rows)
    assert all(r["decision"] == "reject" for r in echo_rows)
    assert summary["accepted_n"] >= 21, (
        f"expected ≥21 accepts under dry companion path; got {summary['accepted_n']}"
    )
    assert summary["error_n"] == 0
    assert summary["packet_bytes"]["any_over_budget"] is False
    assert summary["recent_turns"]["any_over_cap"] is False
    assert summary["continuity"]["codeword_hit_rate"] == 1.0

    # Final recent_turns must still be fitted and non-empty after long session
    assert summary["recent_turns"]["final_n"] >= 1
    assert summary["recent_turns"]["final_bytes"] <= RECENT_TURNS_MAX_BYTES

    # Packet must still compile cleanly after 21+ accepts
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    packet = build_arrival_packet(
        state,
        "Post-benchmark compile self-check.",
        profile=load_profile("orin_nano_8gb"),
        enforce_budget=True,
    )
    assert packet["_edge"]["packet_bytes"] <= load_profile("orin_nano_8gb").max_packet_bytes

    # Human-readable one-liner for -s
    print(
        f"\n[ck chat bench] turns={summary['turns_executed']} "
        f"accept={summary['accepted_n']} "
        f"pkt_max={summary['packet_bytes']['max']}/{summary['packet_bytes']['budget']} "
        f"rt_final={summary['recent_turns']['final_n']}t/"
        f"{summary['recent_turns']['final_bytes']}B "
        f"codeword={summary['continuity']['codeword_hits']}/"
        f"{summary['continuity']['codeword_probes']} "
        f"wall={summary['wall_seconds']}s"
    )


def test_chat_pipeline_benchmark_report_shape(tmp_path: Path):
    """Summary dict is stable enough to dump as a receipt artifact."""
    state_dir, logs_dir = _bootstrap(tmp_path)
    summary = run_chat_pipeline_benchmark(state_dir, logs_dir)

    required = {
        "benchmark",
        "turns_scripted",
        "turns_executed",
        "accepted_n",
        "accept_rate",
        "packet_bytes",
        "recent_turns",
        "continuity",
        "rows",
    }
    assert required.issubset(summary.keys())
    assert len(summary["rows"]) == summary["turns_executed"]

    # Serializable
    blob = json.dumps(summary, ensure_ascii=False)
    assert "ck_chat_inference_pipeline" in blob
    assert len(blob) > 500


if __name__ == "__main__":
    # Standalone dry run without pytest (writes summary to stdout)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="ck_chat_bench_") as td:
        root = Path(td)
        sd, ld = _bootstrap(root)
        report = run_chat_pipeline_benchmark(sd, ld)
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
        print(f"\nrows={len(report['rows'])} accept_rate={report['accept_rate']}")
