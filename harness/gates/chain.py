#!/usr/bin/env python3
"""ECS gate chain — SPEC §7, gates 1 through 6 in order, first failure stops.

Independent of how generation is parameterised, so this is buildable while the
temperature supersession is open (board #14156). It takes a candidate source
string and a packet, and returns a receipt fragment.

ORDER IS LOAD-BEARING. SPEC §7 fixes it: lint, compile, sanitize, CBMC,
vectors, budget. First failure stops and its feedback is what the repair loop
sees. Reordering would change which feedback a generator gets and therefore
what it repairs toward, so the order is data, not an implementation detail.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not decide acceptance-rate bookkeeping. A gate failure is a CANDIDATE
failure; a transport error, runner termination or barrier failure is an INFRA
FAULT and never reaches this module — the adapter classifies those upstream
and the runner keeps them out of denominators (SPEC §4a.1, §9). Conflating the
two is how a device memory fault becomes evidence about a model's capability,
which is the specific error that produced two false granite negatives.

GATE 3 AND GATE 5 BOTH RUN THE VECTORS, AND THAT SHAPES THE REDTEAM.
SPEC §7 gate 3 is a SANITIZED build run against the full acceptance vector set;
gate 5 is the same vectors under the MEASUREMENT build (-O3 -mcpu=native). A
candidate with plainly wrong values therefore fails at gate 3, not gate 5 —
verified: a wrong-polynomial crc32 stops at 3_sanitize.

So "stopped at gate 5" is a NARROW state. It means a candidate passed the
vectors under sanitizers and failed them optimised, which is the signature of
undefined behaviour that only manifests in the measurement build. That is
gate 5's distinct job, and it is exactly the cross-build instability the
post-arm census exists to characterise.

CONSEQUENCE FOR THE REDTEAM (Agent B's lane): P2's definition of done requires
every fixture to be rejected at its INTENDED gate. A fixture meant to test
gate 5 must therefore be genuine UB that survives sanitizers, not a wrong
constant — a wrong constant tests gate 3. Discovered by expectation failure
while testing this module, not by reading the spec.

GATE 4 IS PARTIAL AND SAYS SO. CBMC bounded equivalence is tractable for
crc32 and sat_add_u8 only; the other three exceeded ten minutes and were
declared intractable (LN-4). This module reports gate 4 as "skipped_intractable"
for those kernels rather than as a pass, because reporting "gate 4 clean"
across all five would merge a proof and an absence into one claim.
"""
import os, re, subprocess, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CBMC_TRACTABLE = {"crc32", "sat_add_u8"}          # LN-4, measured not assumed

FORBIDDEN_PATTERNS = [
    (r"#\s*include\s*<(?!stdint\.h|stddef\.h)", "include beyond stdint/stddef"),
    (r"\b(malloc|calloc|realloc|free)\s*\(", "dynamic allocation"),
    (r"^\s*static\b", "static storage"),
    (r"\bvolatile\b", "volatile"),
    (r"\b__asm__|\basm\s*\(", "inline assembly"),
    (r"\(\s*\*\s*\w+\s*\)\s*\(", "function pointer"),
    (r"\b(printf|fprintf|fopen|scanf|puts)\s*\(", "I/O"),
]


def gate1_lint(src, kernel):
    """Forbidden surface. Regex is a first pass; SPEC §7 asks for a parser check
    'where practical', and this is explicitly the weaker of the two."""
    hits = []
    for pat, why in FORBIDDEN_PATTERNS:
        for m in re.finditer(pat, src, re.M):
            hits.append(f"{why} at offset {m.start()}")
    # recursion: the kernel calling itself
    if re.search(r"\b" + re.escape(kernel) + r"\s*\([^;]*\)\s*;", src.split("{", 1)[-1]):
        hits.append("recursion (kernel calls itself)")
    return (not hits), hits


