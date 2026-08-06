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

EVERY GATE FAILS CLOSED (Anthony, 2026-08-05, P2 held open).
---------------------------------------------------------
An earlier version of this module let three different absences flow onward as
if they were passes:

  - CBMC timing out, or terminating without a verdict, returned "not a failure"
    and the candidate continued toward acceptance UNPROVEN.
  - A declared `stack_bytes_max` or `text_bytes_max` whose actual could not be
    read compared against nothing and passed.
  - A declared `cycles_ratio_max` whose measurement was unusable — no oracle
    pair, frequency drift, transport error — recorded a status string and
    passed.

In all three the artifact was accepted BECAUSE the instrument failed. That is
the worst available direction of error for this experiment: acceptance rate is
a primary endpoint, so instrument failures would have been silently converted
into evidence of generator capability. The rule is now uniform — a declared
constraint that cannot be evaluated is never a pass.

WHICH LEAVES THE QUESTION OF WHAT IT *IS*, and the answer is not always "fail".
Three outcomes are distinguished, and the distinction is the whole point:

  pass / fail            a property of the CANDIDATE. Scored.
  skipped_intractable    a DECLARED exemption (LN-4). Recorded, never a pass.
  infra fault            a property of the INSTRUMENT — ssh died, the payload
                         digest mismatched, core frequency moved mid-measurement,
                         the oracle pair is missing. Raises Infra, consumes no
                         sample, touches no repair budget, enters no acceptance
                         denominator (SPEC §4a.1, §8, §9).

Failing closed into the wrong one of those would trade a silent inflation for a
silent deflation. A frequency drift scored as a slow candidate is exactly the
error SPEC §8 forbids when it says discard and remeasure rather than average.

WEAK-ARM WITHHOLDING IS APPLIED HERE, NOT MERELY RECORDED.
Gates 3 and 5 both run the acceptance vector set, and in arm 3 that set is half
withheld (PREREG §6 arm 3). The receipt named the withheld ids while both gates
went on running the full committed file, so the third of arm 3's three
weakenings did not exist as an experimental manipulation — only as a claim
about one. `run()` now materialises the arm's vector file from
vector_policy.select() and hands THAT to gates 3 and 5.

