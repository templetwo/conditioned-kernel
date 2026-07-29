"""LENS4 point 3: determinism fingerprints at temp=0.3, seed=42 (NOT temp=0).

Uses conditioned_kernel.observatory.compute.jaccard_similarity -- the
pipeline's own symmetric token-similarity function -- rather than a
re-invented metric, per the honesty contract.

Two angles:
  A. Exact byte-identical answer collisions across the whole day (93
     candidates) -- do any two DIFFERENT turns produce the exact same
     answer text? If so, are their inputs identical or merely similar?
  B. Within the 19 dashboard-traced turns, pairs of turns whose model_input
     is near-identical (packet content minus the volatile packet_id/
     created_at fields build_model_input strips) -- do near-identical
     inputs produce near-identical or identical outputs? This is the
     closest the logs get to a controlled repeat at temp=0.3/seed=42.
"""
import sys
import json
import glob
import collections

sys.path.insert(0, "/Users/vaquez/conditioned-kernel/src")
from conditioned_kernel.observatory.compute import jaccard_similarity  # noqa: E402

LOGS = "/Users/vaquez/conditioned-kernel/logs"

with open(f"{LOGS}/candidates.jsonl") as f:
    candidates = [json.loads(l) for l in f]

print("=" * 78)
print("A. exact byte-identical answer text across all 93 candidates")
print("=" * 78)
by_answer = collections.defaultdict(list)
for c in candidates:
    a = c.get("answer") or ""
    if a:
        by_answer[a].append(c["candidate_id"])

dupes = {a: ids for a, ids in by_answer.items() if len(ids) > 1}
print(f"distinct non-empty answer strings: {len(by_answer)}  (over {sum(1 for c in candidates if c.get('answer'))} non-empty answers)")
print(f"answer strings repeated verbatim by >=2 different candidates: {len(dupes)}")
for a, ids in dupes.items():
    print(f"\n  answer ({len(a)} chars): {a!r}")
    print(f"  produced by candidate_ids: {ids}")

print()
print("=" * 78)
print("A2. exact byte-identical raw_text (whole JSON payload) collisions")
print("=" * 78)
by_raw = collections.defaultdict(list)
for c in candidates:
    rt = c.get("raw_text") or ""
    if rt:
        by_raw[rt].append(c["candidate_id"])
raw_dupes = {rt: ids for rt, ids in by_raw.items() if len(ids) > 1}
print(f"raw_text strings repeated verbatim by >=2 different candidates: {len(raw_dupes)}")
for rt, ids in raw_dupes.items():
    print(f"  candidate_ids: {ids}  raw_text[:120]={rt[:120]!r}")

print()
print("=" * 78)
print("B. within-turn repair pairs: pass0 vs pass1 answer similarity")
print("=" * 78)
print("(repair regenerates a NEW packet with repair guidance appended -- these")
print(" are not identical-input trials, but they show how much a single")
print(" temp=0.3/seed=42 turn's answer shifts when only the repair note changes.)")
cand_by_id = {c["candidate_id"]: c for c in candidates}
with open(f"{LOGS}/receipts.jsonl") as f:
    receipts = [json.loads(l) for l in f]
by_created_pair = collections.defaultdict(dict)
for r in receipts:
    pass_ = r["pass_index"]
    # Group repair pairs by proximity: pass0 timestamp then pass1 within same
    # turn -- use candidates.jsonl ordering (file is already chronological)
# Simpler: walk receipts in file order and pair consecutive (0,1) rows.
pairs = []
prev0 = None
for r in receipts:
    if r["pass_index"] == 0:
        prev0 = r
    elif r["pass_index"] == 1 and prev0 is not None:
        pairs.append((prev0, r))
        prev0 = None
print(f"pass0->pass1 repair pairs found (by file order): {len(pairs)}")
sims = []
for r0, r1 in pairs:
    a0 = cand_by_id[r0["candidate_id"]].get("answer") or ""
    a1 = cand_by_id[r1["candidate_id"]].get("answer") or ""
    sim = jaccard_similarity(a0, a1)
    sims.append(sim)
import statistics as stats
print(f"jaccard_similarity(pass0.answer, pass1.answer) over {len(sims)} pairs: "
      f"min={min(sims):.3f} median={stats.median(sims):.3f} max={max(sims):.3f} mean={stats.mean(sims):.3f}")
identical_pairs = sum(1 for r0, r1 in pairs if (cand_by_id[r0["candidate_id"]].get("answer") or "") == (cand_by_id[r1["candidate_id"]].get("answer") or ""))
print(f"repair pairs with byte-identical answer despite a changed (repaired) packet: {identical_pairs}")

print()
print("=" * 78)
print("C. dashboard-traced turns: near-identical packet -> output comparison")
print("=" * 78)
turn_files = sorted(glob.glob(f"{LOGS}/dashboard/turns/*.json"))
traced = []
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    p0 = d["passes"][0]
    traced.append({
        "turn_id": d["turn_id"],
        "user_input": d["user_input"],
        "answer": p0.get("answer") or "",
        "raw_text": p0.get("raw_text") or "",
        "packet": p0.get("packet") or {},
    })

print(f"traced turns (pass0 only): {len(traced)}")
print("\npairwise jaccard_similarity(user_input_i, user_input_j) -- flag pairs >= 0.5")
n = len(traced)
close_pairs = []
for i in range(n):
    for j in range(i + 1, n):
        sim_in = jaccard_similarity(traced[i]["user_input"], traced[j]["user_input"])
        if sim_in >= 0.5:
            sim_out = jaccard_similarity(traced[i]["answer"], traced[j]["answer"])
            close_pairs.append((sim_in, sim_out, i, j))

if not close_pairs:
    print("no two dashboard turns had jaccard_similarity(user_input) >= 0.5 -- "
          "every traced user_input this session was lexically distinct, so "
          "the logs contain no genuine 'repeat the same question' trial to")
    print("directly test determinism against across DIFFERENT turns.")
else:
    for sim_in, sim_out, i, j in sorted(close_pairs, reverse=True):
        print(f"  user_input sim={sim_in:.3f}  answer sim={sim_out:.3f}  "
              f"[{traced[i]['turn_id']}] {traced[i]['user_input']!r}  vs  "
              f"[{traced[j]['turn_id']}] {traced[j]['user_input']!r}")

print()
print("-- same-turn pass0 vs pass1 packet similarity (repair-loop within one turn) --")
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    if len(d["passes"]) < 2:
        continue
    p0, p1 = d["passes"][0], d["passes"][1]
    a0 = p0.get("answer") or ""
    a1 = p1.get("answer") or ""
    sim = jaccard_similarity(a0, a1)
    print(f"  {d['turn_id']}: pass0 answer ({len(a0)}c) vs pass1 answer ({len(a1)}c) "
          f"jaccard={sim:.3f}  identical={a0 == a1}")
