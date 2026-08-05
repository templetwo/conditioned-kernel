#!/usr/bin/env python3
"""Regenerate every P2 receipt against a COMMITTED harness revision.

SPEC §13a item 5. Anthony held P2 open for this: the earlier receipts were
produced by an instrument that accepted candidates when it failed to measure
them, applied no weak-arm withholding, sent a prompt no generator saw, and
staged untrusted source on the device inside a breakable heredoc. Those
receipts describe a different instrument. They are superseded, not amended.

REFUSES TO RUN ON A DIRTY TREE. A receipt whose harness_git_sha does not
reproduce the harness that made it is worth less than no receipt, because it
looks like evidence.

Two outputs, both regenerated in one pass so they share a revision:
  receipts/p2_stub/<kernel>_<arm>.json   stub cell per ECS packet
  receipts/redteam/p2_fixture_rejection.json   every fixture at its gate
"""
import glob, hashlib, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, os.path.join(ROOT, "harness", "gates"))
sys.path.insert(0, os.path.join(ROOT, "harness", "generators"))

import yaml
import chain
import runner

# Intended gate per fixture, from the filename. The redteam lane names the gate
# it is attacking; a fixture stopping anywhere else is a finding, not a pass.
def intended_gate(fname):
    for tok in os.path.basename(fname).replace(".c", "").split("_"):
        if tok.startswith("gate") and tok[4:].isdigit():
            return tok[4:]
    return None


def main():
    h = runner.harness_git_sha()
    if h["harness_tree_dirty"]:
        print("REFUSING: tree is dirty. SPEC §13a item 5 requires receipts bound "
              "to a committed harness revision.\n"
              "Commit the harness first, then regenerate.")
        return 2
    print(f"harness_git_sha = {h['harness_git_sha']}  (clean)\n")

    # ---- stub cells, one per ECS packet -------------------------------------
    stub_dir = os.path.join(ROOT, "receipts", "p2_stub")
    cells = []
    for pkt in sorted(glob.glob(os.path.join(ROOT, "ecs", "*.ecs.yaml"))):
        name = os.path.basename(pkt)
        t0 = time.time()
        c = runner.run_cell(pkt, lambda prompt, k: runner.stub_generator(prompt, k),
                            n_samples=1, out_dir=stub_dir)
        cand = c["candidates"][0] if c["candidates"] else {}
        vp = c.get("vector_policy", {})
        print(f"  {name:26s} accepted={cand.get('accepted')} "
              f"vectors {vp.get('vectors_used')}/{vp.get('vectors_total')} "
              f"({vp.get('vector_policy')})  {round(time.time()-t0)}s")
        cells.append({"packet": name, "accepted": bool(cand.get("accepted")),
                      "infra_abort": bool(cand.get("infra_abort")),
                      "vectors_used": vp.get("vectors_used"),
                      "vectors_total": vp.get("vectors_total")})

    # ---- redteam fixtures ---------------------------------------------------
    print()
    fixtures = []
    for f in sorted(glob.glob(os.path.join(ROOT, "redteam", "*.c"))):
        g = intended_gate(f)
        if g is None:
            print(f"  {os.path.basename(f):34s} SKIP (no gate in filename)")
            continue
        src = open(f).read()
        kernel = os.path.basename(f).split("_")[0]
        pkt = yaml.safe_load(open(os.path.join(ROOT, "ecs", f"{kernel}.ecs.yaml")))
        r = chain.run(src, pkt)
        stopped = r.get("stopped_at")
        ok = stopped == f"{g}_" + {"1": "lint", "2": "compile", "3": "sanitize",
                                   "4": "cbmc", "5": "vectors", "6": "budget"}[g]
        if r.get("infra_fault"):
            ok, stopped = False, f"INFRA: {r.get('infra_reason','')[:80]}"
        print(f"  {os.path.basename(f):34s} intended {g} -> {stopped}  "
              f"{'OK' if ok else 'MISMATCH'}")
        fixtures.append({
            "file": os.path.basename(f), "intended_gate": g,
            "stopped_at": stopped, "rejected_at_intended_gate": ok,
            "sha256": hashlib.sha256(src.encode()).hexdigest(),
            "gate_results": {k: v["result"] for k, v in r.get("gates", {}).items()}})

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "P2 DoD: every redteam fixture rejected at its INTENDED gate.",
        "harness": h,
        "supersedes": ("receipts produced before the §7a fail-closed corrections; "
                       "those describe an instrument that could accept a candidate "
                       "because it failed to measure it"),
        "fixtures": fixtures,
        "summary": {"fixtures": len(fixtures),
                    "rejected_at_intended_gate": sum(
                        1 for x in fixtures if x["rejected_at_intended_gate"])}}
    p = os.path.join(ROOT, "receipts", "redteam", "p2_fixture_rejection.json")
    json.dump(out, open(p, "w"), indent=1)

    green = {"generated_utc": out["generated_utc"], "harness": h,
             "purpose": "P2 DoD: stub generator produces a full green receipt end to end.",
             "cells": cells,
             "summary": {"packets": len(cells),
                         "green": sum(1 for c in cells if c["accepted"])}}
    json.dump(green, open(os.path.join(ROOT, "receipts", "redteam",
                                       "p2_green_receipt.json"), "w"), indent=1)

    print(f"\n  stub cells green : {green['summary']['green']}/{green['summary']['packets']}")
    print(f"  fixtures at gate : {out['summary']['rejected_at_intended_gate']}"
          f"/{out['summary']['fixtures']}")
    return 0 if (green["summary"]["green"] == len(cells)
                 and out["summary"]["rejected_at_intended_gate"] == len(fixtures)) else 1


if __name__ == "__main__":
    sys.exit(main())
