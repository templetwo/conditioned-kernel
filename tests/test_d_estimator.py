"""harness/analysis/d_estimator.py — PREREG §3 D, pure, offline.

Hand-computed expectations throughout: a D test that recomputes D with the
same code proves serialization, not arithmetic.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness", "analysis"))

import d_estimator as de


def art(**outcomes):
    """Artifact in receipt shape: list of {probe_id, output_class}."""
    return [{"probe_id": k, "output_class": v} for k, v in outcomes.items()]


def test_unanimous_is_zero():
    r = de.compute_d([art(p0="sha256:aa", p1="sha256:bb"),
                      art(p0="sha256:aa", p1="sha256:bb"),
                      art(p0="sha256:aa", p1="sha256:bb")])
    assert r["state"] == "ok"
    assert r["D"] == 0.0
    assert r["k"] == 3 and r["probe_count"] == 2


def test_hand_computed_mixed_case():
    # probe p0: clusters {aa: 2, bb: 1} -> largest 2/3 -> disagreement 1/3
    # probe p1: unanimous               -> disagreement 0
    # D = (1/3 + 0) / 2 = 1/6
    r = de.compute_d([art(p0="sha256:aa", p1="sha256:cc"),
                      art(p0="sha256:aa", p1="sha256:cc"),
                      art(p0="sha256:bb", p1="sha256:cc")])
    assert r["state"] == "ok"
    assert abs(r["D"] - 1.0 / 6.0) < 1e-12
    assert r["per_probe_largest_fraction"]["p0"] == 2.0 / 3.0
    assert r["per_probe_largest_fraction"]["p1"] == 1.0


def test_total_disagreement():
    # every artifact its own cluster on the single probe: largest 1/4, D = 3/4
    r = de.compute_d([art(p0=f"sha256:{i}") for i in range(4)])
    assert r["D"] == 0.75


def test_crash_is_a_labeled_class_not_a_discard():
    # two trapping artifacts AGREE (same class); one value artifact disagrees
    # p0 clusters: {CRASH:sig11: 2, sha256:aa: 1} -> largest 2/3
    r = de.compute_d([art(p0="CRASH:sig11"),
                      art(p0="CRASH:sig11"),
                      art(p0="sha256:aa")])
    assert r["state"] == "ok"
    assert abs(r["D"] - 1.0 / 3.0) < 1e-12
    # different signals are different classes — a SIGSEGV and a SIGFPE do not
    # agree about anything
    r2 = de.compute_d([art(p0="CRASH:sig11"), art(p0="CRASH:sig8")])
    assert r2["D"] == 0.5


def test_quantum_reflects_k_not_probe_count():
    r = de.compute_d([art(**{f"p{i}": "sha256:x" for i in range(256)})] * 5)
    assert r["quantum"] == 1.0 / 5.0
    assert r["probe_count"] == 256


def test_no_artifacts_is_cannot_evaluate_not_zero():
    r = de.compute_d([])
    assert r["state"] == "cannot_evaluate"
    assert "D" not in r
    assert "no accepted artifacts" in r["cause"]


def test_coverage_mismatch_is_cannot_evaluate():
    r = de.compute_d([art(p0="sha256:a", p1="sha256:b"),
                      art(p0="sha256:a")])
    assert r["state"] == "cannot_evaluate"
    assert "coverage mismatch" in r["cause"]


def test_malformed_outcome_is_cannot_evaluate():
    r = de.compute_d([[{"probe_id": "p0"}]])
    assert r["state"] == "cannot_evaluate"
    r2 = de.compute_d([[{"probe_id": "p0", "output_class": ""}]])
    assert r2["state"] == "cannot_evaluate"


def test_duplicate_probe_id_is_cannot_evaluate():
    r = de.compute_d([[{"probe_id": "p0", "output_class": "sha256:a"},
                       {"probe_id": "p0", "output_class": "sha256:b"}]])
    assert r["state"] == "cannot_evaluate"


def test_k1_is_degenerate_and_flagged():
    r = de.compute_d([art(p0="sha256:a")])
    assert r["state"] == "ok" and r["D"] == 0.0
    assert r["degenerate_k"] is True


def _cell(cands):
    return {"cell": {"kernel": "crc32", "arm": "full"}, "candidates": cands}


def test_cell_extraction_pools_accepted_only():
    cell = _cell([
        {"accepted": True, "sample_index": 0,
         "probe_output_hashes": art(p0="sha256:a")},
        {"accepted": False, "sample_index": 1},
        {"accepted": True, "sample_index": 2,
         "probe_output_hashes": art(p0="sha256:b")},
    ])
    arts, problems = de.outcomes_from_cell_receipt(cell)
    assert len(arts) == 2 and not problems


def test_accepted_without_probe_record_poisons_the_cell():
    # a receipt from a pre-probe instrument must not silently shrink the pool
    cell = _cell([
        {"accepted": True, "sample_index": 0,
         "probe_output_hashes": art(p0="sha256:a")},
        {"accepted": True, "sample_index": 1},   # no probe record
    ])
    r = de.compute_d_for_cells([cell])
    assert r["state"] == "cannot_evaluate"
    assert "no probe_output_hashes" in r["cause"]


def test_pooling_across_cells():
    c1 = _cell([{"accepted": True, "sample_index": 0,
                 "probe_output_hashes": art(p0="sha256:a")}])
    c2 = _cell([{"accepted": True, "sample_index": 0,
                 "probe_output_hashes": art(p0="sha256:b")}])
    r = de.compute_d_for_cells([c1, c2])
    assert r["state"] == "ok" and r["k"] == 2 and r["D"] == 0.5
