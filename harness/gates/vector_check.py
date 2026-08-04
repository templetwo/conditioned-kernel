#!/usr/bin/env python3
"""ECS gate 5 — acceptance vectors (SPEC §7), signature-driven.

Compiles one or more implementations against a committed vector file and
requires bit-exact match on every vector. Also used to validate a NEW vector
file against both sealed oracles before it is trusted — a vector file checked
only against its generating oracle is circular.

GENERALISED 2026-08-04. The original handled only the single-buffer
`uint32_t f(const uint8_t*, size_t)` shape, which covered crc32 and nothing
else. `fir_q15`, `matmul8_i32` and `median3x3_u8` all have shapes it could not
express, and Agent B was blocked from sealing them (board #13899). Signatures
now live in `kernel_signatures.json` as the single source; adding a kernel
means adding an entry there, not writing another driver.

Buffers are initialised from byte-hex via memcpy, so element width and
signedness are handled uniformly and host byte order is used consistently on
both sides of every comparison.

DOMAIN REFUSAL. Vector files carry a `domain` block. This gate REFUSES to run
a vector whose inputs fall outside the declared domain rather than silently
testing behaviour the ECS never pinned — e.g. the NULL-with-n>0 case that
SPEC §5 places out of domain by decision (board #13818). Testing unpinned
behaviour would manufacture disagreement that is an artifact of the gate
rather than a property of the generators, and D must measure unpinned
specification bits, not gate sloppiness.

Usage:
  vector_check.py <vectors.json> <impl.c> [<impl2.c> ...]
Exit 0 iff every implementation matches every in-domain vector.
"""
import json, os, subprocess, sys, tempfile

CC = ["gcc", "-std=c11", "-O2", "-w"]
HERE = os.path.dirname(os.path.abspath(__file__))
SIGS = os.path.join(HERE, "kernel_signatures.json")


def load_sigs():
    with open(SIGS) as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def carr(name, data):
    """Emit a byte blob; the typed buffer is memcpy'd from it by the caller."""
    body = ",".join(str(b) for b in data) or "0"
    return f"static const unsigned char {name}_b[]={{{body}}};"


def emit_driver(kernel, sig, vectors, symbols):
    p = sig["params"]
    ret = sig["returns"]
    tn = sig.get("trailing_n", False)
    L = ["#include <stdint.h>", "#include <stddef.h>", "#include <stdio.h>",
         "#include <string.h>"]

    # forward declarations, one per implementation
    for s in symbols:
        args = ", ".join(
            ("const " if q["dir"] == "in" else "") + q["ctype"] + " *" for q in p)
        if tn:
            args += ", size_t"
        L.append(f"{ret} {s}({args});")

    L.append("int main(void){int bad=0,n_=0;")
    for vi, v in enumerate(vectors):
        L.append("{")
        # inputs
        for q in p:
            if q["dir"] != "in":
                continue
            raw = bytes.fromhex(v.get(q["hex"], "") or "")
            L.append(carr(f"v{vi}_{q['name']}", raw))
            n_el = len(raw) // _width(q["ctype"])
            L.append(f"static {q['ctype']} {q['name']}[{max(n_el,1)}];"
                     f"memcpy({q['name']},v{vi}_{q['name']}_b,sizeof v{vi}_{q['name']}_b);")
        # outputs, one buffer per implementation so they cannot alias
        outs = [q for q in p if q["dir"] == "out"]
        for q in outs:
            for s in symbols:
                L.append(f"static {q['ctype']} {q['name']}_{s}[{q['elems']}];"
                         f"memset({q['name']}_{s},0,sizeof {q['name']}_{s});")
        L.append("n_++;")
        for s in symbols:
            call_args = []
            for q in p:
                call_args.append(q["name"] if q["dir"] == "in" else f"{q['name']}_{s}")
            if tn:
                call_args.append(str(v["n"]))
            call = f"{s}({','.join(call_args)})"
            exp = sig["expect"]
            if exp["kind"] == "scalar":
                L.append(f'{{{ret} g={call};if(g!=({ret}){v[exp["field"]]})'
                         f'{{bad++;printf("  FAIL [{s}] {v["id"]}\\n");}}}}')
            else:
                raw = bytes.fromhex(v.get(exp["hex"], "") or "")
                L.append(carr(f"v{vi}_exp_{s}", raw))
                tgt = f'{exp["param"]}_{s}'
                L.append(f'{call};'
                         f'if(memcmp({tgt},v{vi}_exp_{s}_b,sizeof v{vi}_exp_{s}_b))'
                         f'{{bad++;printf("  FAIL [{s}] {v["id"]}\\n");}}')
        L.append("}")
    L.append(f'printf("kernel=%s vectors=%d failures=%d\\n","{kernel}",n_,bad);')
    L.append("return bad?1:0;}")
    return "\n".join(L)


