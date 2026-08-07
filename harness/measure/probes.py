#!/usr/bin/env python3
"""Host side of the probe battery — SPEC §9's `probe` stage, fail-closed.

Ships probe_run.py and the candidate to the device, verifies the realized
probe file against its COMMITTED hash (SPEC §6: "hash-checked against the
committed hashes at every run"), runs the battery, and returns per-probe
output classes for the receipt.

WHAT NEVER CROSSES. Probe bytes stay on the device; this module moves only
the candidate (base64-opaque per SPEC §7a.3, via remote.put), the battery
script, the signature file, and — back — output digests. Nothing returned
here may reach a prompt, and nothing here is importable from the prompt path.

EVERY FAILURE IS AN INFRA FAULT, raised as chain.Infra. The candidate was
already ACCEPTED when the battery runs, so no battery outcome is a verdict on
the candidate — a battery that cannot run is a broken instrument, and per
SPEC §7a.2b / §9 it consumes no sample and is never a silent skip. The one
exception is a probe that CRASHES: that is a real, labeled output class of
the artifact (see probe_run.py) and comes back as data, not as a fault.

Committed-hash source: probes/probe_hashes.json at the repo root. Until the
device-side realization step has run and its manifest is committed, that file
is absent and this module fails closed — an arm cannot start probing against
probes nothing pins.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "harness", "gates"))
import remote as rmt
from chain import Infra

DEVICE = "jetson"
MANIFEST = os.path.join(ROOT, "probes", "probe_hashes.json")
DEVICE_PROBE_DIR = "~/ecs/probes"
REMOTE_WORK = "~/ecs/probework"

# Reserved exit codes on the device script. 91 is remote.put's transfer
# mismatch; these must not collide with it.
EXIT_HASH_MISMATCH = 92
EXIT_PROBES_ABSENT = 93
EXIT_CANNOT_EVALUATE = 94


def committed_hash(kernel, manifest_path=MANIFEST):
    """The committed pin for this kernel's realized probe file, or Infra."""
    if not os.path.exists(manifest_path):
        raise Infra(f"no committed probe-hash manifest at {manifest_path}; "
                    f"realize probes on the device (probes/gen_probes.py) and "
                    f"commit the manifest before any arm probes")
    m = json.load(open(manifest_path))
    entry = (m.get("kernels") or {}).get(kernel)
    if not entry or not entry.get("sha256"):
        raise Infra(f"probe-hash manifest has no entry for {kernel}")
    return entry["sha256"], entry.get("count")


def battery(candidate_src, kernel, device=DEVICE, manifest_path=MANIFEST):
    """Run the full probe battery on-device. Returns the receipt fragment
    {probe_count, results: [{probe_id, output_class}]} or raises Infra."""
    expected_sha, expected_count = committed_hash(kernel, manifest_path)

    probe_file = f"{DEVICE_PROBE_DIR}/{kernel}.probes.json"
    remotedir = f"{REMOTE_WORK}/{kernel}"
    dev = os.path.join(ROOT, "harness", "device")
    sigs = os.path.join(ROOT, "harness", "gates", "kernel_signatures.json")

    # The battery script and signature table are SHIPPED each run rather than
    # assumed present — same rule as the eviction barrier: "the file was
    # already there" is not a version claim.
    script = ["set -e", f"rm -rf {remotedir}", f"mkdir -p {remotedir}",
              f"cd {remotedir}"]
    script += rmt.put("probe_run.py", open(os.path.join(dev, "probe_run.py")).read())
    script += rmt.put("kernel_signatures.json", open(sigs).read())
    script += rmt.put("cand.c", candidate_src)
    script += [
        # the realized probes are verified against the COMMITTED hash before
        # any probe runs; a mutated or missing probe file is instrument state
        f"test -f {probe_file} || exit {EXIT_PROBES_ABSENT}",
        f'test "$(sha256sum {probe_file} | cut -d\\  -f1)" = "{expected_sha}" '
        f"|| exit {EXIT_HASH_MISMATCH}",
        f"python3 probe_run.py --probes {probe_file} --candidate cand.c "
        f"--kernel {kernel} --signatures kernel_signatures.json",
    ]
    try:
        r = rmt.run(device, script, timeout=1800)
    except Exception as e:
        raise Infra(f"probe battery transport failed: {str(e)[:200]}")
    if rmt.transfer_failed(r):
        raise Infra("probe battery payload digest mismatch on device")
    if r.returncode == 255:
        raise Infra(f"probe battery ssh transport failed: {r.stderr[:300]}")
    if r.returncode == EXIT_PROBES_ABSENT:
        raise Infra(f"no realized probe file at {probe_file}; run "
                    f"probes/gen_probes.py on the device first")
    if r.returncode == EXIT_HASH_MISMATCH:
        raise Infra(f"realized probe file at {probe_file} does not match its "
                    f"committed hash; treat as mutation until shown otherwise "
                    f"(PREREG §12.7)")

    payload = None
    for line in r.stdout.splitlines():
        if line.startswith("{"):
            payload = json.loads(line)
    if payload is None:
        raise Infra(f"probe battery emitted no result "
                    f"(rc={r.returncode}): {(r.stderr or r.stdout)[:300]}")
    if payload.get("status") != "ok":
        raise Infra(f"probe battery cannot-evaluate: "
                    f"{payload.get('cause', 'no cause reported')}")
    results = payload.get("results") or []
    if expected_count is not None and len(results) != expected_count:
        raise Infra(f"probe battery returned {len(results)} classes; the "
                    f"committed manifest pins {expected_count}")
    return {"probe_count": len(results), "probe_set": "ecs-probes-v1",
            "results": results}


if __name__ == "__main__":
    src = open(sys.argv[1]).read()
    print(json.dumps(battery(src, sys.argv[2] if len(sys.argv) > 2 else "crc32"),
                     indent=1))
