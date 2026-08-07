"""harness/analysis/calibration.py — the PREREG §6 arm-1 gate, offline.

The three-state discipline is the subject: pass, fail, and cannot-evaluate
must be distinct, and cannot-evaluate must never surface as pass.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness", "analysis"))

import calibration as cal


def art(outcomes):
    return [{"probe_id": k, "output_class": v} for k, v in outcomes.items()]


def cell(kernel, accepted_outcomes):
    return {"cell": {"kernel": kernel, "arm": "full"},
            "candidates": [{"accepted": True, "sample_index": i,
                            "probe_output_hashes": art(o)}
                           for i, o in enumerate(accepted_outcomes)]}


def _uniform(n_probes, cls):
    return {f"p{i:03d}": cls for i in range(n_probes)}


def test_clean_calibration_passes_as_weak_clearance():
    c = cell("crc32", [_uniform(256, "sha256:same")] * 4)
    r = cal.evaluate([c])
    assert r["state"] == "pass"
    assert r["D"] == 0.0
    assert "WEAK CLEARANCE" in r["note"]        # LN-2, standing consequence 2


def test_boundary_d_exactly_at_threshold_passes():
    # frozen gate is D <= 1%: with k=4 and 256 probes, per-probe disagreement
    # steps by 1/4, so ~10 disagreeing probes give D just under 0.01 and 11
    # give just over. Build exactly D = 0.01: need mean = 0.01 over 256
    # probes with per-probe values in {0, 0.25, ...} -> impossible exactly;
    # use k=100 artifacts, 1 probe of 100 with largest fraction 0.99... keep
    # it simple: k=100, one probe, 99 agree 1 dissents -> D = 0.01 exactly.
    outcomes = [{"p0": "sha256:same"} for _ in range(99)] + \
               [{"p0": "sha256:other"}]
    r = cal.evaluate([cell("crc32", outcomes)])
    assert abs(r["D"] - 0.01) < 1e-12
    assert r["state"] == "pass"                 # <=, per the frozen row


def test_leaky_calibration_fails_and_halts():
    # one probe of two splits 2/2 -> per-probe 0.5, D = 0.25 >> 1%
    outcomes = [{"p0": "sha256:a", "p1": "sha256:x"},
                {"p0": "sha256:a", "p1": "sha256:x"},
                {"p0": "sha256:b", "p1": "sha256:x"},
                {"p0": "sha256:b", "p1": "sha256:x"}]
    r = cal.evaluate([cell("crc32", outcomes)])
    assert r["state"] == "fail"
    assert "HARD HALT" in r["note"]


def test_wrong_kernel_is_cannot_evaluate():
    r = cal.evaluate([cell("fir_q15", [_uniform(4, "sha256:same")] * 2)])
    assert r["state"] == "cannot_evaluate"
    assert "crc32 only" in r["cause"]


def test_no_accepted_artifacts_is_cannot_evaluate_not_pass():
    empty = {"cell": {"kernel": "crc32", "arm": "full"}, "candidates": []}
    r = cal.evaluate([empty])
    assert r["state"] == "cannot_evaluate"
    assert "D" not in r


def test_single_artifact_is_cannot_evaluate():
    # k=1 yields D=0 by arithmetic; the gate must not read that as clearance
    r = cal.evaluate([cell("crc32", [_uniform(8, "sha256:same")])])
    assert r["state"] == "cannot_evaluate"
    assert "k=1" in r["cause"]


def test_missing_probe_records_are_cannot_evaluate():
    c = {"cell": {"kernel": "crc32", "arm": "full"},
         "candidates": [{"accepted": True, "sample_index": 0},
                        {"accepted": True, "sample_index": 1}]}
    r = cal.evaluate([c])
    assert r["state"] == "cannot_evaluate"


def test_evaluate_dir_empty_is_cannot_evaluate(tmp_path):
    r = cal.evaluate_dir(str(tmp_path))
    assert r["state"] == "cannot_evaluate"
    assert "no cell receipts" in r["cause"]
