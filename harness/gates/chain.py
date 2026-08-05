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

GATES 3 AND 5 RUN ON THE DEVICE. SPEC §7 says gate 5 is "Acceptance vectors on
device" and gate 4 is "host side, spares Jetson RAM". Gate 3 belongs there too,
and not only by the spec: homebrew gcc's sanitizer runtime HANGS on this macOS
arm64 host for `int main(void){return 0;}`, while the Jetson runs the full
sanitized crc32 vector set in 7.5 seconds.

GATE 3 AND GATE 5 BOTH RUN THE VECTORS, AND THAT SHAPES THE REDTEAM.
SPEC §7 gate 3 is a SANITIZED build run against the full acceptance vector set;
gate 5 is the same vectors under the MEASUREMENT build (-O3 -mcpu=native). A
candidate with plainly wrong values therefore fails at gate 3, not gate 5 —
verified: a wrong-polynomial crc32 stops at 3_sanitize.

DEMONSTRATED, not merely argued: a candidate containing a shift past the width
of int produces CORRECT VALUES at -O3 and is accepted by gate 5 (exit 0), and
is REJECTED by gate 3 (exit 1, "shift exponent 32 is too large"). The clean
oracle passes both. That is the full truth table, so a gate-5 fixture can now
be proven to exercise gate 5 rather than asserted to.

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
import os, re, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CBMC_TRACTABLE = {"crc32", "sat_add_u8"}          # LN-4, measured not assumed
DEVICE = "jetson"   # gates 3 and 5 run ON DEVICE — SPEC §7, and because this
                    # workstation's gcc sanitizer runtime hangs on an empty
                    # main() while the Jetson runs the same build in 7.5s

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
        ["python3", os.path.join(ROOT, "harness", "gates", "vector_check.py"),
         "--device", DEVICE,
         "--cc", "-O1 -g -fsanitize=undefined,address -fno-sanitize-recover=all",
         vec, cand],
        capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    return (r.returncode == 0), ([] if r.returncode == 0 else [out[:800]])


def gate4_cbmc(kernel):
    """STUB. This is a tractability MEMBERSHIP CHECK, not a live CBMC run.

    "pass" here means "bounded equivalence was established for this KERNEL at
    P1", never "this CANDIDATE was proved equivalent on this run" (Agent B,
    board #14171). No receipt language may claim the latter. Wiring a per-
    candidate CBMC invocation is open work.
    """
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
                        "--device", DEVICE,
                        "--cc", "-O3 -mcpu=native", vec, cand],
                       capture_output=True, text=True)
    first3 = [l for l in r.stdout.splitlines() if "FAIL" in l][:3]
    return (r.returncode == 0), ([] if r.returncode == 0 else first3 or [r.stdout[:400]])


