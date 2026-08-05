#!/usr/bin/env python3
"""Vector withholding policy for the dose-response arm (SPEC §11 arm 3).

PREREG §6 arm 3 weakens the constraint surface three ways: the forbidden list
is dropped, budgets are dropped, and HALF THE VECTORS ARE WITHHELD.

Agent B's note at board #14096 is the reason this file exists: withholding
must be RUNNER-ENFORCED from `completeness`, never a free-form field a packet
author can set. If an author chose which vectors to withhold, the strength of
the manipulation would vary with who wrote the packet, and arm 3 would be
measuring authorship as much as constraint completeness.

THE RULE, fixed here and not parameterised:

  completeness == "full"  ->  every vector is used.
  completeness == "weak"  ->  vectors at ODD INDEX in committed file order
                              are withheld; even indices are used.

Deterministic, reproducible from the committed vector file alone, and
identical for every generator and every sample in the cell. No seed, because
a seed is one more thing that could differ between runs or seats.

Even-index selection rather than a random half is deliberate: vector files are
authored edges-first, then length series, then seeded-random, so a contiguous
"first half" would withhold nearly all the random coverage and keep nearly all
the edges — a systematically different weakening than intended. Alternating
preserves the mix of vector kinds on both sides of the split.

The withheld set is RECORDED in the receipt, so the weakening is auditable
after the fact even though it was never author-chosen.
"""
import json, sys


def select(vectors, completeness):
    """Return (used, withheld) per the fixed policy."""
    if completeness == "full":
        return list(vectors), []
    if completeness == "weak":
        used = [v for i, v in enumerate(vectors) if i % 2 == 0]
        withheld = [v for i, v in enumerate(vectors) if i % 2 == 1]
        return used, withheld
    raise ValueError(f"unknown completeness {completeness!r}; expected 'full' or 'weak'")


def receipt_fields(vectors, completeness):
    used, withheld = select(vectors, completeness)
    return {
        "vector_policy": "even-index-kept" if completeness == "weak" else "all",
        "completeness": completeness,
        "vectors_total": len(vectors),
        "vectors_used": len(used),
        "vectors_withheld": len(withheld),
        "withheld_ids": [v.get("id") for v in withheld],
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    spec = json.load(open(sys.argv[1]))
    print(json.dumps(receipt_fields(spec["vectors"], sys.argv[2]), indent=1))
