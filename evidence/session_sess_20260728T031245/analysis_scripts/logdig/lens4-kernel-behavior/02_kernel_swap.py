"""LENS4 point 4: the kernel swap.

Evidence sources (all read-only):
  - git history of configs/edge/orin_nano_8gb.json (outside logs/, source repo)
  - state/current.json (session_id, receipt_count_24h)
  - dashboard/turns/*.json runtime_config (explicit model/think per traced turn)
  - conditioned_kernel/cli.py _cmd_chat / _apply_profile_defaults (to establish
    WHEN the model is chosen -- once at session start, not per-turn)
  - receipts.jsonl / candidates.jsonl behavioral stats, hour-bucketed
"""
import json
import subprocess
import collections
import statistics as stats

REPO = "/Users/vaquez/conditioned-kernel"
LOGS = f"{REPO}/logs"

print("=" * 78)
print("1. git evidence for the config swap (configs/edge/orin_nano_8gb.json)")
print("=" * 78)
log = subprocess.run(
    ["git", "-C", REPO, "log", "--follow", "--format=%H|%ad|%s", "--date=iso-strict",
     "--", "configs/edge/orin_nano_8gb.json"],
    capture_output=True, text=True, check=True,
).stdout.strip()
print(log)

diff = subprocess.run(
    ["git", "-C", REPO, "show", "330128e973359896f951b6443cf062cfe2ea420a",
     "--", "configs/edge/orin_nano_8gb.json"],
    capture_output=True, text=True, check=True,
).stdout
print("\n--- diff of the swap commit ---")
print(diff)

print("=" * 78)
print("2. when is the profile (and hence model) chosen relative to a session?")
print("=" * 78)
print("""\
conditioned_kernel/cli.py:_cmd_chat calls _apply_profile_defaults(args) ONCE,
before entering the `while True: input("you> ")` loop. _apply_profile_defaults
calls load_profile(), which does a fresh `json.load` of
configs/edge/<profile>.json at that moment. Every subsequent turn in that
chat session reuses the same in-memory `args.model` -- the profile file is
NOT re-read per turn. So the model backing any given candidate is fixed by
which session it belongs to, not by wall-clock time relative to the commit
that changed the file on disk.
""")

print("=" * 78)
print("3. state/current.json -- the one session we can name directly")
print("=" * 78)
with open(f"{REPO}/state/current.json") as f:
    state = json.load(f)
print(json.dumps({k: state[k] for k in ("session_id", "active_profile", "receipt_count_24h", "updated_at")}, indent=2))

print("=" * 78)
print("4. dashboard/turns/*.json -- explicit runtime_config per traced turn")
print("=" * 78)
import glob
turn_files = sorted(glob.glob(f"{LOGS}/dashboard/turns/*.json"))
models_seen = collections.Counter()
think_seen = collections.Counter()
temp_seen = collections.Counter()
seed_seen = collections.Counter()
session_ids = collections.Counter()
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    rc = d["runtime_config"]
    models_seen[rc["model"]] += 1
    think_seen[rc["think"]] += 1
    temp_seen[rc["temperature"]] += 1
    seed_seen[rc["seed"]] += 1
    session_ids[d["session_id"]] += 1
print(f"model field across 19 traced turns:       {dict(models_seen)}")
print(f"think field across 19 traced turns:        {dict(think_seen)}")
print(f"temperature field across 19 traced turns:  {dict(temp_seen)}")
print(f"seed field across 19 traced turns:         {dict(seed_seen)}")
print(f"session_id field across 19 traced turns:   {dict(session_ids)}")

print("=" * 78)
print("5. session-boundary reasoning for the 71 pre-dashboard candidates")
print("=" * 78)
with open(f"{LOGS}/receipts.jsonl") as f:
    receipts = [json.loads(l) for l in f]
ts_sorted = sorted(r["created_at"] for r in receipts)

SWAP_COMMIT_UTC = "2026-07-28T03:00:08Z"   # git commit 330128e, authored -0400
SESSION_START = "2026-07-28T03:12:45Z"     # state/current.json session_id timestamp

