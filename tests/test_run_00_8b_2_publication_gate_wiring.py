"""RUN 00.8B.2 — mandatory publication-gate wiring (no model invocation)."""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

from conditioned_kernel.artifact_publication import sha256_file, verify_artifact_publication
from conditioned_kernel.cli import main as ck_main
from conditioned_kernel.governed_run_finalization import (
    FinalizationError,
    finalize_governed_run,
    verify_publication_only,
)
from conditioned_kernel.ollama_commissioning import execute_commissioning_run

REPO = Path(__file__).resolve().parents[1]
RUN_8B = REPO / "experiments" / "runs" / "commissioning_00_8b"
COMMIT_8B = "39dc0ec3603a3a4a2f63a292a91a598503558d79"


def test_finalizer_invokes_verifier_and_passes_00_8b():
    result = finalize_governed_run(
        run_dir=RUN_8B,
        repository_root=REPO,
        commit_ref=COMMIT_8B,
        execution_complete=True,
        write_receipts=False,
        fail_closed=True,
    )
    assert result["verifier_invoked"] is True
    assert result["publication_complete"] is True
    assert result["review_ready"] is True
    assert result["release_ready"] is True
    assert result["execution_complete"] is True
    assert result["scientific_completion"] is False
    assert result["headline_eligible"] is False
    assert result["m0_authorized"] is False
    assert "publication_receipt" in result
    assert result["publication_receipt"]["publication_complete"] is True


def test_finalizer_rejects_caller_publication_kwargs():
    sig = inspect.signature(finalize_governed_run)
    assert "publication_complete" not in sig.parameters
    assert "review_ready" not in sig.parameters
    assert "release_ready" not in sig.parameters


def test_finalizer_fail_closed_on_missing_manifest(tmp_path):
    d = tmp_path / "empty_run"
    d.mkdir()
    try:
        finalize_governed_run(
            run_dir=d,
            repository_root=tmp_path,
            commit_ref="HEAD",
            staging_mode=True,
            write_receipts=False,
            fail_closed=True,
        )
        assert False, "expected FinalizationError"
    except FinalizationError as e:
        assert e.reason_code == "ARTIFACT_MANIFEST_MISSING"


def test_finalizer_fail_closed_when_ignored(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / ".gitignore").write_text(
        "experiments/runs/*\n!experiments/runs/commissioning_*/\n",
        encoding="utf-8",
    )
    run = tmp_path / "experiments" / "runs" / "novel_prefix_abc_01"
    run.mkdir(parents=True)
    f = run / "evidence.bin"
    f.write_bytes(b"secret\n")
    man = {"evidence.bin": sha256_file(f)}
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps(man, sort_keys=True), encoding="utf-8"
    )
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README", ".gitignore"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    try:
        finalize_governed_run(
            run_dir=run,
            repository_root=tmp_path,
            commit_ref="HEAD",
            staging_mode=True,
            write_receipts=True,
            fail_closed=True,
        )
        assert False, "expected fail closed"
    except FinalizationError as e:
        assert e.reason_code == "PUBLICATION_INCOMPLETE"


def test_cli_verify_publication_exit_0_on_complete():
    code = ck_main(
        [
            "verify-publication",
            "--run-dir",
            str(RUN_8B),
            "--commit-ref",
            COMMIT_8B,
            "--repo-root",
            str(REPO),
        ]
    )
    assert code == 0


def test_cli_verify_publication_exit_nonzero_on_failure(tmp_path):
    run = tmp_path / "bad"
    run.mkdir()
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps({"missing.json": "0" * 64}), encoding="utf-8"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    code = ck_main(
        [
            "verify-publication",
            "--run-dir",
            str(run),
            "--repo-root",
            str(tmp_path),
            "--staging",
        ]
    )
    assert code != 0


def test_cli_finalize_writes_receipts(tmp_path):
    # Copy a minimal complete run is heavy; use 00.8B and write to temp by
    # finalizing 00.8B with write_receipts into that dir is wrong path.
    # Instead finalize 00.8B and check receipts appear (idempotent).
    out_pub = RUN_8B / "publication_receipt.json"
    out_fin = RUN_8B / "finalization_receipt.json"
    if out_pub.exists():
        out_pub.unlink()
    if out_fin.exists():
        out_fin.unlink()
    code = ck_main(
        [
            "finalize-governed-run",
            "--run-dir",
            str(RUN_8B),
            "--commit-ref",
            COMMIT_8B,
            "--repo-root",
            str(REPO),
            "--execution-complete",
        ]
    )
    assert code == 0
    assert out_pub.is_file()
    assert out_fin.is_file()
    fin = json.loads(out_fin.read_text(encoding="utf-8"))
    assert fin["publication_complete"] is True
    assert fin["verifier_invoked"] is True
    assert fin["scientific_completion"] is False


def test_module_cli_verify():
    from conditioned_kernel.artifact_publication import main as mod_main

    code = mod_main(
        [
            "verify-publication",
            "--run-dir",
            str(RUN_8B),
            "--commit-ref",
            COMMIT_8B,
            "--repo-root",
            str(REPO),
        ]
    )
    assert code == 0


def test_execution_complete_true_publication_false_possible(tmp_path):
    run = tmp_path / "partial"
    run.mkdir()
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps({"gone.json": "a" * 64}), encoding="utf-8"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    result = finalize_governed_run(
        run_dir=run,
        repository_root=tmp_path,
        commit_ref="HEAD",
        execution_complete=True,
        staging_mode=True,
        write_receipts=True,
        fail_closed=False,
    )
    assert result["execution_complete"] is True
    assert result["publication_complete"] is False
    assert result["review_ready"] is False
    assert result["release_ready"] is False


def test_ollama_commissioning_module_calls_finalizer():
    src = inspect.getsource(execute_commissioning_run)
    assert "finalize_governed_run" in src
    assert "verify_artifact_publication" not in src or "finalize_governed_run" in src


def test_verify_publication_only_matches_verifier():
    a = verify_publication_only(
        run_dir=RUN_8B,
        repository_root=REPO,
        commit_ref=COMMIT_8B,
    )
    b = verify_artifact_publication(
        RUN_8B,
        RUN_8B / "artifact_manifest_hashes.json",
        REPO,
        COMMIT_8B,
    ).to_dict()
    assert a["publication_complete"] == b["publication_complete"]
    assert a["declared_artifact_count"] == b["declared_artifact_count"]
