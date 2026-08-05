#!/usr/bin/env python3
"""Probe-seed guard — Anthony's Rider 2 for P1 (seat board #13778).

Answers the half of PREREG §12.7 that hash commitments cannot cover:
a MUTATION of realized probes is detectable by hash; a READ of the seed is
detectable by nothing at all unless reads are instrumented.

WHAT THIS GIVES YOU, PRECISELY
------------------------------
  - The seed file is created 0400 inside a 0700 directory (owner-only).
  - Every open/access/modify of the seed appends a timestamped JSON receipt
    to the audit log. A read stops being invisible.
  - Permission drift is detectable via `verify`.

WHAT THIS DOES NOT GIVE YOU — read before trusting it
-----------------------------------------------------
  1. NO PROCESS ATTRIBUTION. inotify reports that an event happened, not who
     caused it. auditd is not installed on this device and fanotify (which
     does report PID) requires CAP_SYS_ADMIN and is denied unprivileged.
     A receipt therefore says "the seed was opened at T", never "X opened it".
  2. NO COVERAGE WHILE THE WATCHER IS DOWN. Events occurring when the watcher
     is not running are lost, not queued. Gaps in the log are gaps in
     knowledge, not evidence of absence. `verify` reports watcher liveness so
     a gap is at least attributable to downtime.
  3. ROOT DEFEATS IT. A privileged user can stop the watcher, or read the
     file after stopping it, and leave no receipt.
  4. atime IS NOT A FALLBACK. This filesystem is mounted `relatime`, so
     access times are not updated per-read and cannot corroborate the log.

So this converts an unobservable risk into an observable one. It does not
convert it into a prevented one. Do not describe it as tamper-proof.

The seed VALUE is never read, logged, printed, or transmitted by this tool.
Only its metadata and access events are handled.

LANE NOTE: the probe seed itself is Agent B's deliverable (trusted/, SPEC §6).
This guard is device/harness work (Agent A). Intended use is that the guard
arms at seed creation rather than being retrofitted afterwards.
"""
import ctypes, json, os, stat, struct, sys, time

SEED = os.path.expanduser("~/ecs/.probe_seed")
AUDIT = os.path.expanduser("~/ecs/receipts/probe_seed_audit.jsonl")

IN_ACCESS, IN_MODIFY, IN_ATTRIB = 0x001, 0x002, 0x004
IN_OPEN, IN_MOVE_SELF, IN_DELETE_SELF = 0x020, 0x800, 0x400
WATCH_MASK = IN_ACCESS | IN_MODIFY | IN_ATTRIB | IN_OPEN | IN_MOVE_SELF | IN_DELETE_SELF
EVENT_NAMES = {IN_ACCESS: "ACCESS", IN_MODIFY: "MODIFY", IN_ATTRIB: "ATTRIB",
               IN_OPEN: "OPEN", IN_MOVE_SELF: "MOVE_SELF", IN_DELETE_SELF: "DELETE_SELF"}


def _receipt(event, **extra):
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    rec = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event}
    rec.update(extra)
    with open(AUDIT, "a") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        # 0600, NOT 0400. The log must stay appendable by its owner; chmod 0400
        # here silently breaks every subsequent append and the log records
        # exactly one event. Found by testing 2026-08-04 — the read that was
        # supposed to be caught produced no receipt because of this.
        # True append-only (chattr +a) needs root and is not available here.
        os.chmod(AUDIT, 0o600)
    except OSError:
        pass
    return rec


def harden():
    """0700 on the containing directory, 0400 on the seed. Idempotent."""
    d = os.path.dirname(SEED)
    os.makedirs(d, exist_ok=True)
    os.chmod(d, 0o700)
    if os.path.exists(SEED):
        os.chmod(SEED, 0o400)
    return {"dir": oct(stat.S_IMODE(os.stat(d).st_mode)),
            "seed": oct(stat.S_IMODE(os.stat(SEED).st_mode)) if os.path.exists(SEED) else None}


