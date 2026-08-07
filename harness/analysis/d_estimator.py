#!/usr/bin/env python3
"""D — the primary endpoint, PREREG §3 item 1, computed exactly as frozen:

    For every probe input, cluster accepted artifacts by output;
    D = mean over probes of (1 - largest cluster fraction).

PURE. No device, no I/O beyond the CLI convenience at the bottom. Inputs are
per-artifact probe outcome maps as they appear in receipts
(`probe_output_hashes`: [{probe_id, output_class}]). Output classes are
opaque strings — a value digest (`sha256:<hex>`) and a trap (`CRASH:sig11`)
cluster by identical rules, because CRASH is a labeled output class, not a
missing value (census discipline; two artifacts that both trap agree about
something real).

THREE STATES (SPEC §7a.2b). The return always carries `state`:
  ok               D computed; per-probe largest-cluster fractions included
  cannot_evaluate  with `cause` — no accepted artifacts, mismatched probe
                   coverage between artifacts, or a malformed outcome. Never
                   encoded as D = 0.0: zero disagreement is a RESULT, and the
                   absence of anything to disagree about is not.

LN-1 is carried in the record, not hidden: `k` and `quantum` (1/k) ride along
so a reader can see that D's per-probe resolution is set by the accepted-
artifact count, not by the probe count, and `k = 1` is flagged degenerate —
the frozen definition yields D = 0 there, and the flag says how weak that is.
"""
import json, sys
from fractions import Fraction


def _as_outcome_map(artifact):
    """Normalise one artifact's probe outcomes to {probe_id: output_class}.

    Accepts either the receipt list shape or an already-built dict. Returns
    (map, problem) — problem is a cause string, never an exception, so the
    caller can fold it into cannot_evaluate with context."""
    if isinstance(artifact, dict):
        items = artifact.items()
    elif isinstance(artifact, list):
        try:
            items = [(e["probe_id"], e["output_class"]) for e in artifact]
        except (TypeError, KeyError):
            return None, "entry missing probe_id/output_class"
    else:
        return None, f"unsupported outcome shape {type(artifact).__name__}"
    out = {}
    for pid, cls in items:
        if not pid or not isinstance(cls, str) or not cls:
            return None, f"malformed outcome for probe {pid!r}"
        if pid in out:
            return None, f"duplicate outcome for probe {pid!r}"
        out[pid] = cls
    return out, None


def compute_d(artifacts):
    """D over accepted artifacts' probe outcomes, per PREREG §3.

    `artifacts`: list, one entry per ACCEPTED artifact, each the receipt's
    `probe_output_hashes` list or an equivalent {probe_id: class} dict.
    """
    if not artifacts:
        return {"state": "cannot_evaluate",
                "cause": "no accepted artifacts; D is defined over accepted "
                         "artifacts and there are none to cluster"}
    maps = []
    for i, a in enumerate(artifacts):
        m, problem = _as_outcome_map(a)
        if problem:
            return {"state": "cannot_evaluate",
                    "cause": f"artifact {i}: {problem}"}
        maps.append(m)

    probe_ids = set(maps[0])
    for i, m in enumerate(maps[1:], start=1):
        if set(m) != probe_ids:
            # Every consumer would otherwise average over a silently smaller
            # intersection — a different estimand than the frozen one.
            missing = probe_ids ^ set(m)
            return {"state": "cannot_evaluate",
                    "cause": f"probe coverage mismatch: artifact {i} differs "
                             f"from artifact 0 on {len(missing)} probe id(s) "
                             f"(e.g. {sorted(missing)[:3]})"}
    if not probe_ids:
        return {"state": "cannot_evaluate",
                "cause": "artifacts carry zero probe outcomes"}

    # EXACT ARITHMETIC. Cluster counts are integers, so D is a rational
    # number; computing it in floats can carry a representation error across
    # the frozen `<= 1%` comparison in either direction (measured: 99 of 100
    # agreeing gives float D = 0.010000000000000009 > 0.01, turning a passing
    # calibration into a spurious hard halt). D_exact is authoritative;
    # the float is for reading.
    k = len(maps)
    per_probe = {}
    total = Fraction(0)
    for pid in sorted(probe_ids):
        counts = {}
        for m in maps:
            counts[m[pid]] = counts.get(m[pid], 0) + 1
        largest = Fraction(max(counts.values()), k)
        per_probe[pid] = float(largest)
        total += 1 - largest

    d = total / len(probe_ids)
    rec = {"state": "ok", "D": float(d),
           "D_exact": [d.numerator, d.denominator],
           "k": k, "probe_count": len(probe_ids),
           "quantum": 1.0 / k,
           "per_probe_largest_fraction": per_probe,
           "note": "per-probe disagreement is quantized to 1/k (LN-1); "
                   "resolution is set by accepted-artifact count, not by "
                   "probe count"}
    if k == 1:
        rec["degenerate_k"] = True
        rec["note"] = ("k = 1: the frozen definition yields D = 0 trivially — "
                       "one artifact cannot disagree with itself. Reported "
                       "because PREREG §3 defines it, flagged because it "
                       "measures nothing (LN-1)")
    return rec


def outcomes_from_cell_receipt(cell):
    """Extract accepted artifacts' probe outcomes from a cell receipt dict.

    Returns (artifacts, problems): artifacts feed compute_d; problems lists
    accepted candidates whose receipts LACK a probe record — under the
    fail-closed runner that cannot happen, so a non-empty list marks a receipt
    from a different (pre-probe) instrument and the caller must not compute D
    over the remainder as if nothing were missing."""
    artifacts, problems = [], []
    for c in cell.get("candidates", []):
        if not c.get("accepted"):
            continue
        po = c.get("probe_output_hashes")
        if po is None:
            problems.append(f"accepted candidate sample_index="
                            f"{c.get('sample_index')} has no probe_output_hashes")
        else:
            artifacts.append(po)
    return artifacts, problems


def compute_d_for_cells(cells):
    """D pooled over the accepted artifacts of one or more cell receipts —
    the shape both the calibration gate (one kernel, four generators) and the
    per-kernel-per-arm endpoint need."""
    artifacts, problems = [], []
    for cell in cells:
        a, p = outcomes_from_cell_receipt(cell)
        artifacts.extend(a)
        problems.extend(p)
    if problems:
        return {"state": "cannot_evaluate",
                "cause": "; ".join(problems[:5]) +
                         (f" (+{len(problems) - 5} more)" if len(problems) > 5
                          else "")}
    return compute_d(artifacts)


if __name__ == "__main__":
    cells = [json.load(open(p)) for p in sys.argv[1:]]
    out = compute_d_for_cells(cells)
    out.pop("per_probe_largest_fraction", None)   # too wide for a terminal
    print(json.dumps(out, indent=1))
