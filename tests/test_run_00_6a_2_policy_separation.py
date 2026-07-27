"""RUN 00.6A.2 — ledger facts vs experiment headline policy.

TerminalLedger must not hardcode Episode-A or matrix headline decisions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from conditioned_kernel.generate import InferenceResult, RunStatus
from conditioned_kernel.outcomes import (
    ExecutionOutcome,
    ManifestCell,
    TerminalLedger,
    outcome_from_inference,
)

_POLICY_KEYS = frozenset(
    {
        "headline_eligible",
        "headline_ineligible_reason",
        "scientific_status",
    }
)
_EPISODE_A_MARKERS = (
    "episode_a",
    "deferred_episode_a",
    "accept_persist_reload",
)


def _load_experiment(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"ck_exp_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _cell(i: int = 0, cond: str = "ck") -> ManifestCell:
    return ManifestCell(run_id="run", task_id=f"t{i}", condition_id=cond, episode="B")


# ---------------------------------------------------------------------------
# 1–2. Ledger facts only
# ---------------------------------------------------------------------------


def test_ledger_completed_valid_reports_factual_counts():
    cell = _cell(0, "ck_strict")
    led = TerminalLedger([cell])
    led.record(
        cell.cell_id,
        ExecutionOutcome.completed_valid(
            cell=cell,
            output='{"answer":"ok"}',
            decision="accept",
        ),
    )
    d = led.diagnostic_counts()
    assert d["planned_n"] == 1
    assert d["terminal_n"] == 1
    assert d["accepted_n"] == 1
    assert d["scientific_completion_n"] == 1
    assert d["inference_completed_n"] == 1
    assert d["final_response_present_n"] == 1
    assert d["failed_n"] == 0


def test_diagnostic_counts_contain_no_headline_policy_or_episode_a_text():
    cell = _cell()
    led = TerminalLedger([cell])
    led.record(
        cell.cell_id,
        ExecutionOutcome.completed_valid(cell=cell, output="{}", decision="accept"),
    )
    d = led.diagnostic_counts()
    for key in _POLICY_KEYS:
        assert key not in d, f"ledger must not emit policy key {key}"
    blob = str(d).lower()
    for marker in _EPISODE_A_MARKERS:
        assert marker not in blob, f"ledger facts leaked Episode-A text: {marker}"


# ---------------------------------------------------------------------------
# 3. Continuity policy remains Episode-A-specific
# ---------------------------------------------------------------------------


def test_continuity_headline_policy_is_episode_a_deferred():
    root = Path(__file__).resolve().parents[1]
    mod = _load_experiment("continuity", root / "experiments" / "run_continuity.py")
    policy = mod.continuity_headline_policy()
    assert policy["headline_eligible"] is False
    assert policy["scientific_status"] == "deferred_episode_a_lifecycle"
    assert (
        policy["headline_ineligible_reason"]
        == "episode_a_accept_persist_reload_not_implemented"
    )


def test_continuity_event_shape_uses_policy_not_ledger(tmp_path: Path, monkeypatch):
    """Dry continuity report attaches continuity policy outside ledger facts."""
    root = Path(__file__).resolve().parents[1]
    mod = _load_experiment("continuity_event", root / "experiments" / "run_continuity.py")
    # Reuse real dry path with limit 1
    out = tmp_path / "cont.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_continuity.py",
            "--limit",
            "1",
            "--dry",
            "--out",
            str(out),
        ],
    )
    rc = mod.main()
    assert rc == 0
    import json

    report = json.loads(out.read_text())
    assert report["headline_eligible"] is False
    assert report["scientific_status"] == "deferred_episode_a_lifecycle"
    assert (
        report["headline_ineligible_reason"]
        == "episode_a_accept_persist_reload_not_implemented"
    )
    # Ledger facts block has no policy keys
    diag = report["terminal_ledger"]["diagnostic_counts"]
    for key in _POLICY_KEYS:
        assert key not in diag
    # Event carries both facts and policy
    ev = report["event"]
    assert ev["headline_eligible"] is False
    assert ev["scientific_status"] == "deferred_episode_a_lifecycle"
    assert "episode_a" in ev["headline_ineligible_reason"]


# ---------------------------------------------------------------------------
# 4–5. Matrix policy never uses Episode-A language
# ---------------------------------------------------------------------------


def test_matrix_headline_policy_not_episode_a():
    root = Path(__file__).resolve().parents[1]
    mod = _load_experiment("matrix", root / "experiments" / "run_matrix.py")
    policy = mod.matrix_headline_policy()
    assert policy["headline_eligible"] is False
    assert policy["scientific_status"] == "pending_ratified_headline_rule"
    assert policy["headline_ineligible_reason"] == "matrix_headline_rule_not_ratified"
    reason = policy["headline_ineligible_reason"].lower()
    for marker in _EPISODE_A_MARKERS:
        assert marker not in reason
    assert "episode_a" not in policy["scientific_status"]


def test_matrix_completed_valid_not_auto_marked_episode_a_ineligible():
    """A genuine matrix COMPLETED_VALID row is factually complete; matrix policy
    is separate and must not inject Episode-A ineligibility into the ledger."""
    cell = ManifestCell(
        run_id="matrix_run", task_id="probe1", condition_id="ck_strict", episode=None
    )
    led = TerminalLedger([cell])
    led.record(
        cell.cell_id,
        ExecutionOutcome.completed_valid(
            cell=cell, output='{"answer":"ok"}', decision="accept"
        ),
    )
    d = led.diagnostic_counts()
    assert d["accepted_n"] == 1
    assert d["scientific_completion_n"] == 1
    assert "headline_ineligible_reason" not in d
    # Matrix policy (caller) may still be unratified — but not Episode-A.
    root = Path(__file__).resolve().parents[1]
    mod = _load_experiment("matrix2", root / "experiments" / "run_matrix.py")
    policy = mod.matrix_headline_policy()
    assert "episode_a" not in policy["headline_ineligible_reason"]
    assert "episode_a" not in policy["scientific_status"]
    # Facts + policy must not be conflated: sci completion can be > 0 while
    # headline_eligible remains false for unratified matrix rule.
    assert d["scientific_completion_n"] >= 1
    assert policy["headline_eligible"] is False


# ---------------------------------------------------------------------------
# 6. All-failure vs completed matrix runs differ observably
# ---------------------------------------------------------------------------


def test_all_failure_and_completed_matrix_ledgers_differ():
    completed_cells = [
        ManifestCell(run_id="m", task_id=f"p{i}", condition_id="ck_strict")
        for i in range(2)
    ]
    failed_cells = [
        ManifestCell(run_id="m", task_id=f"p{i}", condition_id="ck_strict")
        for i in range(2)
    ]
    ok = TerminalLedger(completed_cells)
    for c in completed_cells:
        ok.record(
            c.cell_id,
            ExecutionOutcome.completed_valid(cell=c, output="{}", decision="accept"),
        )
    bad = TerminalLedger(failed_cells)
    for c in failed_cells:
        bad.record(
            c.cell_id,
            outcome_from_inference(
                InferenceResult(
                    status=RunStatus.TIMEOUT,
                    output=None,
                    error="timed out",
                    elapsed_seconds=1.0,
                    timeout_seconds=90.0,
                ),
                cell=c,
            ),
        )
    o, b = ok.diagnostic_counts(), bad.diagnostic_counts()
    assert o["accepted_n"] == 2 and b["accepted_n"] == 0
    assert o["inference_completed_n"] == 2 and b["inference_completed_n"] == 0
    assert o["failed_n"] == 0 and b["failed_n"] == 2
    assert o["scientific_completion_n"] == 2 and b["scientific_completion_n"] == 0


# ---------------------------------------------------------------------------
# 7. No headline eligibility from inference_completed_n alone
# ---------------------------------------------------------------------------


def test_no_caller_infers_headline_from_inference_completed_alone():
    root = Path(__file__).resolve().parents[1]
    cont = _load_experiment("c3", root / "experiments" / "run_continuity.py")
    mat = _load_experiment("m3", root / "experiments" / "run_matrix.py")
    # Even with high inference_completed_n (simulated), policies stay ineligible.
    high_inf = {
        "inference_completed_n": 100,
        "scientific_completion_n": 0,
        "accepted_n": 0,
    }
    cp = cont.continuity_headline_policy()
    mp = mat.matrix_headline_policy()
    assert high_inf["inference_completed_n"] > 0
    assert cp["headline_eligible"] is False
    assert mp["headline_eligible"] is False
    # Eligibility is not a function of inference_completed_n in either policy.
    assert "inference" not in cp["headline_ineligible_reason"]
    assert "inference" not in mp["headline_ineligible_reason"]
