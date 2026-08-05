#!/usr/bin/env python3
"""ECS SPEC 4a - generator eviction barrier, corrected.

Thresholds are read from generators.json (single source of truth). Do NOT
hardcode NEED constants here: stale constants re-open the soft-barrier hole
(Grok reservation R2, #13712).

Mechanism (#13706): ollama admits loads on MemAvailable-style accounting that
CUDA cannot honor on Tegra, because unified-memory allocation does not trigger
page-cache reclaim. Poll MemFree, reclaim page cache, and FAIL CLOSED.
"""
import json, time, mmap, os, sys, urllib.request

API = "http://127.0.0.1:11434"
HERE = os.path.dirname(os.path.abspath(__file__))

def load_table(path=None):
    with open(path or os.path.join(HERE, "generators.json")) as f:
        return json.load(f)["generators"]

def meminfo(k):
    """MB for a /proc/meminfo key, or None if it cannot be read.

    None is a REAL return value here and callers must handle it. The old
    version fell off the end and returned None implicitly, and the caller then
    evaluated `None >= need_mb`, which raises TypeError on Python 3 - so an
    unreadable meminfo surfaced as a crash rather than as a state.
    """
    try:
        for l in open("/proc/meminfo"):
            if l.startswith(k + ":"):
                return int(l.split()[1]) // 1024
    except Exception:
        return None
    return None

def ps():
    return json.loads(urllib.request.urlopen(API + "/api/ps", timeout=30).read()).get("models", [])

def post(p, b, t=300):
    r = urllib.request.Request(API + p, data=json.dumps(b).encode(),
                               headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=t).read())

def reclaim(target_mb, rounds=4):
    """Evict page cache by faulting in anonymous pages, then releasing. No root needed."""
    mf = meminfo("MemFree")
    if mf is None:
        return 0, False          # unreadable: barrier() classifies, not this
    if mf >= target_mb:
        return 0, False
    t0, did = time.time(), False
    for _ in range(rounds):
        avail = meminfo("MemAvailable")
        if avail is None:
            break
        n = max(500, avail - 500)
        try:
            m = mmap.mmap(-1, n * 1024 * 1024)
            for off in range(0, n * 1024 * 1024, 4096):
                m[off] = 1
            m.close()
            did = True
        except Exception:
            pass
        time.sleep(1.5)
        now = meminfo("MemFree")
        if now is None or now >= target_mb:
            break
    return round((time.time() - t0) * 1000), did

def barrier(need_mb, settle_s=1.5):
    """Evict all resident models, verify ps empty, reclaim to MemFree>=need, settle.

    barrier_ok MUST gate the subsequent load. barrier_ok False is an
    INFRASTRUCTURE FAULT per SPEC 9: not a candidate failure, no sample
    consumed, no repair budget touched.

    THREE STATES, not two (SPEC 7a.2b, standing policy 2026-08-05). The old
    version returned a bare barrier_ok bool, which collapsed two different
    things into one False:

      REFUSED       the barrier ran, measured, and the device does not have the
                    memory. A real answer.
      CANNOT_EVALUATE   the barrier could not tell - ollama unreachable, so the
                    resident set is unknown, or /proc/meminfo unreadable, so
                    MemFree is unknown.

    Both still block the load, so the old code was not unsafe. It was
    UNDIAGNOSABLE: an operator reading a receipt could not tell "this device is
    too small for this model" from "this device did not answer", and those have
    opposite remedies. `state` and `reason` are now carried alongside
    barrier_ok, which keeps every existing caller correct.
    """
    t0 = time.time()
    try:
        resident = ps()
        for r in resident:
            post("/api/generate", {"model": r["name"], "prompt": "", "keep_alive": 0,
                                   "stream": False})
        while time.time() - t0 < 120 and ps():
            time.sleep(0.5)
        empty = not ps()
    except Exception as e:
        return {"barrier_ok": False, "state": "CANNOT_EVALUATE", "need_mb": need_mb,
                "reason": f"ollama unreachable ({type(e).__name__}); resident set "
                          f"unknown, so eviction is unverified",
                "evict_ms": round((time.time() - t0) * 1000)}
    evict_ms = round((time.time() - t0) * 1000)
    reclaim_ms, reclaimed = reclaim(need_mb)
    time.sleep(settle_s)
    mf = meminfo("MemFree")
    out = {"evict_ms": evict_ms, "ps_empty": empty, "reclaim_ms": reclaim_ms,
           "reclaimed": reclaimed, "need_mb": need_mb, "memfree_before_load_mb": mf,
           "memavailable_mb": meminfo("MemAvailable")}
    if mf is None:
        out.update(barrier_ok=False, state="CANNOT_EVALUATE",
                   reason="/proc/meminfo unreadable; MemFree unknown, and an "
                          "unknown MemFree is not a satisfied threshold")
    elif not empty:
        out.update(barrier_ok=False, state="REFUSED",
                   reason="models still resident after eviction window")
    elif mf < need_mb:
        out.update(barrier_ok=False, state="REFUSED",
                   reason=f"MemFree {mf}MB below required {need_mb}MB")
    else:
        out.update(barrier_ok=True, state="OK", reason="")
    return out