def _width(ctype):
    return {"uint8_t": 1, "int8_t": 1, "int16_t": 2, "uint16_t": 2,
            "int32_t": 4, "uint32_t": 4}.get(ctype, 1)


def in_domain(v, domain, sig):
    n_max = domain.get("n_max")
    if n_max is not None and v.get("n", 0) > n_max:
        return False, f"n={v['n']} exceeds declared n_max={n_max}"
    for q in sig["params"]:
        if q["dir"] != "in":
            continue
        h = v.get(q["hex"], "")
        if sig.get("trailing_n") and v.get("n", 0) > 0 and not h:
            return False, (f"n>0 with empty buffer '{q['name']}' violates the "
                           f"pointer precondition")
        if "elems" in q and h and len(bytes.fromhex(h)) != q["elems"] * _width(q["ctype"]):
            return False, (f"buffer '{q['name']}' is "
                           f"{len(bytes.fromhex(h))} bytes, signature requires "
                           f"{q['elems'] * _width(q['ctype'])}")
    return True, ""


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    spec = json.load(open(argv[0]))
    impls = argv[1:]
    kernel = spec.get("kernel", "unknown")
    sigs = load_sigs()
    if kernel not in sigs:
        print(f"UNKNOWN KERNEL '{kernel}' — add a signature to "
              f"{os.path.basename(SIGS)} rather than writing a bespoke driver.")
        return 2
    sig = sigs[kernel]
    domain = spec.get("domain", {})

    usable, rejected = [], []
    for v in spec["vectors"]:
        ok, why = in_domain(v, domain, sig)
        (usable.append(v) if ok else rejected.append((v.get("id"), why)))
    if rejected:
        print(f"REFUSED {len(rejected)} out-of-domain vector(s) — the gate does "
              f"not test what the ECS did not pin:")
        for vid, why in rejected:
            print(f"  {vid}: {why}")

    symbols = [f"impl{i}" for i in range(len(impls))]
    with tempfile.TemporaryDirectory() as td:
        objs = []
        for i, path in enumerate(impls):
            o = os.path.join(td, f"i{i}.o")
            r = subprocess.run(CC + [f"-D{kernel}={symbols[i]}", "-c", path, "-o", o],
                               capture_output=True, text=True)
            if r.returncode:
                print(f"COMPILE FAIL {path}\n{r.stderr[:400]}")
                return 1
            objs.append(o)
        drv = os.path.join(td, "drv.c")
        open(drv, "w").write(emit_driver(kernel, sig, usable, symbols))
        exe = os.path.join(td, "drv")
        r = subprocess.run(CC + ["-o", exe, drv] + objs, capture_output=True, text=True)
        if r.returncode:
            print(f"LINK FAIL\n{r.stderr[:600]}")
            return 1
        r = subprocess.run([exe], capture_output=True, text=True)
        print(r.stdout.rstrip())
        for i, path in enumerate(impls):
            print(f"  {symbols[i]} = {path}")
        return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
