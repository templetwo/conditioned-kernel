# RUN 00.8B.1 — Implementation Receipt

**Base:** `39dc0ec3603a3a4a2f63a292a91a598503558d79`  
**Branch:** `grok/ck-run-00-8b-1-artifact-publication-invariant`  
**M0:** NO-GO · Adaptive: HOLD · No models

## Original silent-ignore reproduction

1. `.gitignore` has `experiments/runs/*` plus selective `!experiments/runs/<prefix>_*/`  
2. A **novel** prefix (e.g. `future_family_xyz_01`) is **not** allowlisted  
3. `git add -A` stages reports/docs outside runs but **omits** nested evidence  
4. `verify_artifact_publication` returns `publication_complete=false` with
   `GOVERNED_ARTIFACT_IGNORED` and/or `GOVERNED_ARTIFACT_UNTRACKED`

Regression: `test_ignored_artifact_fails` (novel prefix).

## Generalized failure class

Deny-by-default + manual prefix allowlist → silent evidence omission.

## Verifier architecture

See `RUN_00_8B_1_ARTIFACT_PUBLICATION_SPEC.md`.  
`publication_complete` derived from six checks; gates `review_ready` /
`release_ready` only when complete.

## Git evidence commands

```text
git check-ignore -q <path>
git ls-files --error-unmatch <path>
git cat-file -e <commit>:<path>
git show <commit>:<path> | sha256
```

## RUN 00.8B verification against 39dc0ec

| Metric | Value |
|---|---|
| declared (manifest entries) | 63 |
| existing / hash-verified | 63 / 63 |
| tracked / committed | 63 / 63 |
| git ls-files under run | **64** (includes artifact_manifest_hashes.json) |
| ignored / untracked / absent | 0 |
| publication_complete | **true** |
| retired manifest 9ec3d37a… | unchanged |

## Commands

```text
pytest -q tests/test_run_00_8b_1_artifact_publication.py
14 passed

pytest -q
454 passed
```

## Files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/artifact_publication.py` | created |
| `tests/test_run_00_8b_1_artifact_publication.py` | created |
| `docs/adaptive/RUN_00_8B_1_*.md` | created |

## Untouched

- RUN 00.8B evidence bytes  
- scorer / scientific semantics  
- no model invocation  
- retired candidate manifest  

## Remaining limitations

- Artifact manifest does not self-list; 64th file verified via `git ls-files`  
- Report claim check focuses on evidence-hash field names and path-like tokens  
- Broader un-ignore redesign deferred; verifier is authoritative  

## Ready for independent review?

**Yes.**
