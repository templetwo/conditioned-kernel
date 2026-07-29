"""LENS4 point 2: response shape across all 93 candidates/receipts.

- word/char distributions of candidate.answer
- distance to the 120-word cap (profile.max_answer_words, clamped into
  packet.constraints.max_words by edge.enforce_packet_budget -- see
  src/conditioned_kernel/edge.py:239-241)
- JSON schema compliance: parse_ok rate, required_section violations
- think channel: dashboard telemetry.thinking_chars (all 22 passes) plus a
  raw_text scan across all 93 candidates for any literal <think> leakage
"""
import json
import re
import glob
import statistics as stats
import collections

LOGS = "/Users/vaquez/conditioned-kernel/logs"

with open(f"{LOGS}/candidates.jsonl") as f:
    candidates = [json.loads(l) for l in f]
with open(f"{LOGS}/receipts.jsonl") as f:
    receipts = [json.loads(l) for l in f]

recpt_by_id = {r["candidate_id"]: r for r in receipts}

print("=" * 78)
print("1. JSON schema compliance (parse_ok)")
print("=" * 78)
parse_ok_ct = collections.Counter(c["parse_ok"] for c in candidates)
print(f"parse_ok counts across 93 candidates: {dict(parse_ok_ct)}")
parse_errors = [c for c in candidates if not c["parse_ok"]]
print(f"parse failures: {len(parse_errors)}")
for c in parse_errors:
    print(f"  {c['candidate_id']}: parse_error={c['parse_error']!r}")

required_section_fails = collections.Counter()
for r in receipts:
    for v in r.get("violations") or []:
        if str(v).startswith("required_section:"):
            required_section_fails[v] += 1
print(f"required_section:* violations across 93 receipts: {dict(required_section_fails) or 'NONE'}")

print()
print("=" * 78)
print("2. answer word/char distribution, all 93 candidates")
print("=" * 78)
word_counts = [recpt_by_id[c["candidate_id"]]["word_count"] for c in candidates]
char_counts = [len(c.get("answer") or "") for c in candidates]

print(f"word_count  (n=93): min={min(word_counts)} p25={stats.quantiles(word_counts, n=4)[0]:.1f} "
      f"median={stats.median(word_counts):.1f} p75={stats.quantiles(word_counts, n=4)[2]:.1f} "
      f"max={max(word_counts)} mean={stats.mean(word_counts):.1f}")
print(f"answer chars (n=93): min={min(char_counts)} median={stats.median(char_counts):.1f} "
      f"max={max(char_counts)} mean={stats.mean(char_counts):.1f}")

print()
print("=" * 78)
print("3. distance to the 120-word cap (profile.max_answer_words)")
print("=" * 78)
CAP = 120
over_cap = [wc for wc in word_counts if wc > CAP]
near_cap = [wc for wc in word_counts if wc >= CAP * 0.75]
print(f"CAP = {CAP} words (orin_nano_8gb profile max_answer_words, clamped into "
      f"packet.constraints.max_words by edge.enforce_packet_budget)")
print(f"answers exceeding {CAP} words: {len(over_cap)} / 93  -> {over_cap or 'none'}")
print(f"answers at or above 75% of cap ({CAP*0.75:.0f} words): {len(near_cap)} / 93 -> {sorted(near_cap)}")
print(f"max observed word_count all day: {max(word_counts)} "
      f"({max(word_counts)/CAP*100:.1f}% of the cap)")

max_words_exceeded = [v for r in receipts for v in (r.get("violations") or []) if str(v).startswith("max_words_exceeded")]
print(f"max_words_exceeded violations fired in receipts.jsonl: {len(max_words_exceeded)} -> {max_words_exceeded or 'none'}")

print()
print("=" * 78)
print("4. think channel: thinking_chars from dashboard telemetry (22 passes)")
print("=" * 78)
turn_files = sorted(glob.glob(f"{LOGS}/dashboard/turns/*.json"))
think_flags = collections.Counter()
thinking_chars_all = []
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    think_flags[d["runtime_config"]["think"]] += 1
    for p in d["passes"]:
        thinking_chars_all.append(p["telemetry"]["thinking_chars"])
print(f"runtime_config.think value across 19 traced turns: {dict(think_flags)}")
print(f"telemetry.thinking_chars across 22 traced passes: "
      f"min={min(thinking_chars_all)} max={max(thinking_chars_all)} "
      f"(all-zero: {all(t == 0 for t in thinking_chars_all)})")

print()
print("-- scan for literal <think> / reasoning-tag leakage in all 93 raw_text bodies --")
think_pattern = re.compile(r"<think>|</think>|\bthinking\b", re.IGNORECASE)
leaks = [c["candidate_id"] for c in candidates if think_pattern.search(c.get("raw_text") or "")]
print(f"candidates whose raw_text contains a think-tag/keyword match: {len(leaks)} -> {leaks or 'none'}")

print()
print("=" * 78)
print("5. word/char distribution split by confirmed kernel (reuses swap boundary)")
print("=" * 78)
SWAP = "2026-07-28T03:00:08Z"
SESSION = "2026-07-28T03:12:45Z"


def grp(r):
    t = r["created_at"]
    if t < SWAP:
        return "old (qwen2.5:0.5b, confirmed)"
    if t >= SESSION:
        return "new (qwen3.5:0.8b think=false, confirmed)"
    return "ambiguous window"


by_group = collections.defaultdict(list)
for c in candidates:
    r = recpt_by_id[c["candidate_id"]]
    by_group[grp(r)].append((r["word_count"], len(c.get("answer") or "")))

for g, vals in by_group.items():
    wc = [v[0] for v in vals]
    cc = [v[1] for v in vals]
    print(f"\n{g} (n={len(vals)})")
    print(f"   words: min={min(wc)} median={stats.median(wc):.1f} max={max(wc)}")
    print(f"   chars: min={min(cc)} median={stats.median(cc):.1f} max={max(cc)}")
