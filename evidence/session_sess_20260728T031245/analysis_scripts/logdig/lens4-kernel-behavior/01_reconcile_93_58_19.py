"""LENS4 point 5: reconcile candidates.jsonl (93) / history.jsonl (58) /
dashboard/turns (19 TurnTrace files) exactly.

Read-only against /Users/vaquez/conditioned-kernel/logs.
"""
import json
import collections
import glob

LOGS = "/Users/vaquez/conditioned-kernel/logs"

with open(f"{LOGS}/candidates.jsonl") as f:
    candidates = [json.loads(l) for l in f]
with open(f"{LOGS}/receipts.jsonl") as f:
    receipts = [json.loads(l) for l in f]
with open(f"{LOGS}/history.jsonl") as f:
    history = [json.loads(l) for l in f]

print(f"candidates.jsonl lines: {len(candidates)}")
print(f"receipts.jsonl lines:   {len(receipts)}")
print(f"history.jsonl lines:    {len(history)}")

# candidates and receipts are 1:1 by candidate_id
cand_ids = {c["candidate_id"] for c in candidates}
recpt_cand_ids = {r["candidate_id"] for r in receipts}
print(f"\ncandidate_id sets equal (candidates vs receipts): {cand_ids == recpt_cand_ids}")

# Every receipt has a UNIQUE packet_id (repair regenerates a fresh packet,
# not the same packet_id reused across pass_index).
pkt_ids = [r["packet_id"] for r in receipts]
print(f"distinct packet_ids across 93 receipts: {len(set(pkt_ids))} (expect 93 -> one packet per pass, not per turn)")

# pass_index / decision crosstab
ct = collections.Counter((r["pass_index"], r["decision"]) for r in receipts)
print("\n(pass_index, decision) counts over the 93 receipts:")
for k in sorted(ct):
    print(f"  pass_index={k[0]} decision={k[1]:8s} n={ct[k]}")

n_pass0 = sum(v for k, v in ct.items() if k[0] == 0)
n_pass1 = sum(v for k, v in ct.items() if k[0] == 1)
n_pass0_accept = ct.get((0, "accept"), 0)
n_pass0_repair = ct.get((0, "repair"), 0)
n_pass0_reject = ct.get((0, "reject"), 0)
n_pass1_accept = ct.get((1, "accept"), 0)
n_pass1_reject = ct.get((1, "reject"), 0)

print(f"\npass_index=0 rows (== one row per turn, since every turn starts at pass 0): {n_pass0}")
print(f"pass_index=1 rows (== repair retries, capped at max_repair=1 per profile config): {n_pass1}")
print(f"  -> {n_pass0} + {n_pass1} = {n_pass0 + n_pass1} = {len(receipts)} (all receipts)")
print(f"pass_index=0 direct reject count: {n_pass0_reject} (expect 0 -- validate.py sets "
      f"repairable=True at pass_index==0 unless accepted, so pass 0 never terminally rejects)")

n_turns = n_pass0  # one turn = one pass_index=0 event
n_accept_turns = n_pass0_accept + n_pass1_accept
n_reject_turns = n_pass1_reject  # only repaired-and-still-bad turns end in reject
print(f"\nturn-level totals (turn = the pass_index=0 event that opened it):")
print(f"  turns total:        {n_turns}")
print(f"  turns accepted:     {n_accept_turns}  ({n_pass0_accept} accepted pass-0 + {n_pass1_accept} accepted after 1 repair)")
print(f"  turns rejected:     {n_reject_turns}  (all from failed repair passes; pass-0 never rejects outright)")
print(f"  turns accept+reject = {n_accept_turns + n_reject_turns} (expect == len(history.jsonl) == {len(history)})")

# history.jsonl: does it hold exactly the accept/reject terminal rows (58),
# omitting the 35 provisional "repair" rows?
hist_decisions = collections.Counter(h["decision"] for h in history)
print(f"\nhistory.jsonl decision counts: {dict(hist_decisions)}")
print(f"history.jsonl has NO 'repair' rows: {'repair' not in hist_decisions}")

# Verify each history row's candidate_id matches the receipt with that
# packet_id/candidate_id and that decision (accept/reject) agrees exactly.
recpt_by_cand = {r["candidate_id"]: r for r in receipts}
mismatch = 0
missing = 0
for h in history:
    r = recpt_by_cand.get(h["candidate_id"])
    if r is None:
        missing += 1
        continue
    if r["decision"] != h["decision"]:
        mismatch += 1
print(f"\nhistory rows with no matching receipt candidate_id: {missing}")
print(f"history rows whose decision disagrees with the matched receipt: {mismatch}")

# Confirm history.jsonl candidate_ids are EXACTLY the terminal-decision
# candidates: {pass0 accepts} union {pass1 accepts, pass1 rejects}
terminal_cand_ids = {
    r["candidate_id"] for r in receipts
    if (r["pass_index"] == 0 and r["decision"] == "accept")
    or (r["pass_index"] == 1)
}
hist_cand_ids = {h["candidate_id"] for h in history}
print(f"\nhistory candidate_ids == {{pass0 accepts}} u {{all pass1 rows}}: {hist_cand_ids == terminal_cand_ids}")
print(f"  size of that terminal set: {len(terminal_cand_ids)}  (expect {len(history)})")

# --- dashboard/turns reconciliation ---
turn_files = sorted(glob.glob(f"{LOGS}/dashboard/turns/*.json"))
print(f"\ndashboard/turns/*.json file count: {len(turn_files)}")

total_dash_passes = 0
dash_rows = []
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    n = len(d["passes"])
    total_dash_passes += n
    dash_rows.append((fp.split("/")[-1], d["started_at"], d["final_decision"]["decision"], n))

print(f"total passes summed across the 19 TurnTrace files: {total_dash_passes}")

for row in dash_rows:
    print(f"  {row[0]:42s} started={row[1]} final={row[2]:7s} passes={row[3]}")

# Cross-check: do those 22 passes correspond 1:1 (by candidate_id) with the
# 22 receipts.jsonl rows whose created_at falls in hour 19 or hour 20?
r_19_20 = [r for r in receipts if r["created_at"][11:13] in ("19", "20")]
print(f"\nreceipts.jsonl rows with created_at hour in {{19,20}}: {len(r_19_20)}")

dash_cand_ids = set()
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    for p in d["passes"]:
        dash_cand_ids.add(p["candidate_id"])

r_19_20_ids = {r["candidate_id"] for r in r_19_20}
print(f"candidate_id sets equal (dashboard passes vs hour19/20 receipts): {dash_cand_ids == r_19_20_ids}")

# hour buckets across the whole day, for completeness
hour_ct = collections.Counter(r["created_at"][11:13] for r in receipts)
print(f"\nreceipts.jsonl by UTC hour bucket: {dict(sorted(hour_ct.items()))}")
print(f"hours {{00,02,03}} (pre-dashboard chat sessions) total: "
      f"{hour_ct['00'] + hour_ct['02'] + hour_ct['03']}")
print(f"hours {{19,20}} (live dashboard session) total: {hour_ct['19'] + hour_ct['20']}")
