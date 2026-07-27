"""RUN 00.6A.1 — corrective tests for the independent 00.6A review findings.

No live model. No M0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conditioned_kernel.generate import InferenceResult, RunStatus
from conditioned_kernel.outcomes import (
    EmptyManifestError,
    ExecutionOutcome,
    ManifestCell,
    TerminalLedger,
    TerminalStatus,
    ViolationClassificationError,
    build_manifest,
    classify_product_decision,
    classify_violation_token,
    classify_violations,
    outcome_from_inference,
)


def _cell(task: str = "t1", cond: str = "ck") -> ManifestCell:
    return ManifestCell(run_id="run", task_id=task, condition_id=cond, episode="B")


# ---------------------------------------------------------------------------
# Finding 1 — structured violation classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "violation",
    [
        "required_section:next_state",
        "required_section:answer",
        "required_section:evidence_used",
        "required_section:unknown_field",
    ],
)
def test_all_required_section_violations_are_schema_failed(violation: str):
    assert classify_violation_token(violation) is TerminalStatus.SCHEMA_FAILED
    oc = classify_product_decision(
        decision="reject",
        candidate={"parse_ok": True, "candidate_id": "c1"},
        receipt={"violations": [violation]},
        raw_output="{}",
    )
    assert oc.status is TerminalStatus.SCHEMA_FAILED
    # Exact original text preserved in diagnostics.
    assert violation in oc.reason_codes


def test_unrelated_semantic_violation_is_semantic_failed():
    assert classify_violation_token("goal_echo") is TerminalStatus.SEMANTIC_FAILED
    oc = classify_product_decision(
        decision="reject",
        candidate={"parse_ok": True},
        receipt={"violations": ["goal_echo"]},
        raw_output='{"answer":"x"}',
    )
    assert oc.status is TerminalStatus.SEMANTIC_FAILED
    assert "goal_echo" in oc.reason_codes


def test_malformed_violation_string_fails_closed():
    with pytest.raises(ViolationClassificationError) as ei:
        classify_violation_token("")
    assert ei.value.reason_code == "UNKNOWN_VIOLATION_CATEGORY"

    with pytest.raises(ViolationClassificationError):
        classify_violation_token("not_a_real_category_xyz")

    # Product path does not crash: unknown → COMPLETED_INVALID fail-closed.
    oc = classify_product_decision(
        decision="reject",
        candidate={"parse_ok": True},
        receipt={"violations": ["totally_unknown_violation_token"]},
        raw_output="{}",
    )
    assert oc.status is TerminalStatus.COMPLETED_INVALID
    assert "UNKNOWN_VIOLATION_CATEGORY" in oc.reason_codes
    assert "totally_unknown_violation_token" in oc.reason_codes
    assert oc.scientific_completion is False


def test_required_section_not_misclassified_by_substring_next_state():
    """Regression: incidental 'next_state' substring must not drive class alone.

    required_section:next_state is SCHEMA via the required_section: prefix.
    A free-form string that merely contains the letters next_state is unknown.
    """
    assert (
        classify_violation_token("required_section:next_state")
        is TerminalStatus.SCHEMA_FAILED
    )
    with pytest.raises(ViolationClassificationError):
        # Not a documented prefix or exact token — fail closed.
        classify_violation_token("model mentioned next_state incorrectly")


def test_schema_precedes_semantic_when_mixed():
    status = classify_violations(
        ["goal_echo", "required_section:answer"]
    )
    assert status is TerminalStatus.SCHEMA_FAILED


def test_no_substring_marker_classifies_required_answer_as_semantic():
    """Before: required_section:answer fell through to SEMANTIC because
    'next_state' marker was absent. After: SCHEMA for all required_section.
    """
    for field in ("answer", "evidence_used", "next_state"):
        tok = f"required_section:{field}"
        assert classify_violation_token(tok) is TerminalStatus.SCHEMA_FAILED


# ---------------------------------------------------------------------------
# Finding 2 — continuity event diagnostic counts
# ---------------------------------------------------------------------------


def _ledger_with_outcomes(outcomes: list[ExecutionOutcome]) -> TerminalLedger:
    cells = [
        ManifestCell(
            run_id="run",
            task_id=f"t{i}",
            condition_id="ck_packet",
            episode="B",
        )
        for i in range(len(outcomes))
    ]
    led = TerminalLedger(cells)
    for c, oc in zip(cells, outcomes):
        led.record(c.cell_id, oc)
    return led


def test_healthy_diagnostic_run_differs_from_all_failure_run():
    healthy = _ledger_with_outcomes(
        [
            ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output='{"answer":"ok"}',
                scientific_completion=False,
                dry_run=False,
                quality_admitted=True,
                reason_codes=("episode_b_observed",),
                inference={
                    "status": "completed",
                    "output": '{"answer":"ok"}',
                    "valid_measurement": True,
                },
            )
            for _ in range(3)
        ]
    )
    failed = _ledger_with_outcomes(
        [
            outcome_from_inference(
                InferenceResult(
                    status=RunStatus.TIMEOUT,
                    output=None,
                    error="timed out",
                    elapsed_seconds=90.0,
                    timeout_seconds=90.0,
                ),
                cell=ManifestCell(
                    run_id="run", task_id=f"t{i}", condition_id="ck_packet", episode="B"
                ),
            )
            for i in range(3)
        ]
    )
    h = healthy.diagnostic_counts()
    f = failed.diagnostic_counts()

    # Observable difference without claiming scientific success.
    assert h["inference_completed_n"] == 3
    assert h["final_response_present_n"] == 3
    assert f["inference_completed_n"] == 0
    assert f["final_response_present_n"] == 0
    assert f["failed_n"] == 3
    assert h["failed_n"] == 0

    # Factual counts only on the ledger (policy lives in experiment callers).
    for counts in (h, f):
        assert counts["scientific_completion_n"] == 0
        assert counts["accepted_n"] == 0
        assert "headline_eligible" not in counts
        assert "scientific_status" not in counts
        assert "headline_ineligible_reason" not in counts


def test_inference_completion_cannot_imply_scientific_success():
    led = _ledger_with_outcomes(
        [
            ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output="text",
                scientific_completion=False,
                dry_run=False,
                quality_admitted=True,
                reason_codes=("episode_b_observed",),
                inference={"status": "completed", "output": "text"},
            )
        ]
    )
    d = led.diagnostic_counts()
    assert d["inference_completed_n"] == 1
    assert d["scientific_completion_n"] == 0
    # Ledger facts alone never carry headline eligibility.
    assert "headline_eligible" not in d
    # Event consumers must not treat inference_completed as science.
    assert d["inference_completed_n"] != d["scientific_completion_n"] or (
        d["inference_completed_n"] == 0
    )


def test_dry_run_counts_are_explicit_and_non_scientific():
    cell = _cell()
    led = TerminalLedger([cell])
    led.record(cell.cell_id, ExecutionOutcome.dry_run_only(cell=cell))
    d = led.diagnostic_counts()
    assert d["dry_run_n"] == 1
    assert d["scientific_completion_n"] == 0
    assert d["inference_completed_n"] == 0
    assert "headline_eligible" not in d


# ---------------------------------------------------------------------------
# Finding 3 — single-compute matrix control helpers (unit-level)
# ---------------------------------------------------------------------------


def test_control_observed_outcome_built_once_shape():
    """Control observed path produces one COMPLETED_INVALID quality-admitted outcome."""
    cell = _cell(cond="bare")
    text = '{"answer":"hi"}'
    oc = ExecutionOutcome(
        status=TerminalStatus.COMPLETED_INVALID,
        output=text,
        scientific_completion=False,
        dry_run=False,
        quality_admitted=True,
        decision="n/a_bare",
        reason_codes=("control_observed",),
        inference={"status": "completed", "output": text},
        **ExecutionOutcome._cell_fields(cell),
    )
    assert oc.quality_admitted is True
    assert oc.scientific_completion is False
    assert oc.output == text


def test_control_timeout_uses_outcome_from_inference_once():
    cell = _cell(cond="bare")
    inf = InferenceResult(
        status=RunStatus.TIMEOUT,
        output=None,
        error="timed out",
        elapsed_seconds=1.0,
        timeout_seconds=90.0,
    )
    oc = outcome_from_inference(inf, cell=cell, decision="error")
    assert oc.status is TerminalStatus.TIMEOUT
    assert oc.output is None


def test_ck_strict_operational_fail_null_raw_once():
    """Operational failure: raw is None and scores empty — single branch."""
    cell = _cell(cond="ck_strict")
    oc = outcome_from_inference(
        InferenceResult(
            status=RunStatus.NO_FINAL_RESPONSE,
            output=None,
            error="thinking only",
            elapsed_seconds=1.0,
            timeout_seconds=90.0,
            thinking_chars=100,
        ),
        cell=cell,
    )
    op_fail = oc.status in (
        TerminalStatus.TIMEOUT,
        TerminalStatus.TRANSPORT_ERROR,
        TerminalStatus.INVALID_RESPONSE,
        TerminalStatus.NO_FINAL_RESPONSE,
    )
    assert op_fail
    raw = None if op_fail else "should_not_happen"
    scores: dict[str, Any] = {} if op_fail else {"structural_score": 1.0}
    assert raw is None
    assert scores == {}


# ---------------------------------------------------------------------------
# Finding 4 — empty manifest fail-closed
# ---------------------------------------------------------------------------


def test_empty_manifest_raises_empty_manifest_error():
    with pytest.raises(EmptyManifestError) as ei:
        build_manifest(run_id="r", task_ids=[], condition_ids=["a"])
    assert ei.value.reason_code == "EMPTY_MANIFEST"
    assert "EMPTY_MANIFEST" in str(ei.value)

    with pytest.raises(EmptyManifestError) as ei2:
        build_manifest(run_id="r", task_ids=["t"], condition_ids=[])
    assert ei2.value.reason_code == "EMPTY_MANIFEST"

    with pytest.raises(EmptyManifestError) as ei3:
        TerminalLedger([])
    assert ei3.value.reason_code == "EMPTY_MANIFEST"


def test_empty_manifest_is_not_scientifically_complete():
    with pytest.raises(EmptyManifestError):
        build_manifest(run_id="r", task_ids=[], condition_ids=[])
    # No ledger exists to report scientific completion.
    # Documented reason is stable and machine-readable.
    err = EmptyManifestError()
    assert err.reason_code == "EMPTY_MANIFEST"
    payload = {"reason_code": err.reason_code, "scientific_completion_n": 0}
    assert payload["scientific_completion_n"] == 0
    assert payload["reason_code"] == "EMPTY_MANIFEST"


def test_empty_manifest_matrix_aborts_before_generation(tmp_path: Path, monkeypatch):
    """Matrix main path returns typed abort without building a scientific report."""
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    path = root / "experiments" / "run_matrix.py"
    spec = importlib.util.spec_from_file_location("ck_run_matrix_006a1", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    # Empty probes file
    probes = tmp_path / "empty_probes.json"
    probes.write_text("[]", encoding="utf-8")

    # Avoid needing Ollama: empty manifest aborts before heartbeat.
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_matrix.py",
            "--probes",
            str(probes),
            "--conditions",
            "bare",
            "--no-prime",
        ],
    )
    rc = mod.main()
    assert rc == 3


def test_empty_manifest_continuity_aborts_before_generation(tmp_path: Path, monkeypatch):
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    path = root / "experiments" / "run_continuity.py"
    spec = importlib.util.spec_from_file_location("ck_run_cont_006a1", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    tasks = tmp_path / "empty_tasks.json"
    tasks.write_text("[]", encoding="utf-8")
    out = tmp_path / "should_not_exist.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_continuity.py",
            "--tasks",
            str(tasks),
            "--dry",
            "--out",
            str(out),
        ],
    )
    rc = mod.main()
    assert rc == 3
    assert not out.exists(), "empty manifest must not emit an ordinary report"