def create(nbytes=32):
    """Create the seed if absent. Never prints the value. Records only its hash."""
    if os.path.exists(SEED):
        print(json.dumps({"status": "exists", "note": "refusing to overwrite", **harden()}))
        return 1
    import hashlib
    val = os.urandom(nbytes)
    d = os.path.dirname(SEED)
    os.makedirs(d, exist_ok=True)
    os.chmod(d, 0o700)
    fd = os.open(SEED, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, val.hex().encode())
    finally:
        os.close(fd)
    digest = hashlib.sha256(val.hex().encode()).hexdigest()
    del val
    rec = _receipt("SEED_CREATED", nbytes=nbytes, seed_sha256=digest, **harden())
    print(json.dumps({"status": "created", **rec}))
    return 0


def verify():
    """Report permission state, watcher liveness, and audit-log continuity."""
    out: "dict[str, object]" = {"seed_exists": os.path.exists(SEED),
                                "audit_exists": os.path.exists(AUDIT)}
    if out["seed_exists"]:
        st = os.stat(SEED)
        out["seed_mode"] = oct(stat.S_IMODE(st.st_mode))
        out["seed_mode_ok"] = stat.S_IMODE(st.st_mode) == 0o400
        out["dir_mode"] = oct(stat.S_IMODE(os.stat(os.path.dirname(SEED)).st_mode))
        out["dir_mode_ok"] = stat.S_IMODE(os.stat(os.path.dirname(SEED)).st_mode) == 0o700
    if out["audit_exists"]:
        lines = [l for l in open(AUDIT) if l.strip()]
        out["audit_events"] = len(lines)
        out["last_event"] = json.loads(lines[-1]) if lines else None
    # match BOTH entry points. An earlier version matched only 'watch' and
    # would report the watcher down while it was running under 'arm' — a
    # liveness check that lies in the safe-looking direction is worse than none.
    out["watcher_running"] = os.system(
        "pgrep -f 'seed_guard.py (watch|arm)' >/dev/null 2>&1") == 0
    out["caveat"] = ("inotify gives no process attribution; gaps during watcher downtime "
                     "are lost, not queued; root can defeat this; relatime makes atime useless")
    print(json.dumps(out, indent=1))
    return 0 if out.get("seed_mode_ok", False) else 1


def watch():
    """Block, logging every access event to the seed as a receipt."""
    if not os.path.exists(SEED):
        print(json.dumps({"error": "seed does not exist; create it first"}))
        return 1
    harden()
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    fd = libc.inotify_init()
    if fd < 0:
        print(json.dumps({"error": "inotify_init failed"}))
        return 1
    wd = libc.inotify_add_watch(fd, SEED.encode(), WATCH_MASK)
    if wd < 0:
        print(json.dumps({"error": "inotify_add_watch failed"}))
        return 1
    _receipt("WATCH_ARMED", seed=SEED, pid=os.getpid())
    print(json.dumps({"status": "watching", "seed": SEED, "audit": AUDIT}), flush=True)
    try:
        while True:
            data = os.read(fd, 4096)
            off = 0
            while off < len(data):
                mask, length = struct.unpack_from("iIII", data, off)[1::2]
                off += 16 + length
                for bit, name in EVENT_NAMES.items():
                    if mask & bit:
                        rec = _receipt(name, seed=SEED,
                                       note="inotify: no process attribution available")
                        print(json.dumps(rec), flush=True)
    except KeyboardInterrupt:
        _receipt("WATCH_STOPPED", reason="interrupt")
        return 0


def arm():
    """Create the seed and arm the watch in ONE process, with no gap.

    `create` then `watch` as separate commands leaves a window between the
    seed existing and the watcher running, during which a read produces no
    receipt. The window is short but it is exactly the moment the seed is
    newest and least protected. This closes it: the file is created and the
    watch is armed without returning to the shell in between.
    """
    if os.path.exists(SEED):
        print(json.dumps({"status": "exists", "note": "refusing to overwrite; "
                          "run 'watch' to arm against the existing seed"}))
        return 1
    rc = create()
    if rc != 0:
        return rc
    return watch()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    sys.exit({"create": create, "watch": watch, "verify": verify, "arm": arm,
              "harden": lambda: (print(json.dumps(harden())), 0)[1]}.get(cmd, verify)())