SPEC §7 gate 3 says "the full acceptance vector set"; read against PREREG §6
that means the full set the ARM has, not the full committed file. Applying
withholding at gate 5 alone would leave the weak arm's candidates still held to
every vector under sanitizers, which nullifies the manipulation while appearing
to implement it. Posted for counter-sign as a §7 clarification.
"""
import json, os, re, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vector_policy


class Infra(Exception):
    """Instrument fault. NOT a candidate failure and never scored (SPEC §4a.1).

    Raised only where the cause is demonstrably ours: transport, digest
    mismatch, a missing oracle pair, a bench whose clock moved. Everything a
    candidate could have caused fails closed as a candidate failure instead.
    """
CBMC_TRACTABLE = {"crc32", "sat_add_u8"}          # LN-4, measured not assumed
# The exemption is DECLARED, per kernel, never inherited by absence. A kernel
# in neither set has no measured tractability on record; under §7a.2b that is
# cannot-evaluate (infra), not an exemption. fir_q15_canary enters one of
# these sets only after its own LN-4-discipline measurement (SUPERSESSION-002).
CBMC_INTRACTABLE_DECLARED = {"fir_q15", "matmul8_i32", "median3x3_u8"}  # LN-4
DEVICE = "jetson"   # gates 3 and 5 run ON DEVICE — SPEC §7, and because this
                    # workstation's gcc sanitizer runtime hangs on an empty
                    # main() while the Jetson runs the same build in 7.5s

FORBIDDEN_PATTERNS = [
    (r"#\s*include\s*<(?!stdint\.h|stddef\.h)", "include beyond stdint/stddef"),
    (r"\b(malloc|calloc|realloc|free)\s*\(", "dynamic allocation"),
    (r"\bvolatile\b", "volatile"),
    (r"\b__asm__|\basm\s*\(", "inline assembly"),
    (r"\(\s*\*\s*\w+\s*\)\s*\(", "function pointer"),
    (r"\b(printf|fprintf|fopen|scanf|puts)\s*\(", "I/O"),
]


def _sha_file(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _static_storage_hits(src):
    """`static` STORAGE only — not `static` linkage on a function.

    SPEC §7 forbids "`static` storage": a variable with static storage duration,
    i.e. hidden state that survives across calls. A `static` HELPER FUNCTION has
    no storage at all; it is internal linkage and is ordinary, idiomatic C.

    A naive `^\s*static` regex conflates them, and that is not hypothetical: it
    rejected BOTH of Agent B's sealed oracles for fir_q15 and median3x3_u8,
    which use `static int16_t sat_i16(...)` and `static void sort9(...)`. A
    sealed, dual-agreed oracle failing its own gate is the loudest possible
    signal that the gate is wrong, and in a real arm it would have rejected
    valid generator output for a reason unrelated to the ECS — inflating the
    rejection rate and corrupting acceptance rate, a primary endpoint.

    Discriminator: from `static` to the first `;` or `{`, a function declarator
    contains `(`. A storage declaration does not.
    """
    hits = []
    for m in re.finditer(r"^[ \t]*static\b", src, re.M):
        tail = src[m.start():]
        end = min((tail.index(c) for c in ";{" if c in tail), default=len(tail))
        if "(" not in tail[:end]:
            hits.append(f"static storage at offset {m.start()}")
    return hits


def gate1_lint(src, kernel):
    """Forbidden surface. Regex is a first pass; SPEC §7 asks for a parser check
    'where practical', and this is explicitly the weaker of the two."""
    hits = _static_storage_hits(src)
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


def _vector_run(vec, src, workdir, name, cc):
    """Shared body of gates 3 and 5: same vectors, different build.

    `vec` is the ARM's vector file, already filtered by vector_policy — not the
    committed file. Exit 91 from vector_check means the device payload digest
    mismatched, which is instrument, not candidate.
    """
    if not os.path.exists(vec):
        raise Infra(f"no vector file for this arm at {vec}")
    cand = os.path.join(workdir, name)
    open(cand, "w").write(src)
    r = subprocess.run(
        ["python3", os.path.join(ROOT, "harness", "gates", "vector_check.py"),
         "--device", DEVICE, "--cc", cc, vec, cand],
        capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode == 91 or "ECS_TRANSFER_MISMATCH" in out:
        raise Infra(f"device transfer failed: {out[:300]}")
    if r.returncode == 255:
        raise Infra(f"ssh transport failed: {out[:300]}")
    return (r.returncode == 0), ([] if r.returncode == 0 else [out[:800]])


def gate3_sanitize(src, kernel, workdir, vec):
    """Rebuild under UBSan+ASan and run the arm's acceptance vectors.

    Any sanitizer report fails. A missing vector file is now an Infra rather
    than the old `None` — `None` meant "declared exemption", and a vector file
    that is absent is a broken instrument, not a declared exemption. Reported as
    skipped, it would have carried the candidate onward with gate 3 never run.
    """
    return _vector_run(vec, src, workdir, "cand.c",
                       "-O1 -g -fsanitize=undefined,address -fno-sanitize-recover=all")


def gate4_cbmc(kernel, src=None, workdir=None):
    """LIVE bounded equivalence between the candidate and a sealed oracle.

    Anthony directed this to execute CBMC rather than return a stub. It now
    does — for the two kernels where LN-4 measured it tractable. For the other
    three it still reports skipped_intractable, and wiring the invocation does
    not change that: bounded equivalence for fir_q15, matmul8_i32 and
    median3x3_u8 exceeded ten minutes and one exceeded thirty-five. Making the
    call real makes two kernels real; it does not manufacture a third.

    Runs HOST-side per SPEC §7 ("host side, spares Jetson RAM"), which is also
    where cbmc is installed. Unlike gates 3 and 5, nothing about CBMC needs the
    device.
    """
    if kernel in CBMC_INTRACTABLE_DECLARED:
        return None, [f"bounded equivalence intractable for {kernel} on this "
                      f"hardware (LN-4); reported as skipped, NOT as a pass"]
    if kernel not in CBMC_TRACTABLE:
        raise Infra(f"gate 4 has no measured tractability verdict for {kernel}: "
                    f"neither declared tractable nor declared intractable (LN-4). "
                    f"Measure it and declare it; an exemption is never inherited "
                    f"by absence (§7a.2b)")
    if src is None:
        return False, ["no candidate supplied; unproven, and unproven is not a pass"]
    # A missing harness or oracle is OUR omission, not the candidate's. Both
    # used to report `None` — the same value as LN-4's declared exemption — so a
    # repo in which the CBMC harness had simply never been written was
    # indistinguishable in the receipt from one where intractability was
    # measured and declared.
    harness = os.path.join(ROOT, "harness", "gates", "cbmc", f"equiv_{kernel}.c")
    if not os.path.exists(harness):
        raise Infra(f"no CBMC harness for {kernel}, which is declared tractable")
    oracle = os.path.join(ROOT, "trusted", "oracles", f"{kernel}_agentB.c")
    if not os.path.exists(oracle):
        raise Infra(f"no sealed oracle for {kernel} to compare against")

    sym = {"crc32": ("crc32_A", "crc32_B"), "sat_add_u8": ("sat_add_A", "sat_add_B")}[kernel]
    unwind = {"crc32": "60", "sat_add_u8": "10"}[kernel]
    a = os.path.join(workdir, "cbmc_cand.c")
    b = os.path.join(workdir, "cbmc_base.c")
    open(a, "w").write(src.replace(f"{kernel}(", f"{sym[0]}("))
    open(b, "w").write(open(oracle).read().replace(f"{kernel}(", f"{sym[1]}("))
    try:
        r = subprocess.run(
            ["cbmc", harness, a, b, "--arch", "arm64", "--bounds-check",
             "--pointer-check", "--signed-overflow-check", "--unwind", unwind,
             "--unwinding-assertions"],
            capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise Infra("cbmc is not installed on this host; gate 4 cannot run")
    except subprocess.TimeoutExpired:
        # FAIL CLOSED. The old text — "not a pass and not a failure" — was
        # honest about the epistemics and wrong about the consequence: it
        # returned None, which the chain read as a declared skip, and the
        # candidate continued to gates 5 and 6 and could be ACCEPTED unproven.
        # A timeout is a property of this candidate's own complexity on a
        # kernel LN-4 measured as tractable, so it is scored as a failure.
        return False, [f"CBMC exceeded 600s for {kernel}, a kernel LN-4 measured "
                       f"tractable; the candidate is UNPROVEN and unproven is "
                       f"not a pass"]
    if "VERIFICATION SUCCESSFUL" in r.stdout:
        return True, []
    fails = [l for l in r.stdout.splitlines() if "FAILURE" in l][:3]
    if fails:
        return False, fails
    # No verdict either way: a parse error, an unwinding assertion, a crash.
    # Also fails closed, and says which it was rather than borrowing the
    # counterexample wording.
    return False, [f"CBMC terminated without a verdict (rc={r.returncode}); "
                   f"unproven, not a pass", (r.stdout or r.stderr)[-400:]]


def gate5_vectors(src, kernel, workdir, vec):
    """Bit-exact match on the ARM's vectors under the measurement build.

    Withholding is applied by vector_policy upstream in run(), keyed on
    completeness — never by anything a packet author can set.
    """
    return _vector_run(vec, src, workdir, "cand5.c", "-O3 -mcpu=native")


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

    import remote as rmt
    remotedir = f"~/ecs/gatework/budget_{kernel}"
    script = ["set -e", f"rm -rf {remotedir}", f"mkdir -p {remotedir}",
              f"cd {remotedir}"] + rmt.put("c.c", src) + [
        # measurement build, plus stack usage accounting
        "gcc -std=c11 -O3 -mcpu=native -fstack-usage -c c.c -o c.o 2>/dev/null",
        "echo TEXT=$(size c.o | awk 'NR==2{print $1}')",
        "echo STACK=$(awk -F'\t' '{print $2}' c.su 2>/dev/null | sort -n | tail -1)",
    ]
    r = rmt.run(DEVICE, script, timeout=300)
    if rmt.transfer_failed(r):
        raise Infra("gate 6 payload digest mismatch on device")
    if r.returncode == 255:
        raise Infra(f"gate 6 ssh transport failed: {r.stderr[:300]}")
    if r.returncode != 0:
        return False, [f"measurement build failed on device: {r.stderr[:300]}"], {}
    actual = {}
    for line in r.stdout.splitlines():
        if line.startswith("TEXT="):
            actual["text_bytes"] = int(line[5:]) if line[5:].strip().isdigit() else None
        elif line.startswith("STACK="):
            actual["stack_bytes"] = int(line[6:]) if line[6:].strip().isdigit() else None

    # EVERY DECLARED CAP PRODUCES A VERDICT. An unreadable actual is a failure,
    # not a pass: `size` or `-fstack-usage` producing nothing on a build that
    # otherwise succeeded is a property of what the candidate emitted, and
    # "the cap could not be measured" must never read as "the cap was met".
    fails = []
    for key, field, label in (("text_bytes_max", "text_bytes", ".text"),
                              ("stack_bytes_max", "stack_bytes", "stack")):
        cap = budgets.get(key)
        if not cap:
            continue
        got = actual.get(field)
        if got is None:
            fails.append(f"{label} cap {cap} declared but NOT MEASURABLE on the "
                         f"device build; unmeasured is not a pass")
        elif got > cap:
            fails.append(f"{label} {got} exceeds cap {cap}")

    cap = budgets.get("cycles_ratio_max")
    if cap:
        # SPEC §8 protocol on device: pinned clocks, isolated core, same-batch
        # baseline. Baseline is the FASTER oracle, measured back to back with
        # the candidate under one pin so inter-batch drift cannot enter the
        # ratio — drift reached 15% on this board when the power mode differed.
        import glob
        oracles = sorted(glob.glob(os.path.join(ROOT, "trusted", "oracles",
                                                f"{kernel}_agent*.c")))
        # Every unusable outcome below raises Infra rather than recording a
        # status string and falling through to a pass. These causes are all
        # OURS — a repo missing an oracle pair, a bench whose clock moved, a
        # dead transport — so the sample is not spent and the cell remeasures,
        # which is exactly what SPEC §8 requires instead of averaging over a
        # drifted measurement or scoring it as a slow candidate.
        if len(oracles) < 2:
            raise Infra(f"cycles_ratio_max declared for {kernel} but no oracle "
                        f"pair is present to form a baseline")
        sys.path.insert(0, os.path.join(ROOT, "harness", "measure"))
        import cycles as cyc
        fastest = None
        for o in oracles:
            m = cyc.measure(open(o).read(), open(oracles[0]).read(), kernel)
            if m.get("status") == "ok":
                if fastest is None or m["candidate_ns"] < fastest[1]:
                    fastest = (o, m["candidate_ns"])
        if fastest is None:
            raise Infra("baseline measurement unusable; no oracle produced a "
                        "clean same-batch timing")
        m = cyc.measure(src, open(fastest[0]).read(), kernel)
        actual["cycles_measure"] = m
        actual["baseline_oracle"] = os.path.basename(fastest[0])
        if m.get("status") == "discard_refreq":
            raise Infra(f"core frequency moved during measurement "
                        f"({m.get('freq_pre')} -> {m.get('freq_post')}); SPEC §8 "
                        f"discards and remeasures — never a slow candidate")
        if m.get("status") != "ok":
            raise Infra(f"cycle measurement failed: {str(m.get('error'))[:160]}")
        actual["cycles_ratio"] = m["ratio"]
        actual["cycles_status"] = "measured"
        if m["ratio"] > cap:
            fails.append(f"cycles ratio {m['ratio']:.3f} exceeds cap {cap}")
    return (not fails), fails, actual


def run(src, packet, workdir=None):
    """Run the chain. Returns a receipt fragment; first failure stops."""
    kernel = packet["kernel"]
    completeness = packet["completeness"]
    workdir = workdir or tempfile.mkdtemp()
    rec = {"kernel": kernel, "completeness": completeness,
           "gates": {}, "accepted": False, "stopped_at": None,
           "infra_fault": False,
           "gate_order": ["1_lint", "2_compile", "3_sanitize", "4_cbmc",
                          "5_vectors", "6_budget"]}
    t0 = time.time()

    # --- the ARM's vector set, withheld half actually removed ---------------
    committed = os.path.join(ROOT, "trusted", "vectors", f"{kernel}.json")
    if not os.path.exists(committed):
        rec.update(infra_fault=True,
                   infra_reason=f"no committed vector file for {kernel}")
        return rec
    spec = json.load(open(committed))
    used, _withheld = vector_policy.select(spec["vectors"], completeness)
    armvec = os.path.join(workdir, f"{kernel}.{completeness}.json")
    json.dump({**spec, "vectors": used}, open(armvec, "w"))
    rec["vector_policy"] = vector_policy.receipt_fields(spec["vectors"], completeness)
    rec["vector_policy"]["applied_to"] = ["3_sanitize", "5_vectors"]
    rec["vector_policy"]["arm_vector_file_sha256"] = _sha_file(armvec)

    steps = [
        ("1_lint", lambda: gate1_lint(src, kernel)),
        ("2_compile", lambda: gate2_compile(src, workdir)),
        ("3_sanitize", lambda: gate3_sanitize(src, kernel, workdir, armvec)),
        ("4_cbmc", lambda: gate4_cbmc(kernel, src, workdir)),
        ("5_vectors", lambda: gate5_vectors(src, kernel, workdir, armvec)),
    ]
    try:
        for name, fn in steps:
            ok, feedback = fn()[:2]
            rec["gates"][name] = {"result": ("pass" if ok else
                                             "skipped_intractable" if ok is None
                                             else "fail"),
                                  "feedback": feedback}
            if ok is False:
                rec["stopped_at"] = name
                rec["elapsed_ms"] = round((time.time() - t0) * 1000)
                return rec
        ok, feedback, actual = gate6_budget(src, workdir,
                                            packet.get("budgets") or {}, kernel)
    except Infra as e:
        # Not a candidate failure. The runner spends no sample, touches no
        # repair budget, and keeps this out of every acceptance denominator.
        rec.update(infra_fault=True, infra_reason=str(e),
                   stopped_at=None, accepted=False,
                   elapsed_ms=round((time.time() - t0) * 1000))
        return rec
    rec["gates"]["6_budget"] = {"result": "pass" if ok else "fail",
                                "feedback": feedback, "actual": actual}
    if not ok:
        rec["stopped_at"] = "6_budget"
        rec["budget_only_rejection"] = True      # LN-3: direction unresolved
    else:
        rec["accepted"] = True
    rec["elapsed_ms"] = round((time.time() - t0) * 1000)
    return rec
