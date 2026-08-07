#!/usr/bin/env python3
"""Probe-input generation — SPEC §6, deterministic given the probe seed.

WHERE THIS RUNS, AND WHY THAT IS THE WHOLE DESIGN
-------------------------------------------------
The probe seed lives ONLY on the Jetson at ~/ecs/.probe_seed, under
seed_guard (PREREG §12.7). This script therefore runs ON THE DEVICE, or is
pointed at the seed with --seed-path where that path resolves. What the repo
commits is the SHA-256 of each realized probe file (probes/probe_hashes.json),
never a probe byte: the git record pins the probes without revealing them,
and a mutation of the realized files is detectable at every run.

PROBE BLINDNESS. Nothing produced here may ever reach a generation or repair
prompt (SPEC §2 rule 5, §9). prompt.py cannot express such a leak — it takes a
packet path and gate feedback only — and this script reinforces the boundary
by never writing probe bytes to stdout: files land in --out-dir, stdout
carries hashes and counts only.

CONTENT. 256 probes per kernel for the frozen five: structured adversarial
cases the acceptance vector set deliberately omits, then seeded-random inputs
over each kernel's ECS domain (SPEC §5 table — matmul entries stay in
[-1024, 1023] because the domain bound is part of the surface, not a
suggestion). fir_q15_canary is EXCLUDED by design: its probes wait on its
sealed packet (SUPERSESSION-002), and generating them from this seed before
the draw is pinned would couple the two failure domains the canary spec keeps
apart.

DETERMINISM. A SHA-256 counter DRBG keyed on (seed bytes, kernel, counter).
Same seed -> byte-identical probe files; different seed -> different probes.
No stdlib random module, because its stream is not guaranteed stable across
Python versions and a probe file that silently changes with an interpreter
upgrade would fail its own committed hash for a reason that looks like
tampering.

Encodings match trusted/vectors/ and kernel_signatures.json: byte-hex,
little-endian host order for multi-byte element types.

Usage (on the device):
  gen_probes.py --out-dir ~/ecs/probes --manifest-out probe_hashes.json
  gen_probes.py --verify --manifest probes/probe_hashes.json --dir ~/ecs/probes
"""
import argparse, hashlib, json, os, struct, sys

PROBES_PER_KERNEL = 256          # PREREG §7, frozen row
DEFAULT_SEED_PATH = "~/ecs/.probe_seed"
KERNELS = ["crc32", "sat_add_u8", "fir_q15", "matmul8_i32", "median3x3_u8"]

I16_MIN, I16_MAX = -32768, 32767
MM_LO, MM_HI = -1024, 1023       # SPEC §5: matmul8_i32 entry domain


class Drbg:
    """SHA-256 counter DRBG. Streams are independent per (seed, label)."""

    def __init__(self, seed_bytes, label):
        self._key = seed_bytes + b"|" + label.encode()
        self._ctr = 0
        self._buf = b""

    def bytes(self, n):
        while len(self._buf) < n:
            self._buf += hashlib.sha256(
                self._key + self._ctr.to_bytes(8, "big")).digest()
            self._ctr += 1
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def int(self, lo, hi):
        """Uniform integer in [lo, hi] via rejection, so no modulo bias."""
        span = hi - lo + 1
        nbytes = (span.bit_length() + 7) // 8
        limit = (256 ** nbytes // span) * span
        while True:
            v = int.from_bytes(self.bytes(nbytes), "big")
            if v < limit:
                return lo + v % span


def _i16s(vals):
    return struct.pack("<%dh" % len(vals), *vals).hex()


def _i32s(vals):
    return struct.pack("<%di" % len(vals), *vals).hex()


def _rand_i16s(rng, n):
    return [rng.int(I16_MIN, I16_MAX) for _ in range(n)]


# --- structured adversarial cases, per kernel -------------------------------
# Each returns a list of probe dicts WITHOUT ids; ids are assigned by build().
# These target the seams the vector sets leave for the probes: boundary
# handling, saturation edges, layout-revealing asymmetry, rounding bits.

def _adv_crc32(rng):
    p = []
    p.append({"n": 0, "input_hex": ""})
    for b in (0x00, 0xFF, 0x80, 0x7F):
        p.append({"n": 1, "input_hex": bytes([b]).hex()})
    p.append({"n": 4096, "input_hex": (b"\x00" * 4096).hex()})
    p.append({"n": 4096, "input_hex": (b"\xff" * 4096).hex()})
    p.append({"n": 4096, "input_hex": bytes(i & 0xFF for i in range(4096)).hex()})
    p.append({"n": 4095, "input_hex": rng.bytes(4095).hex()})
    for k in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048):
        p.append({"n": k, "input_hex": rng.bytes(k).hex()})
    # single set bit walking through the first word: register-entry ordering
    for bit in range(8):
        p.append({"n": 4, "input_hex": bytes([1 << bit, 0, 0, 0]).hex()})
    return p


