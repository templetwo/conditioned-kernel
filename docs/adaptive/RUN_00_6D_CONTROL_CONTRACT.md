# RUN 00.6D — Control Contract

## Primary budget rule

**Exact UTF-8 byte count equality** of the final serialized runtime request
for budget-matched pairs (C3 vs C1).

Token counts may be recorded later as diagnostics; they are not binding here.

Equality is measured **after** final serialization (`complete_bytes`), not on
templates.

## Padding mechanism (`ck.padding.spaces_v1`)

1. Build unpadded user content (`Packet:\n` + canonical body JSON).  
2. Append fixed delimiter `\n<<CK_PAD>>\n` only if space permits.  
3. Append only U+0020 SPACE bytes until the complete request UTF-8 length equals
   the treatment target.  
4. Padding is scanned for task ids, relation names, and forbidden fragments.  
5. Padding bytes and mechanism version appear on receipts.  

Padding is never model-generated and never meaningful prose.

## Mechanical verifier (`ck.control_verifier.v1`)

Compares two `CompiledPacket`s and reports:

| Field | Role |
|---|---|
| exact UTF-8 byte count | budget |
| SHA-256 of complete input bytes | identity of serialization |
| task-fact set | information identity |
| operational-set | operational identity |
| instruction block hash | instruction identity |
| output-schema hash | schema identity |
| model tag + generation parameters | runtime identity |
| condition / task ids | labeling |
| packet / annotation versions | provenance |

### Verdicts

- `PASS` — no prohibited mismatches  
- `FAIL` — any prohibited mismatch; reason includes `CONTROL_CONTRACT_FAILED`  
- Failed comparisons are **headline-ineligible** and **not scientific**  

### Prohibited mismatches (examples)

- `BYTE_COUNT_MISMATCH` / `ONE_BYTE_DRIFT`  
- `TASK_FACT_MISMATCH`  
- `INSTRUCTION_MISMATCH`  
- `OUTPUT_SCHEMA_MISMATCH`  
- `MODEL_TAG_MISMATCH`  
- `GENERATION_PARAMETER_MISMATCH`  

### Intended differences (disclosed, not failures)

For C3 vs C1:

- C3 carries reconstructed `accepted_relations` organization  
- C1 is flat; may include inert padding  

## Scientific-experiment guard

`ExecutionScope.SCIENTIFIC_EXPERIMENT` requires a ratified
`experiment_contract_id`. Omitted id fails closed. Candidate acceptance alone
does not activate run-level scientific completion.

Control receipts always set `scientific_completion=false`.

## Control-integrity receipt

Each comparison emits:

- condition pair  
- left/right byte counts and input hashes  
- declared intended differences  
- prohibited mismatches  
- padding disclosure  
- packet contract + task-dep versions  
- verifier version  
- repo commit (when provided)  
- `headline_eligible` only if verdict PASS  
- `scientific_completion=false` always  
