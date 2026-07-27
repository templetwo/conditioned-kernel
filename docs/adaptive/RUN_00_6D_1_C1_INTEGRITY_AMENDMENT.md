# RUN 00.6D.1 — C1 Integrity Amendment

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6d-controls`  
**Base commit:** `3abd15e54027f55f88edbb97486b95a187f52455`  
**Disposition:** C1 construction fails closed without verified byte-length match

## 1. Original reproduction

```python
compile_condition_packet(ConditionId.C1_BUDGET_MATCHED_BARE, ann, runtime)
# previously returned a C1-labeled packet with no padding / no match
```

Also present: dead `apply_space_padding()` unused by production (actual path
`_pad_user_to_complete_target`).

## 2. Root cause

C1 padding branch was gated on `target_complete_bytes is not None`, so a direct
caller could omit the target and still receive a packet labeled
`C1_budget_matched_bare` without mechanical byte-length verification.

## 3. Fail-closed behavior

| Input | Reason code |
|---|---|
| missing target | `C1_TARGET_REQUIRED` |
| `0`, negative, non-int, bool | `C1_TARGET_INVALID` |
| target < unpadded complete length | `C1_TARGET_UNREACHABLE` |
| pad search cannot hit length | `C1_TARGET_UNREACHABLE` |
| final length ≠ target after pad | `C1_BYTE_MATCH_FAILED` |

No C1 object is returned unless:

```text
len(final_serialized_C1_utf8) == target_complete_bytes
byte_match_verified == true
paired_condition == C3_static_ck
```

## 4. Target semantics

`target_complete_bytes` = finalized **complete serialized request** UTF-8
length of the paired **C3** packet (messages + format + options), not a
template estimate.

## 5. Construction-time vs pair-builder verification

1. **Inside C1 construction:** length check before return; fields recorded.  
2. **Pair builder defense-in-depth:** re-checks `byte_match_verified` and
   `actual == c3.byte_count`, then runs `verify_c3_vs_c1`.

## 6. Dead-code disposition

Removed `apply_space_padding()`. Sole production pad path:
`_pad_user_to_complete_target()` (delimiter + U+0020 spaces).

## 7. Test-first failures

New tests expected the unfixed path to mislabel C1 / leave dead code. After fix:

```text
pytest -q tests/test_run_00_6d_1_c1_integrity.py tests/test_run_00_6d_controls.py
46 passed

pytest -q
251 passed in 3.79s
```

## 8. Files changed

| Path | Change |
|---|---|
| `src/conditioned_kernel/control_contract.py` | mandatory C1 target; verified fields; remove dead pad |
| `tests/test_run_00_6d_1_c1_integrity.py` | **created** |
| `tests/test_run_00_6d_controls.py` | C1-target-aware updates |
| `docs/adaptive/RUN_00_6D_1_C1_INTEGRITY_AMENDMENT.md` | this file |
| `docs/adaptive/RUN_00_6D_CONTROL_CONTRACT.md` | note construction-time C1 rule |
| `docs/adaptive/RUN_00_6D_IMPLEMENTATION_RECEIPT.md` | 00.6D.1 note |
| `docs/adaptive/RUN_00_6D_CHANGE_MAP.md` | 00.6D.1 note |

## 9. Negative-action confirmation

- no models, M0, matrix  
- no scorer / threshold / persistence / adaptive changes  
- no `SCIENTIFIC_EXPERIMENT` activation  
- no experiment_contract_id minted  
- successful match does not set scientific_completion or headline_eligible  

## 10. Ready for focused re-review?

**Yes** — for C1 construction integrity and dead-code removal.

M0 remains `NO-GO`.