def run_cycle(seq, table, prompt="return the single word ok"):
    out = {"spec": "4a", "metric": "MemFree", "sequence": seq,
           "threshold_source": "generators.json", "transitions": [], "oom_count": 0,
           "infra_faults": 0}
    prev = None
    for i, m in enumerate(seq):
        need = table[m]["memfree_needed_mb"]
        rec = {"step": i, "model": m, "preceding_model": prev, "barrier": barrier(need)}
        if not rec["barrier"]["barrier_ok"]:
            rec.update(loaded=None, infra_fault=True,
                       note="BARRIER FAILED CLOSED - infra fault, not a candidate failure, not scored")
            out["infra_faults"] += 1
            out["transitions"].append(rec); prev = m; continue
        t0 = time.time()
        try:
            r = post("/api/generate", {"model": m, "prompt": prompt, "stream": False,
                                       "keep_alive": "3m",
                                       "options": {"num_ctx": table[m]["num_ctx"], "num_predict": 8}})
            rec.update(loaded=True, infra_fault=False, resp=(r.get("response") or "").strip()[:24])
        except Exception as e:
            rec.update(loaded=False, infra_fault=True, error=str(e)[:160])
            out["infra_faults"] += 1
            if "memory" in str(e).lower() or "terminated" in str(e).lower():
                out["oom_count"] += 1
        rec["load_gen_ms"] = round((time.time() - t0) * 1000)
        p = ps()
        rec["resident_mb"] = round(p[0]["size"] / 1048576) if p else None
        out["transitions"].append(rec); prev = m
    out["all_loaded"] = all(t.get("loaded") for t in out["transitions"])
    return out

if __name__ == "__main__":
    table = load_table()
    # --barrier-for <model>: run the barrier ONCE and report, for the runner's
    # per-cell boundary call (SPEC 4a.1). Compact single-line JSON so the caller
    # can parse it out of an ssh stream without guessing where it ends.
    if "--barrier-for" in sys.argv:
        m = sys.argv[sys.argv.index("--barrier-for") + 1]
        if m not in table:
            print(json.dumps({"barrier_ok": False, "model": m,
                              "error": "model absent from generators.json; no "
                                       "threshold of record, so FAILED CLOSED"}))
            sys.exit(0)
        out = barrier(table[m]["memfree_needed_mb"])
        out.update(model=m, threshold_source="generators.json")
        print(json.dumps(out))
        sys.exit(0)
    seq = sys.argv[1:] or ["qwen2.5-coder:3b", "granite4:micro", "qwen2.5-coder:3b"]
    print(json.dumps(run_cycle(seq, table), indent=1))
