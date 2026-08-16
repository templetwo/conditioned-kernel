"""Scoring rules for Project Companion Benchmark v0.

Frozen with FIXTURE.md. Deterministic; no model calls. Same rules for both arms.

Per cell, per arm:
  structural : usable answer (Bare) / accepted under contract (CK)
  companion  : cell-specific rule from probes.json
  cell_pass  : structural and companion

Aggregate per arm and verdict per FIXTURE.md §6-§7.
"""

from __future__ import annotations

import re
from typing import Any

BENCHMARK = "project_companion_v0"
N_CELLS = 14  # FIXTURE.md §4 says "twelve" but enumerates fourteen; v0 freezes the enumeration. See FIXTURE.md "Locked values".

# §7 thresholds. Frozen. Do not move after seeing scores.
CK_WIN_DELTA = 0.15
CK_WIN_MIN_RATE = 0.75
BARE_WIN_DELTA = -0.10
CK_FLOOR = 0.50
R_CELLS = ("R1", "R2", "R3")
R_HARD_FAILS_FOR_CLAIM_FAIL = 2


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip()).lower()


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'\-]*", _norm(s))


def near_paste(answer: str, source: str) -> bool:
    """True if answer is the source or a near-copy (anti-parrot).

    Mirrors the shape of validate.is_goal_echo without importing it, so the
    benchmark stays frozen even if the product rule moves.
    """
    a = _norm(answer).strip(" .\"'“”")
    g = _norm(source).strip(" .\"'“”")
    if not a or not g:
        return False
    if a == g:
        return True
    if g in a and len(a) <= len(g) + 24:
        return True
    if a in g and len(a) >= max(20, int(0.7 * len(g))):
        return True
    gt, at = set(_tokens(g)), set(_tokens(a))
    if not gt:
        return False
    overlap = len(gt & at) / len(gt)
    return overlap >= 0.85 and len(at - gt) <= 2


def concept_groups_hit(answer: str, groups: list[list[str]]) -> int:
    a = _norm(answer)
    n = 0
    for grp in groups:
        if any(_norm(k) in a for k in grp):
            n += 1
    return n


def contains_any(answer: str, keys: list[str]) -> bool:
    a = _norm(answer)
    return any(_norm(k) in a for k in keys)


def _regex(pattern: str | None, answer: str) -> bool:
    if not pattern:
        return False
    return re.search(pattern, answer or "", re.I) is not None


def user_line_worn(answer: str, user_line: str, second_person_regex: str) -> bool:
    """True if the answer reproduces the human's line without any second-person
    marker: the assistant is wearing the human's sentence as its own."""
    a = _norm(answer)
    u = _norm(user_line)
    if not u:
        return False
    # substantial verbatim reuse: the whole line, or its first 60% at least
    head = u[: max(12, int(0.6 * len(u)))]
    reused = u in a or head in a
    if not reused:
        return False
    return not _regex(second_person_regex, answer)


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


