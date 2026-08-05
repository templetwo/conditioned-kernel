#!/usr/bin/env python3
"""ECS standing pre-arm check.

Runs before a kernel's first generation arm. Verifies that the kernel's
interface agrees across every place it is written down, and that its
choice-point row still exists.

  1. SPEC §5 prototype
  2. harness/gates/kernel_signatures.json
  3. both sealed oracle prototypes in trusted/oracles/
  4. presence of a row in evidence/choice_point_map.md

Origin: Agent B's standing signature rule (board #13996), extended to the
choice-point map (#14047). A bit that silently changes channel between P1 and
P3 would change what D measures without changing D's definition.

NORMALISATION MATTERS, AND A FIRST VERSION OF THIS CHECK GOT IT WRONG.
Comparing prototype strings verbatim flags three of five kernels, all of them
false alarms: SPEC writes `const uint8_t*` where the oracles write
`const uint8_t *data`, and one oracle writes `[256]` where SPEC writes
`[16*16]`. Parameter names are not part of a C prototype's type, and 16*16
is 256. A check that cries wolf gets ignored, which defeats the purpose of
having it. So this compares the TYPE SEQUENCE: qualifiers, base type,
pointer/array-ness, and evaluated array extents, with names discarded.

Usage:
  prearm_check.py [kernel ...]      # default: all kernels in the signature file
Exit 0 iff every checked kernel agrees everywhere.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIGS = os.path.join(ROOT, "harness", "gates", "kernel_signatures.json")
SPEC = os.path.join(ROOT, "SPEC.md")
ORACLES = os.path.join(ROOT, "trusted", "oracles")
CPMAP = os.path.join(ROOT, "evidence", "choice_point_map.md")


def norm_params(proto):
    """Return a normalised type tuple for a C prototype's parameter list.

    Names dropped; array extents evaluated; `T x[N]` and `T *x` both become
    ('T', 'ptr') since an array parameter decays to a pointer. Extents are
    kept separately so a genuine size change is still visible.
    """
    inner = proto[proto.index("(") + 1: proto.rindex(")")]
    out = []
    for raw in [p.strip() for p in inner.split(",") if p.strip()]:
        if raw == "void":
            continue
        extent = None
        m = re.search(r"\[([^\]]*)\]", raw)
        if m:
            e = m.group(1).strip()
            if e:
                try:
                    extent = eval(e, {"__builtins__": {}}, {})   # e.g. "16*16" -> 256
                except Exception:
                    extent = e
            raw = raw[: m.start()]
        raw = re.sub(r"\[[^\]]*\]", "", raw)
        is_ptr = "*" in raw or m is not None
        raw = raw.replace("*", " ")
        toks = raw.split()
        # drop a trailing identifier that is not a type keyword
        TYPES = {"const", "unsigned", "signed", "void", "size_t", "char", "int",
                 "short", "long", "uint8_t", "int8_t", "uint16_t", "int16_t",
                 "uint32_t", "int32_t", "uint64_t", "int64_t"}
        while toks and toks[-1] not in TYPES:
            toks.pop()
        out.append((" ".join(toks), "ptr" if is_ptr else "val", extent))
    return tuple(out)


def norm_ret(proto):
    return proto.split("(")[0].strip().split()[0]


def check(kernel, sigs):
    problems = []
    sig = sigs[kernel]

    spec_txt = open(SPEC).read()
    m = re.search(r"^\| " + re.escape(kernel) + r" \| `([^`]+)`", spec_txt, re.M)
    if not m:
        return [f"no SPEC §5 row for {kernel}"]
    spec_proto = m.group(1)

    refs = {"SPEC": spec_proto, "signatures.json": sig["signature"]}
    for seat in ("agentA", "agentB"):
        p = os.path.join(ORACLES, f"{kernel}_{seat}.c")
        if not os.path.exists(p):
            problems.append(f"{seat} oracle not revealed")
            continue
        mm = re.search(r"^\s*(?:void|uint\d+_t|int\d+_t)\s+" + re.escape(kernel) +
                       r"\s*\([^)]*\)", open(p).read(), re.M)
        if not mm:
            problems.append(f"{seat} oracle prototype not found")
            continue
        refs[seat] = " ".join(mm.group(0).split())

    base_name, base = next(iter(refs.items()))
    base_t, base_r = norm_params(base), norm_ret(base)
    for name, proto in refs.items():
        if norm_params(proto) != base_t:
            problems.append(f"{name} parameter types differ from {base_name}\n"
                            f"      {name}: {norm_params(proto)}\n"
                            f"      {base_name}: {base_t}")
        if norm_ret(proto) != base_r:
            problems.append(f"{name} return type {norm_ret(proto)} != {base_r}")

    if os.path.exists(CPMAP):
        if kernel not in open(CPMAP).read():
            problems.append("no row in evidence/choice_point_map.md")
    else:
        problems.append("choice_point_map.md missing")

    return problems


def main(argv):
    sigs = {k: v for k, v in json.load(open(SIGS)).items() if not k.startswith("_")}
    kernels = argv or sorted(sigs)
    bad = 0
    for k in kernels:
        if k not in sigs:
            print(f"  {k:14s} UNKNOWN — not in kernel_signatures.json")
            bad += 1
            continue
        probs = check(k, sigs)
        if probs:
            bad += 1
            print(f"  {k:14s} PROBLEM")
            for p in probs:
                print(f"      {p}")
        else:
            print(f"  {k:14s} OK   SPEC ≡ signatures.json ≡ both sealed oracles; "
                  f"choice-point row present")
    print(f"\n{len(kernels) - bad}/{len(kernels)} kernels clean")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