def _adv_sat_add(rng):
    p = []
    consts = [(0xFF, 0xFF), (0xFF, 0x01), (0x80, 0x80), (0x7F, 0x7F),
              (0x00, 0x00), (0xFE, 0x01), (0xFF, 0x00), (0x01, 0xFE)]
    for a, b in consts:
        p.append({"n": 256, "a_hex": (bytes([a]) * 256).hex(),
                  "b_hex": (bytes([b]) * 256).hex()})
    # exact-boundary sweeps: a+b == 255 (no saturation) and == 256 (saturates)
    a = bytes(i & 0xFF for i in range(256))
    p.append({"n": 256, "a_hex": a.hex(),
              "b_hex": bytes((255 - i) & 0xFF for i in range(256)).hex()})
    p.append({"n": 256, "a_hex": a.hex(),
              "b_hex": bytes((256 - i) & 0xFF for i in range(256)).hex()})
    return p


def _adv_fir_q15(rng):
    p = []
    def probe(x, h):
        return {"x_hex": _i16s(x), "h_hex": _i16s(h)}
    # accumulator and saturation stress: extremes in every combination
    p.append(probe([I16_MIN] * 256, [I16_MIN] * 16))
    p.append(probe([I16_MAX] * 256, [I16_MAX] * 16))
    p.append(probe([I16_MIN] * 256, [I16_MAX] * 16))
    p.append(probe([I16_MAX] * 256, [I16_MIN] * 16))
    # impulses: left-boundary handling (choice point A1) and tap ordering
    imp = [0] * 256
    imp[0] = I16_MAX
    p.append(probe(imp, _rand_i16s(rng, 16)))
    for tap in (0, 1, 15):
        h = [0] * 16
        h[tap] = I16_MAX
        p.append(probe(_rand_i16s(rng, 256), h))
    # alternating full-scale: sign handling in the saturating accumulate
    p.append(probe([I16_MAX if i % 2 == 0 else I16_MIN for i in range(256)],
                   [I16_MAX if i % 2 == 0 else I16_MIN for i in range(16)]))
    # small odd values so the >>15 rounding bit (choice point A4) is live
    p.append(probe([rng.int(-3, 3) | 1 for _ in range(256)],
                   [rng.int(-255, 255) | 1 for _ in range(16)]))
    return p


