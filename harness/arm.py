#!/usr/bin/env python3
"""Arm orchestration — PREREG §6's three arms over runner.run_cell.

This module OWNS the arm-scoped invariants and delegates everything cell-
scoped to the runner, which it reuses rather than rewrites:

  ARM STATE IS CREATED ONCE PER ARM and threaded into every cell, so the
  served-string identity assertion is arm-wide (PREREG §7): a provider
  re-pointing an alias between two cells hours apart invalidates the arm
  exactly as one re-pointing between two samples does.

  CELLS RUN GENERATOR-MAJOR. All of one generator's cells run consecutively,
  so local-model transitions are bounded by the number of generators, not the
  number of cells — §4a's batching default, one level up from the per-cell
  barrier run_cell already invokes.

  INFRA-ABORTED SLOTS ARE REFILLED by run_cell (SPEC §13a item 3); this
  module's job is only to stop the arm when run_cell reports the abort or
  refill cap tripped, never to adjust around it.

  THE LN-6 CONTRACT PROBE runs at arm open and arm close (standing
  consequence 11). A changed contract invalidates the arm on the same rule
  as a served-string change; an UNVERIFIABLE contract blocks the arm from
  closing as valid, with instrument triage rather than provider blame.

  CALIBRATION GATES EVERYTHING (PREREG §6 arm 1). run_pilot will not open
  the main or dose-response arm unless the calibration gate returns `pass` —
  and `cannot_evaluate` halts exactly as `fail` does, because a gate that
  could not read its instrument has cleared nothing (SPEC §7a.2b).

ARM OUTCOME SET — three classes, every consumer branches on all of them:
  complete         every cell ran, contract unchanged
  invalidated      served-string change, contract change, or abort caps —
                   the arm is RERUN, never averaged or adjusted
  cannot_evaluate  the arm's validity is unknowable from its own record
                   (contract unverifiable, orchestration fault); with cause

The device and generator boundaries are injectable (`run_cell_fn`,
`generators`, `contract_calls`, `post_accept`) so every transition above is
testable offline; production defaults reach the real adapters and device.
"""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, os.path.join(ROOT, "harness", "generators"))
sys.path.insert(0, os.path.join(ROOT, "harness", "analysis"))

import runner
import contract_probe
import calibration

N_SAMPLES = 10                      # PREREG §7 frozen row

# Generator roster — call shapes match run_candidate's generate(prompt, kernel).
# local_model feeds the §4a.1 barrier at cell boundaries; frontier generators
# have no device residency and are the LN-6 probe's subjects.
def _generators():
    import adapters
    return {
        "G1": {"call": lambda p, k: adapters.anthropic(p),
               "local_model": None, "frontier": True},
        "G2": {"call": lambda p, k: adapters.xai(p),
               "local_model": None, "frontier": True},
        "G3": {"call": lambda p, k: adapters.ollama(p, "qwen2.5-coder:3b", "G3"),
               "local_model": "qwen2.5-coder:3b", "frontier": False},
        "G4": {"call": lambda p, k: adapters.ollama(p, "granite4:micro", "G4"),
               "local_model": "granite4:micro", "frontier": False},
    }


def _pkt(name):
    return os.path.join(ROOT, "ecs", name)


# PREREG §6, the three arms as frozen. The canary (SPEC §5a) is NOT listed:
# its packet does not exist until the sealed draw's pinning channel lands,
# and adding it here before then would let an orchestrator invent a kernel
# the trusted tier has not sealed. When ecs/fir_q15_canary.ecs.yaml exists
# it joins `main` by a dated edit here, and its cells are reported
# separately, never pooled into the frozen five (SUPERSESSION-002).
ARMS = {
    "calibration": {"packets": ["crc32.ecs.yaml"],
                    "generators": ["G1", "G2", "G3", "G4"]},
    "main": {"packets": ["crc32.ecs.yaml", "sat_add_u8.ecs.yaml",
                         "fir_q15.ecs.yaml", "matmul8_i32.ecs.yaml",
                         "median3x3_u8.ecs.yaml"],
             "generators": ["G1", "G2", "G3", "G4"]},
    "dose_response": {"packets": ["fir_q15.weak.ecs.yaml"],
                      "generators": ["G1", "G2", "G3", "G4"]},
}


