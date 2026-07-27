# RUN 00.9A — Information-Matching Policy (C3 vs C1)

Byte equality alone is **insufficient**.

## Matched (required where mechanically enforceable)

| Axis | Policy |
|---|---|
| Finalized UTF-8 complete-request length | Equal (C1 padded to C3) |
| Entity mentions (candidate inventory) | Equal counts |
| Relation-label mentions in candidates | Equal inventory |
| Candidate-state item count | Equal |
| Schema instructions / output requirements | Equal |
| Query text | Equal |
| Formatting depth / envelope | Equal where not the treatment |
| Condition-neutral metadata | Equal; no model-visible condition ids |

## Declared treatment difference

**C3** preserves the mapping between relation candidates and accepted/rejected
status (structured verified continuity).

**C1** contains the same candidate items and status-symbol **mass** but breaks
that mapping via a frozen noninformative permutation/assignment.

## Residual confounds (must declare)

- Unmatched free-form lexical residue  
- Tokenizer-level differences after padding  
- Any axis listed as “not guaranteed” must not be claimed as matched  

Do **not** claim semantic equivalence from byte parity alone.

Static gate reason: `INFORMATION_MATCHING_FAILED` / `CONTROL_PACKET_SEMANTIC_MISMATCH`.