def _adv_matmul(rng):
    p = []
    def probe(a, b):
        return {"a_hex": _i32s(a), "b_hex": _i32s(b)}
    ident = [1 if i // 8 == i % 8 else 0 for i in range(64)]
    rnd = [rng.int(MM_LO, MM_HI) for _ in range(64)]
    p.append(probe([MM_LO] * 64, [MM_LO] * 64))
    p.append(probe([MM_HI] * 64, [MM_HI] * 64))
    p.append(probe([MM_LO] * 64, [MM_HI] * 64))
    p.append(probe(ident, rnd))
    p.append(probe(rnd, ident))
    # deliberately asymmetric single-entry pairs: a transposed reading of
    # either operand produces a different product, so layout divergence among
    # accepted artifacts is visible to D rather than cancelling out
    for (i, j) in ((0, 7), (7, 0), (1, 3), (6, 2)):
        e = [0] * 64
        e[i * 8 + j] = MM_HI
        p.append(probe(e, rnd))
        p.append(probe(rnd, e))
    return p


def _adv_median(rng):
    p = []
    def probe(img):
        return {"in_hex": bytes(img).hex()}
    p.append(probe([0x00] * 256))
    p.append(probe([0xFF] * 256))
    p.append(probe([0xFF if (i // 16 + i % 16) % 2 == 0 else 0x00
                    for i in range(256)]))
    # horizontal vs vertical gradients: a transposed reading of the image
    # swaps these two, so they separate row/column confusion where a
    # symmetric input cannot (the vector set is asymmetry-weighted for the
    # same reason)
    p.append(probe([(i % 16) * 17 for i in range(256)]))
    p.append(probe([(i // 16) * 17 for i in range(256)]))
    # single hot pixel at an interior corner and at dead centre
    for hot in (17, 17 * 8):
        img = [0] * 256
        img[hot] = 0xFF
        p.append(probe(img))
    # near-uniform with one-bit perturbations: median ties and sort stability
    base = list(rng.bytes(256))
    p.append(probe(base))
    p.append(probe([b ^ 1 for b in base]))
    return p


# --- random fill over the ECS domain ----------------------------------------

def _rand_crc32(rng):
    n = rng.int(0, 4096)
    return {"n": n, "input_hex": rng.bytes(n).hex()}


def _rand_sat_add(rng):
    return {"n": 256, "a_hex": rng.bytes(256).hex(), "b_hex": rng.bytes(256).hex()}


def _rand_fir(rng):
    return {"x_hex": _i16s(_rand_i16s(rng, 256)),
            "h_hex": _i16s(_rand_i16s(rng, 16))}


def _rand_matmul(rng):
    return {"a_hex": _i32s([rng.int(MM_LO, MM_HI) for _ in range(64)]),
            "b_hex": _i32s([rng.int(MM_LO, MM_HI) for _ in range(64)])}


def _rand_median(rng):
    return {"in_hex": rng.bytes(256).hex()}


ADVERSARIAL = {"crc32": _adv_crc32, "sat_add_u8": _adv_sat_add,
               "fir_q15": _adv_fir_q15, "matmul8_i32": _adv_matmul,
               "median3x3_u8": _adv_median}
RANDOM = {"crc32": _rand_crc32, "sat_add_u8": _rand_sat_add,
          "fir_q15": _rand_fir, "matmul8_i32": _rand_matmul,
          "median3x3_u8": _rand_median}


def build(kernel, seed_bytes, count=PROBES_PER_KERNEL):
    """Return the realized probe object for one kernel. Pure and deterministic."""
    if kernel not in ADVERSARIAL:
        raise KeyError(f"no probe generator for kernel {kernel!r}; the frozen "
                       f"five are {KERNELS}")
    rng = Drbg(seed_bytes, f"ecs-probes-v1:{kernel}")
    probes = ADVERSARIAL[kernel](rng)
    if len(probes) > count:
        raise ValueError(f"{kernel}: {len(probes)} adversarial cases exceed the "
                         f"frozen probe count {count}")
    while len(probes) < count:
        probes.append(RANDOM[kernel](rng))
    for i, p in enumerate(probes):
        p["id"] = f"{kernel}_probe_{i:03d}"
    return {"kernel": kernel, "probe_set": "ecs-probes-v1", "count": count,
            "probes": probes}


def serialize(obj):
    """Canonical bytes for hashing: key-sorted, no whitespace. The committed
    hash is over these exact bytes, so serialization is part of the contract."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _read_seed(path):
    """Seed file bytes, verbatim. The value is never printed, logged, or
    included in any output; only material derived through SHA-256 leaves."""
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return f.read().strip()


def generate(seed_path, out_dir, kernels=None, manifest_out=None):
    """Realize probe files and return the hash manifest (which is printable;
    the probe files themselves are not)."""
    seed = _read_seed(seed_path)
    if seed is None or not seed:
        # THREE STATES (SPEC §7a.2b): a missing seed is not an empty probe set
        # and not an error about the kernels — it is cannot-evaluate, and the
        # cause names the remedy (run where the seed path resolves).
        return {"state": "CANNOT_EVALUATE",
                "cause": f"no probe seed at {seed_path}; generation runs only "
                         f"where that path resolves (the device). Nothing was "
                         f"written."}
    out_dir = os.path.expanduser(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"probe_set": "ecs-probes-v1",
                "probes_per_kernel": PROBES_PER_KERNEL,
                "note": ("sha256 of each realized probe file; committed so the "
                         "git record pins the probes without revealing them "
                         "(SPEC §6). Probe bytes live only on the device."),
                "kernels": {}}
    for k in (kernels or KERNELS):
        blob = serialize(build(k, seed))
        path = os.path.join(out_dir, f"{k}.probes.json")
        with open(path, "wb") as f:
            f.write(blob)
        os.chmod(path, 0o600)
        manifest["kernels"][k] = {"sha256": hashlib.sha256(blob).hexdigest(),
                                  "count": PROBES_PER_KERNEL,
                                  "bytes": len(blob)}
    if manifest_out:
        with open(os.path.expanduser(manifest_out), "w") as f:
            json.dump(manifest, f, indent=1)
    return {"state": "OK", "out_dir": out_dir, "manifest": manifest}


def verify(manifest_path, probe_dir):
    """Hash-check realized probe files against the committed manifest.

    Per-kernel outcomes are OK / MISMATCH / CANNOT_EVALUATE — a file that is
    absent has not failed its hash, and a hash that fails is not an absence;
    the remedies differ (regenerate vs. investigate mutation)."""
    manifest = json.load(open(os.path.expanduser(manifest_path)))
    out = {"state": "OK", "kernels": {}}
    for k, entry in manifest["kernels"].items():
        p = os.path.join(os.path.expanduser(probe_dir), f"{k}.probes.json")
        if not os.path.exists(p):
            out["kernels"][k] = {"state": "CANNOT_EVALUATE",
                                 "cause": f"no realized probe file at {p}"}
            out["state"] = "CANNOT_EVALUATE"
            continue
        got = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if got == entry["sha256"]:
            out["kernels"][k] = {"state": "OK"}
        else:
            out["kernels"][k] = {"state": "MISMATCH", "expected": entry["sha256"],
                                 "got": got,
                                 "cause": "realized probe file does not match "
                                          "its committed hash; treat as "
                                          "mutation until shown otherwise"}
            out["state"] = "MISMATCH"
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed-path", default=DEFAULT_SEED_PATH)
    ap.add_argument("--out-dir", default="~/ecs/probes")
    ap.add_argument("--manifest-out", default=None,
                    help="also write the hash manifest here (this file is the "
                         "committable artifact)")
    ap.add_argument("--kernel", action="append", default=None,
                    help="restrict to specific kernels (default: frozen five)")
    ap.add_argument("--verify", action="store_true",
                    help="hash-check realized files against a committed manifest")
    ap.add_argument("--manifest", default=None, help="manifest path for --verify")
    ap.add_argument("--dir", default="~/ecs/probes", help="probe dir for --verify")
    a = ap.parse_args(argv)

    if a.verify:
        if not a.manifest:
            print(json.dumps({"state": "CANNOT_EVALUATE",
                              "cause": "--verify requires --manifest"}))
            return 2
        out = verify(a.manifest, a.dir)
        print(json.dumps(out, indent=1))
        return 0 if out["state"] == "OK" else 1

    out = generate(a.seed_path, a.out_dir, a.kernel, a.manifest_out)
    print(json.dumps(out, indent=1))
    return 0 if out["state"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
