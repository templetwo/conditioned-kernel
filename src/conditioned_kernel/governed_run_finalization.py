"""RUN 00.8B.2 — mandatory publication-gate wiring for governed runs.

Authority path: finalize_governed_run always invokes verify_artifact_publication.
No caller-supplied publication_complete / review_ready / release_ready is trusted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from conditioned_kernel.artifact_publication import (
    PublicationReceipt,
    finalize_publication_gate,
    verify_artifact_publication,
)
from conditioned_kernel.paths import repo_root as default_repo_root

FINALIZATION_SCHEMA = "ck.governed_run_finalization.v1"
PUBLICATION_RECEIPT_NAME = "publication_receipt.json"
FINALIZATION_RECEIPT_NAME = "finalization_receipt.json"


class FinalizationError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def _current_head(repo: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise FinalizationError("GIT_HEAD_UNAVAILABLE", r.stderr.strip())
    return r.stdout.strip()


def _discover_report_paths(run_dir: Path) -> list[Path]:
    candidates = [
        run_dir / "terminal_report.json",
        run_dir / "admission.json",
        run_dir / "preflight.json",
    ]
    return [p for p in candidates if p.is_file()]


def finalize_governed_run(
    *,
    run_dir: Path | str,
    repository_root: Path | str | None = None,
    commit_ref: str | None = None,
    artifact_manifest_path: Path | str | None = None,
    execution_complete: bool = False,
    run_id: str | None = None,
    report_paths: Sequence[Path | str] | None = None,
    staging_mode: bool = False,
    write_receipts: bool = True,
    fail_closed: bool = True,
) -> dict[str, Any]:
    """Authoritative governed-run finalization.

    Always calls verify_artifact_publication. Rejects any attempt to inject
    publication_complete / review_ready / release_ready via kwargs (not accepted).

    staging_mode=True: check disk + ignore + track only (pre-commit).
    staging_mode=False: full commit-tree verification against commit_ref.
    """
    repo = Path(repository_root) if repository_root else default_repo_root()
    repo = repo.resolve()
    run = Path(run_dir)
    if not run.is_absolute():
        run = (repo / run).resolve()
    if not run.is_dir():
        raise FinalizationError("RUN_DIR_MISSING", str(run))

    man_path = (
        Path(artifact_manifest_path)
        if artifact_manifest_path
        else run / "artifact_manifest_hashes.json"
    )
    if not man_path.is_absolute():
        man_path = (repo / man_path).resolve() if not man_path.exists() else man_path
    if not man_path.is_file():
        # try under run dir
        alt = run / "artifact_manifest_hashes.json"
        if alt.is_file():
            man_path = alt
        else:
            raise FinalizationError("ARTIFACT_MANIFEST_MISSING", str(man_path))

    ref = commit_ref or _current_head(repo)
    rid = run_id or run.name
    reports = list(report_paths) if report_paths is not None else _discover_report_paths(run)

    # Core gate — always invoke the accepted verifier
    pub_receipt: PublicationReceipt = verify_artifact_publication(
        run,
        man_path,
        repo,
        ref,
        run_id=rid,
        report_paths=reports,
        require_git_not_ignored=True,
        require_tracked=True,
        require_in_commit=not staging_mode,
    )

    gate = finalize_publication_gate(
        execution_complete=bool(execution_complete),
        publication_receipt=pub_receipt,
    )

    result: dict[str, Any] = {
        "schema_version": FINALIZATION_SCHEMA,
        "run_id": rid,
        "run_directory": str(run),
        "repository_root": str(repo),
        "commit_ref": ref,
        "staging_mode": bool(staging_mode),
        "artifact_manifest_path": str(man_path),
        "execution_complete": gate["execution_complete"],
        "publication_complete": gate["publication_complete"],
        "review_ready": gate["review_ready"],
        "release_ready": gate["release_ready"],
        "scientific_completion": False,
        "headline_eligible": False,
        "m0_authorized": False,
        "efficacy_claim_permitted": False,
        "reason_codes": list(gate["reason_codes"]),
        "publication_receipt": pub_receipt.to_dict(),
        "verifier_invoked": True,
        "note": gate["note"],
    }

    if write_receipts:
        pub_out = run / PUBLICATION_RECEIPT_NAME
        fin_out = run / FINALIZATION_RECEIPT_NAME
        pub_out.write_text(
            json.dumps(pub_receipt.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        fin_out.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        result["publication_receipt_path"] = str(pub_out)
        result["finalization_receipt_path"] = str(fin_out)

    if fail_closed and not result["publication_complete"]:
        raise FinalizationError(
            "PUBLICATION_INCOMPLETE",
            ",".join(result["reason_codes"]) or "publication_complete=false",
        )

    return result


def verify_publication_only(
    *,
    run_dir: Path | str,
    repository_root: Path | str | None = None,
    commit_ref: str | None = None,
    artifact_manifest_path: Path | str | None = None,
    staging_mode: bool = False,
    report_paths: Sequence[Path | str] | None = None,
) -> dict[str, Any]:
    """Verify publication without writing finalization receipts (CLI helper)."""
    repo = Path(repository_root) if repository_root else default_repo_root()
    repo = repo.resolve()
    run = Path(run_dir)
    if not run.is_absolute():
        run = (repo / run).resolve()
    man_path = (
        Path(artifact_manifest_path)
        if artifact_manifest_path
        else run / "artifact_manifest_hashes.json"
    )
    if not man_path.is_file():
        alt = run / "artifact_manifest_hashes.json"
        if alt.is_file():
            man_path = alt
        else:
            raise FinalizationError("ARTIFACT_MANIFEST_MISSING", str(man_path))
    ref = commit_ref or _current_head(repo)
    reports = list(report_paths) if report_paths is not None else _discover_report_paths(run)
    rec = verify_artifact_publication(
        run,
        man_path,
        repo,
        ref,
        run_id=run.name,
        report_paths=reports,
        require_git_not_ignored=True,
        require_tracked=True,
        require_in_commit=not staging_mode,
    )
    return rec.to_dict()
