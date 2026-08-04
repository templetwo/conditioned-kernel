#!/usr/bin/env python3
"""ECS gate 5 — acceptance vectors (SPEC §7).

Compiles a candidate (or an oracle) against a committed vector file and
requires bit-exact match on every vector. Also usable to validate a NEW
vector file against both sealed oracles before it is trusted, which is how
trusted/vectors/crc32.json was accepted (93/93 against A and B independently).

Vector files carry a `domain` block. This gate REFUSES to run a vector whose
inputs fall outside the declared domain, so the harness cannot quietly test
behaviour the ECS never pinned — e.g. the NULL-with-n>0 case that SPEC §5
places out of domain by decision (board #13818).

Usage:
  vector_check.py <vectors.json> <impl.c> [<impl2.c> ...]
Exit 0 iff every implementation matches every vector.
"""
import json, os, subprocess, sys, tempfile

CC = ["gcc", "-std=c11", "-O2", "-w"]


def emit_driver(vectors, kernel, symbols):
    """Generate a C driver comparing each symbol against expected values."""
    lines = ["#include <stdint.h>", "#include <stddef.h>", "#include <stdio.h>"]
    for s in symbols:
        lines.append(f"uint32_t {s}(const uint8_t*, size_t);")
    lines.append("int main(void){int bad=0,n_=0;")
    for v in vectors:
        h = v.get("input_hex", "")
        data = bytes.fromhex(h) if h else b""
        arr = ",".join(str(b) for b in data) or "0"
        lines.append(f'{{static const uint8_t d[]={{{arr}}};uint32_t e={v["expected"]};n_++;')
        for s in symbols:
            lines.append(
                f'{{uint32_t g={s}(d,{v["n"]});'
                f'if(g!=e){{bad++;printf("  FAIL [{s}] {v["id"]} exp=0x%08X got=0x%08X\\n",e,g);}}}}')
        lines.append("}")
    lines.append('printf("kernel=%s vectors=%d failures=%d\\n","' + kernel + '",n_,bad);')
    lines.append("return bad?1:0;}")
    return "\n".join(lines)


def in_domain(v, domain):
    """Reject vectors outside the declared domain rather than silently running them."""
    n_max = domain.get("n_max")
    if n_max is not None and v.get("n", 0) > n_max:
        return False, f"n={v['n']} exceeds declared n_max={n_max}"
    # A vector with n>0 must carry input bytes; a null/empty buffer with n>0 is
    # out of domain by the SPEC §5 pointer precondition.
    if v.get("n", 0) > 0 and not v.get("input_hex"):
        return False, "n>0 with no input bytes violates the pointer precondition"
    return True, ""


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    spec = json.load(open(argv[0]))
    impls = argv[1:]
    kernel = spec.get("kernel", "unknown")
    domain = spec.get("domain", {})
    vectors = spec["vectors"]

    rejected = []
    usable = []
    for v in vectors:
        ok, why = in_domain(v, domain)
        (usable if ok else rejected).append(v if ok else (v.get("id"), why))
    if rejected:
        print(f"REFUSED {len(rejected)} out-of-domain vector(s) — the gate does not test "
              f"what the ECS did not pin:")
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
        open(drv, "w").write(emit_driver(usable, kernel, symbols))
        exe = os.path.join(td, "drv")
        r = subprocess.run(CC + ["-o", exe, drv] + objs, capture_output=True, text=True)
        if r.returncode:
            print(f"LINK FAIL\n{r.stderr[:400]}")
            return 1
        r = subprocess.run([exe], capture_output=True, text=True)
        print(r.stdout.rstrip())
        for i, p in enumerate(impls):
            print(f"  {symbols[i]} = {p}")
        return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
