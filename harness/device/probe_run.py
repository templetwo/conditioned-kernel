#!/usr/bin/env python3
"""Device-side probe battery — SPEC §6/§9, the `probe` stage after ACCEPT.

Runs an ACCEPTED candidate against the realized probe inputs and emits one
JSON line: per-probe output CLASSES, never probe bytes. The host stores the
classes in the receipt (SPEC §10 `probe_output_hashes`); disagreement analysis
happens downstream in results/.

WHY THIS FILE RUNS ON THE DEVICE. The probe inputs exist only on the Jetson
(PREREG §12.7); embedding them in a host-generated driver would move probe
bytes through the workstation and into ssh streams for no reason. Inputs stay
here; only SHA-256 digests of the outputs leave.

OUTPUT CLASSES, one per probe, exactly one of:
  sha256:<hex>     digest of the raw output bytes (scalar return in LE host
                   order, or the full output buffer)
  CRASH:sig<N>     the probe trapped. A crash is a LABELED CLASS, not a
                   discard (census discipline): two artifacts that both trap
                   agree about something real, and one that traps while
                   another returns a value genuinely disagree. Probes are not
                   a gate — a crash here rejects nothing and repairs nothing.
  CRASH:exit<N>    abnormal normal-exit (a kernel cannot legitimately exit).

THE DRIVER FORKS PER PROBE so one trapping probe cannot take the other 255
with it. The child computes and prints; the parent only accounts. Order is
preserved because forks are sequential and the child flushes before _exit.

Battery-level outcomes (SPEC §7a.2b — the script itself is trinary):
  exit 0   ok; the JSON line carries status "ok" and all probe classes
  exit 94  CANNOT_EVALUATE, cause in the JSON line — compile failure,
           malformed probe file, or a truncated run. The host maps this to an
           infra fault: the candidate was already accepted, so an instrument
           that cannot run the battery says nothing about the candidate.

Usage:
  probe_run.py --probes <probes.json> --candidate <cand.c> --kernel <k> \
               --signatures <kernel_signatures.json> [--cflags "..."]
"""
import argparse, hashlib, json, os, subprocess, sys, tempfile

MEASUREMENT_CFLAGS = "-O3 -mcpu=native"     # the build the artifact was accepted under


def cannot_evaluate(cause):
    print(json.dumps({"status": "CANNOT_EVALUATE", "cause": cause[:400]}))
    return 94


def _carr(name, data):
    """Byte blob as a string literal — one token, not one per byte. Same
    reasoning as vector_check.carr: the list form blows compile wall clock."""
    esc = "".join("\\%03o" % b for b in data)
    return f'static const unsigned char {name}_b[]="{esc}";'


def emit_driver(kernel, sig, probes):
    """C driver: fork per probe, child prints `PROBE <id> OUT <hex>`, parent
    prints `PROBE <id> CRASH ...` when the child dies. Signature-driven from
    the same kernel_signatures.json the vector gates use, so a kernel cannot
    be probed under a shape that disagrees with the shape it was verified
    under (the LN-7 lesson, applied before the defect this time)."""
    p, ret, tn = sig["params"], sig["returns"], sig.get("trailing_n", False)
    L = ["#include <stdint.h>", "#include <stddef.h>", "#include <stdio.h>",
         "#include <string.h>", "#include <unistd.h>", "#include <sys/wait.h>",
         "#include <stdlib.h>"]
    args = ", ".join(("const " if q["dir"] == "in" else "") + q["ctype"] + " *"
                     for q in p)
    if tn:
        args += ", size_t"
    L.append(f"{ret} {kernel}({args});")

    MAXEL = 4096
    for q in p:
        elems = q.get("elems", MAXEL)
        qual = "static "
        L.append(f"{qual}{q['ctype']} {q['name']}[{elems}];")

    L.append(r'''
static void print_hex(const unsigned char *b, size_t n){
    for(size_t i=0;i<n;i++) printf("%02x", b[i]);
}''')
    L.append("int main(void){")
    for pi, probe in enumerate(probes):
        pid = probe["id"]
        L.append("{")
        for q in p:
            if q["dir"] != "in":
                continue
            raw = bytes.fromhex(probe.get(q["hex"], "") or "")
            L.append(_carr(f"p{pi}_{q['name']}", raw))
        L.append("pid_t c=fork();")
        L.append("if(c==0){")
        # inputs land in the child so a corrupting probe cannot poison later ones
        for q in p:
            if q["dir"] == "in":
                L.append(f"memset({q['name']},0,sizeof {q['name']});")
                L.append(f"memcpy({q['name']},p{pi}_{q['name']}_b,"
                         f"sizeof p{pi}_{q['name']}_b-1);")
            else:
                L.append(f"memset({q['name']},0,sizeof {q['name']});")
        call_args = [q["name"] for q in p]
        if tn:
            call_args.append(str(probe.get("n", 0)))
        call = f"{kernel}({','.join(call_args)})"
        L.append(f'printf("PROBE {pid} OUT ");')
        if ret == "void":
            out = next(q for q in p if q["dir"] == "out")
            n_bytes = f"sizeof({out['ctype']})*{out.get('elems', MAXEL)}"
            L.append(f"{call};")
            L.append(f"print_hex((const unsigned char*){out['name']},{n_bytes});")
        else:
            L.append(f"{ret} g={call};")
            # scalar leaves as its LE-host-order bytes, matching the vector
            # files' encoding convention
            L.append('print_hex((const unsigned char*)&g,sizeof g);')
        L.append(r'printf("\n"); fflush(stdout); _exit(0);}')
        L.append("int st=0; waitpid(c,&st,0);")
        L.append(f'if(!(WIFEXITED(st)&&WEXITSTATUS(st)==0)){{'
                 f'if(WIFSIGNALED(st)) printf("PROBE {pid} CRASH sig%d\\n",WTERMSIG(st));'
                 f'else printf("PROBE {pid} CRASH exit%d\\n",WEXITSTATUS(st));}}')
        L.append("}")
    L.append("return 0;}")
    return "\n".join(L)