before_commit = [t for t in ts_sorted if t < SWAP_COMMIT_UTC]
after_commit_before_session = [t for t in ts_sorted if SWAP_COMMIT_UTC <= t < SESSION_START]
in_named_session = [t for t in ts_sorted if t >= SESSION_START]

print(f"swap commit (config file changed on disk): {SWAP_COMMIT_UTC}")
print(f"current named session started:              {SESSION_START}  (from state/current.json session_id)")
print()
print(f"receipts strictly BEFORE the swap commit:                    {len(before_commit)}"
      f"  (first={before_commit[0] if before_commit else None}, last={before_commit[-1] if before_commit else None})")
print(f"  -> any session that produced these had already called load_profile()")
print(f"     before the file changed, so these are qwen2.5:0.5b with CONFIDENCE.")
print()
print(f"receipts AFTER commit but BEFORE the named session start:    {len(after_commit_before_session)}"
      f"  ({after_commit_before_session})")
print(f"  -> AMBIGUOUS: these could belong to a session that started before")
print(f"     03:00:08Z (still holding qwen2.5:0.5b in memory) or a short-lived")
print(f"     session that started after 03:00:08Z but before 03:12:45Z (which")
print(f"     would have picked up qwen3.5:0.8b). candidates.jsonl/receipts.jsonl")
print(f"     carry no session_id field, so this cannot be resolved from the logs.")
print()
print(f"receipts inside the named session sess_20260728T031245 (>= {SESSION_START}): {len(in_named_session)}")
print(f"  -> CONFIRMED qwen3.5:0.8b / think=false: this session's own id postdates")
print(f"     the swap commit, and dashboard traces for this same session_id (19:xx,")
print(f"     20:xx) show runtime_config.model == 'qwen3.5:0.8b' directly.")

print("=" * 78)
print("6. behavioral comparison: confirmed-old-model vs confirmed-new-model")
print("=" * 78)
with open(f"{LOGS}/candidates.jsonl") as f:
    candidates = [json.loads(l) for l in f]
cand_by_id = {c["candidate_id"]: c for c in candidates}

old_ids = set()
new_ids = set()
ambiguous_ids = set()
for r in receipts:
    t = r["created_at"]
    if t < SWAP_COMMIT_UTC:
        old_ids.add(r["candidate_id"])
    elif t >= SESSION_START:
        new_ids.add(r["candidate_id"])
    else:
        ambiguous_ids.add(r["candidate_id"])

recpt_by_id = {r["candidate_id"]: r for r in receipts}


def group_stats(label, ids):
    wc = [recpt_by_id[i]["word_count"] for i in ids]
    ans_chars = [len(cand_by_id[i].get("answer") or "") for i in ids]
    parse_ok = sum(1 for i in ids if cand_by_id[i].get("parse_ok"))
    viol_ct = collections.Counter()
    for i in ids:
        for v in recpt_by_id[i].get("violations") or []:
            key = v.split(":", 1)[0]
            viol_ct[key] += 1
    print(f"\n-- {label} (n={len(ids)}) --")
    if wc:
        print(f"   word_count:  min={min(wc)} median={stats.median(wc):.1f} max={max(wc)} mean={stats.mean(wc):.1f}")
        print(f"   answer chars: min={min(ans_chars)} median={stats.median(ans_chars):.1f} max={max(ans_chars)}")
    print(f"   parse_ok: {parse_ok}/{len(ids)}")
    print(f"   violation types (by prefix, counted across all passes in group): {dict(viol_ct.most_common())}")
    decisions = collections.Counter(recpt_by_id[i]["decision"] for i in ids)
    print(f"   decisions: {dict(decisions)}")


group_stats("CONFIRMED qwen2.5:0.5b (created_at < swap commit 03:00:08Z)", old_ids)
group_stats("AMBIGUOUS window (commit <= created_at < named session start)", ambiguous_ids)
group_stats("CONFIRMED qwen3.5:0.8b think=false (created_at >= session start 03:12:45Z)", new_ids)

print(f"\nsanity: {len(old_ids)} + {len(ambiguous_ids)} + {len(new_ids)} = "
      f"{len(old_ids) + len(ambiguous_ids) + len(new_ids)} (expect {len(receipts)})")