def run_arm(arm_name, out_dir, n_samples=N_SAMPLES, run_cell_fn=None,
            generators=None, contract_calls=None, post_accept=None):
    """One arm: contract probe, generator-major cells under one arm_state,
    contract probe again, verdict."""
    spec = ARMS[arm_name]
    generators = generators if generators is not None else _generators()
    run_cell_fn = run_cell_fn or runner.run_cell
    gen_ids = spec["generators"]

    rec = {"arm": arm_name, "opened_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                        time.gmtime()),
           "n_samples": n_samples, "cells": [], "state": None}

    # --- LN-6 contract probe, arm open -------------------------------------
    frontier = {g for g in gen_ids if generators[g].get("frontier")}
    if contract_calls is None:
        contract_calls = {g: c for g, c in
                          contract_probe.default_frontier_calls().items()
                          if g in frontier}
    rec["contract_open"] = contract_probe.probe(contract_calls)

    arm_state = runner.new_arm_state()      # ONCE per arm — PREREG §7 scope
    halted = None
    for gen_id in gen_ids:                  # generator-major: §4a batching
        gen = generators[gen_id]
        for packet in spec["packets"]:
            cell = run_cell_fn(_pkt(packet), gen["call"], n_samples,
                               out_dir=os.path.join(out_dir, gen_id),
                               arm_state=arm_state,
                               local_model=gen.get("local_model"),
                               post_accept=post_accept)
            rec["cells"].append({"generator": gen_id, "packet": packet,
                                 "summary": cell.get("summary"),
                                 "receipt_path": cell.get("receipt_path"),
                                 "arm_invalidated": cell.get("arm_invalidated",
                                                             False),
                                 "cell_aborted": cell.get("cell_aborted",
                                                          False)})
            if cell.get("arm_invalidated") or arm_state.get("invalidated"):
                halted = (f"arm invalidated at ({gen_id}, {packet}): "
                          f"{cell.get('note', 'served-string or abort cap')}")
                break
            if cell.get("cell_aborted"):
                halted = (f"cell aborted at ({gen_id}, {packet}): barrier "
                          f"failed closed; the device is not fit to run this "
                          f"arm")
                break
        if halted:
            break

    # --- LN-6 contract probe, arm close -------------------------------------
    rec["contract_close"] = contract_probe.probe(contract_calls)
    rec["contract_comparison"] = cmp = contract_probe.compare(
        rec["contract_open"], rec["contract_close"])

    if halted:
        rec.update(state="invalidated", cause=halted)
    elif cmp["state"] == "changed":
        rec.update(state="invalidated",
                   cause=f"contract changed mid-arm: {cmp['diffs']} — same "
                         f"rule as a served-string change (LN-6)")
    elif cmp["state"] == "cannot_evaluate":
        rec.update(state="cannot_evaluate", cause=cmp["cause"])
    else:
        rec["state"] = "complete"
    rec["infra_aborts"] = arm_state["infra_aborts"]
    rec["closed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"arm_{arm_name}.json")
    json.dump(rec, open(p, "w"), indent=1)
    rec["arm_receipt_path"] = p
    return rec


def _cell_receipts(arm_rec):
    out = []
    for c in arm_rec["cells"]:
        if c.get("receipt_path") and os.path.exists(c["receipt_path"]):
            out.append(json.load(open(c["receipt_path"])))
    return out


def run_pilot(out_root, n_samples=N_SAMPLES, run_cell_fn=None, generators=None,
              contract_calls=None, post_accept=None):
    """The full PREREG §6 run plan, with the calibration gate between arm 1
    and everything else. Halts are RECORDED, not just raised: a pilot receipt
    that stops after calibration must show why."""
    kw = dict(n_samples=n_samples, run_cell_fn=run_cell_fn,
              generators=generators, contract_calls=contract_calls,
              post_accept=post_accept)
    pilot = {"opened_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "arms": {}}

    cal_arm = run_arm("calibration", os.path.join(out_root, "calibration"), **kw)
    pilot["arms"]["calibration"] = cal_arm
    if cal_arm["state"] != "complete":
        pilot.update(state="halted",
                     cause=f"calibration arm did not complete: "
                           f"{cal_arm.get('cause')}")
        return _close_pilot(pilot, out_root)

    gate = calibration.evaluate(_cell_receipts(cal_arm))
    pilot["calibration_gate"] = gate
    if gate["state"] == "fail":
        pilot.update(state="halted",
                     cause="calibration gate FAILED: nothing proceeds past a "
                           "leaky calibration (PREREG §6); find the leak, "
                           "rerun")
        return _close_pilot(pilot, out_root)
    if gate["state"] != "pass":
        # cannot_evaluate halts exactly as fail does, with instrument triage:
        # a gate that could not read its instrument has cleared nothing.
        pilot.update(state="halted",
                     cause=f"calibration gate could not evaluate: "
                           f"{gate.get('cause')} — not a pass (SPEC §7a.2b)")
        return _close_pilot(pilot, out_root)

    for arm_name in ("main", "dose_response"):
        arm_rec = run_arm(arm_name, os.path.join(out_root, arm_name), **kw)
        pilot["arms"][arm_name] = arm_rec
        if arm_rec["state"] != "complete":
            pilot.update(state="halted",
                         cause=f"{arm_name} arm did not complete: "
                               f"{arm_rec.get('cause')}")
            return _close_pilot(pilot, out_root)

    pilot["state"] = "complete"
    return _close_pilot(pilot, out_root)


def _close_pilot(pilot, out_root):
    pilot["closed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(out_root, exist_ok=True)
    p = os.path.join(out_root, "pilot.json")
    json.dump(pilot, open(p, "w"), indent=1)
    pilot["pilot_receipt_path"] = p
    return pilot


if __name__ == "__main__":
    out = run_pilot(os.path.join(ROOT, "receipts",
                                 time.strftime("p3_%Y%m%dT%H%M%SZ",
                                               time.gmtime())))
    print(json.dumps({k: v for k, v in out.items() if k != "arms"}, indent=1))
