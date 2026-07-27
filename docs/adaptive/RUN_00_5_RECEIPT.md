# RUN 00.5 — Receipt

Run: Baseline Integrity Repair Specification  
Date: 2026-07-26  
Disposition: documentation and test design complete; implementation and M0 remain `NO-GO`

## 1. Baseline

- Audited commit: `db668a91e32843c3e53de58325cc17fff4b9c746`
- Starting branch: `codex/ck-run-00-audit`
- Documentation branch created for this run: `codex/ck-run-00-5-spec`
- Ending branch: `codex/ck-run-00-5-spec`
- No commit was created.
- No push was attempted.

## 2. Starting Git status

Captured before creating the RUN 00.5 branch:

```text
## codex/ck-run-00-audit
?? docs/adaptive/
```

The untracked directory already contained the four RUN 00 documents from the preceding authorized audit:

- `docs/adaptive/RUN_00_CURRENT_SYSTEM_AUDIT.md`
- `docs/adaptive/RUN_00_FAILURE_REGISTER.md`
- `docs/adaptive/RUN_00_OPEN_QUESTIONS.md`
- `docs/adaptive/RUN_00_RECEIPT.md`

Those four files were read and left unmodified by RUN 00.5.

## 3. Ending Git status

```text
## codex/ck-run-00-5-spec
?? docs/adaptive/
```

`git diff --name-only` and `git diff --stat` were empty because all RUN 00 and RUN 00.5 documents remain untracked. No tracked file changed.

## 4. Files created

Exactly these six files were created:

1. `docs/adaptive/RUN_00_5_BASELINE_REPAIR_SPEC.md`
2. `docs/adaptive/RUN_00_5_CONTROL_MATCHING_SPEC.md`
3. `docs/adaptive/RUN_00_5_SCORER_REPAIR_SPEC.md`
4. `docs/adaptive/RUN_00_5_TEST_PLAN.md`
5. `docs/adaptive/RUN_00_5_AUTHORITY_NOTE.md`
6. `docs/adaptive/RUN_00_5_RECEIPT.md`

The five non-receipt document hashes are recorded in §11. The receipt cannot embed its own final digest without changing that digest; its external final digest is reported at handoff.

## 5. Materials read

Governing and protocol documents:

- `AGENTS.md`
- `COSMIC.md`
- `README.md`
- `docs/EXPERIMENT_PROTOCOL.md`
- `docs/EDGE_SPEC.md`

All four RUN 00 documents listed in §2 were read in full.

Implementation and experiment paths inspected included:

- `src/conditioned_kernel/state.py`
- `src/conditioned_kernel/compile.py`
- `src/conditioned_kernel/generate.py`
- `src/conditioned_kernel/pipeline.py`
- `src/conditioned_kernel/continuity.py`
- `src/conditioned_kernel/score.py`
- `src/conditioned_kernel/return_path/parse.py`
- `src/conditioned_kernel/return_path/validate.py`
- `src/conditioned_kernel/return_path/assess.py`
- `src/conditioned_kernel/return_path/accept.py`
- `src/conditioned_kernel/return_path/repair.py`
- `experiments/run_continuity.py`
- `experiments/run_matrix.py`
- Episode A/B corpus, product, matrix, compiler, scorer, inference, acceptance, persistence, qualification, and receipt paths cited by RUN 00.

All current tests were inventoried, with focused review of pipeline dry execution, measurement validity/missingness, continuity corpus/scoring, compiler/edge behavior, matrix environment, model qualification, validation, and score aggregation.

## 6. Commands run

Read-only baseline/provenance commands:

```text
git status --short --branch
git rev-parse HEAD
git branch --show-current
git switch -c codex/ck-run-00-5-spec
git diff --name-only
git diff --stat
rg --files ...
rg -n ...
sed -n ...
wc -l ...
```

The ellipses above denote repeated explicit file/search arguments used only to inventory and read the paths listed in §5; no shell command wrote those files.

The repository-mandated Helix path was retried under the repository's supported Node runtime after the default runtime produced an ABI mismatch. Read-only Helix boot, recall, and state inspection succeeded under:

```text
/usr/bin/env PATH=/Users/vaquez/.nvm/versions/node/v20.19.4/bin:/usr/bin:/bin /Users/vaquez/bin/cosmic-cli helix ...
```

