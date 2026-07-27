"""RUN 00.8B.1 — governed artifact publication invariant."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conditioned_kernel.artifact_publication import (
    finalize_publication_gate,
    sha256_file,
    verify_artifact_publication,
)
from conditioned_kernel.m0_manifest import RETIRED_MANIFEST_SHA256
from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

REPO = Path(__file__).resolve().parents[1]
RUN_8B = REPO / "experiments" / "runs" / "commissioning_00_8b"
COMMIT_8B = "39dc0ec3603a3a4a2f63a292a91a598503558d79"


def test_00_8b_passes_against_commit_39dc0ec():
    assert RUN_8B.is_dir()
    man = RUN_8B / "artifact_manifest_hashes.json"
    rec = verify_artifact_publication(
        RUN_8B,
        man,
        REPO,
        COMMIT_8B,
        run_id="commissioning_00_8b",
        report_paths=[
            RUN_8B / "terminal_report.json",
            REPO / "docs/adaptive/RUN_00_8B_EXECUTION_RECEIPT.md",
        ],
    )
    d = rec.to_dict()
    assert rec.declared_artifact_count == 63  # file entries in artifact_manifest
    assert rec.existing_artifact_count == rec.declared_artifact_count
    assert rec.hash_verified_count == rec.declared_artifact_count
    assert rec.tracked_artifact_count == rec.declared_artifact_count
    assert rec.committed_artifact_count == rec.declared_artifact_count
    assert not rec.missing_paths
    assert not rec.hash_mismatches
    assert not rec.ignored_paths
    assert not rec.untracked_paths
    assert not rec.absent_from_commit_paths
    assert not rec.committed_hash_mismatches
    assert rec.publication_complete is True
    assert rec.review_ready is True
    assert rec.scientific_completion is False
    assert rec.headline_eligible is False
    # Core 00.8B evidence (63 listed + artifact_manifest) remains; later
    # publication receipts may add tracked files without shrinking the set.
    tracked = subprocess.run(
        ["git", "ls-files", "experiments/runs/commissioning_00_8b"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    n = len([ln for ln in tracked.stdout.splitlines() if ln.strip()])
    assert n >= 64
    assert "artifact_manifest_hashes.json" in tracked.stdout
    assert d["m0_authorized"] is False


def test_all_64_evidence_hash_correct_on_disk():
    man = json.loads((RUN_8B / "artifact_manifest_hashes.json").read_text())
    for rel, expected in man.items():
        p = RUN_8B / rel
        assert p.is_file(), rel
        assert sha256_file(p) == expected, rel


def test_retired_manifest_unchanged():
    p = REPO / "experiments/manifests/m0_candidate_v1.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    body = {k: v for k, v in m.items() if k != "manifest_sha256"}
    assert sha256_hex(canonical_json_bytes(body)) == RETIRED_MANIFEST_SHA256
    assert m["manifest_sha256"] == RETIRED_MANIFEST_SHA256


def test_missing_governed_artifact_fails(tmp_path):
    run = tmp_path / "runs" / "gov_a"
    run.mkdir(parents=True)
    (run / "a.json").write_text("{}\n", encoding="utf-8")
    h = sha256_file(run / "a.json")
    man = {"a.json": h, "missing.json": "0" * 64}
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps(man, sort_keys=True), encoding="utf-8"
    )
    # init mini repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    # no commit of files yet
    rec = verify_artifact_publication(
        run,
        run / "artifact_manifest_hashes.json",
        tmp_path,
        "HEAD",
        require_in_commit=False,
        require_tracked=False,
        require_git_not_ignored=False,
    )
    assert rec.publication_complete is False
    assert "GOVERNED_ARTIFACT_MISSING" in rec.reason_codes


def test_hash_mismatched_artifact_fails(tmp_path):
    run = tmp_path / "gov"
    run.mkdir()
    (run / "a.json").write_text("x\n", encoding="utf-8")
    man = {"a.json": "1" * 64}
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps(man), encoding="utf-8"
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    rec = verify_artifact_publication(
        run,
        run / "artifact_manifest_hashes.json",
        tmp_path,
        "HEAD",
        require_in_commit=False,
        require_tracked=False,
        require_git_not_ignored=False,
    )
    assert rec.publication_complete is False
    assert "GOVERNED_ARTIFACT_HASH_MISMATCH" in rec.reason_codes


def test_ignored_artifact_fails(tmp_path):
    """Novel future run prefix silently omitted by ordinary staging; verifier blocks."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    # Same deny-by-default pattern as the real repo
    (tmp_path / ".gitignore").write_text(
        "experiments/runs/*\n"
        "!experiments/runs/ladder_*/\n"
        "!experiments/runs/commissioning_*/\n",
        encoding="utf-8",
    )
    # Novel prefix NOT on allowlist
    run = tmp_path / "experiments" / "runs" / "future_family_xyz_01"
    run.mkdir(parents=True)
    evidence = run / "raw_response.txt"
    evidence.write_text("secret-evidence\n", encoding="utf-8")
    report = run / "terminal_report.json"
    report.write_text(
        json.dumps({"result": "ok", "execution_scope": "commissioning_validation"}),
        encoding="utf-8",
    )
    man = {
        "raw_response.txt": sha256_file(evidence),
        "terminal_report.json": sha256_file(report),
    }
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps(man, indent=2), encoding="utf-8"
    )
    man["artifact_manifest_hashes.json"] = sha256_file(
        run / "artifact_manifest_hashes.json"
    )
    (run / "artifact_manifest_hashes.json").write_text(
        json.dumps(man, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Ordinary staging: report+evidence under ignored prefix stay out
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "future_family_xyz_01" not in staged or "raw_response" not in staged

    rec = verify_artifact_publication(
        run,
        run / "artifact_manifest_hashes.json",
        tmp_path,
        "HEAD",
        require_in_commit=False,
        require_tracked=True,
        require_git_not_ignored=True,
    )
    assert rec.publication_complete is False
    assert "GOVERNED_ARTIFACT_IGNORED" in rec.reason_codes or (
        "GOVERNED_ARTIFACT_UNTRACKED" in rec.reason_codes
    )


def test_untracked_artifact_fails(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    run = tmp_path / "runx"
    run.mkdir()
    f = run / "a.json"
    f.write_text("{}\n", encoding="utf-8")
    man = {"a.json": sha256_file(f)}
    (run / "artifact_manifest_hashes.json").write_text(json.dumps(man), encoding="utf-8")
    # commit empty so HEAD exists
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    rec = verify_artifact_publication(
        run,
        run / "artifact_manifest_hashes.json",
        tmp_path,
        "HEAD",
        require_git_not_ignored=False,
        require_tracked=True,
        require_in_commit=True,
    )
    assert rec.publication_complete is False
    assert (
        "GOVERNED_ARTIFACT_UNTRACKED" in rec.reason_codes
        or "GOVERNED_ARTIFACT_ABSENT_FROM_COMMIT" in rec.reason_codes
    )


def test_absent_from_commit_fails(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    run = tmp_path / "r"
    run.mkdir()
    f = run / "a.json"
    f.write_text("{}\n", encoding="utf-8")
    man = {"a.json": sha256_file(f)}
    mp = run / "artifact_manifest_hashes.json"
    mp.write_text(json.dumps(man), encoding="utf-8")
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    # track but don't commit the evidence? untracked
    # force add and don't commit
    subprocess.run(["git", "add", "-f", str(f), str(mp)], cwd=tmp_path, check=True, capture_output=True)
    # HEAD still without them
    rec = verify_artifact_publication(
        run,
        mp,
        tmp_path,
        "HEAD",
        require_git_not_ignored=False,
        require_tracked=True,
        require_in_commit=True,
    )
    assert rec.publication_complete is False
    assert "GOVERNED_ARTIFACT_ABSENT_FROM_COMMIT" in rec.reason_codes


def test_committed_byte_hash_mismatch_fails(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    run = tmp_path / "r"
    run.mkdir()
    f = run / "a.json"
    f.write_text("v1\n", encoding="utf-8")
    h1 = sha256_file(f)
    man = {"a.json": h1}
    mp = run / "artifact_manifest_hashes.json"
    mp.write_text(json.dumps(man), encoding="utf-8")
    subprocess.run(
        ["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "v1"], cwd=tmp_path, check=True, capture_output=True
    )
    # alter working tree to match manifest still, but change committed content scenario:
    # re-commit wrong content then fix working tree to original hash with wrong commit
    f.write_text("v2-wrong\n", encoding="utf-8")
    man2 = {"a.json": sha256_file(f)}
    mp.write_text(json.dumps(man2), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "v2"], cwd=tmp_path, check=True, capture_output=True
    )
    # Now declare old hash while commit has new bytes
    man_bad = {"a.json": h1}
    mp.write_text(json.dumps(man_bad), encoding="utf-8")
    # disk also wrong vs man_bad
    rec = verify_artifact_publication(
        run,
        man_bad,  # mapping form
        tmp_path,
        "HEAD",
        require_git_not_ignored=False,
        require_tracked=True,
        require_in_commit=True,
    )
    assert rec.publication_complete is False
    assert (
        "GOVERNED_ARTIFACT_HASH_MISMATCH" in rec.reason_codes
        or "GOVERNED_ARTIFACT_COMMITTED_HASH_MISMATCH" in rec.reason_codes
    )


def test_complete_governed_run_passes(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    run = tmp_path / "experiments" / "runs" / "commissioning_mini"
    run.mkdir(parents=True)
    f = run / "a.json"
    f.write_text('{"ok":true}\n', encoding="utf-8")
    man = {"a.json": sha256_file(f)}
    mp = run / "artifact_manifest_hashes.json"
    mp.write_text(json.dumps(man, sort_keys=True), encoding="utf-8")
    # un-ignore like real policy
    (tmp_path / ".gitignore").write_text(
        "experiments/runs/*\n!experiments/runs/commissioning_*/\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "gov"], cwd=tmp_path, check=True, capture_output=True
    )
    rec = verify_artifact_publication(
        run,
        mp,
        tmp_path,
        "HEAD",
    )
    assert rec.publication_complete is True
    assert rec.review_ready is True
    assert rec.release_ready is True


def test_execution_complete_does_not_imply_publication():
    # synthetic incomplete receipt
    from conditioned_kernel.artifact_publication import PublicationReceipt

    inc = PublicationReceipt(publication_complete=False, reason_codes=["GOVERNED_ARTIFACT_MISSING"])
    gate = finalize_publication_gate(execution_complete=True, publication_receipt=inc)
    assert gate["execution_complete"] is True
    assert gate["publication_complete"] is False
    assert gate["review_ready"] is False
    assert gate["release_ready"] is False
    assert gate["scientific_completion"] is False


def test_report_reference_missing_path_fails(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run = tmp_path / "r"
    run.mkdir()
    f = run / "a.json"
    f.write_text("{}\n", encoding="utf-8")
    man = {"a.json": sha256_file(f)}
    mp = run / "artifact_manifest_hashes.json"
    mp.write_text(json.dumps(man), encoding="utf-8")
    report = run / "terminal_report.json"
    report.write_text(
        json.dumps({"path": "cells/C0_bare/raw_response.txt"}),
        encoding="utf-8",
    )
    rec = verify_artifact_publication(
        run,
        mp,
        tmp_path,
        "HEAD",
        report_paths=[report],
        require_git_not_ignored=False,
        require_tracked=False,
        require_in_commit=False,
    )
    assert rec.publication_complete is False
    assert "REPORT_PATH_UNRESOLVED" in rec.reason_codes or rec.report_missing_paths


def test_report_undeclared_evidence_hash_fails(tmp_path):
    run = tmp_path / "r"
    run.mkdir()
    f = run / "a.json"
    f.write_text("{}\n", encoding="utf-8")
    man = {"a.json": sha256_file(f)}
    mp = run / "artifact_manifest_hashes.json"
    mp.write_text(json.dumps(man), encoding="utf-8")
    report = run / "terminal_report.json"
    report.write_text(
        json.dumps({"request_sha256": "ab" * 32}),
        encoding="utf-8",
    )
    rec = verify_artifact_publication(
        run,
        mp,
        tmp_path,
        "HEAD",
        report_paths=[report],
        require_git_not_ignored=False,
        require_tracked=False,
        require_in_commit=False,
    )
    assert rec.publication_complete is False
    assert "REPORT_HASH_UNDECLARED" in rec.reason_codes


def test_scientific_labels_always_false_on_receipt():
    rec = verify_artifact_publication(
        RUN_8B,
        RUN_8B / "artifact_manifest_hashes.json",
        REPO,
        COMMIT_8B,
    )
    d = rec.to_dict()
    assert d["scientific_completion"] is False
    assert d["headline_eligible"] is False
    assert d["m0_authorized"] is False
