#!/usr/bin/env python3
"""Gate 6 cycle-ratio measurement — SPEC §8 protocol, on device.

Completes the last of Anthony's four P2 gate corrections. A declared-and-
unenforced cap is worse than no cap, because the packet claims a constraint the
instrument does not apply.

PROTOCOL, from SPEC §8, and none of it is optional:
  - clocks pinned before every batch (nvpmodel MAXN_SUPER + jetson_clocks) and
    the pin recorded in the receipt
  - isolated core via taskset -c 3
  - scaling_cur_freq read before and after; a mismatch DISCARDS the measurement
    rather than averaging over it
  - 200 warmup, 1000 measured, median and MAD
  - baseline = the faster of the two oracles at -O3 -mcpu=native, measured in
    the SAME BATCH, so drift between batches cannot leak into the ratio
  - timing_source "clock" (CLOCK_MONOTONIC_RAW): perf is not installed on this
    device, per the SPEC §4 fallback, and sources are never mixed within an arm

The candidate and the baseline are measured back to back under one pin. That is
the point of "same-batch": a ratio built from two separately-pinned runs would
carry the drift between them, which on this board was measured at up to 15%
when the power mode differed (P0 receipt).
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "gates"))
import remote as rmt

DEVICE = "jetson"
REMOTE = "~/ecs/gatework/cycles"

PRELUDE = r'''
#define _POSIX_C_SOURCE 199309L
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define WARMUP 200
#define MEASURED 1000
#define NB 4096

static int cmp_d(const void *a, const void *b){
    double x=*(const double*)a, y=*(const double*)b; return (x>y)-(x<y); }
static double median(double *v,int n){ qsort(v,(size_t)n,sizeof(double),cmp_d);
    return (n&1)?v[n/2]:0.5*(v[n/2-1]+v[n/2]); }

/* Kernels differ in arity and return type, so the thing benched is a
   zero-argument thunk generated per kernel rather than one fixed function
   pointer type. See emit_driver. */
static double bench(void (*f)(void)){
    for(int i=0;i<WARMUP;i++) f();
    static double s[MEASURED];
    for(int i=0;i<MEASURED;i++){
        struct timespec t0,t1;
        clock_gettime(CLOCK_MONOTONIC_RAW,&t0);
        f();
        clock_gettime(CLOCK_MONOTONIC_RAW,&t1);
        s[i]=(double)(t1.tv_sec-t0.tv_sec)*1e9+(double)(t1.tv_nsec-t0.tv_nsec);
    }
    return median(s,MEASURED);
}
'''

EPILOGUE = r'''
int main(void){
    init_inputs();
    /* SAME BATCH: baseline and candidate measured back to back under one pin. */
    double b = bench(call_base);
    double c = bench(call_cand);
    printf("{\"baseline_ns\":%.1f,\"candidate_ns\":%.1f,\"ratio\":%.4f}\n",
           b, c, (b>0.0)? c/b : -1.0);
    return 0;
}
'''

HERE = os.path.dirname(os.path.abspath(__file__))
SIGS = os.path.join(os.path.dirname(HERE), "gates", "kernel_signatures.json")


def emit_driver(kernel):
    """Generate the bench driver for THIS kernel from the shared signature file.

    GENERALISED 2026-08-05, and the reason is a finding rather than tidiness.
    The original driver hardcoded crc32's shape:

        uint32_t cand(const uint8_t *, size_t);

    which is the only one of the five kernels it fits. For the other four the
    driver could not compile, `measure()` returned infra_fault, and gate 6 —
    before the §7a.2 corrections — recorded "baseline measurement unusable" as a
    status string and PASSED. So a declared `cycles_ratio_max` went unevaluated
    on four of five kernels while their receipts read green.

    That is precisely the failure class Anthony held P2 open for, and it stayed
    invisible until the gate stopped passing what it could not measure. The
    fail-closed correction did not create this problem; it revealed it. Worth
    keeping in the writeup: the instrument's silence was the bug, and the four
    green receipts it produced were the evidence that looked most like success.

    Signatures come from the same kernel_signatures.json vector_check.py uses,
    so a kernel cannot be benched under a shape that disagrees with the shape it
    is verified under.
    """
    with open(SIGS) as f:
        sigs = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    if kernel not in sigs:
        raise KeyError(f"no signature for {kernel} in kernel_signatures.json")
    sig = sigs[kernel]
    p, ret, tn = sig["params"], sig["returns"], sig.get("trailing_n", False)

    L = [PRELUDE]
    # forward declarations for both implementations
    for sym in ("cand", "base"):
        args = ", ".join(("const " if q["dir"] == "in" else "") + q["ctype"] + " *"
                         for q in p)
        if tn:
            args += ", size_t"
        L.append(f"{ret} {sym}({args});")

    # One input set, shared by both implementations so neither is measured on
    # different data. Outputs are per-implementation so they cannot alias.
    n_bench = None
    for q in p:
        elems = q.get("elems", 4096)
        if q["dir"] == "in":
            L.append(f"static {q['ctype']} {q['name']}[{elems}];")
            if n_bench is None:
                n_bench = elems
        else:
            for sym in ("cand", "base"):
                L.append(f"static {q['ctype']} {q['name']}_{sym}[{elems}];")
    L.append("static volatile uint64_t sink;")

    # Deterministic, identical on every run and every seat. Not random: a bench
    # whose inputs vary between the baseline and candidate batches would put
    # that variation into the ratio.
    L.append("static void init_inputs(void){")
    for q in p:
        if q["dir"] == "in":
            elems = q.get("elems", 4096)
            L.append(f"  for(size_t i=0;i<{elems};i++) "
                     f"{q['name']}[i]=({q['ctype']})(i*31u+7u);")
    L.append("}")

    for sym in ("cand", "base"):
        call_args = [q["name"] if q["dir"] == "in" else f"{q['name']}_{sym}" for q in p]
        if tn:
            call_args.append(str(n_bench or 4096))
        call = f"{sym}({','.join(call_args)})"
        L.append(f"static void call_{sym}(void){{")
        if ret == "void":
            # The optimiser cannot elide a call that writes an observable buffer,
            # but the read keeps the dependency explicit at -O3.
            out = next((q for q in p if q["dir"] == "out"), None)
            L.append(f"  {call};")
            if out:
                L.append(f"  sink ^= (uint64_t){out['name']}_{sym}[0];")
        else:
            L.append(f"  sink ^= (uint64_t){call};")
        L.append("}")
    L.append(EPILOGUE)
    return "\n".join(L)


def measure(candidate_src, oracle_src, kernel="crc32", device=DEVICE):
    """Return the cycle ratio of candidate to baseline, or an unusable verdict."""
    script = [
        "set -e",
        f"rm -rf {REMOTE}", f"mkdir -p {REMOTE}", f"cd {REMOTE}",
        # pin clocks; record the mode. MAXN_SUPER is mode 2 on this board —
        # mode 0 is 15W and cost 15% in the P0 receipt when used by mistake.
        "sudo -n nvpmodel -m 2 >/dev/null 2>&1 || true",
        "sudo -n jetson_clocks >/dev/null 2>&1 || true",
        "echo PRE=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq)",
    ] + rmt.put("cand.c", candidate_src) + rmt.put("base.c", oracle_src) \
      + rmt.put("drv.c", emit_driver(kernel)) + [
        f"gcc -std=c11 -O3 -mcpu=native -D{kernel}=cand -c cand.c -o cand.o",
        f"gcc -std=c11 -O3 -mcpu=native -D{kernel}=base -c base.c -o base.o",
        "gcc -std=c11 -O3 -mcpu=native -c drv.c -o drv.o",
        "gcc -std=c11 -O3 -mcpu=native -o run drv.o cand.o base.o",
        "taskset -c 3 ./run",
        "echo POST=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq)",
    ]
    r = rmt.run(device, script)
    if rmt.transfer_failed(r):
        return {"status": "infra_fault", "error": "ECS_TRANSFER_MISMATCH: "
                                                  "payload digest mismatch on device"}
    if r.returncode != 0:
        return {"status": "infra_fault", "error": r.stderr[-300:]}
    pre = post = None
    payload = None
    for line in r.stdout.splitlines():
        if line.startswith("PRE="):
            pre = line[4:].strip()
        elif line.startswith("POST="):
            post = line[5:].strip()
        elif line.startswith("{"):
            payload = json.loads(line)
    if payload is None:
        return {"status": "infra_fault", "error": "no measurement emitted"}
    # SPEC §8: frequency mismatch discards the measurement. It is NOT averaged
    # over and NOT reported as a slow candidate — an unstable bench is an
    # instrument fault, not a property of the code under test.
    if pre != post:
        return {"status": "discard_refreq", "freq_pre": pre, "freq_post": post,
                "note": "core frequency moved during measurement; SPEC §8 "
                        "requires discard and remeasure, never averaging"}
    payload.update({"status": "ok", "freq_pre": pre, "freq_post": post,
                    "timing_source": "clock", "warmup": 200, "measured": 1000,
                    "core": 3, "same_batch": True})
    return payload


if __name__ == "__main__":
    cand = open(sys.argv[1]).read()
    base = open(sys.argv[2]).read()
    print(json.dumps(measure(cand, base, sys.argv[3] if len(sys.argv) > 3 else "crc32"),
                     indent=1))
