"""RUN 00.6A — canonical typed outcomes and manifest terminal ledger.

These tests pin the audited baseline defects (CK-R00-003, CK-R00-004):
product/matrix bypass of typed inference, missing terminal rows, and dry
runs admitted as completed science.

No live model is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conditioned_kernel.generate import InferenceResult, RunStatus
from conditioned_kernel.outcomes import (
    ExecutionOutcome,
    ManifestCell,
    TerminalLedger,
    TerminalLedgerError,
    TerminalStatus,
    classify_inference,
    classify_unknown_status,
    is_scientific_completion,
    outcome_from_inference,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inf(
    status: RunStatus,
    output: str | None = None,
    error: str | None = None,
    thinking_chars: int = 0,
) -> InferenceResult:
    return InferenceResult(
        status=status,
        output=output,
        error=error,
        elapsed_seconds=1.0,
        timeout_seconds=90.0,
        thinking_chars=thinking_chars,
        final_response_chars=len(output or ""),
    )


def _cell(
    task_id: str,
    condition_id: str,
    *,
    episode: str | None = "B",
    replicate_id: str = "0",
) -> ManifestCell:
    return ManifestCell(
        run_id="run_test",
        task_id=task_id,
        condition_id=condition_id,
        episode=episode,
        replicate_id=replicate_id,
    )


# ---------------------------------------------------------------------------
# 1. Every planned task receives exactly one terminal record
# ---------------------------------------------------------------------------


def test_every_planned_task_has_exactly_one_terminal_record():
    cells = [
        _cell("t1", "ck_packet"),
        _cell("t1", "bare_serialized"),
        _cell("t2", "ck_packet"),
    ]
    ledger = TerminalLedger(cells)
    for c in cells:
        ledger.record(
            c.cell_id,
            outcome_from_inference(
                _inf(RunStatus.TIMEOUT, None, "timed out"),
                cell=c,
            ),
        )
    assert ledger.validate() is True
    assert ledger.terminal_count() == 3
    assert {r.manifest_cell_id for r in ledger.rows()} == {c.cell_id for c in cells}


# ---------------------------------------------------------------------------
# 2. Timeout remains present in the ledger
# ---------------------------------------------------------------------------


def test_timeout_remains_present_in_ledger():
    cell = _cell("t1", "ck_strict")
    ledger = TerminalLedger([cell])
    oc = outcome_from_inference(_inf(RunStatus.TIMEOUT, None, "timed out"), cell=cell)
    ledger.record(cell.cell_id, oc)
    row = ledger.rows()[0]
    assert row.status is TerminalStatus.TIMEOUT
    assert row.output is None
    assert row.scientific_completion is False
    assert is_scientific_completion(row) is False


# ---------------------------------------------------------------------------
# 3. Transport failure remains present in the ledger
# ---------------------------------------------------------------------------


def test_transport_failure_remains_present_in_ledger():
    cell = _cell("t1", "bare")
    ledger = TerminalLedger([cell])
    oc = outcome_from_inference(
        _inf(RunStatus.TRANSPORT_ERROR, None, "Ollama unreachable"),
        cell=cell,
    )
    ledger.record(cell.cell_id, oc)
    row = ledger.rows()[0]
    assert row.status is TerminalStatus.TRANSPORT_ERROR
    assert row.output is None
    assert row.scientific_completion is False


# ---------------------------------------------------------------------------
# 4. No-final-response cannot become an empty successful result
# ---------------------------------------------------------------------------


def test_no_final_response_cannot_become_empty_successful_result():
    cell = _cell("t1", "ck_strict")
    inf = _inf(
        RunStatus.NO_FINAL_RESPONSE,
        None,
        "thinking only",
        thinking_chars=5000,
    )
    oc = outcome_from_inference(inf, cell=cell)
    assert oc.status is TerminalStatus.NO_FINAL_RESPONSE
    assert oc.output is None
    assert oc.scientific_completion is False
    assert oc.quality_admitted is False
    # Coercion trap: callers must not treat missing final as "".
    assert oc.output != ""


# ---------------------------------------------------------------------------
# 5. Invalid response cannot enter completed-valid counts
# ---------------------------------------------------------------------------


def test_invalid_response_cannot_enter_completed_valid_counts():
    cells = [_cell("t1", "ck_strict"), _cell("t2", "ck_strict")]
    ledger = TerminalLedger(cells)
    ledger.record(
        cells[0].cell_id,
        outcome_from_inference(
            _inf(RunStatus.INVALID_RESPONSE, None, "no text field"),
            cell=cells[0],
        ),
    )
    ledger.record(
        cells[1].cell_id,
        ExecutionOutcome.completed_valid(
            cell=cells[1],
            output='{"answer":"ok"}',
            decision="accept",
        ),
    )
    assert ledger.count_status(TerminalStatus.INVALID_RESPONSE) == 1
    assert ledger.count_status(TerminalStatus.COMPLETED_VALID) == 1
    assert ledger.scientific_completion_count() == 1
    assert ledger.scientific_completion_count() != ledger.terminal_count()


# ---------------------------------------------------------------------------
# 6. Dry run cannot count as completed science
# ---------------------------------------------------------------------------


def test_dry_run_cannot_count_as_completed_science():
    cell = _cell("t1", "ck_packet")
    oc = ExecutionOutcome.dry_run_only(cell=cell, reason="offline_plumbing")
    assert oc.status is TerminalStatus.DRY_RUN_ONLY
    assert oc.dry_run is True
    assert oc.scientific_completion is False
    assert oc.quality_admitted is False
    assert oc.output is None
    assert is_scientific_completion(oc) is False

    ledger = TerminalLedger([cell])
    ledger.record(cell.cell_id, oc)
    assert ledger.scientific_completion_count() == 0
    assert ledger.count_status(TerminalStatus.DRY_RUN_ONLY) == 1


# ---------------------------------------------------------------------------
# 7. Product and matrix paths use the canonical typed classifier
# ---------------------------------------------------------------------------


def test_product_and_matrix_paths_use_canonical_typed_classifier():
    """classify_inference is the single map from RunStatus → TerminalStatus."""
    cases = [
        (RunStatus.TIMEOUT, TerminalStatus.TIMEOUT),
        (RunStatus.TRANSPORT_ERROR, TerminalStatus.TRANSPORT_ERROR),
        (RunStatus.INVALID_RESPONSE, TerminalStatus.INVALID_RESPONSE),
        (RunStatus.NO_FINAL_RESPONSE, TerminalStatus.NO_FINAL_RESPONSE),
        (RunStatus.COMPLETED, None),  # not yet terminal; lifecycle continues
    ]
    for run_status, expected in cases:
        got = classify_inference(run_status)
        assert got is expected, f"{run_status} → {got}, expected {expected}"

    # Product-style projection of a timeout InferenceResult
    product = outcome_from_inference(_inf(RunStatus.TIMEOUT, None, "t"), cell=_cell("p", "product"))
    # Matrix-style projection of the same InferenceResult
    matrix = outcome_from_inference(_inf(RunStatus.TIMEOUT, None, "t"), cell=_cell("p", "matrix"))
    assert product.status is matrix.status is TerminalStatus.TIMEOUT
    assert product.output is matrix.output is None


def test_product_pipeline_timeout_classification_survives_pipeline_path(tmp_path: Path):
    """Product run_turn must preserve TIMEOUT via OllamaClient.run, not generate()."""
    from conditioned_kernel.pipeline import run_turn

    class _TimeoutClient:
        def run(self, model_input: dict[str, Any]) -> InferenceResult:
            return _inf(RunStatus.TIMEOUT, None, "Ollama request timed out after 90s")

        def generate(self, model_input: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("product path must not call generate() for scored turns")

    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": "Demonstrate substrate gain under edge budgets.",
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_test",
                "receipt_count_24h": 0,
                "flags": {
                    "sensors": False,
                    "tools": False,
                    "cloud": False,
                    "max_repair_passes": 0,
                    "edge_target": "jetson_orin_nano_8gb",
                    "one_model_only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text("[]", encoding="utf-8")
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")

    result = run_turn(
        "Summarize design intent.",
        state_dir=state_dir,
        logs_dir=logs_dir,
        client=_TimeoutClient(),  # type: ignore[arg-type]
        max_repair=0,
    )
    assert result.execution_outcome is not None
    assert result.execution_outcome.status is TerminalStatus.TIMEOUT
    assert result.execution_outcome.output is None
    assert result.execution_outcome.scientific_completion is False
    assert result.ok is False
    # Must not look like a successful empty answer
    assert result.decision != "accept"


def test_matrix_fair_generate_uses_typed_run_not_string_heuristics():
    """Matrix control path must consume InferenceResult, not exception strings."""
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    path = root / "experiments" / "run_matrix.py"
    spec = importlib.util.spec_from_file_location("ck_run_matrix_00_6a", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid re-exec pollution if already loaded under another name
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    class _TimeoutClient:
        def run(self, model_input: dict[str, Any]) -> InferenceResult:
            return _inf(RunStatus.TIMEOUT, None, "timed out")

        def generate(self, model_input: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("matrix control path must not call generate()")

    # New API: returns InferenceResult (typed), not bare str
    res = mod.fair_generate(
        _TimeoutClient(),  # type: ignore[arg-type]
        "fake-model",
        "hello",
        num_ctx=2048,
        system="sys",
        use_format=False,
    )
    assert isinstance(res, InferenceResult)
    assert res.status is RunStatus.TIMEOUT
    assert res.output is None
    terminal = outcome_from_inference(res, cell=_cell("probe1", "bare"))
    assert terminal.status is TerminalStatus.TIMEOUT


# ---------------------------------------------------------------------------
# 8. Duplicate terminal records are rejected
# ---------------------------------------------------------------------------


def test_duplicate_terminal_records_are_rejected():
    cell = _cell("t1", "ck_packet")
    ledger = TerminalLedger([cell])
    oc = outcome_from_inference(_inf(RunStatus.TIMEOUT, None, "t"), cell=cell)
    ledger.record(cell.cell_id, oc)
    with pytest.raises(TerminalLedgerError, match="duplicate"):
        ledger.record(cell.cell_id, oc)


# ---------------------------------------------------------------------------
# 9. Missing terminal records are detected
# ---------------------------------------------------------------------------


def test_missing_terminal_records_are_detected():
    cells = [_cell("t1", "a"), _cell("t1", "b")]
    ledger = TerminalLedger(cells)
    ledger.record(
        cells[0].cell_id,
        outcome_from_inference(_inf(RunStatus.TIMEOUT, None, "t"), cell=cells[0]),
    )
    with pytest.raises(TerminalLedgerError, match="missing"):
        ledger.validate()
    missing = ledger.missing_cell_ids()
    assert cells[1].cell_id in missing


# ---------------------------------------------------------------------------
# 10. Unknown statuses fail closed
# ---------------------------------------------------------------------------


def test_unknown_statuses_fail_closed():
    with pytest.raises(ValueError, match="unknown"):
        classify_unknown_status("probably_fine")
    with pytest.raises(ValueError, match="unknown"):
        classify_unknown_status("")
    with pytest.raises(ValueError, match="unknown"):
        classify_unknown_status(None)

    # Known terminal values are accepted
    assert classify_unknown_status("timeout") is TerminalStatus.TIMEOUT
    assert classify_unknown_status(TerminalStatus.DRY_RUN_ONLY) is TerminalStatus.DRY_RUN_ONLY
    assert classify_unknown_status(RunStatus.NO_FINAL_RESPONSE) is TerminalStatus.NO_FINAL_RESPONSE


def test_dry_pipeline_marks_dry_run_only_not_scientific(tmp_path: Path):
    """dry_candidate_text is plumbing: never scientific completion."""
    from conditioned_kernel.pipeline import run_turn

    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": (
                    "Demonstrate conditioned-kernel substrate gain over bare generation "
                    "on a small local model under Jetson Orin Nano 8GB edge budgets."
                ),
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_test",
                "receipt_count_24h": 0,
                "flags": {
                    "sensors": False,
                    "tools": False,
                    "cloud": False,
                    "max_repair_passes": 0,
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
                }
            ]
        ),
        encoding="utf-8",
    )
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    dry = json.dumps(
        {
            "answer": (
                "Design intent is edge-first substrate conditioning: keep models small "
                "and local, put continuity in files, measure gain under Jetson budgets."
            ),
            "evidence_used": [
                "This system is fully local.",
                "Edge target: jetson_orin_nano_8gb (one model at a time).",
            ],
            "next_state": {"thread_touch": ["thread_min_model"]},
        }
    )
    result = run_turn(
        "Summarize design intent.",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        max_repair=0,
    )
    assert result.execution_outcome is not None
    assert result.execution_outcome.status is TerminalStatus.DRY_RUN_ONLY
    assert result.execution_outcome.scientific_completion is False
    assert result.execution_outcome.dry_run is True
    # Plumbing may still exercise accept for offline circuit tests
    assert result.ok is True
    assert result.decision == "accept"


def test_failed_cell_does_not_disappear_from_planned_denominator():
    cells = [
        _cell("ok", "ck_packet"),
        _cell("fail", "ck_packet"),
        _cell("fail", "bare_serialized"),
    ]
    ledger = TerminalLedger(cells)
    ledger.record(
        cells[0].cell_id,
        ExecutionOutcome.completed_valid(cell=cells[0], output="{}", decision="accept"),
    )
    ledger.record(
        cells[1].cell_id,
        outcome_from_inference(
            _inf(RunStatus.TRANSPORT_ERROR, None, "boom"),
            cell=cells[1],
        ),
    )
    ledger.record(
        cells[2].cell_id,
        ExecutionOutcome.not_run(
            cell=cells[2],
            reason="blocked_by_episode_a",
            blocked_by_manifest_cell_id=cells[1].cell_id,
        ),
    )
    assert ledger.validate() is True
    assert ledger.terminal_count() == 3  # planned denominator
    assert ledger.scientific_completion_count() == 1
    statuses = {r.manifest_cell_id: r.status for r in ledger.rows()}
    assert statuses[cells[1].cell_id] is TerminalStatus.TRANSPORT_ERROR
    assert statuses[cells[2].cell_id] is TerminalStatus.NOT_RUN


def test_empty_string_is_not_successful_no_final_response():
    """Genuinely observed empty final is COMPLETED at inference layer;
    NO_FINAL_RESPONSE remains distinct and never becomes ''."""
    empty = _inf(RunStatus.COMPLETED, "")
    no_final = _inf(RunStatus.NO_FINAL_RESPONSE, None, "thinking only", thinking_chars=100)
    assert empty.output == ""
    assert empty.observed is True
    assert no_final.output is None
    assert no_final.observed is False
    # Terminal projection keeps the distinction
    cell = _cell("t", "c")
    oc_empty = outcome_from_inference(empty, cell=cell)
    # COMPLETED is not terminal by itself — projection returns provisional or
    # requires explicit lifecycle finalization. If projected as non-terminal
    # marker, status must not be NO_FINAL_RESPONSE.
    assert oc_empty.status is not TerminalStatus.NO_FINAL_RESPONSE
    oc_nf = outcome_from_inference(no_final, cell=cell)
    assert oc_nf.status is TerminalStatus.NO_FINAL_RESPONSE
    assert oc_nf.output is None
