# RUN 00.5 — Control Matching Specification

Status: design only  
Applies to: the existing static CK treatment and its existing primary budget-matched bare control  
Does not authorize: a control run, a new condition, a threshold, M0, or a model matrix

## 1. Causal contrast

The primary control must answer one question:

> Holding instructions, task information, response contract, runtime, decoding, and model-visible byte budget fixed, what changes when the same information atoms are organized as the Conditioned Kernel continuity substrate rather than as a deterministic flat serialization?

This is a structure contrast. It is not a bare-versus-informed contrast, an instruction-following contrast, a context-volume contrast, or a format/API contrast.

The current `budget_matched_bare` path does not satisfy this contract. Its system instruction differs from the CK compiler's instruction, its prompt is not actually padded or otherwise proven equal in bytes or tokens, and it is assembled independently from the treatment information set.

## 2. Shared construction inputs

Both arms must be generated from one immutable `ControlInformationSet` produced before either serialization:

```text
ControlInformationSet(
  task_id,
  prompt,
  goal,
  required_facts: tuple[FactAtom, ...],
  included_optional_facts: tuple[FactAtom, ...],
  required_threads: tuple[ThreadAtom, ...],
  included_optional_threads: tuple[ThreadAtom, ...],
  constraints,
  allowed_operations,
  allowed_identifiers,
  output_schema_id,
  profile_id
)
```

This object contains operational information, not serialized prose. It is content-addressed and shared by the treatment and control builders. A builder may rearrange and label these atoms but may not add, remove, summarize, expand, or alter their values.

Gold answers, expected writes, scoring keys, progress-trace keys, correct-action lists, and forbidden-invention examples are excluded before the shared object is built.

## 3. Six matching contracts

### 3.1 Instruction identity

The complete system message bytes are identical. The user-message wrapper outside the representation region is also identical. The instructions must not name either arm and must describe the same task, evidence rule, state-write proposal rule, and JSON response schema.

Both arms receive the same:

- system role and system text bytes;
- user role and fixed wrapper bytes;
- output schema object and schema serialization;
- response-format parameter;
- instruction order;
- forbidden-action language;
- repair policy, if a repair pass is in scope.

Receipt test: `sha256(system_bytes)` and `sha256(wrapper_without_representation_bytes)` are equal across the pair.

### 3.2 Byte or token budget matching

The binding primary contract should be exact UTF-8 byte equality of the complete model-visible messages, combined with identical `num_ctx`. This is deterministic without depending on an unavailable or version-drifting tokenizer.

The shared compiler first ensures that the complete required information set fits both representations. It chooses a fixed representation-region byte length before arm serialization. Each arm is then followed by deterministic ASCII-space padding inside the delimited representation region until both complete user messages have exactly the same UTF-8 length. Padding contains no identifiers, instructions, answer cues, field labels, or state facts.

Required receipt fields:

- unpadded representation bytes for each arm;
- padding bytes for each arm;
- complete system, user, schema, and request-envelope byte counts;
- complete model-visible message SHA-256 values;
- common target byte count;
- `num_ctx`;
- tokenizer identity/version and observed token count when a reliable local tokenizer is available.

The implementation must compare actual serialized request content, not a pre-serialization object or an estimated packet length.

Token counts are diagnostic under the recommended primary contract. Exact byte equality does not generally imply exact tokenizer-token equality because structure and whitespace tokenize differently. Exact simultaneous byte and token equality cannot be guaranteed for arbitrary information sets by one model-agnostic control. If Anthony requires exact token equality as the binding estimand, that requires a model/tokenizer-specific compiler and a separately authorized control contract; it is not silently added by RUN 00.5.

### 3.3 Task-fact identity

Every information atom appears exactly once in both arms with the same canonical value. The pair must have equal multisets of:

- task prompt and requested operation;
- goal;
- fact IDs and values;
- thread IDs, titles, statuses, and allowed relations;
- constraints;
- allowed operations and identifiers.

The flat control may change separators and ordering only as declared below. It may not omit labels whose semantic content is necessary to disambiguate an atom; instead, the treatment/control atom mapping must state which flat delimiter encodes the same relation.

Receipt test: the two arm builders emit the same sorted atom hashes and the same `ControlInformationSet` hash.

### 3.4 Output-schema identity

The response JSON schema, `format` parameter, required keys, nested types, identifier enum/set, maximum-output constraint, parsing logic, validation logic, repair ceiling, and candidate acceptance policy are identical. Both arms use the same return path and corrected scorer.

The control cannot be scored as unconstrained prose while CK is required to emit JSON. Conversely, a control candidate cannot bypass validation merely because it is a control.

### 3.5 Runtime and decoding identity

For a paired cell, the following values are identical and receipt-bound:

