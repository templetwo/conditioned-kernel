"""Post-accept measure/probe pipeline — offline slices of every layer.

  runner:      an accepted candidate whose probe battery cannot run is an
               INFRA ABORT with a refilled slot, never a green receipt
  probes.py:   fails closed with no manifest, before any ssh
  post_accept: gate-6 measurement reuse is pure and device-free
  probe_run:   driver generation + a local end-to-end battery under the host
               gcc (skipped if gcc is absent), including the CRASH class

No device, no Ollama: the runner test mocks the gate chain and the
post-accept stage at their seams; the probe_run test runs entirely in
tmp_path with local subprocesses.
"""
import json, os, shutil, subprocess, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, os.path.join(ROOT, "harness", "gates"))
sys.path.insert(0, os.path.join(ROOT, "harness", "measure"))
sys.path.insert(0, os.path.join(ROOT, "harness", "device"))

import runner
import chain
import probes as probes_mod
import post_accept as pa
import probe_run

CRC32_PACKET = os.path.join(ROOT, "ecs", "crc32.ecs.yaml")
SIGS = os.path.join(ROOT, "harness", "gates", "kernel_signatures.json")


def fake_generate(prompt, kernel):
    return {"generator_id": "TEST", "model_string_requested": "t",
            "model_string_served": "t", "status": "ok", "temperature": 0.8,
            "elapsed_ms": 0, "output": "uint32_t crc32(...){}"}


def accepted_gates(*_a, **_k):
    return {"kernel": "crc32", "completeness": "full", "accepted": True,
            "infra_fault": False, "stopped_at": None,
            "vector_policy": {"completeness": "full"},
            "gates": {"1_lint": {"result": "pass", "feedback": []}}}


def probe_outcomes(n=4, cls="sha256:x"):
    return [{"probe_id": f"p{i:03d}", "output_class": cls} for i in range(n)]


# --- runner: ACCEPT -> measure -> probe, failing closed ----------------------

def test_accepted_candidate_carries_probe_record(monkeypatch):
    monkeypatch.setattr(runner.chain, "run", accepted_gates)
    ok_stage = lambda src, packet, gates: {
        "measurement": {"status": "ok", "ratio": 1.0},
        "probe_output_hashes": probe_outcomes(),
        "probe_count": 4, "probe_set": "ecs-probes-v1"}
    cell = runner.run_cell(CRC32_PACKET, fake_generate, n_samples=1,
                           arm_state=runner.new_arm_state(),
                           post_accept=ok_stage)
    c = cell["candidates"][0]
    assert c["accepted"] is True
    assert c["probe_output_hashes"] == probe_outcomes()
    assert c["measurement"]["status"] == "ok"


def test_probe_infra_aborts_slot_and_refills(monkeypatch):
    monkeypatch.setattr(runner.chain, "run", accepted_gates)
    calls = {"n": 0}

    def flaky_stage(src, packet, gates):
        calls["n"] += 1
        if calls["n"] == 1:
            raise chain.Infra("probe battery unreachable")
        return {"measurement": {"status": "ok"},
                "probe_output_hashes": probe_outcomes(),
                "probe_count": 4, "probe_set": "ecs-probes-v1"}

    arm_state = runner.new_arm_state()
    cell = runner.run_cell(CRC32_PACKET, fake_generate, n_samples=1,
                           arm_state=arm_state, post_accept=flaky_stage)
    # first slot: ACCEPTED by gates but the instrument could not probe it —
    # infra abort, no green receipt, slot refilled (SPEC §7a.2b, §13a item 3)
    first, second = cell["candidates"]
    assert first["infra_abort"] is True
    assert first["accepted"] is False
    assert "probe_output_hashes" not in first
    assert first["slot_refilled"] is True
    assert second["accepted"] is True
    assert cell["summary"]["scored_samples"] == 1
    assert cell["summary"]["acceptance_denominator"] == 1
    assert arm_state["infra_aborts"] == 1


# --- probes.py host side: fails closed before any ssh ------------------------

def test_battery_without_committed_manifest_is_infra(tmp_path):
    with pytest.raises(chain.Infra) as e:
        probes_mod.battery("int x;", "crc32",
                           manifest_path=str(tmp_path / "absent.json"))
    assert "manifest" in str(e.value)


def test_battery_without_kernel_entry_is_infra(tmp_path):
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"kernels": {"sat_add_u8": {"sha256": "aa"}}}))
    with pytest.raises(chain.Infra) as e:
        probes_mod.battery("int x;", "crc32", manifest_path=str(m))
    assert "no entry for crc32" in str(e.value)


# --- post_accept: gate-6 measurement reuse is pure ---------------------------

