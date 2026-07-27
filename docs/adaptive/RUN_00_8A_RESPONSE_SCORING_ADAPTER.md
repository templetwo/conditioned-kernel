# RUN 00.8A — Response Scoring Adapter (`ck.response_scoring_adapter.v1`)

## Route

```text
raw response bytes
  → typed inference status
  → structured parser (continuity_assertions only)
  → relational scorer (when parse yields list)
```

No prose relation inference.

## Deterministic mapping

| Parse kind | Terminal class | primary_score |
|---|---|---|
| STRUCTURED_ASSERTIONS | SCORED | scorer output |
| EMPTY_ASSERTION_LIST | SCORED | scorer (typically 0.0) |
| EMPTY_FINAL_RESPONSE | NO_FINAL_RESPONSE | **null** |
| NULL_RESPONSE | NO_FINAL_RESPONSE | **null** |
| MALFORMED_JSON | MALFORMED_ASSERTIONS | **null** |
| WRONG_SCHEMA_KEY | MALFORMED_ASSERTIONS | **null** |
| PROSE_ONLY | MALFORMED_ASSERTIONS | **null** |
| PARSER_EXCEPTION | MALFORMED_ASSERTIONS | **null** |
| INFERENCE_TIMEOUT | TIMEOUT | **null** |
| INFERENCE_TRANSPORT | TRANSPORT_ERROR | **null** |
| INFERENCE_INVALID | INVALID_RESPONSE | **null** |
| INFERENCE_NO_FINAL | NO_FINAL_RESPONSE | **null** |

Empty list ≠ empty final response. Malformed paths never use ad-hoc zero.

## Evidence

Every parse retains `raw_response_sha256`, byte length, channel status.
