#!/usr/bin/env python3
"""Validate ECS packets against the schema, and against the choice-point map.

Schema validation alone is not enough. The packet is the experiment's
INDEPENDENT VARIABLE, so the dangerous error is not a malformed packet — it is
a well-formed packet that quietly pins a bit the choice-point map records as
pinned by a different channel. That would change what completeness means for
that kernel without changing anything a schema could see.

So this runs two checks:
  1. JSON Schema validation.
  2. A CHANNEL WARNING: if a packet's prose mentions a term associated with a
     bit the map records as VECTOR-pinned, it is surfaced for a human to
     confirm. Advisory, never automatic — promoting a bit is a legitimate
     manipulation when deliberate, and the point is that it must be deliberate.

Usage: packet_validate.py <packet.yaml> [...]
"""
import json, os, re, sys
import yaml, jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA = os.path.join(ROOT, "ecs", "schema", "ecs.schema.json")

# Terms that would indicate a VECTOR-pinned bit has been described in prose.
# Keyed by kernel, from evidence/choice_point_map.md §2.
VECTOR_PINNED_TERMS = {
    "matmul8_i32": ["row-major", "row major", "column-major", "column major",
                    "a[i*8", "c[i*8", "transpose"],
    "median3x3_u8": ["row-major", "row major", "column-major", "column major",
                     "in[r*16", "out[(r-1)"],
}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    schema = json.load(open(SCHEMA))
    bad = 0
    for path in argv:
        pkt = yaml.safe_load(open(path))
        name = os.path.basename(path)
        try:
            jsonschema.validate(pkt, schema)
        except jsonschema.ValidationError as e:
            print(f"  {name}: SCHEMA FAIL — {e.message}")
            bad += 1
            continue

        kernel = pkt.get("kernel", "")
        # SCAN ONLY PROMPT-RENDERED FIELDS. `notes` is defined by the schema as
        # non-normative and never rendered into a prompt, so a term appearing
        # there cannot reach a generator and cannot promote a channel. An
        # earlier version scanned notes too and fired on the matmul and median
        # packets — whose notes exist precisely to DOCUMENT that layout was not
        # promoted. A warning that fires on the documentation of a
        # non-promotion is the cry-wolf failure this project has already been
        # bitten by once, in prearm_check.
        prose = " ".join(str(pkt.get(k, "")) for k in
                         ("semantics", "implementation_hint")).lower()
        hits = [t for t in VECTOR_PINNED_TERMS.get(kernel, []) if t.lower() in prose]
        flag = ""
        if hits:
            flag = (f"\n      CHANNEL WARNING: prose mentions {hits}. The map records "
                    f"{kernel}'s layout as VECTOR-pinned — enforced at gate 5 and "
                    f"invisible to the generator. Describing it here PROMOTES it to "
                    f"TEXT and changes this cell's completeness. Confirm that is "
                    f"intended.")
        hint = " [carries implementation_hint]" if pkt.get("implementation_hint") else ""
        print(f"  {name}: OK  kernel={kernel} completeness={pkt['completeness']}{hint}{flag}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
