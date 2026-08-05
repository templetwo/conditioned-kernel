#!/usr/bin/env python3
"""Opaque file transfer to the device. Replaces fixed-delimiter heredocs.

WHY THIS FILE EXISTS
--------------------
Every device-side gate used to stage its files like this:

    cat > cand.c <<'__ECS_EOF__'
    <candidate source>
    __ECS_EOF__

The delimiter is a FIXED STRING and the candidate is UNTRUSTED MODEL OUTPUT.
A candidate containing a line equal to `__ECS_EOF__` terminates the heredoc
early; every following line of that candidate is then read by `bash -s` as a
command, on the device, with the operator's credentials. Nothing in the gate
chain looks for this, and it would not surface as a gate failure — it would
surface as a strange compile error, or as nothing at all.

That is not only a safety hole. It is a MEASUREMENT hole: a candidate that can
influence its own build has escaped the instrument, and any receipt it produces
is unsound. Anthony directed the replacement in the same breath as the
fail-closed corrections, and the two belong together.

THE REPLACEMENT. Payloads are base64-encoded on the host and decoded on the
device, inside a heredoc whose delimiter is `__ECS_B64__`. Base64's alphabet is
`A-Za-z0-9+/=`, and the delimiter contains `_`, which is NOT in that alphabet.
No line of any payload can therefore equal the delimiter — not by accident and
not by construction. That is a proof about the character set rather than a hope
about content, which is the difference from the scheme it replaces.

The bytes that land in the file are byte-identical to the bytes that left the
host; a sha256 comparison on both sides asserts it, so a truncated or mangled
transfer is a loud infra fault rather than a quiet miscompile.

A single-argument form (`printf %s <b64> | base64 -d`) was rejected: Linux caps
one argv string at MAX_ARG_STRLEN = 128 KiB, and the generated vector driver for
crc32 exceeds that once base64 expands it by a third. The heredoc has no such
ceiling.

The command list itself is still ours and still fixed. The only thing that
crosses as data is data.
"""
import base64, hashlib, subprocess

DELIM = "__ECS_B64__"      # contains '_', outside the base64 alphabet, by design


def put(name, content):
    """Emit shell lines that materialise `content` at `name` on the device."""
    if isinstance(content, str):
        content = content.encode()
    b64 = base64.b64encode(content).decode()
    wrapped = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
    sha = hashlib.sha256(content).hexdigest()
    return [
        f"base64 -d > {name} <<'{DELIM}'",
        wrapped,
        DELIM,
        # fail closed, and loudly, if what landed is not what was sent
        f'test "$(sha256sum {name} | cut -d" " -f1)" = "{sha}" || '
        f'{{ echo "ECS_TRANSFER_MISMATCH {name}" >&2; exit 91; }}',
    ]


def run(host, script, timeout=900):
    """Run a fixed script on the device. Only `put` payloads cross as data."""
    return subprocess.run(["ssh", "-o", "BatchMode=yes", host, "bash -s"],
                          input="\n".join(script), capture_output=True,
                          text=True, timeout=timeout)


def transfer_failed(completed):
    """True if the remote refused a payload; that is infra, never a candidate."""
    return completed.returncode == 91 or "ECS_TRANSFER_MISMATCH" in (completed.stderr or "")
