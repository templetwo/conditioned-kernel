"""LENS 3, Q3: evidence citation behavior.

Ground truth, no packet reconstruction needed for the MISS/TOO_SHORT counts:
validate.py's `_evidence_ok` (called once per pass inside `validate_candidate`)
appends ONE violations entry per bad citation —
`evidence_too_short:<item[:40]>` or `evidence_not_in_packet:<item[:80]>` —
so receipts.jsonl already contains the real pipeline's own per-citation
verdict for every one of the 93 logged passes, not just the 22 dashboard
ones. A citation counts as MATCHED if it is not named in either violation
list for its pass (candidates.jsonl logs the exact evidence_used list per
pass, so the totals are exact, not estimated).

The richer "which pool entry, near-miss vs unrelated vs truncation" detail
(compute.citation_audit's `_explain_miss`) needs the real packet body,
which is only present for the 19 dashboard TurnTraces (22 passes) — used
here as-is, not re-derived, for that qualitative layer.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from common import load_candidates, load_dashboard_turns, load_receipts


def full_93_census():
    cands = load_candidates()
    rcpts = load_receipts()
    total_evidence_items = 0
    total_too_short = 0
    total_miss = 0
    passes_with_evidence = 0
    miss_examples = []
    too_short_examples = []
    for c, r in zip(cands, rcpts):
        ev = list(c.get("evidence_used") or [])
        if not ev:
            continue
        passes_with_evidence += 1
        total_evidence_items += len(ev)
        violations = [str(v) for v in (r.get("violations") or [])]
        for v in violations:
            if v.startswith("evidence_too_short:"):
                total_too_short += 1
                too_short_examples.append(v.split(":", 1)[1])
            elif v.startswith("evidence_not_in_packet:"):
                total_miss += 1
                miss_examples.append(v.split(":", 1)[1])
    matched = total_evidence_items - total_too_short - total_miss
    return {
        "passes_with_nonempty_evidence_used": passes_with_evidence,
        "total_evidence_citations": total_evidence_items,
        "matched_implied": matched,
        "too_short": total_too_short,
        "miss": total_miss,
        "miss_examples_full": miss_examples,
        "too_short_examples_full": too_short_examples,
    }


def dashboard_ground_truth():
    dash = load_dashboard_turns()
    status_counts = Counter()
    by_status_examples = defaultdict(list)
    miss_kind_counts = Counter()
    rows = []
    for d in dash:
        for p in d["passes"]:
            for row in p["citation_audit"]:
                status_counts[row["status"]] += 1
                rows.append({
                    "turn_file": d["_file"],
                    "pass_index": p["pass_index"],
                    "citation": row["citation"],
                    "status": row["status"],
                    "reason": row.get("reason"),
                    "match_source_key": (row.get("match") or {}).get("source_key") if row.get("match") else None,
                    "kind": row.get("kind"),
                })
                if row["status"] == "MISS":
                    miss_kind_counts[row.get("kind", "unknown")] += 1
                by_status_examples[row["status"]].append(row["citation"][:100])
    return status_counts, miss_kind_counts, rows


PHANTOM_PATTERNS = [
    ("looks_like_json_or_thread_key_name", re.compile(r"^[a-z0-9_]+(_[a-z0-9]+)+$", re.I)),
    ("looks_like_numeric_spec_claim", re.compile(r"\b\d+\s?(kb|mb|gb|bit)\b", re.I)),
]


def classify_phantom(text: str) -> str:
    t = text.strip()
    for label, pat in PHANTOM_PATTERNS:
        if pat.search(t):
            return label
    if len(t) < 12:
        return "under_12_char_floor"
    return "prose_fragment_not_in_pool"


def main():
    full = full_93_census()
    status_counts, miss_kind_counts, dash_rows = dashboard_ground_truth()

    miss_phantom_class = Counter(classify_phantom(m) for m in full["miss_examples_full"])
    too_short_class = Counter(classify_phantom(m) for m in full["too_short_examples_full"])

    report = {
        "full_93_pass_exact_census": full,
        "dashboard_22_pass_ground_truth_citation_audit": {
            "status_counts": dict(status_counts),
            "miss_kind_breakdown": dict(miss_kind_counts),
            "rows": dash_rows,
        },
        "phantom_citation_clustering_full_93": {
            "note": "classified from the exact violation-string text logged by the real "
                     "pipeline (evidence_not_in_packet:<item[:80]> / evidence_too_short:<item[:40]>), "
                     "not from a reconstructed pool.",
            "miss_examples_classified": dict(miss_phantom_class),
            "too_short_examples_classified": dict(too_short_class),
        },
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
