"""probes/gen_probes.py — determinism, domain respect, and fail-closed states.

Offline: no device, no seed on this machine. Tests pass a synthetic seed
path, which is the sanctioned seam (`--seed-path ... that only resolves
there`); nothing here reads or expects ~/ecs/.probe_seed.
"""
import hashlib, json, os, struct, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "probes"))

import gen_probes as gp


SEED_A = b"a" * 64
SEED_B = b"b" * 64


def test_same_seed_same_probes():
    for k in gp.KERNELS:
        assert gp.serialize(gp.build(k, SEED_A)) == gp.serialize(gp.build(k, SEED_A))


def test_different_seed_different_probes():
    for k in gp.KERNELS:
        assert gp.serialize(gp.build(k, SEED_A)) != gp.serialize(gp.build(k, SEED_B))


def test_kernels_have_independent_streams():
    # the DRBG is labeled per kernel; two kernels must not share a stream
    a = gp.build("crc32", SEED_A)
    b = gp.build("sat_add_u8", SEED_A)
    assert gp.serialize(a) != gp.serialize(b)


def test_probe_count_is_frozen_256():
    for k in gp.KERNELS:
        obj = gp.build(k, SEED_A)
        assert obj["count"] == 256
        assert len(obj["probes"]) == 256
        ids = [p["id"] for p in obj["probes"]]
        assert len(set(ids)) == 256


def test_crc32_domain_n_max_4096():
    for p in gp.build("crc32", SEED_A)["probes"]:
        assert 0 <= p["n"] <= 4096
        assert len(bytes.fromhex(p["input_hex"])) == p["n"]


def test_sat_add_domain_n_256():
    for p in gp.build("sat_add_u8", SEED_A)["probes"]:
        assert p["n"] == 256
        assert len(bytes.fromhex(p["a_hex"])) == 256
        assert len(bytes.fromhex(p["b_hex"])) == 256


def test_fir_q15_buffer_shapes():
    for p in gp.build("fir_q15", SEED_A)["probes"]:
        assert len(bytes.fromhex(p["x_hex"])) == 256 * 2
        assert len(bytes.fromhex(p["h_hex"])) == 16 * 2


def test_matmul_entries_within_spec5_domain():
    # SPEC §5: entries in [-1024, 1023] — the bound is part of the surface
    for p in gp.build("matmul8_i32", SEED_A)["probes"]:
        for field in ("a_hex", "b_hex"):
            raw = bytes.fromhex(p[field])
            assert len(raw) == 64 * 4
            for v in struct.unpack("<64i", raw):
                assert -1024 <= v <= 1023


def test_median_buffer_shape():
    for p in gp.build("median3x3_u8", SEED_A)["probes"]:
        assert len(bytes.fromhex(p["in_hex"])) == 256


def test_canary_excluded_by_design():
    with pytest.raises(KeyError):
        gp.build("fir_q15_canary", SEED_A)


def test_generate_without_seed_is_cannot_evaluate(tmp_path):
    # absence of the seed is CANNOT_EVALUATE with cause, not an error and
    # not an empty run (SPEC §7a.2b)
    out = gp.generate(str(tmp_path / "no_such_seed"), str(tmp_path / "out"))
    assert out["state"] == "CANNOT_EVALUATE"
    assert "seed" in out["cause"]
    assert not os.path.exists(tmp_path / "out")


def test_generate_writes_files_and_manifest(tmp_path):
    seed = tmp_path / "seed"
    seed.write_bytes(SEED_A)
    out = gp.generate(str(seed), str(tmp_path / "probes"),
                      kernels=["crc32"],
                      manifest_out=str(tmp_path / "manifest.json"))
    assert out["state"] == "OK"
    realized = tmp_path / "probes" / "crc32.probes.json"
    blob = realized.read_bytes()
    m = json.load(open(tmp_path / "manifest.json"))
    assert m["kernels"]["crc32"]["sha256"] == hashlib.sha256(blob).hexdigest()
    # the manifest (the committable artifact) carries hashes, never probe bytes
    assert "probes" not in m["kernels"]["crc32"]
    assert "input_hex" not in json.dumps(m)


def test_verify_three_states(tmp_path):
    seed = tmp_path / "seed"
    seed.write_bytes(SEED_A)
    gp.generate(str(seed), str(tmp_path / "probes"), kernels=["crc32"],
                manifest_out=str(tmp_path / "manifest.json"))
    ok = gp.verify(str(tmp_path / "manifest.json"), str(tmp_path / "probes"))
    assert ok["state"] == "OK"

    # mutation -> MISMATCH, with cause
    p = tmp_path / "probes" / "crc32.probes.json"
    p.write_bytes(p.read_bytes() + b" ")
    mut = gp.verify(str(tmp_path / "manifest.json"), str(tmp_path / "probes"))
    assert mut["state"] == "MISMATCH"
    assert "mutation" in mut["kernels"]["crc32"]["cause"]

    # absence -> CANNOT_EVALUATE, distinct from MISMATCH
    p.unlink()
    absent = gp.verify(str(tmp_path / "manifest.json"), str(tmp_path / "probes"))
    assert absent["state"] == "CANNOT_EVALUATE"
    assert absent["kernels"]["crc32"]["state"] == "CANNOT_EVALUATE"


def test_drbg_int_bounds():
    rng = gp.Drbg(SEED_A, "t")
    vals = [rng.int(-5, 5) for _ in range(500)]
    assert min(vals) >= -5 and max(vals) <= 5
    assert len(set(vals)) > 5          # actually varies
