# RUN 00.8B — Runtime Provenance

## Model identity

| Field | Value |
|---|---|
| model_tag | `qwen2.5:0.5b` |
| resolved_model_digest | `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67` |
| parameter_size | 494.03M |
| quantization | Q4_K_M |
| family | qwen2 |
| format | gguf |
| size_bytes | 397821319 |

## Runtime

| Field | Value |
|---|---|
| Ollama version | 0.20.7 |
| base_url | http://127.0.0.1:11434 |
| backend | local_http_api |
| host architecture | arm64 |
| host platform | macOS 26.5.1 arm64 |

## Generation options

| Option | Requested | Serialized | Confirmation |
|---|---|---|---|
| temperature | 0.0 | 0.0 | `requested_but_not_confirmable` |
| seed | 0 | 0 | `requested_but_not_confirmable` |
| num_ctx | 2048 | 2048 | `requested_but_not_confirmable` |

Ollama chat API does not return confirmed option echo in this harness. No
confirmation was invented. No determinism claim is permitted.

## Invocations

| Metric | Value |
|---|---|
| Max allowed | 4 |
| Actual | 4 |
| Retries | 0 |
| Other models | none |
