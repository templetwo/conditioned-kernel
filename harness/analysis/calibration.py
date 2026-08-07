#!/usr/bin/env python3
"""Calibration gate — PREREG §6 arm 1, D(crc32) <= 1% or nothing proceeds.

Evaluates the frozen gate over the calibration arm's cell receipts: crc32
only, all four generators, accepted artifacts pooled. The threshold is a
frozen row (PREREG §7) and is not a parameter here — a knob would invite the
exact quiet loosening the freeze exists to prevent.

THREE OUTCOMES, never two (SPEC §7a.2b):
  pass             D <= threshold. Recorded as a WEAK CLEARANCE per LN-2 /
                   standing consequence 2: necessary, not sufficient — crc32
                   is the most memorized kernel in the set and a real leak
                   can hide under shared priors. The record says so; the
                   writeup may not omit it.
  fail             D > threshold. A hard halt, and still fully informative:
                   disagreement on a fully closed spec is strong evidence of
                   a harness leak. The arm stops, the leak is found, the run
                   reruns (PREREG §6: "Nothing proceeds past a leaky
                   calibration").
  cannot_evaluate  with cause — no accepted artifacts, missing probe records,
                   mismatched coverage. NOT a pass: a gate that cannot read
                   its own instrument has cleared nothing, and encoding this
                   as pass is precisely the LN-7 defect one layer up.

Consumers (the arm orchestrator) must branch on all three; the third blocks
exactly as fail does but is triaged as instrument, not as leak.
"""
import glob, json, os, sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d_estimator

CALIBRATION_KERNEL = "crc32"
THRESHOLD = 0.01          # PREREG §7 frozen row: calibration leak D <= 1%


def evaluate(cells):
    """The gate, over calibration-arm cell receipt dicts."""
    wrong = [c.get("cell", {}).get("kernel") for c in cells
             if c.get("cell", {}).get("kernel") != CALIBRATION_KERNEL]
    if wrong:
        return {"state": "cannot_evaluate",
                "cause": f"calibration is {CALIBRATION_KERNEL} only; got cell "
                         f"receipts for {sorted(set(wrong))}"}
    d = d_estimator.compute_d_for_cells(cells)
    rec = {"kernel": CALIBRATION_KERNEL, "threshold": THRESHOLD,
           "cells": len(cells)}
    if d["state"] != "ok":
        rec.update(state="cannot_evaluate", cause=d["cause"])
        return rec
    rec.update(D=d["D"], D_exact=d["D_exact"], k=d["k"], quantum=d["quantum"],
               probe_count=d["probe_count"])
    if d.get("degenerate_k"):
        # k = 1 yields D = 0 by arithmetic, not by agreement. One artifact
        # clears nothing; the gate cannot see a leak it has no pair to
        # disagree with. Triage: instrument coverage, not candidate property.
        rec.update(state="cannot_evaluate",
                   cause="only one accepted artifact in the calibration arm; "
                         "D is degenerate at k=1 and clears nothing")
        return rec
    # The comparison is over the EXACT rational D, not its float rendering:
    # counts are integers, the threshold is 1/100, and a float artifact must
    # not decide a frozen gate in either direction.
    if Fraction(*d["D_exact"]) <= Fraction(1, 100):
        rec.update(state="pass",
                   note="WEAK CLEARANCE (LN-2, standing consequence 2): "
                        "necessary, not sufficient; a leak smaller than "
                        "shared priors on the most memorized kernel would "
                        "not be seen here")
    else:
        rec.update(state="fail",
                   note="HARD HALT (PREREG §6): nothing proceeds past a "
                        "leaky calibration; find the leak, rerun the arm")
    return rec


def evaluate_dir(receipt_dir):
    """Convenience: evaluate every cell receipt in a calibration out_dir."""
    paths = sorted(glob.glob(os.path.join(receipt_dir, "*.json")))
    if not paths:
        return {"state": "cannot_evaluate",
                "cause": f"no cell receipts found in {receipt_dir}"}
    return evaluate([json.load(open(p)) for p in paths])


if __name__ == "__main__":
    print(json.dumps(evaluate_dir(sys.argv[1]), indent=1))