def test_measure_stage_reuses_gate6_same_batch():
    gates = {"gates": {"6_budget": {"actual": {
        "cycles_measure": {"status": "ok", "ratio": 1.2, "candidate_ns": 100.0},
        "baseline_oracle": "crc32_agentA.c"}}}}
    m = pa.measure_stage("src", "crc32", gates, device=None)
    assert m["source"] == "gate6_same_batch"
    assert m["ratio"] == 1.2
    assert m["baseline_oracle"] == "crc32_agentA.c"


# --- probe_run: local end-to-end under the host compiler ---------------------

GOOD_CRC32 = r"""
#include <stdint.h>
#include <stddef.h>
uint32_t crc32(const uint8_t *d, size_t n){
    uint32_t c = 0xFFFFFFFFu;
    for(size_t i = 0; i < n; i++){
        c ^= d[i];
        for(int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return c ^ 0xFFFFFFFFu;
}
"""

CRASHY_CRC32 = GOOD_CRC32.replace(
    "uint32_t c = 0xFFFFFFFFu;",
    "uint32_t c = 0xFFFFFFFFu;\n"
    "    if(n == 3){ volatile int *p = 0; *p = 1; }")


def _probe_file(tmp_path):
    probes = [
        {"id": "crc32_probe_000", "n": 0, "input_hex": ""},
        {"id": "crc32_probe_001", "n": 9,
         "input_hex": b"123456789".hex()},
        {"id": "crc32_probe_002", "n": 3, "input_hex": "010203"},
        {"id": "crc32_probe_003", "n": 4, "input_hex": "deadbeef"},
    ]
    p = tmp_path / "crc32.probes.json"
    p.write_text(json.dumps({"kernel": "crc32", "probe_set": "ecs-probes-v1",
                             "count": len(probes), "probes": probes}))
    return str(p)


def _run_battery(tmp_path, capsys, src, name):
    cand = tmp_path / name
    cand.write_text(src)
    rc = probe_run.run(_probe_file(tmp_path), str(cand), "crc32", SIGS,
                       cflags="-O2", workdir=str(tmp_path / f"wd_{name}"))
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return rc, json.loads(out)


needs_gcc = pytest.mark.skipif(shutil.which("gcc") is None,
                               reason="no host gcc")


@needs_gcc
def test_probe_run_end_to_end_and_deterministic(tmp_path, capsys):
    rc, out = _run_battery(tmp_path, capsys, GOOD_CRC32, "a.c")
    assert rc == 0 and out["status"] == "ok"
    assert out["probe_count"] == 4
    classes = {r["probe_id"]: r["output_class"] for r in out["results"]}
    assert all(c.startswith("sha256:") for c in classes.values())
    # the "123456789" probe must hash the LE bytes of 0xCBF43926
    import hashlib
    expect = hashlib.sha256((0xCBF43926).to_bytes(4, "little")).hexdigest()
    assert classes["crc32_probe_001"] == f"sha256:{expect}"

    # a byte-different but behaviour-identical build clusters identically
    rc2, out2 = _run_battery(tmp_path, capsys, GOOD_CRC32 + "\n/*x*/", "b.c")
    classes2 = {r["probe_id"]: r["output_class"] for r in out2["results"]}
    assert classes2 == classes


@needs_gcc
def test_probe_run_crash_is_labeled_class_not_truncation(tmp_path, capsys):
    rc, out = _run_battery(tmp_path, capsys, CRASHY_CRC32, "c.c")
    assert rc == 0 and out["status"] == "ok"       # a crash is DATA, not a fault
    classes = {r["probe_id"]: r["output_class"] for r in out["results"]}
    assert classes["crc32_probe_002"].startswith("CRASH:")
    # the trapping probe took nothing else with it — fork isolation
    assert classes["crc32_probe_001"].startswith("sha256:")
    assert len(classes) == 4


def test_probe_run_wrong_kernel_is_cannot_evaluate(tmp_path, capsys):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"kernel": "sat_add_u8", "probes": [{"id": "x"}]}))
    cand = tmp_path / "c.c"
    cand.write_text("int x;")
    rc = probe_run.run(str(p), str(cand), "crc32", SIGS)
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 94
    assert out["status"] == "CANNOT_EVALUATE"
    assert "cause" in out


def test_probe_run_empty_probe_file_is_cannot_evaluate(tmp_path, capsys):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"kernel": "crc32", "probes": []}))
    cand = tmp_path / "c.c"
    cand.write_text("int x;")
    rc = probe_run.run(str(p), str(cand), "crc32", SIGS)
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 94 and out["status"] == "CANNOT_EVALUATE"
