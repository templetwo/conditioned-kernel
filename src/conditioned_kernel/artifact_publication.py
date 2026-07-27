"""RUN 00.8B.1 — governed artifact publication verifier.

A run is publication-complete only when every artifact listed in the artifact
manifest exists on disk, matches its declared SHA-256, is not git-ignored,
is tracked, and matches the intended commit tree byte-for-byte.

publication_complete is derived, never caller-supplied.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

PUBLICATION_SCHEMA = "ck.artifact_publication_receipt.v1"


class PublicationError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_artifact_manifest(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise PublicationError("ARTIFACT_MANIFEST_INVALID", str(path))
    out: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str) or len(v) != 64:
            raise PublicationError("ARTIFACT_MANIFEST_INVALID", f"{k}={v!r}")
        out[k] = v.lower()
    return out


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


def git_check_ignore(repo: Path, rel_path: str) -> bool:
    """True if path is ignored by git (even if force-added historically)."""
    r = _run_git(repo, "check-ignore", "-q", rel_path)
    return r.returncode == 0


def git_is_tracked(repo: Path, rel_path: str) -> bool:
    r = _run_git(repo, "ls-files", "--error-unmatch", rel_path)
    return r.returncode == 0


def git_blob_hash_at_commit(repo: Path, commit_ref: str, rel_path: str) -> str | None:
    """Return hex sha256 of blob contents at commit, or None if absent."""
    # git show COMMIT:path → file bytes
    r = _run_git(repo, "show", f"{commit_ref}:{rel_path}")
    if r.returncode != 0:
        return None
    # stdout is text mode — re-get as binary
    r2 = subprocess.run(
        ["git", "show", f"{commit_ref}:{rel_path}"],
        cwd=str(repo),
        capture_output=True,
        check=False,
    )
    if r2.returncode != 0:
        return None
    return hashlib.sha256(r2.stdout).hexdigest()


def git_path_exists_in_commit(repo: Path, commit_ref: str, rel_path: str) -> bool:
    r = _run_git(repo, "cat-file", "-e", f"{commit_ref}:{rel_path}")
    return r.returncode == 0


@dataclass
class PublicationReceipt:
    schema_version: str = PUBLICATION_SCHEMA
    run_id: str = ""
    run_directory: str = ""
    artifact_manifest_path: str = ""
    artifact_manifest_sha256: str = ""
    commit_ref: str = ""
    declared_artifact_count: int = 0
    existing_artifact_count: int = 0
    hash_verified_count: int = 0
    tracked_artifact_count: int = 0
    committed_artifact_count: int = 0
    missing_paths: list[str] = field(default_factory=list)
    hash_mismatches: list[str] = field(default_factory=list)
    ignored_paths: list[str] = field(default_factory=list)
    untracked_paths: list[str] = field(default_factory=list)
    absent_from_commit_paths: list[str] = field(default_factory=list)
    committed_hash_mismatches: list[str] = field(default_factory=list)
    report_missing_paths: list[str] = field(default_factory=list)
    report_undeclared_hashes: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    publication_complete: bool = False
    execution_complete: bool | None = None
    review_ready: bool = False
    release_ready: bool = False
    scientific_completion: bool = False
    headline_eligible: bool = False
    m0_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_directory": self.run_directory,
            "artifact_manifest_path": self.artifact_manifest_path,
            "artifact_manifest_sha256": self.artifact_manifest_sha256,
            "commit_ref": self.commit_ref,
            "declared_artifact_count": self.declared_artifact_count,
            "existing_artifact_count": self.existing_artifact_count,
            "hash_verified_count": self.hash_verified_count,
            "tracked_artifact_count": self.tracked_artifact_count,
            "committed_artifact_count": self.committed_artifact_count,
            "missing_paths": list(self.missing_paths),
            "hash_mismatches": list(self.hash_mismatches),
            "ignored_paths": list(self.ignored_paths),
            "untracked_paths": list(self.untracked_paths),
            "absent_from_commit_paths": list(self.absent_from_commit_paths),
            "committed_hash_mismatches": list(self.committed_hash_mismatches),
            "report_missing_paths": list(self.report_missing_paths),
            "report_undeclared_hashes": list(self.report_undeclared_hashes),
            "reason_codes": list(self.reason_codes),
            "publication_complete": self.publication_complete,
            "execution_complete": self.execution_complete,
            "review_ready": self.review_ready,
            "release_ready": self.release_ready,
            "scientific_completion": False,
            "headline_eligible": False,
            "m0_authorized": False,
        }


def verify_artifact_publication(
    run_directory: Path | str,
    artifact_manifest: Path | str | Mapping[str, str],
    repository_root: Path | str,
    commit_ref: str,
    *,
    run_id: str | None = None,
    report_paths: Sequence[Path | str] | None = None,
    require_git_not_ignored: bool = True,
    require_tracked: bool = True,
    require_in_commit: bool = True,
) -> PublicationReceipt:
    """Verify every declared governed artifact for publication completeness."""
    repo = Path(repository_root).resolve()
    run_dir = Path(run_directory)
    if not run_dir.is_absolute():
        run_dir = (repo / run_dir).resolve()
    else:
        run_dir = run_dir.resolve()

    if isinstance(artifact_manifest, Mapping):
        manifest = {str(k): str(v).lower() for k, v in artifact_manifest.items()}
        man_path = run_dir / "artifact_manifest_hashes.json"
        man_sha = ""
        if man_path.is_file():
            man_sha = sha256_file(man_path)
    else:
        man_path = Path(artifact_manifest)
        if not man_path.is_absolute():
            man_path = (repo / man_path).resolve()
        if not man_path.is_file():
            rec = PublicationReceipt(
                run_id=run_id or run_dir.name,
                run_directory=str(run_dir),
                commit_ref=commit_ref,
                reason_codes=["ARTIFACT_MANIFEST_INVALID"],
            )
            return rec
        manifest = load_artifact_manifest(man_path)
        man_sha = sha256_file(man_path)

    # Paths relative to repo for git operations
    try:
        run_rel = run_dir.relative_to(repo)
    except ValueError:
        run_rel = run_dir

    receipt = PublicationReceipt(
        run_id=run_id or run_dir.name,
        run_directory=str(run_rel).replace("\\", "/"),
        artifact_manifest_path=str(
            man_path.relative_to(repo) if man_path.is_relative_to(repo) else man_path
        ).replace("\\", "/"),
        artifact_manifest_sha256=man_sha,
        commit_ref=commit_ref,
        declared_artifact_count=len(manifest),
    )

    reasons: list[str] = []

    for rel, expected in sorted(manifest.items()):
        abs_path = run_dir / rel
        repo_rel = str((run_rel / rel)).replace("\\", "/")

        # 1. exists on disk
        if not abs_path.is_file():
            receipt.missing_paths.append(repo_rel)
            reasons.append("GOVERNED_ARTIFACT_MISSING")
            continue
        receipt.existing_artifact_count += 1

        # 2. disk hash
        actual = sha256_file(abs_path)
        if actual != expected:
            receipt.hash_mismatches.append(f"{repo_rel}:{actual}!={expected}")
            reasons.append("GOVERNED_ARTIFACT_HASH_MISMATCH")
        else:
            receipt.hash_verified_count += 1

        # 3. not ignored (current working tree rules)
        if require_git_not_ignored and git_check_ignore(repo, repo_rel):
            receipt.ignored_paths.append(repo_rel)
            reasons.append("GOVERNED_ARTIFACT_IGNORED")

        # 4. tracked in index
        if require_tracked:
            if git_is_tracked(repo, repo_rel):
                receipt.tracked_artifact_count += 1
            else:
                receipt.untracked_paths.append(repo_rel)
                reasons.append("GOVERNED_ARTIFACT_UNTRACKED")

        # 5–6. present in commit with matching bytes
        if require_in_commit:
            if not git_path_exists_in_commit(repo, commit_ref, repo_rel):
                receipt.absent_from_commit_paths.append(repo_rel)
                reasons.append("GOVERNED_ARTIFACT_ABSENT_FROM_COMMIT")
            else:
                receipt.committed_artifact_count += 1
                blob_hash = git_blob_hash_at_commit(repo, commit_ref, repo_rel)
                if blob_hash is None:
                    receipt.absent_from_commit_paths.append(repo_rel)
                    reasons.append("GOVERNED_ARTIFACT_ABSENT_FROM_COMMIT")
                elif blob_hash != expected:
                    receipt.committed_hash_mismatches.append(
                        f"{repo_rel}:{blob_hash}!={expected}"
                    )
                    reasons.append("GOVERNED_ARTIFACT_COMMITTED_HASH_MISMATCH")

    # Claim/evidence: report path references and evidence file hashes
    if report_paths:
        declared_hashes = set(manifest.values())
        # also accept hashes of files that exist under run_dir even if listed
        for rel, expected in manifest.items():
            declared_hashes.add(expected)

        for rp in report_paths:
            rpath = Path(rp)
            if not rpath.is_absolute():
                rpath = (repo / rpath).resolve()
            if not rpath.is_file():
                receipt.report_missing_paths.append(str(rp))
                reasons.append("REPORT_ARTIFACT_MISSING")
                continue
            try:
                text = rpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            # path-like references under the run directory
            run_prefix = str(run_rel).replace("\\", "/") + "/"
            for line in text.splitlines():
                if run_prefix in line or "cells/" in line:
                    # extract simple relative path tokens
                    for token in line.replace('"', " ").replace("'", " ").split():
                        if token.startswith("cells/") or token.startswith(run_prefix):
                            t = token.split(run_prefix)[-1] if run_prefix in token else token
                            t = t.rstrip(".,;:")
                            if "/" in t and not t.startswith("http"):
                                if t not in manifest and not (run_dir / t).is_file():
                                    # only flag if it looks like our artifact paths
                                    if any(
                                        t.endswith(ext)
                                        for ext in (
                                            ".json",
                                            ".txt",
                                            ".bin",
                                            ".jsonl",
                                        )
                                    ):
                                        if t not in receipt.report_missing_paths:
                                            receipt.report_missing_paths.append(t)
                                            reasons.append("REPORT_PATH_UNRESOLVED")

            # evidence hashes that must appear in the artifact manifest values
            # only check fields that name file content hashes
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                _collect_evidence_hash_claims(
                    obj, declared_hashes, receipt, reasons
                )

    # Derive publication_complete — never accept caller claim
    receipt.reason_codes = _dedupe(reasons)
    receipt.publication_complete = (
        receipt.declared_artifact_count > 0
        and receipt.existing_artifact_count == receipt.declared_artifact_count
        and receipt.hash_verified_count == receipt.declared_artifact_count
        and not receipt.missing_paths
        and not receipt.hash_mismatches
        and not receipt.ignored_paths
        and not receipt.untracked_paths
        and not receipt.absent_from_commit_paths
        and not receipt.committed_hash_mismatches
        and not receipt.report_missing_paths
        and not receipt.report_undeclared_hashes
    )
    # Finalization gates: separate from execution/scientific completion
    receipt.review_ready = receipt.publication_complete
    receipt.release_ready = receipt.publication_complete
    receipt.scientific_completion = False
    receipt.headline_eligible = False
    receipt.m0_authorized = False
    return receipt


def _collect_evidence_hash_claims(
    obj: Any,
    declared_hashes: set[str],
    receipt: PublicationReceipt,
    reasons: list[str],
) -> None:
    """For known evidence-hash fields, require membership in artifact manifest values."""
    evidence_keys = {
        "request_sha256",
        "response_sha256",
        "raw_response_sha256",
        "packet_request_sha256",
    }
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in evidence_keys and isinstance(v, str) and len(v) == 64:
                if v.lower() not in declared_hashes:
                    if v.lower() not in receipt.report_undeclared_hashes:
                        receipt.report_undeclared_hashes.append(v.lower())
                        reasons.append("REPORT_HASH_UNDECLARED")
            else:
                _collect_evidence_hash_claims(v, declared_hashes, receipt, reasons)
    elif isinstance(obj, list):
        for item in obj:
            _collect_evidence_hash_claims(item, declared_hashes, receipt, reasons)


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def assert_publication_complete(receipt: PublicationReceipt) -> None:
    if not receipt.publication_complete:
        raise PublicationError(
            "PUBLICATION_INCOMPLETE",
            ",".join(receipt.reason_codes) or "publication_complete=false",
        )


def finalize_publication_gate(
    *,
    execution_complete: bool,
    publication_receipt: PublicationReceipt,
) -> dict[str, Any]:
    """Separate execution completion from publication readiness."""
    pub = publication_receipt.publication_complete
    return {
        "execution_complete": execution_complete,
        "publication_complete": pub,
        "review_ready": pub,
        "release_ready": pub,
        "scientific_completion": False,
        "headline_eligible": False,
        "m0_authorized": False,
        "note": (
            "execution_complete does not imply publication_complete"
            if execution_complete and not pub
            else "publication gate derived from artifact verifier"
        ),
        "reason_codes": list(publication_receipt.reason_codes),
    }