def gate6_budget(src, workdir, budgets, kernel):
    """ALL declared budgets, enforced on device. SPEC §7 gate 6.

    Anthony directed that every declared budget be enforced; an earlier version
    checked only .text and silently ignored cycles_ratio_max and
    stack_bytes_max, which are declared in every full packet. A cap that is
    declared and unenforced is worse than no cap: the packet claims a
    constraint the instrument does not apply.

    Caps are sanity bounds, not optimisation targets. Actuals are recorded
    either way, and per LN-3 a budget-only rejection is co-reported with its
    direction on D left UNRESOLVED — gate 6 inflates D when it removes a
    largest-cluster member and deflates it when it removes a minority one.
    """
    if not budgets:
        return True, [], {"note": "no budgets declared (weak arm)"}

    remote = f"~/ecs/gatework/budget_{kernel}"
    script = [
        "set -e", f"rm -rf {remote}", f"mkdir -p {remote}", f"cd {remote}",
        "cat > c.c <<'__ECS_EOF__'", src, "__ECS_EOF__",
        # measurement build, plus stack usage accounting
        "gcc -std=c11 -O3 -mcpu=native -fstack-usage -c c.c -o c.o 2>/dev/null",
        "echo TEXT=$(size c.o | awk 'NR==2{print $1}')",
        "echo STACK=$(awk -F'\t' '{print $2}' c.su 2>/dev/null | sort -n | tail -1)",
    ]
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", DEVICE, "bash -s"],
                       input="\n".join(script), capture_output=True, text=True,
                       timeout=300)
    if r.returncode != 0:
        return False, [f"measurement build failed on device: {r.stderr[:300]}"], {}
    actual = {}
    for line in r.stdout.splitlines():
        if line.startswith("TEXT="):
            actual["text_bytes"] = int(line[5:] or 0)
        elif line.startswith("STACK="):
            actual["stack_bytes"] = int(line[6:] or 0) if line[6:].strip() else None

    fails = []
    cap = budgets.get("text_bytes_max")
    if cap and actual.get("text_bytes", 0) > cap:
        fails.append(f".text {actual['text_bytes']} exceeds cap {cap}")
    cap = budgets.get("stack_bytes_max")
    if cap and actual.get("stack_bytes") and actual["stack_bytes"] > cap:
        fails.append(f"stack {actual['stack_bytes']} exceeds cap {cap}")

    cap = budgets.get("cycles_ratio_max")
    if cap:
        # SPEC §8 protocol on device: pinned clocks, isolated core, same-batch
        # baseline. Baseline is the FASTER oracle, measured back to back with
        # the candidate under one pin so inter-batch drift cannot enter the
        # ratio — drift reached 15% on this board when the power mode differed.
        import glob
        oracles = sorted(glob.glob(os.path.join(ROOT, "trusted", "oracles",
                                                f"{kernel}_agent*.c")))
        if len(oracles) < 2:
            actual["cycles_status"] = "no oracle pair available"
        else:
            sys.path.insert(0, os.path.join(ROOT, "harness", "measure"))
            import cycles as cyc
            fastest = None
            for o in oracles:
                m = cyc.measure(open(o).read(), open(oracles[0]).read(), kernel)
                if m.get("status") == "ok":
                    if fastest is None or m["candidate_ns"] < fastest[1]:
                        fastest = (o, m["candidate_ns"])
            if fastest is None:
                actual["cycles_status"] = "baseline measurement unusable"
            else:
                m = cyc.measure(src, open(fastest[0]).read(), kernel)
                actual["cycles_measure"] = m
                if m.get("status") == "discard_refreq":
                    # instrument fault, NOT a slow candidate. SPEC §8 discards.
                    actual["cycles_status"] = "DISCARDED (core frequency moved)"
                elif m.get("status") != "ok":
                    actual["cycles_status"] = f"infra_fault: {m.get('error','')[:120]}"
                else:
                    actual["cycles_ratio"] = m["ratio"]
                    actual["cycles_status"] = "measured"
                    if m["ratio"] > cap:
                        fails.append(f"cycles ratio {m['ratio']:.3f} exceeds cap {cap}")
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
        rec["gates"][name] = {"result": (("kernel_proved_at_p1" if name == "4_cbmc" else "pass") if ok else
                                         "skipped_intractable" if ok is None else "fail"),
                              "feedback": feedback}
        if ok is False:
            rec["stopped_at"] = name
            rec["elapsed_ms"] = round((time.time() - t0) * 1000)
            return rec
    ok, feedback, actual = gate6_budget(src, workdir, packet.get("budgets") or {}, kernel)
    rec["gates"]["6_budget"] = {"result": "pass" if ok else "fail",
                                "feedback": feedback, "actual": actual}
    if not ok:
        rec["stopped_at"] = "6_budget"
        rec["budget_only_rejection"] = True      # LN-3: direction unresolved
    else:
        rec["accepted"] = True
    rec["elapsed_ms"] = round((time.time() - t0) * 1000)
    return rec
