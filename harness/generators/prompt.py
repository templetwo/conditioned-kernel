#!/usr/bin/env python3
"""Prompt assembly — the integrity-critical part of the harness.

SPEC §9 permits a generation or repair prompt to be built from EXACTLY three
things and nothing else:

  1. the rendered ECS packet
  2. the C signature
  3. (repair only) the current gate's feedback

Never probe data. Never oracle source. Never other candidates. Never other
models' outputs. The runner stores the prompt SHA-256 in every receipt and
REFUSES to send a prompt assembled from any other source.

This module is the single place a prompt can be built, so "refuses" is
enforced by construction rather than by discipline. Everything that could leak
is absent from this file's inputs: it takes a packet path and a gate feedback
string, and it has no access to trusted/probes, trusted/oracles, or any
sibling candidate.

Two packet fields are deliberately NOT rendered:
  `notes`   — schema-declared non-normative, never rendered into a prompt.
              LN-5 and the layout ruling live in notes precisely because they
              are commentary for us, not specification for a generator.
  `prereg_tag` — bookkeeping.

Rendering `notes` would leak the layout ruling into matmul and median prompts
and silently promote a VECTOR-pinned bit to TEXT, which is exactly the
manipulation the choice-point map says must be deliberate. The exclusion is
asserted by a test in this file, not just documented.
"""
import hashlib, json, sys
import yaml

RENDERED_FIELDS = ["kernel", "completeness", "signature", "domain", "semantics",
                   "check_values", "forbidden", "budgets", "implementation_hint"]
EXCLUDED_FIELDS = ["notes", "prereg_tag"]


def render_packet(packet: dict) -> str:
    """Render the packet to the text a generator sees. Deterministic."""
    L = []
    L.append(f"KERNEL: {packet['kernel']}")
    L.append(f"SIGNATURE: {packet['signature']}")
    d = packet.get("domain", {})
    L.append("\nINPUT DOMAIN:")
    L.append(f"  {d.get('description','').strip()}")
    for k in ("n", "n_max", "element_range"):
        if k in d:
            L.append(f"  {k}: {d[k]}")
    if d.get("pointer_precondition"):
        L.append(f"  pointer precondition: {d['pointer_precondition'].strip()}")
    L.append("\nREQUIRED BEHAVIOUR:")
    L.append(f"  {packet['semantics'].strip()}")
    if packet.get("check_values"):
        L.append("\nPUBLISHED CHECK VALUES:")
        for c in packet["check_values"]:
            L.append(f"  input {c['input']!r} -> {c['expected']}")
    forb = packet.get("forbidden", [])
    L.append("\nFORBIDDEN CONSTRUCTS:" if forb else "\nFORBIDDEN CONSTRUCTS: none")
    for f in forb:
        L.append(f"  - {f}")
    b = packet.get("budgets", {})
    if b:
        L.append("\nRESOURCE BUDGETS:")
        for k, v in sorted(b.items()):
            L.append(f"  {k}: {v}")
    else:
        L.append("\nRESOURCE BUDGETS: none")
    if packet.get("implementation_hint"):
        L.append(f"\nIMPLEMENTATION NOTE: {packet['implementation_hint'].strip()}")
    L.append("\nEmit a single C translation unit implementing the signature above. "
             "Emit only code.")
    return "\n".join(L)


def build(packet_path: str, gate_feedback: str | None = None) -> dict:
    """Assemble a prompt. Returns text plus the SHA-256 that lands in the receipt."""
    packet = yaml.safe_load(open(packet_path))
    text = render_packet(packet)
    if gate_feedback is not None:
        text += ("\n\nThe previous attempt failed a gate. Feedback follows. "
                 "Emit a corrected single C translation unit, only code.\n\n"
                 + gate_feedback.strip())
    return {
        "prompt": text,
        "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "packet": packet_path,
        "is_repair": gate_feedback is not None,
    }


def _selftest():
    """Assert the exclusions hold. Run as `python3 prompt.py --selftest`."""
    import glob, os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bad = 0
    for f in sorted(glob.glob(os.path.join(root, "ecs", "*.ecs.yaml"))):
        pkt = yaml.safe_load(open(f))
        out = build(f)["prompt"]
        name = os.path.basename(f)
        for field in EXCLUDED_FIELDS:
            val = str(pkt.get(field, "")).strip()
            if val and val[:60] in out:
                print(f"  LEAK {name}: {field} reached the prompt")
                bad += 1
        # the layout ruling lives in notes; assert it never surfaces
        for term in ("row-major", "column-major", "VECTOR-pinned", "#14126"):
            if term.lower() in out.lower():
                print(f"  LEAK {name}: {term!r} reached the prompt")
                bad += 1
        print(f"  {name}: prompt {len(out)} chars, sha {build(f)['prompt_sha256'][:12]}…, "
              f"no excluded field present")
    print(f"\n  {'SELFTEST PASS' if not bad else f'SELFTEST FAIL ({bad} leaks)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(json.dumps(build(sys.argv[1]), indent=1)[:1500])
