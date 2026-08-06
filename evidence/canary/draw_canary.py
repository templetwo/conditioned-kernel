#!/usr/bin/env python3
"""canary-draw/1.0 — sealed derivation draw for kernel six (fir_q15_canary).

Run by Anthony per evidence/SUPERSESSION-002.md. Writes the four-component
sealed bundle (procedure, seed, algorithm, mapping) plus the resulting draw
into evidence/canary/DRAW.md, OTS-stamps it in the same act, and prints ONLY
the SHA-256 and stamp status — never the mapping, so no agent context sees
the draw before the seal.

Verify a completed draw (third party, from the seed alone):
    python3 draw_canary.py --verify DRAW.md
"""

import hashlib
import hmac
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DRAW_PATH = os.path.join(HERE, "DRAW.md")
PROCEDURE_PATH = os.path.join(HERE, "PROCEDURE.md")
ALGORITHM_ID = "canary-draw/1.0"

# Enumeration order and option sets are fixed in PROCEDURE.md, pre-draw.
CHOICES = [
    ("C1", "left boundary policy",
     ["zero-pad", "edge-replicate (x[0])", "circular wrap (x[n-k+256])"]),
    ("C2", "accumulator",
     ["exact wide accumulation", "int32 two's-complement wraparound (defined)"]),
    ("C3", "saturation placement",
     ["clamp final shifted result once", "saturating accumulation at every add"]),
    ("C4", "rounding on right shift",
     ["truncate (arithmetic shift)", "round-to-nearest, half away from zero"]),
    ("C5", "shift amount s (nonce)",
     ["12", "13", "14", "16"]),
]


class Stream:
    """HMAC-SHA256 counter-mode byte stream keyed by the seed."""

    def __init__(self, seed: bytes):
        self.seed = seed
        self.counter = 0
        self.buf = b""

    def next_byte(self) -> int:
        if not self.buf:
            msg = self.counter.to_bytes(8, "big")
            self.buf = hmac.new(self.seed, msg, hashlib.sha256).digest()
            self.counter += 1
        b, self.buf = self.buf[0], self.buf[1:]
        return b

    def uniform(self, k: int) -> int:
        limit = 256 - (256 % k)
        while True:
            b = self.next_byte()
            if b < limit:
                return b % k


def perform_draw(seed: bytes):
    s = Stream(seed)
    return [(cid, name, opts[s.uniform(len(opts))], opts)
            for cid, name, opts in CHOICES]


def write_bundle(seed: bytes, drawn) -> str:
    with open(PROCEDURE_PATH, "r", encoding="utf-8") as f:
        procedure = f.read()
    lines = [
        "# Canary twin — sealed draw bundle (DO NOT EDIT; supersede only)",
        "",
        f"drawn_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"algorithm: {ALGORITHM_ID}  (HMAC-SHA256 counter stream, rejection-sampled uniform; see procedure below)",
        f"seed_hex: {seed.hex()}",
        "performed_by: Anthony Vasquez Sr (principal investigator), per SUPERSESSION-002",
        "",
        "## Mapping — the draw",
        "",
        "| id | choice point | drawn value |",
        "|---|---|---|",
    ]
    for cid, name, value, _opts in drawn:
        lines.append(f"| {cid} | {name} | {value} |")
    lines += [
        "",
        "## Procedure (verbatim, sealed with the draw)",
        "",
        procedure,
    ]
    return "\n".join(lines) + "\n"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp(path: str) -> bool:
    try:
        r = subprocess.run(["ots", "stamp", path], capture_output=True,
                           text=True, timeout=300)
        return r.returncode == 0 and os.path.exists(path + ".ots")
    except Exception:
        return False


def main_draw():
    if os.path.exists(DRAW_PATH):
        print("REFUSED: DRAW.md already exists. A draw is not repeatable; "
              "supersede on the record if it must be redone.")
        return 1
    seed = os.urandom(32)
    drawn = perform_draw(seed)
    bundle = write_bundle(seed, drawn)
    tmp = DRAW_PATH + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(bundle)
    os.replace(tmp, DRAW_PATH)
    digest = sha256_file(DRAW_PATH)
    ok = stamp(DRAW_PATH)
    print(f"DRAW.md written. sha256: {digest}")
    print(f"OTS stamp: {'ok — DRAW.md.ots created' if ok else 'FAILED — run: ots stamp evidence/canary/DRAW.md before anything else'}")
    print("The mapping was not printed. Commit DRAW.md and DRAW.md.ots now.")
    return 0 if ok else 2


def main_verify(path: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^seed_hex: ([0-9a-f]{64})$", text, re.M)
    if not m:
        print("verify FAILED: no seed_hex found")
        return 1
    drawn = perform_draw(bytes.fromhex(m.group(1)))
    bad = [cid for cid, name, value, _o in drawn
           if f"| {cid} | {name} | {value} |" not in text]
    if bad:
        print(f"verify FAILED: recorded mapping does not match re-derivation for {bad}")
        return 1
    print("verify OK: recorded mapping re-derives exactly from the recorded seed")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--verify":
        sys.exit(main_verify(sys.argv[2]))
    if len(sys.argv) == 1:
        sys.exit(main_draw())
    print(__doc__)
    sys.exit(1)
