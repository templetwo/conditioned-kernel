# RUN 00.8B.2 — Mandatory Publication-Gate Wiring

**Base HEAD (pre-edit):** `bf6eb9583615a256a4fbcc67fa4067d5f6b45d70`  
**Branch:** `grok/ck-run-00-8b-2-publication-gate-wiring`

## Defect

RUN 00.8B.1 verifier existed but had **no production caller**.
Verification true in design, false in operation — third occurrence of the pattern.

## Invariant

No governed run may claim `publication_complete` / `review_ready` /
`release_ready` unless `verify_artifact_publication(...)` was executed and
returned `publication_complete=true`.

Caller-supplied booleans for those fields are not accepted.

## Authority path

```text
finalize_governed_run(...)
  → verify_artifact_publication(...)   # always
  → derive gates
  → write publication_receipt.json + finalization_receipt.json
  → fail closed unless allow-incomplete
```

Module: `src/conditioned_kernel/governed_run_finalization.py`

## CLI

```text
ck verify-publication --run-dir <path> --commit-ref <ref>
ck finalize-governed-run --run-dir <path> --commit-ref <ref> [--execution-complete]

python -m conditioned_kernel.artifact_publication verify-publication ...
python -m conditioned_kernel.artifact_publication finalize-governed-run ...
```

Exit code **0** only when `publication_complete=true`.

## Production callers

- `ollama_commissioning.execute_commissioning_run` invokes `finalize_governed_run`
  after writing the artifact manifest (staging mode for pre-commit; derived
  flags written into terminal_report).
- CLI / module entry points for CI and review.

## Orthogonal flags

| Flag | Source |
|---|---|
| execution_complete | caller / run outcome |
| publication_complete | verifier only |
| scientific_completion | always false in this path |
