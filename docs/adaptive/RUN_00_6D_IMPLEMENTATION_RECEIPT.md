# RUN 00.6D — Implementation Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6d-controls`  
**Starting commit:** `b67fa2b0879830559dc9c19942f5647549763f78`  
**Disposition:** packet sufficiency + control contracts implemented offline;
amended by **RUN 00.6D.1** (C1 construction-time match). M0 remains `NO-GO`

## 1. Mission

Repair packet and control contracts so a future M0 comparison can isolate
structured substrate continuity under exact UTF-8 byte budget matching.

No models were run. No matrix. No M0.

## 2. Frozen condition definitions

See `RUN_00_6D_CONTROL_MATRIX.md`:

- **C0** bare  
- **C1** budget-matched bare (primary structure control)  
- **C2** instruction-identical static  
- **C3** static Conditioned Kernel  

## 3. Task-dependency annotation schema

Version `ck.task_dep.v1`. Fields: `field_id`, `classification` (closed enum),
`value`. Fixture: `tests/fixtures/control_task_live_plumbing_01.json`.

## 4. Final-byte serialization method

```text
UTF-8(canonical_json({
  model, messages[system,user], format, stream:false,
  options:{temperature, seed, num_ctx}
}))
```

`sort_keys=True`, compact separators. No silent Unicode normalization.

## 5. Unicode handling

Exact UTF-8 of the Python string as provided. NFC/NFD differences are real
byte differences (adversarial fixture covered).

## 6. Padding mechanism

`ck.padding.spaces_v1`: optional delimiter `\n<<CK_PAD>>\n` + U+0020 spaces
only, searched to hit exact complete-request length. Scanned for ids,
relations, and forbidden fragments.

## 7. Control-verifier fields

Documented in `RUN_00_6D_CONTROL_CONTRACT.md`. Failed cells carry
`CONTROL_CONTRACT_FAILED` and remain in planned ledger denominators
(`test_failed_control_retained_in_ledger_denominator`).

## 8. Adversarial fixture results

Covered in `tests/test_run_00_6d_controls.py`:

- missing decisive fact → `TASK_FACT_MISMATCH`  
- extra helpful fact → `TASK_FACT_MISMATCH`  
- reordered source fields → identical canonical bytes  
- hidden whitespace in system → different complete bytes  
- Unicode NFC/NFD → different hashes  
- different output-schema key → `OUTPUT_SCHEMA_MISMATCH`  
- padding leak scans for answer/relation/id  
- instruction-identical but byte-different C3 vs C2 disclosed  

## 9. Commands and results

```text
# After 00.6D.1
pytest -q tests/test_run_00_6d_controls.py tests/test_run_00_6d_1_c1_integrity.py
46 passed

pytest -q
251 passed in 3.73s

python -m ruff check src/conditioned_kernel/control_contract.py \
  tests/test_run_00_6d_controls.py tests/test_run_00_6d_1_c1_integrity.py
All checks passed!

python -m mypy --follow-imports=skip src/conditioned_kernel/control_contract.py
Success: no issues found in 1 source file
```

**Proof no models were run:** all 00.6D/00.6D.1 tests are offline fixtures; no
Ollama calls; no live-plumbing smoke in the control amendment.

## 10. Files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/control_contract.py` | created |
| `tests/fixtures/control_task_live_plumbing_01.json` | created |
| `tests/test_run_00_6d_controls.py` | created |
| `docs/adaptive/RUN_00_6D_*.md` | created (5 files) |

## 11. Negative-action confirmation

- no continuity event/receipt semantic change  
- no scorer change  
- no M0 / matrix / prompt tuning  
- no thresholds / adaptive dials / retrieval / tools  
- no semantic judge  
- no `ExecutionScope.SCIENTIFIC_EXPERIMENT` activation  
- no commit/push required by this receipt  

## 12. Ambiguities for Anthony

1. Whether C1 vs C3 should require **identical** complete request bytes (impossible
   with structure contrast) vs **equal length** (implemented).  
2. Whether C2 should later be forced into a secondary byte-match lane.  
3. Which tasks must receive frozen task-dep annotations before M0.  
4. Ratified `experiment_contract_id` string for any future scientific scope.  

## 13. Ready for independent adversarial review?

**Yes — for RUN 00.6D + 00.6D.1** (contracts + C1 construction integrity).

See `RUN_00_6D_1_C1_INTEGRITY_AMENDMENT.md`.

M0 remains `NO-GO`. Continuity scorer repair still pending.