- model name and immutable model digest;
- runtime and API mode;
- model load-state policy and warm/cold boundary;
- device and runtime version;
- temperature, seed, context limit, repeat penalty, stop policy, streaming mode, and output limit;
- timeout;
- retry/repair policy;
- schema/format parameter;
- keep-alive policy;
- cache/prompt-residency policy.

Pair order must be predetermined or deterministically counterbalanced by the preregistered manifest. RUN 00.5 does not select a new balancing threshold or execution order; it requires the chosen order to be explicit before execution.

### 3.6 Difference attributable only to continuity substrate structure

The treatment representation may use CK's canonical field names, grouping, typed records, and deterministic priority/order. The control representation must be a deterministic flat sequence derived from the same atoms, using a fixed neutral record syntax and an order that does not itself encode the target answer.

Allowed between-arm differences are limited to:

- hierarchical grouping versus flat records;
- structural field labels/separators needed by those representations;
- ordering prescribed by each representation;
- the amount of inert padding necessary for exact byte equality.

Everything else is invariant. The receipt must produce a machine-readable diff whose paths are all classified as one of those allowed structural differences. An extra fact, missing fact, changed instruction, changed schema, or changed runtime field invalidates the pair before inference.

The honest causal label is therefore **continuity-substrate serialization structure under an equal UTF-8 byte envelope**. It does not isolate some abstract notion of structure from tokenizer effects; observed token counts are reported so that limitation remains visible.

## 4. Canonical arm construction

### CK treatment

Serialize the shared information set through the repaired static packet compiler:

1. fixed contract and task operation;
2. task prompt;
3. state digest/goal;
4. facts as typed canonical records;
5. threads as typed canonical records;
6. constraints and allowed operations/IDs.

### Primary control

Serialize the exact shared atoms as flat records:

```text
CONTEXT_REGION_BEGIN
ATOM|kind=<kind>|id=<canonical-id>|relation=<declared-relation>|value=<canonical-value>
...
CONTEXT_REGION_END
<deterministic ASCII-space padding>
```

The record grammar is pinned and escaped canonically. Records are ordered by a fixed kind order and canonical ID, not by answer relevance, corpus author preference, or expected score. The flat representation contains enough relation typing to convey the same facts; it simply does not group them into the CK substrate hierarchy.

Both representations are inserted into the same wrapper and sent through the same executor and return path.

## 5. Can one control satisfy instruction identity and budget matching?

Yes, for the recommended binding contract: one primary control can have byte-identical instructions and exact total UTF-8 byte equality with CK. The fixed wrapper plus deterministic padding makes those requirements compatible. That single repaired `budget_matched_bare` control is sufficient for the existing protocol's primary comparison; RUN 00.5 does not add another arm.

No, if “budget matching” is redefined to require exact tokenizer-token equality in addition to exact byte equality for every model. Structure changes tokenization, so a model-agnostic single control cannot guarantee both equalities. A tokenizer-specific control would support the narrower contrast “structure at equal model-token count,” but it would be a separate, model-bound estimand requiring Anthony's authorization.

The existing unpaired `headline_vs_budget_matched_bare` aggregate must not be called the primary headline. Only a complete manifest-based paired comparison can support the primary contrast, and an incomplete pair set produces no headline.

## 6. Validation receipt

Before any paired inference, `ControlMatchReceipt` must report:

- pair/manifest cell IDs and shared information-set hash;
- `instruction_identity: true` plus system/wrapper hashes;
- `task_fact_identity: true` plus sorted atom hashes;
- `output_schema_identity: true` plus schema hash;
- `runtime_decoding_identity: true` plus a field-by-field equality map;
- `byte_budget_identity: true` plus complete byte counts;
- token counts and tokenizer identity when available, explicitly marked diagnostic;
- allowed structural diff paths and any unexpected diff paths;
- `eligible_for_primary_contrast`, true only when every binding check passes.

A false or missing binding field makes the pair `NOT_RUN` with reason `CONTROL_MATCH_FAILED`. It must not be run and filtered afterward.

## 7. Required tests

The control tests in `RUN_00_5_TEST_PLAN.md` must prove:

- exact system and wrapper instruction identity;
- exact complete-message byte equality;
- identical task/fact/thread atom hashes;
- identical output schema and validator path;
- identical runtime and decoding settings;
- a diff containing only allowlisted structural/padding paths;
- deterministic rebuilds;
- fail-closed behavior for a missing atom, extra atom, changed instruction, changed schema, byte mismatch, or runtime mismatch.

No control is protocol-valid merely because its file or function name contains `budget_matched`.

## 8. Decision for Anthony

Anthony must ratify whether exact UTF-8 bytes are the binding primary budget contract, with actual token counts reported as diagnostics. No token-delta threshold and no alternate control arm is selected here.
