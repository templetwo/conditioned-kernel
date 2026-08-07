"""harness/arm.py + contract_probe — orchestrator state transitions, offline.

The device and generator boundaries are mocked at the seams the orchestrator
exposes for exactly this purpose (`run_cell_fn`, `contract_calls`). What is
under test is the arm-scoped law: arm-wide arm_state threading, generator-
major ordering, halt-on-invalidation, the LN-6 contract rule, and the
calibration gate blocking everything downstream — including via
cannot-evaluate, which must halt exactly as fail does.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, os.path.join(ROOT, "harness", "generators"))
sys.path.insert(0, os.path.join(ROOT, "harness", "analysis"))

import arm as arm_mod
import contract_probe as cp


# --- helpers ----------------------------------------------------------------

def uniform_outcomes(n=4, cls="sha256:same"):
    return [{"probe_id": f"p{i:03d}", "output_class": cls} for i in range(n)]


def ok_contract_calls():
    return {"G1": lambda: {"status": "ok", "model_string_requested": "m",
                           "model_string_served": "m"},
            "G2": lambda: {"status": "ok", "model_string_requested": "m2",
                           "model_string_served": "m2"}}


class FakeRunCell:
    """Stands in for runner.run_cell at the orchestrator's injection seam.
    Records every call; writes a real receipt file so the calibration gate
    can read it back the way production does."""

    def __init__(self, script=None):
        self.calls = []
        self.script = script or {}

    def __call__(self, packet_path, generate, n_samples, out_dir=None,
                 arm_state=None, local_model=None, post_accept=None):
        kernel = os.path.basename(packet_path).split(".")[0]
        key = len(self.calls)
        self.calls.append({"packet": packet_path, "kernel": kernel,
                           "arm_state": arm_state, "out_dir": out_dir,
                           "local_model": local_model})
        cell = self.script.get(key) or {
            "cell": {"kernel": kernel, "arm": "full"},
            "candidates": [{"accepted": True, "sample_index": 0,
                            "probe_output_hashes": uniform_outcomes()}],
            "summary": {"accepted": 1, "acceptance_denominator": 1}}
        if out_dir and not cell.get("skip_receipt"):
            os.makedirs(out_dir, exist_ok=True)
            p = os.path.join(out_dir, f"{kernel}_full_{key}.json")
            json.dump(cell, open(p, "w"), indent=1)
            cell = {**cell, "receipt_path": p}
        return cell


# --- contract probe unit behaviour ------------------------------------------

def test_classify_three_states():
    assert cp.classify({"status": "ok"})["outcome"] == "accepted"
    rej = cp.classify({"status": "infra_fault",
                       "error": "HTTP Error 400: temperature is deprecated"})
    assert rej["outcome"] == "rejected"
    assert "400" in rej["cause"]
    unk = cp.classify({"status": "infra_fault", "error": "timed out"})
    assert unk["outcome"] == "cannot_evaluate"
    assert "unknown" in unk["cause"]


def test_compare_unchanged_changed_and_unknown():
    a = {"generators": {"G1": {"outcome": "accepted"}}}
    b = {"generators": {"G1": {"outcome": "accepted"}}}
    assert cp.compare(a, b)["state"] == "unchanged"

    c = {"generators": {"G1": {"outcome": "rejected"}}}
    changed = cp.compare(a, c)
    assert changed["state"] == "changed"
    assert "G1" in changed["diffs"][0]

    d = {"generators": {"G1": {"outcome": "cannot_evaluate"}}}
    unk = cp.compare(a, d)
    assert unk["state"] == "cannot_evaluate"       # unverifiable != unchanged


def test_probe_survives_raising_call():
    out = cp.probe({"G1": lambda: (_ for _ in ()).throw(RuntimeError("boom"))})
    assert out["generators"]["G1"]["outcome"] == "cannot_evaluate"


# --- run_arm ----------------------------------------------------------------

def test_complete_arm_generator_major_order_and_shared_arm_state(tmp_path):
    rc = FakeRunCell()
    rec = arm_mod.run_arm("main", str(tmp_path), n_samples=2, run_cell_fn=rc,
                          contract_calls=ok_contract_calls())
    assert rec["state"] == "complete"
    assert len(rc.calls) == 4 * 5          # four generators x five kernels
    # generator-major: the first five calls share one generator's out_dir
    first_dirs = {c["out_dir"] for c in rc.calls[:5]}
    assert len(first_dirs) == 1
    # ONE arm_state threaded through every cell — the PREREG §7 arm scope
    states = {id(c["arm_state"]) for c in rc.calls}
    assert len(states) == 1
    # local models reach the barrier seam for G3/G4 cells only
    locals_seen = {c["local_model"] for c in rc.calls}
    assert locals_seen == {None, "qwen2.5-coder:3b", "granite4:micro"}
    assert os.path.exists(rec["arm_receipt_path"])


def test_arm_halts_on_cell_invalidation_and_stops_iterating(tmp_path):
    bad = {"cell": {"kernel": "sat_add_u8", "arm": "full"},
           "candidates": [], "arm_invalidated": True,
           "note": "served string changed mid-arm: a -> b",
           "summary": {}}
    rc = FakeRunCell(script={1: bad})
    rec = arm_mod.run_arm("main", str(tmp_path), run_cell_fn=rc,
                          contract_calls=ok_contract_calls())
    assert rec["state"] == "invalidated"
    assert "served string" in rec["cause"]
    assert len(rc.calls) == 2              # nothing ran after the invalidation


def test_arm_halts_on_barrier_abort(tmp_path):
    aborted = {"cell": {"kernel": "crc32", "arm": "full"}, "candidates": [],
               "cell_aborted": True, "summary": {}}
    rc = FakeRunCell(script={0: aborted})
    rec = arm_mod.run_arm("calibration", str(tmp_path), run_cell_fn=rc,
                          contract_calls=ok_contract_calls())
    assert rec["state"] == "invalidated"
    assert "barrier" in rec["cause"]


def test_contract_change_invalidates_completed_arm(tmp_path):
    flip = {"n": 0}

    def g1():
        flip["n"] += 1
        if flip["n"] == 1:
            return {"status": "ok"}
        return {"status": "infra_fault", "error": "HTTP Error 400: nope"}

    rc = FakeRunCell()
    rec = arm_mod.run_arm("calibration", str(tmp_path), run_cell_fn=rc,
                          contract_calls={"G1": g1})
    assert len(rc.calls) == 4              # the cells all ran...
    assert rec["state"] == "invalidated"   # ...and the arm still dies (LN-6)
    assert "contract changed" in rec["cause"]


def test_unverifiable_contract_is_cannot_evaluate_not_complete(tmp_path):
    flip = {"n": 0}

    def g1():
        flip["n"] += 1
        if flip["n"] == 1:
            return {"status": "ok"}
        return {"status": "infra_fault", "error": "connection reset"}

    rec = arm_mod.run_arm("calibration", str(tmp_path),
                          run_cell_fn=FakeRunCell(),
                          contract_calls={"G1": g1})
    assert rec["state"] == "cannot_evaluate"
    assert rec["state"] != "complete"      # never encoded as success


# --- run_pilot and the calibration gate --------------------------------------

def _pilot(tmp_path, run_cell):
    return arm_mod.run_pilot(str(tmp_path), n_samples=1, run_cell_fn=run_cell,
                             contract_calls=ok_contract_calls())


def test_pilot_completes_when_calibration_is_clean(tmp_path):
    rc = FakeRunCell()                     # every cell: one accepted, unanimous
    pilot = _pilot(tmp_path, rc)
    assert pilot["calibration_gate"]["state"] == "pass"
    assert pilot["state"] == "complete"
    assert set(pilot["arms"]) == {"calibration", "main", "dose_response"}
    # calibration (4 cells) + main (20) + dose-response (4)
    assert len(rc.calls) == 28
    assert os.path.exists(pilot["pilot_receipt_path"])


def test_pilot_halts_everything_on_leaky_calibration(tmp_path):
    # four generators each accept one artifact; they split 2/2 on every probe
    script = {}
    for i in range(4):
        script[i] = {"cell": {"kernel": "crc32", "arm": "full"},
                     "candidates": [{"accepted": True, "sample_index": 0,
                                     "probe_output_hashes":
                                         uniform_outcomes(cls=f"sha256:{i % 2}")}],
                     "summary": {}}
    rc = FakeRunCell(script=script)
    pilot = _pilot(tmp_path, rc)
    assert pilot["calibration_gate"]["state"] == "fail"
    assert pilot["state"] == "halted"
    assert "leaky calibration" in pilot["cause"]
    assert "main" not in pilot["arms"]     # nothing proceeded
    assert len(rc.calls) == 4


def test_pilot_halts_on_calibration_cannot_evaluate(tmp_path):
    # accepted artifacts with NO probe records: gate cannot evaluate, and
    # cannot-evaluate must halt exactly as fail does — never read as pass
    script = {i: {"cell": {"kernel": "crc32", "arm": "full"},
                  "candidates": [{"accepted": True, "sample_index": 0}],
                  "summary": {}} for i in range(4)}
    rc = FakeRunCell(script=script)
    pilot = _pilot(tmp_path, rc)
    assert pilot["calibration_gate"]["state"] == "cannot_evaluate"
    assert pilot["state"] == "halted"
    assert "not a pass" in pilot["cause"]
    assert "main" not in pilot["arms"]


def test_pilot_halts_when_calibration_arm_invalidated(tmp_path):
    bad = {"cell": {"kernel": "crc32", "arm": "full"}, "candidates": [],
           "arm_invalidated": True, "note": "served string changed",
           "summary": {}}
    rc = FakeRunCell(script={0: bad})
    pilot = _pilot(tmp_path, rc)
    assert pilot["state"] == "halted"
    assert "calibration_gate" not in pilot  # gate never evaluated a dead arm


def test_fresh_arm_state_per_arm(tmp_path):
    rc = FakeRunCell()
    _pilot(tmp_path, rc)
    cal_state = rc.calls[0]["arm_state"]
    main_state = rc.calls[4]["arm_state"]
    assert cal_state is not main_state     # arm scope, not pilot scope