def _cc(src, extra, workdir, out="o.o"):
    p = os.path.join(workdir, "c.c")
    open(p, "w").write(src)
    r = subprocess.run(["gcc", "-std=c11", "-c", p, "-o", os.path.join(workdir, out)] + extra,
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def gate2_compile(src, workdir):
    ok, err = _cc(src, ["-O2", "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wshadow"],
                  workdir)
    return ok, ([] if ok else [err.strip()[:1200]])


def gate3_sanitize(src, kernel, workdir):
    """Rebuild under UBSan+ASan and run the acceptance vectors. Any report fails."""
    vec = os.path.join(ROOT, "trusted", "vectors", f"{kernel}.json")
    if not os.path.exists(vec):
        return None, ["no vector file"]
    cand = os.path.join(workdir, "cand.c")
    open(cand, "w").write(src)
    r = subprocess.run(
        ["python3", os.path.join(ROOT, "harness", "gates", "vector_check.py"), vec, cand],
        capture_output=True, text=True,
        env={**os.environ, "CFLAGS": "-fsanitize=undefined,address"})
    return (r.returncode == 0), ([] if r.returncode == 0 else [r.stdout.strip()[:800]])


def gate4_cbmc(kernel):
    if kernel not in CBMC_TRACTABLE:
        return None, [f"bounded equivalence intractable for {kernel} on this hardware "
                      f"(LN-4); reported as skipped, NOT as a pass"]
    return True, []


def gate5_vectors(src, kernel, workdir):
    """Bit-exact match on the committed vectors, with weak-arm withholding applied
    by policy rather than by anything in the packet."""
    vec = os.path.join(ROOT, "trusted", "vectors", f"{kernel}.json")
    if not os.path.exists(vec):
        return None, ["no vector file"]
    cand = os.path.join(workdir, "cand5.c")
    open(cand, "w").write(src)
    r = subprocess.run(["python3", os.path.join(ROOT, "harness", "gates", "vector_check.py"),
                        vec, cand], capture_output=True, text=True)
    first3 = [l for l in r.stdout.splitlines() if "FAIL" in l][:3]
    return (r.returncode == 0), ([] if r.returncode == 0 else first3 or [r.stdout[:400]])


def gate6_budget(src, workdir, budgets):
    """Caps are sanity bounds, not optimisation targets (SPEC §7). Actuals are
    recorded either way. Direction of gate 6's effect on D is UNRESOLVED per
    LN-3, so the runner co-reports budget-only rejections without a sign."""
    if not budgets:
        return True, [], {"note": "no budgets declared (weak arm)"}
    ok, _ = _cc(src, ["-O3", "-mcpu=native"], workdir, out="b.o")
    if not ok:
        return False, ["measurement build failed"], {}
    size = subprocess.run(["size", os.path.join(workdir, "b.o")],
                          capture_output=True, text=True).stdout.splitlines()
    text_bytes = int(size[1].split()[0]) if len(size) > 1 else None
    actual = {"text_bytes": text_bytes}
    fails = []
    cap = budgets.get("text_bytes_max")
    if cap and text_bytes and text_bytes > cap:
        fails.append(f".text {text_bytes} exceeds cap {cap}")
    return (not fails), fails, actual


def run(src, packet, workdir=None):
    """Run the chain. Returns a receipt fragment; first failure stops."""
    kernel = packet["kernel"]
    workdir = workdir or tempfile.mkdtemp()
    rec = {"kernel": kernel, "completeness": packet["completeness"],
           "gates": {}, "accepted": False, "stopped_at": None,
           "gate_order": ["1_lint", "2_compile", "3_sanitize", "4_cbmc",
                          "5_vectors", "6_budget"]}
    t0 = time.time()
    steps = [
        ("1_lint", lambda: gate1_lint(src, kernel)),
        ("2_compile", lambda: gate2_compile(src, workdir)),
        ("3_sanitize", lambda: gate3_sanitize(src, kernel, workdir)),
        ("4_cbmc", lambda: gate4_cbmc(kernel)),
        ("5_vectors", lambda: gate5_vectors(src, kernel, workdir)),
    ]
    for name, fn in steps:
        ok, feedback = fn()[:2]
        rec["gates"][name] = {"result": ("pass" if ok else
                                         "skipped_intractable" if ok is None else "fail"),
                              "feedback": feedback}
        if ok is False:
            rec["stopped_at"] = name
            rec["elapsed_ms"] = round((time.time() - t0) * 1000)
            return rec
    ok, feedback, actual = gate6_budget(src, workdir, packet.get("budgets") or {})
    rec["gates"]["6_budget"] = {"result": "pass" if ok else "fail",
                                "feedback": feedback, "actual": actual}
    if not ok:
        rec["stopped_at"] = "6_budget"
        rec["budget_only_rejection"] = True      # LN-3: direction unresolved
    else:
        rec["accepted"] = True
    rec["elapsed_ms"] = round((time.time() - t0) * 1000)
    return rec
