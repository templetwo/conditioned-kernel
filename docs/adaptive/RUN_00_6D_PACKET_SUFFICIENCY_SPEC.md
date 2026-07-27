# RUN 00.6D — Packet Sufficiency Specification

**Version:** `ck.packet_contract.v1` / `ck.task_dep.v1`  
**Primary budget contract:** exact UTF-8 byte equality of final runtime serialization  
**Token counts:** diagnostic only

## 1. Sufficiency definition

A packet is **sufficient** only when it contains:

1. Bounded objective  
2. All preregistered **REQUIRED_TASK_FACT** values  
3. All **REQUIRED_OPERATIONAL_STATE** values  
4. The permitted relation / identifier universe (as operational state)  
5. Exact structured output schema  
6. Explicit unknown / no-assertion behavior  

It must **not** include:

- expected assertion / gold labels  
- target relation stated as an answer  
- hidden scoring hints  
- unrelated corpus threads  
- prior free-form model rhetoric  
- adaptive diagnostics  
- a larger model’s solution  

## 2. Field classification (closed-set)

| Class | Meaning |
|---|---|
| `REQUIRED_TASK_FACT` | Must appear; omission fails compilation |
| `REQUIRED_OPERATIONAL_STATE` | Must appear (objective, universes, schema id, …) |
| `OPTIONAL_SUPPORT` | May appear after required content fits |
| `FORBIDDEN_ANSWER_LEAKAGE` | Must never appear in model-visible bytes |
| `IRRELEVANT` | Must not be injected as task content |

Unknown classifications fail closed (`UNKNOWN_FIELD_CLASSIFICATION`).

Annotations are versioned (`ck.task_dep.v1`), human-reviewable JSON fixtures.

## 3. Compiler fail-closed conditions

| Condition | Reason code |
|---|---|
| Missing required task fact annotations | `MISSING_REQUIRED_TASK_FACT_ANNOTATIONS` |
| Missing operational state annotations | `MISSING_REQUIRED_OPERATIONAL_STATE_ANNOTATIONS` |
| Forbidden value present in body | `FORBIDDEN_ANSWER_LEAKAGE` |
| Unknown classification string | `UNKNOWN_FIELD_CLASSIFICATION` |
| C1 cannot pad up to target (content already larger) | `BYTE_BUDGET_OVERFLOW` |
| Padding not pure spaces / delimiter | `PADDING_NOT_INERT` |
| Padding contains ids / relations / answers | `PADDING_CONTAINS_*` |

## 4. Serialization method

Model-visible input bytes =

```text
canonical_json({
  model,
  messages: [{role:system, content}, {role:user, content}],
  format: <output schema>,
  stream: false,
  options: {temperature, seed, num_ctx}
})
```

- UTF-8  
- `sort_keys=True`  
- separators `(',', ':')`  
- **No silent Unicode NFC/NFD normalization** after content is fixed  

## 5. Unicode

Hashes use the exact UTF-8 of the Python string as provided.  
NFC vs NFD differences are treated as real byte differences (adversarial fixture).

## 6. Implementation

`src/conditioned_kernel/control_contract.py`
