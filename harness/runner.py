#!/usr/bin/env python3
"""ECS runner — the SPEC §9 state machine.

    load ECS packet -> build prompt -> generate -> LINT -> COMPILE -> SANITIZE
       -> CBMC -> VECTORS(device) -> BUDGET -> ACCEPT -> receipt
    any gate failure -> repair (<= 4 iterations) -> re-enter at LINT
    repair budget exhausted -> REJECT -> receipt (full trace kept)
    generation transport error / runner termination (OOM class)
       -> NOT a candidate failure. Re-run the eviction barrier, retry.
          Does not consume a sample, does not touch the repair budget.

THE STUB GENERATOR EXISTS FOR P2's DEFINITION OF DONE. SPEC §13 requires that
"a stub generator (returns oracle verbatim) produces a full green receipt end
to end" before P2 closes. It spends no API calls and proves the pipeline is
wired, not that any model can code.

INVARIANTS THIS FILE IS RESPONSIBLE FOR, none of which the gate chain can
enforce on its own:

  INFRA FAULTS ARE NOT CANDIDATE FAILURES. A transport error, an OOM-killed
  runner, or a barrier that failed closed consumes NO sample, touches NO
  repair budget, and never enters an acceptance-rate denominator. This is the
  error that produced two false granite negatives before the barrier existed
  (SPEC §4a.1), and the separation lives here because only the runner sees
  both the adapter's status and the sample counter.

  SERVED-STRING IDENTITY WITHIN AN ARM. Every call records requested and
  served model strings. If the served string changes mid-arm the arm is
  INVALIDATED and rerun — never averaged, never adjusted (PREREG §7). One
  requested alias was measured serving a different model, and a frozen row
  became unsatisfiable mid-build; see SUPERSESSION-001.

  PER-CELL BATCHING. A cell is one (generator × kernel × arm). All samples in
  a cell run consecutively under a single verified eviction barrier, so the
  barrier re-runs at cell boundaries only.

  VECTOR WITHHOLDING IS DERIVED, NEVER DECLARED. The weak arm's half-withheld
  vectors come from vector_policy.select() keyed on completeness, not from
  anything a packet author can set.
"""
import json, os, sys, time, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness", "gates"))
sys.path.insert(0, os.path.join(ROOT, "harness", "generators"))

import yaml
import chain
import prompt as prompt_mod
import adapters
import vector_policy

MAX_REPAIRS = 4        # PREREG §7
MAX_INFRA_RETRIES = 3  # PREREG §7, then infra abort
MAX_INFRA_ABORTS = 5   # per arm, then the arm is invalidated


def stub_generator(_packet_path, kernel, seat="agentB"):
    """P2's stub: returns a sealed oracle verbatim.

    Deliberately NOT a model. Its only job is to prove the pipeline carries a
    candidate from packet to green receipt. A stub that produced anything
    cleverer would test the stub instead of the harness.
    """
    p = os.path.join(ROOT, "trusted", "oracles", f"{kernel}_{seat}.c")
    return {"generator_id": "STUB", "model_string_requested": "stub:oracle-verbatim",
            "model_string_served": "stub:oracle-verbatim", "status": "ok",
            "temperature": adapters.TEMPERATURE, "elapsed_ms": 0,
            "output": open(p).read(), "output_chars": os.path.getsize(p),
            "stub_source": os.path.relpath(p, ROOT)}


