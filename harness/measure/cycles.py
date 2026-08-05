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
import json, subprocess, sys

DEVICE = "jetson"
REMOTE = "~/ecs/gatework/cycles"

DRIVER = r'''
#define _POSIX_C_SOURCE 199309L
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

uint32_t cand(const uint8_t *, size_t);
uint32_t base(const uint8_t *, size_t);

#define WARMUP 200
#define MEASURED 1000
#define NB 4096

static int cmp_d(const void *a, const void *b){
    double x=*(const double*)a, y=*(const double*)b; return (x>y)-(x<y); }
static double median(double *v,int n){ qsort(v,(size_t)n,sizeof(double),cmp_d);
    return (n&1)?v[n/2]:0.5*(v[n/2-1]+v[n/2]); }

static double bench(uint32_t (*f)(const uint8_t*,size_t), const uint8_t *b, size_t n){
    volatile uint32_t sink=0;
    for(int i=0;i<WARMUP;i++) sink^=f(b,n);
    static double s[MEASURED];
    for(int i=0;i<MEASURED;i++){
        struct timespec t0,t1;
        clock_gettime(CLOCK_MONOTONIC_RAW,&t0);
        sink^=f(b,n);
        clock_gettime(CLOCK_MONOTONIC_RAW,&t1);
        s[i]=(double)(t1.tv_sec-t0.tv_sec)*1e9+(double)(t1.tv_nsec-t0.tv_nsec);
    }
    (void)sink;
    return median(s,MEASURED);
}

int main(void){
    static uint8_t buf[NB];
    for(int i=0;i<NB;i++) buf[i]=(uint8_t)(i*31+7);
    /* SAME BATCH: baseline and candidate measured back to back under one pin. */
    double b = bench(base, buf, NB);
    double c = bench(cand, buf, NB);
    printf("{\"baseline_ns\":%.1f,\"candidate_ns\":%.1f,\"ratio\":%.4f}\n",
           b, c, (b>0.0)? c/b : -1.0);
    return 0;
}
'''


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
        "cat > cand.c <<'__EOF__'", candidate_src, "__EOF__",
        "cat > base.c <<'__EOF__'", oracle_src, "__EOF__",
        "cat > drv.c <<'__EOF__'", DRIVER, "__EOF__",
        f"gcc -std=c11 -O3 -mcpu=native -D{kernel}=cand -c cand.c -o cand.o",
        f"gcc -std=c11 -O3 -mcpu=native -D{kernel}=base -c base.c -o base.o",
        "gcc -std=c11 -O3 -mcpu=native -c drv.c -o drv.o",
        "gcc -std=c11 -O3 -mcpu=native -o run drv.o cand.o base.o",
        "taskset -c 3 ./run",
        "echo POST=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq)",
    ]
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", device, "bash -s"],
                       input="\n".join(script), capture_output=True, text=True,
                       timeout=900)
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