- Helix session: `8604b82d-502a-46b8-8261-b8afb96d92f2`
- No Helix write/record command was issued.

Authorized document creation used the patch editor only.

Verification command:

```text
pytest -q
```

No command invoked Ollama, a model, M0, a matrix, a continuity experiment, or a dry scientific run.

## 7. Tests run

Existing offline suite:

```text
........................................................................ [ 84%]
.............                                                            [100%]
85 passed in 2.26s
```

Exit status: `0`.

No new test was implemented or executed. `RUN_00_5_TEST_PLAN.md` is test design only.

## 8. Contradictions found

1. The protocol describes Episode A as doing work and writing state; the audited worker only invokes inference and freezes the original seeded artifacts. It never parses, validates, accepts, or persists model output.
2. Episode B is described as a filesystem cold start from Episode A output; the audited worker recreates the original seed state for Episode B.
3. Task seed facts are written to `current.seed_facts` but the canonical fact accessor ignores them.
4. Corpus threads omit `status`, while the compiler exposes only threads whose status is exactly `open`; the CK treatment therefore loses the corpus threads.
5. The bare continuity artifact path retains task facts/threads that the CK packet omits, so the existing arm contrast is not structure-only.
6. A typed `InferenceResult` exists, but product and matrix execution bypass it or reconstruct status from errors and strings.
7. The continuity dry path initializes rows as completed and the report has no authoritative dry-run exclusion.
8. Episode A failures are skipped with `continue`, and `rows_expected` is derived from surviving rows rather than the planned manifest.
9. The named budget-matched control is neither proven byte/token matched nor fully instruction-identical to CK in the matrix path.
10. The continuity scorer is documented as invalid under identifier shotgunning, yet the runner still emits composite M1/M2 values.
11. Grounding may use original artifacts not visible to the scored arm, so hidden evidence can influence credit.
12. Parser coercions/defaults can turn missing or mistyped schema members into empty structures that later validation treats as present.

These contradictions make the current M0 path protocol-invalid; they do not authorize changing the scientific question.

## 9. Decisions reserved for Anthony

Anthony must decide or approve:

1. exact UTF-8 byte equality as the binding primary budget contract, with tokenizer counts diagnostic;
2. task dependency references and closed-set relational gold annotations in the existing corpus, without changing task content;
3. the durable continuity representation: canonical append-only event with derived views, or a recoverable multi-file transaction;
4. required structured `continuity_assertions` for continuity outputs;
5. whether any optional semantic-paraphrase judge is permitted;
6. the static repair implementation lane;
7. any numeric threshold, weight, cutoff, or utility mapping;
8. M0 execution after a clean implementation and gate receipt;
9. any later commit or push;
10. any Adaptive RUN 01 work.

## 10. Negative-action confirmation

Confirmed for RUN 00.5:

- no production code modified;
- no existing test modified;
- no new test implemented;
- no configuration modified;
- no corpus/task modified;
- no scientific threshold, weight, cutoff, or utility changed;
- no model invoked;
- no matrix run;
- no M0 run;
- no adaptive architecture implemented;
- no new experimental condition added;
- no commit created;
- no push attempted.

The only repository worktree changes are the six authorized Markdown documents in §4; the only Git metadata change is creation of the documentation branch reference.

## 11. Final file verification

Final SHA-256 values:

```text
4c038681fa52348ba285eaf8c4c8a075fe5e6b6358d321814fe9d8bcf18d3054  docs/adaptive/RUN_00_5_BASELINE_REPAIR_SPEC.md
c4d79e987a46f92ddb3398e7d45e10c5618c420a9f90de2f8686baf33a89d7a8  docs/adaptive/RUN_00_5_CONTROL_MATCHING_SPEC.md
a99aacdfce2025639bc2b1225b39714f8d4c9ea9454f028277c6a719a00ad938  docs/adaptive/RUN_00_5_SCORER_REPAIR_SPEC.md
9debb1f4b4c05024c3c57e05a1df15f9f9933a3b298f71f9549252158c112831  docs/adaptive/RUN_00_5_TEST_PLAN.md
c5968fddba0ebb359f7da23dc552b79bcf60f9a8224a31438f43110549454bba  docs/adaptive/RUN_00_5_AUTHORITY_NOTE.md
```

Final disposition: RUN 00.5 stops at documentation and test design. M0, implementation, commits, pushes, and Adaptive RUN 01 remain unauthorized.