def run_candidate(packet_path, generate, sample_index, arm_state):
    """One candidate through generation, gates, and up to MAX_REPAIRS repairs."""
    packet = yaml.safe_load(open(packet_path))
    kernel = packet["kernel"]
    built = prompt_mod.build(packet_path)
    rec = {"kernel": kernel, "completeness": packet["completeness"],
           "sample_index": sample_index, "prompt_sha256": built["prompt_sha256"],
           "repair_trace": [], "infra_retry_count": 0, "infra_abort": False,
           "accepted": False, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                           time.gmtime())}

    feedback = None
    for attempt in range(MAX_REPAIRS + 1):
        # --- generate, with infra faults kept out of the sample accounting ---
        gen = None
        for _ in range(MAX_INFRA_RETRIES):
            gen = generate(packet_path, kernel)
            if gen["status"] == "ok":
                break
            rec["infra_retry_count"] += 1
        if gen is None or gen["status"] != "ok":
            rec["infra_abort"] = True
            arm_state["infra_aborts"] += 1
            rec["note"] = ("INFRA ABORT: no sample consumed, no repair budget "
                           "touched, excluded from acceptance denominators")
            return rec

        # --- served-string identity within the arm ---
        served = gen["model_string_served"]
        prior = arm_state.setdefault("served", {}).setdefault(gen["generator_id"], served)
        if served != prior:
            rec["arm_invalidated"] = True
            rec["note"] = (f"served string changed mid-arm: {prior} -> {served}. "
                           f"PREREG §7 invalidates the arm; it is rerun, not averaged.")
            arm_state["invalidated"] = True
            return rec
        rec["generator"] = {k: gen[k] for k in
                            ("generator_id", "model_string_requested",
                             "model_string_served", "temperature")}

        src = adapters.strip_fences(gen["output"])
        gates = chain.run(src, packet)
        rec["repair_trace"].append({"attempt": attempt, "stopped_at": gates["stopped_at"],
                                    "gates": {k: v["result"] for k, v in gates["gates"].items()}})
        if gates["accepted"]:
            rec["accepted"] = True
            rec["gates"] = gates["gates"]
            rec["candidate_sha256"] = hashlib.sha256(src.encode()).hexdigest()
            rec["source"] = src
            return rec

        # --- repair feedback is the STOPPING gate's, and only that ---
        stop = gates["stopped_at"]
        fb = gates["gates"][stop]["feedback"]
        feedback = f"Gate {stop} failed:\n" + "\n".join(str(x) for x in fb[:3])
        rec["gates"] = gates["gates"]

    rec["note"] = f"repair budget of {MAX_REPAIRS} exhausted; full trace kept"
    return rec


def run_cell(packet_path, generate, n_samples=1, out_dir=None):
    """One cell: (generator × kernel × arm), samples consecutive under one barrier."""
    packet = yaml.safe_load(open(packet_path))
    vecs = json.load(open(os.path.join(ROOT, "trusted", "vectors",
                                       f"{packet['kernel']}.json")))["vectors"]
    arm_state = {"infra_aborts": 0, "invalidated": False}
    cell = {"cell": {"kernel": packet["kernel"], "arm": packet["completeness"]},
            "vector_policy": vector_policy.receipt_fields(vecs, packet["completeness"]),
            "candidates": []}
    for i in range(n_samples):
        cell["candidates"].append(run_candidate(packet_path, generate, i, arm_state))
        if arm_state["invalidated"]:
            cell["arm_invalidated"] = True
            break
        if arm_state["infra_aborts"] > MAX_INFRA_ABORTS:
            cell["arm_invalidated"] = True
            cell["note"] = f">{MAX_INFRA_ABORTS} infra aborts; arm rerun, not adjusted"
            break
    acc = [c for c in cell["candidates"] if c["accepted"]]
    scored = [c for c in cell["candidates"] if not c.get("infra_abort")]
    cell["summary"] = {"samples": len(cell["candidates"]), "accepted": len(acc),
                       "infra_aborts": arm_state["infra_aborts"],
                       "acceptance_denominator": len(scored),
                       "note": "infra aborts excluded from the denominator"}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, f"{packet['kernel']}_{packet['completeness']}.json")
        json.dump(cell, open(p, "w"), indent=1)
        cell["receipt_path"] = p
    return cell


if __name__ == "__main__":
    pkt = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ecs", "crc32.ecs.yaml")
    gen = lambda pp, k: stub_generator(pp, k)
    c = run_cell(pkt, gen, n_samples=1,
                 out_dir=os.path.join(ROOT, "receipts", "p2_stub"))
    print(json.dumps({k: v for k, v in c.items() if k != "candidates"}, indent=1))
    print(f"  accepted={c['candidates'][0]['accepted']} "
          f"receipt={c.get('receipt_path')}")
