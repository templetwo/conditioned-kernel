# RUN 00.8B.1 — Governed Artifact Publication Invariant

## Failure class

A deny-by-default `experiments/runs/*` rule plus a manually maintained prefix
allowlist lets new governed run families disappear from `git add -A` while
reports still commit. Evidence is claimed; bytes never reach the tree.

This is the second occurrence of the same class (ladder corrections; then 00.8B
commissioning evidence).

## Publication invariant

For every path listed in a governed run’s artifact manifest:

1. Exists on disk  
2. SHA-256 matches the manifest  
3. Not silently ignored by current Git rules  
4. Tracked in the index  
5. Present in the intended commit tree  
6. Committed bytes match the declared SHA-256  

`publication_complete` is **derived**, never caller-supplied.

## Finalization gates (orthogonal)

| Flag | Meaning |
|---|---|
| execution_complete | pipeline finished cells |
| publication_complete | all six checks pass |
| review_ready / release_ready | equal publication_complete |
| scientific_completion / headline_eligible | always false here |

Execution-complete ⇏ publication-complete.

## Verifier

Module: `src/conditioned_kernel/artifact_publication.py`

```text
verify_artifact_publication(run_directory, artifact_manifest, repository_root, commit_ref)
```

Uses Git:

- `git check-ignore`
- `git ls-files --error-unmatch`
- `git cat-file -e COMMIT:path`
- `git show COMMIT:path` → SHA-256

Reason codes include:

`GOVERNED_ARTIFACT_IGNORED`, `GOVERNED_ARTIFACT_MISSING`,
`GOVERNED_ARTIFACT_HASH_MISMATCH`, `GOVERNED_ARTIFACT_UNTRACKED`,
`GOVERNED_ARTIFACT_ABSENT_FROM_COMMIT`,
`GOVERNED_ARTIFACT_COMMITTED_HASH_MISMATCH`,
`REPORT_PATH_UNRESOLVED`, `REPORT_HASH_UNDECLARED`.

## Defense in depth

- Keep practical ignore for disposable scratch under `experiments/runs/*`
- Keep explicit allowlists for known families as convenience
- **Authoritative gate:** the generic verifier (works for arbitrary future prefixes)

Do not claim the class is closed merely because `commissioning_*/` was allowlisted.
