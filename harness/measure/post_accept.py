#!/usr/bin/env python3
"""Post-accept stages — SPEC §9: ACCEPT -> measure -> probe -> receipt.

The gate chain ends at ACCEPT; these two stages complete the state machine
for an accepted candidate and produce the receipt fields SPEC §10 requires
(`measurement`, `probe_output_hashes`).

MEASURE. The SPEC §8 protocol measurement, as a receipt record. When the arm
declared a cycles cap, gate 6 already produced exactly this measurement
same-batch — it is REUSED, not repeated, because a second pin-and-bench would
cost device time to produce a number the receipt already holds. The weak arm
declares no budgets, so its accepted artifacts are measured here, fresh,
against the faster oracle — the dose-response arm drops the CAP, not the
measurement (SPEC §7 gate 6: actuals are recorded either way).

PROBE. The on-device probe battery (harness/measure/probes.py), hash-checked
against the committed manifest at every run.

FAIL CLOSED. Every unusable outcome raises chain.Infra: the candidate is
already accepted, so nothing that happens here is a verdict on it, and a
stage that cannot run must abort the slot (no sample consumed, slot refilled
by the runner) rather than emit a receipt whose measurement or probe block is
quietly absent. A receipt missing `probe_output_hashes` would make its cell's
D silently uncomputable — the exact shape of defect §7a.2b exists to forbid.
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "harness", "gates"))
sys.path.insert(0, os.path.join(ROOT, "harness", "measure"))
from chain import Infra
import cycles as cyc
import probes as probe_mod


def measure_stage(src, kernel, gates, device=probe_mod.DEVICE):
    """The §10 `measurement` block: gate-6 reuse when present, else fresh."""
    g6 = ((gates or {}).get("gates") or {}).get("6_budget") or {}
    reuse = (g6.get("actual") or {}).get("cycles_measure")
    if reuse and reuse.get("status") == "ok":
        return {**reuse, "baseline_oracle": g6["actual"].get("baseline_oracle"),
                "source": "gate6_same_batch"}

    oracles = sorted(glob.glob(os.path.join(ROOT, "trusted", "oracles",
                                            f"{kernel}_agent*.c")))
    if len(oracles) < 2:
        raise Infra(f"measure stage: no oracle pair for {kernel} to form a "
                    f"baseline")
    fastest = None
    for o in oracles:
        m = cyc.measure(open(o).read(), open(oracles[0]).read(), kernel,
                        device=device)
        if m.get("status") == "ok":
            if fastest is None or m["candidate_ns"] < fastest[1]:
                fastest = (o, m["candidate_ns"])
    if fastest is None:
        raise Infra("measure stage: no oracle produced a clean same-batch "
                    "baseline timing")
    m = cyc.measure(src, open(fastest[0]).read(), kernel, device=device)
    if m.get("status") == "discard_refreq":
        raise Infra(f"measure stage: core frequency moved "
                    f"({m.get('freq_pre')} -> {m.get('freq_post')}); SPEC §8 "
                    f"discards and remeasures, never averages")
    if m.get("status") != "ok":
        raise Infra(f"measure stage failed: {str(m.get('error'))[:200]}")
    return {**m, "baseline_oracle": os.path.basename(fastest[0]),
            "source": "post_accept_fresh"}


def run(src, packet, gates, device=probe_mod.DEVICE):
    """Both stages, in SPEC §9 order. Returns the receipt fragment or raises
    Infra — there is no partial-success return shape, deliberately."""
    kernel = packet["kernel"]
    measurement = measure_stage(src, kernel, gates, device=device)
    probe = probe_mod.battery(src, kernel, device=device)
    return {"measurement": measurement,
            "probe_output_hashes": probe["results"],
            "probe_count": probe["probe_count"],
            "probe_set": probe["probe_set"]}
