"""Supersession only works if the correction travels as far as the claim.

MODEL_LADDER.md on public main pointed readers at a corrections/ path that
404'd, because .gitignore excluded experiments/runs/ in directory form and
`git add -A` silently skipped the nested files. The claim was public; the
correction was on one laptop. This test is the mechanical invariant that
closes that class -- no new subsystem, just a check that cannot be forgotten.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tracked(path: Path) -> bool:
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))],
        cwd=ROOT, capture_output=True,
    )
    return r.returncode == 0


def test_every_correction_manifest_is_tracked_by_git():
    corrections = sorted(ROOT.glob("experiments/runs/*/corrections/*.json"))
    assert corrections, "expected at least one correction manifest on disk"
    untracked = [str(p.relative_to(ROOT)) for p in corrections if not _tracked(p)]
    assert not untracked, (
        "correction manifests exist on disk but are NOT tracked by git, so the "
        f"correction cannot reach anyone the original claim reached: {untracked}"
    )


def test_raw_ladder_artifacts_are_tracked():
    """The evidence a correction supersedes must also be public."""
    artifacts = sorted(ROOT.glob("experiments/runs/ladder_*/*.json"))
    assert artifacts, "expected committed raw ladder artifacts"
    untracked = [str(p.relative_to(ROOT)) for p in artifacts if not _tracked(p)]
    assert not untracked, f"raw evidence untracked: {untracked}"
