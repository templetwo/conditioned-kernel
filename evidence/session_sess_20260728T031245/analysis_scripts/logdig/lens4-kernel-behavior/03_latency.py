"""LENS4 point 1: latency profile.

Timing data (kernel_request/raw_output stage `telemetry.elapsed_seconds`)
exists ONLY inside dashboard/turns/*.json -- candidates.jsonl and
receipts.jsonl carry no timing field at all (verified: their full key sets
have no 'elapsed', 'duration', 'latency', or 'seconds' key anywhere).
The 19 dashboard traces span 19:00:42Z - 20:53:52Z, i.e. entirely the
"evening" cluster; there is no morning/afternoon latency data to compare
against, and that gap cannot be filled from any file under logs/.
"""
import json
import glob
import statistics as stats

LOGS = "/Users/vaquez/conditioned-kernel/logs"

# Confirm no timing field anywhere outside dashboard/turns
for fname in ("candidates.jsonl", "receipts.jsonl", "history.jsonl"):
    with open(f"{LOGS}/{fname}") as f:
        keys = set()
        for line in f:
            keys |= set(json.loads(line).keys())
    timing_like = [k for k in keys if any(t in k.lower() for t in ("elapsed", "duration", "latency", "second", "time"))]
    print(f"{fname}: timing-like keys present = {timing_like or 'NONE'}")

print()
turn_files = sorted(glob.glob(f"{LOGS}/dashboard/turns/*.json"))
rows = []
for fp in turn_files:
    with open(fp) as f:
        d = json.load(f)
    for p in d["passes"]:
        tel = p["telemetry"]
        rows.append({
            "turn_id": d["turn_id"],
            "started_at": d["started_at"],
            "pass_index": p["pass_index"],
            "decision": p["decision"],
            "elapsed_seconds": tel["elapsed_seconds"],
            "packet_bytes": tel["packet_bytes"],
            "final_response_chars": tel["final_response_chars"],
            "thinking_chars": tel["thinking_chars"],
            "word_count": p["word_count"],
            "inference_status": tel["inference_status"],
        })

print(f"total (turn, pass) rows with telemetry: {len(rows)}")

elapsed = [r["elapsed_seconds"] for r in rows]
print("\n-- elapsed_seconds, ALL 22 passes (only latency data that exists) --")
print(f"  min={min(elapsed):.3f}  median={stats.median(elapsed):.3f}  max={max(elapsed):.3f}  mean={stats.mean(elapsed):.3f}  stdev={stats.pstdev(elapsed):.3f}")

first_pass = [r["elapsed_seconds"] for r in rows if r["pass_index"] == 0]
repair_pass = [r["elapsed_seconds"] for r in rows if r["pass_index"] == 1]
print(f"\n-- pass_index=0 (n={len(first_pass)}) --")
print(f"  min={min(first_pass):.3f}  median={stats.median(first_pass):.3f}  max={max(first_pass):.3f}  mean={stats.mean(first_pass):.3f}")
print(f"-- pass_index=1 / repair (n={len(repair_pass)}) --")
print(f"  min={min(repair_pass):.3f}  median={stats.median(repair_pass):.3f}  max={max(repair_pass):.3f}  mean={stats.mean(repair_pass):.3f}")

acc = [r["elapsed_seconds"] for r in rows if r["decision"] == "accept"]
rej = [r["elapsed_seconds"] for r in rows if r["decision"] == "reject"]
rep = [r["elapsed_seconds"] for r in rows if r["decision"] == "repair"]
print(f"\n-- by terminal per-pass decision --")
for label, arr in (("accept", acc), ("reject", rej), ("repair", rep)):
    if arr:
        print(f"  {label:8s} n={len(arr):2d}  min={min(arr):.3f} median={stats.median(arr):.3f} max={max(arr):.3f} mean={stats.mean(arr):.3f}")

# morning vs evening
hours = sorted({r["started_at"][11:13] for r in rows})
print(f"\nhours represented in dashboard traces: {hours}")
print("No dashboard trace (and therefore no elapsed_seconds sample) exists for "
      "the 71 candidates/receipts at hours 00, 02, 03 -- morning-vs-evening "
      "latency comparison CANNOT be determined from these logs. Settling it "
      "would require re-running those prompts under the old kernel with the "
      "same telemetry hook, or a historical dashboard trace file that was "
      "never written for that window.")


def pearson(xs, ys):
    n = len(xs)
    mx, my = stats.mean(xs), stats.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if sx == 0 or sy == 0:
        return float("nan")
    return cov / (sx * sy)


pb = [r["packet_bytes"] for r in rows]
frc = [r["final_response_chars"] for r in rows]
wc = [r["word_count"] for r in rows]

print(f"\n-- correlation (Pearson r), n={len(rows)} passes --")
print(f"  elapsed_seconds vs packet_bytes:          r={pearson(elapsed, pb):+.3f}")
print(f"  elapsed_seconds vs final_response_chars:  r={pearson(elapsed, frc):+.3f}")
print(f"  elapsed_seconds vs word_count (answer):    r={pearson(elapsed, wc):+.3f}")

print("\n-- raw per-pass table --")
for r in rows:
    print(f"  {r['started_at']} p{r['pass_index']} {r['decision']:7s} "
          f"elapsed={r['elapsed_seconds']:.3f}s packet_bytes={r['packet_bytes']:4d} "
          f"resp_chars={r['final_response_chars']:4d} think_chars={r['thinking_chars']} "
          f"words={r['word_count']:3d} status={r['inference_status']}")
