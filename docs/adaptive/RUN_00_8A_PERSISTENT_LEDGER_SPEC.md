# RUN 00.8A — Persistent Terminal Ledger

**Schema:** `ck.persistent_terminal_ledger.v1`  
**Module:** `persistent_terminal_ledger.py`

## Key

```text
(manifest_sha256, cell_id)
```

## Properties

- Open from path only  
- Append-only JSONL + fsync  
- Meta file binds `manifest_sha256`  
- Reject second terminalization after process restart  
- Reject unplanned cells  
- Integrity verify reloads disk and checks row hashes  
- No silent truncate/overwrite  
- Separate from continuity event store  

## Files

```text
<run_dir>/terminal_ledger.jsonl
<run_dir>/terminal_ledger.meta.json
```