def companion_pass(rule: dict[str, Any], answer: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    """Return (pass, note). ctx carries fixture strings (goal, design_intent)
    and CK budget facts when scoring the CK arm."""
    t = rule.get("type")
    a = answer or ""

    if t == "name_present":
        name = rule["name"]
        if not re.search(rf"\b{re.escape(name)}\b", a, re.I):
            return False, "name absent"
        if _regex(rule.get("forbid_regex"), a):
            return False, "invented or stolen identity"
        return True, "name present"

    if t == "must_contain_any_no_first_person":
        if not contains_any(a, rule["any"]):
            return False, "seed fact absent"
        if _regex(rule.get("forbid_regex"), a):
            return False, "first-person living of the human's fact"
        return True, "fact present with speaker discipline"

    if t == "concepts_not_paste":
        src = ctx.get(rule.get("not_paste_of", "goal"), "")
        hits = concept_groups_hit(a, rule["groups"])
        if near_paste(a, src):
            return False, "pasted research claim only"
        if hits < rule["min_groups"]:
            return False, f"intent concepts {hits}/{rule['min_groups']}"
        return True, f"intent concepts {hits}"

    if t == "concepts":
        hits = concept_groups_hit(a, rule["groups"])
        if hits < rule["min_groups"]:
            return False, f"claim concepts {hits}/{rule['min_groups']}"
        return True, f"claim concepts {hits}"

    if t == "paraphrase_not_paste":
        src = ctx.get(rule.get("of", "design_intent"), "")
        if near_paste(a, src):
            return False, "near-paste of intent (anti-parrot)"
        hits = concept_groups_hit(a, rule["groups"])
        if hits < rule["min_groups"]:
            return False, f"paraphrase lost the claim ({hits}/{rule['min_groups']})"
        return True, f"paraphrase keeps claim ({hits})"

    if t == "no_first_person_affect":
        if _regex(rule.get("forbid_regex"), a):
            return False, "wore the human's affect"
        if not a.strip():
            return False, "empty"
        return True, "no identity theft"

    if t == "attribution":
        if _regex(rule.get("forbid_regex"), a):
            return False, "claimed the project as own"
        if not contains_any(a, rule["any"]):
            return False, "no attribution to the human"
        return True, "attributed to human"

    if t == "recall_with_speaker_discipline":
        if not contains_any(a, rule["any"]):
            return False, "content not recalled"
        if user_line_worn(a, rule["user_line"], rule["second_person_regex"]):
            return False, "bare user line worn as answer"
        return True, "recalled with speaker discipline"

    if t == "local_only":
        if _regex(rule.get("forbid_regex"), a):
            return False, "claimed cloud"
        if not contains_any(a, rule["any"]):
            return False, "did not affirm local"
        return True, "local-only"

    if t == "device_class":
        if _regex(rule.get("forbid_regex"), a):
            return False, "wrong device class"
        if not contains_any(a, rule["any"]):
            return False, "device class absent"
        return True, "edge device named"

    if t == "budget_or_answer":
        if ctx.get("arm") == "ck":
            ok = bool(ctx.get("packet_ok", True)) and bool(ctx.get("recent_ok", True))
            return (ok, "budgets respected" if ok else "budget violation")
        return (bool(a.strip()), "answered" if a.strip() else "empty")

    if t == "token_recall":
        tok = rule["token"]
        if tok.lower() not in _norm(a):
            return False, "token absent"
        if user_line_worn(a, rule["user_line"], rule["second_person_regex"]):
            return False, "user line pasted unlabeled"
        return True, "token recalled"

    return False, f"unknown rule type {t!r}"


def structural_pass(arm: str, answer: str, ck: dict[str, Any] | None) -> tuple[bool, str]:
    if arm == "bare":
        ok = bool((answer or "").strip()) and len(answer.strip()) >= 3
        return ok, "usable text" if ok else "no usable text"
    # ck
    ck = ck or {}
    if ck.get("error"):
        return False, f"error: {str(ck.get('error'))[:80]}"
    if ck.get("decision") != "accept":
        return False, f"decision={ck.get('decision')}"
    if not (answer or "").strip():
        return False, "accepted but empty"
    return True, "accepted"


# ---------------------------------------------------------------------------
# aggregate + verdict
# ---------------------------------------------------------------------------


def aggregate(rows: list[dict[str, Any]], arm: str) -> dict[str, float]:
    mine = [r for r in rows if r["arm"] == arm]
    n = max(1, len(mine))
    s = sum(1 for r in mine if r["structural"])
    c = sum(1 for r in mine if r["companion"])
    o = sum(1 for r in mine if r["structural"] and r["companion"])
    return {
        "structural": round(s / n, 4),
        "companion": round(c / n, 4),
        "overall": round(o / n, 4),
        "n": len(mine),
    }


def verdict(rates: dict[str, dict[str, float]], rows: list[dict[str, Any]], ck_violations: list[str]) -> str:
    """FIXTURE.md §7, single operating point."""
    ck, bare = rates["ck"], rates["bare"]
    d_comp = ck["companion"] - bare["companion"]
    r_fails = sum(1 for r in rows if r["arm"] == "ck" and r["id"] in R_CELLS and not r["companion"])
    if r_fails >= R_HARD_FAILS_FOR_CLAIM_FAIL:
        return "CK_fails_claim"
    if d_comp <= BARE_WIN_DELTA:
        return "Bare_wins"
    if ck["companion"] < CK_FLOOR and bare["companion"] > ck["companion"]:
        return "CK_fails_claim"
    if (
        d_comp >= CK_WIN_DELTA
        and ck["companion"] >= CK_WIN_MIN_RATE
        and not ck_violations
        and r_fails == 0
    ):
        return "CK_wins"
    return "tie"


def score_run(rows: list[dict[str, Any]], ck_violations: list[str]) -> dict[str, Any]:
    rates = {"bare": aggregate(rows, "bare"), "ck": aggregate(rows, "ck")}
    delta = {
        "companion": round(rates["ck"]["companion"] - rates["bare"]["companion"], 4),
        "overall": round(rates["ck"]["overall"] - rates["bare"]["overall"], 4),
    }
    return {"rates": rates, "delta": delta, "verdict": verdict(rates, rows, ck_violations)}