def run(probes_path, candidate_path, kernel, signatures_path,
        cflags=MEASUREMENT_CFLAGS, workdir=None):
    try:
        spec = json.load(open(probes_path))
    except Exception as e:
        return cannot_evaluate(f"probe file unreadable: {e}")
    if spec.get("kernel") != kernel:
        return cannot_evaluate(f"probe file is for {spec.get('kernel')!r}, "
                               f"not {kernel!r}")
    probes = spec.get("probes") or []
    if not probes:
        return cannot_evaluate("probe file contains no probes")
    sigs = {k: v for k, v in json.load(open(signatures_path)).items()
            if not k.startswith("_")}
    if kernel not in sigs:
        return cannot_evaluate(f"no signature for {kernel} in signatures file")
    sig = sigs[kernel]

    workdir = workdir or tempfile.mkdtemp(prefix="probe_run_")
    os.makedirs(workdir, exist_ok=True)
    drv = os.path.join(workdir, "drv.c")
    open(drv, "w").write(emit_driver(kernel, sig, probes))
    exe = os.path.join(workdir, "run")
    cc = ["gcc", "-std=c11"] + cflags.split()
    for cmd in (cc + ["-c", candidate_path, "-o", os.path.join(workdir, "cand.o")],
                cc + ["-c", drv, "-o", os.path.join(workdir, "drv.o")],
                cc + ["-o", exe, os.path.join(workdir, "drv.o"),
                      os.path.join(workdir, "cand.o")]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            # The candidate compiled under this exact build at gate 5, so a
            # failure here is environment or driver — instrument, not candidate.
            return cannot_evaluate(f"build failed: {r.stderr[:300]}")
    r = subprocess.run([exe], capture_output=True, text=True, timeout=1800)

    classes, seen = [], set()
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] != "PROBE":
            continue
        pid, verdict = parts[1], parts[2]
        if pid in seen:
            continue
        seen.add(pid)
        if verdict == "OUT":
            payload = parts[3] if len(parts) > 3 else ""
            digest = hashlib.sha256(bytes.fromhex(payload)).hexdigest()
            classes.append({"probe_id": pid, "output_class": f"sha256:{digest}"})
        else:
            classes.append({"probe_id": pid, "output_class": f"CRASH:{verdict}"})
    if len(classes) != len(probes):
        # A truncated battery is not a partial answer; a receipt with 200 of
        # 256 classes would make D silently incomparable across artifacts.
        return cannot_evaluate(f"battery truncated: {len(classes)} of "
                               f"{len(probes)} probes reported (driver rc="
                               f"{r.returncode})")
    print(json.dumps({"status": "ok", "kernel": kernel,
                      "probe_count": len(classes), "cflags": cflags,
                      "results": classes}))
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--signatures", required=True)
    ap.add_argument("--cflags", default=MEASUREMENT_CFLAGS)
    a = ap.parse_args(argv)
    return run(a.probes, a.candidate, a.kernel, a.signatures, a.cflags)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
