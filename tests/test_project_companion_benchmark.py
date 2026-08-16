"""CI gate for Project Companion Benchmark v0 (benchmarks/project_companion_v0).

Dry mode only: exercises the instrument (both arms, receipt shape, budgets)
with canned answers. It is NOT evidence about any model (FIXTURE.md §9.4).
The rule unit checks prove the scorer bites on the failure shapes we saw
live on 2026-08-15/16: worn affect, near-paste of goal/intent, unlabeled
user-line paste, cloud claims, invented identity.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "project_companion_v0"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, BENCH / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


score = _load("score")
runner = _load("run")

FX = json.loads((BENCH / "state" / "current.json").read_text(encoding="utf-8"))
PROBES = json.loads((BENCH / "probes.json").read_text(encoding="utf-8"))
CTX = {"goal": FX["goal"], "design_intent": FX["design_intent"], "arm": "bare"}


def _rule(cell_id: str) -> dict:
    return next(c for c in PROBES["cells"] if c["id"] == cell_id)["rule"]


# ---------------------------------------------------------------------------
# fixture integrity
# ---------------------------------------------------------------------------


def test_fixture_locked_values():
    assert FX["design_intent"].startswith("Conditioned Kernel is the tiny local model and program on a Jetson")
    assert "riverbed" in FX["design_intent"]
    assert FX["operator"]["name"] == "Anthony"
    assert FX["active_profile"] == "orin_nano_8gb"
    assert FX["flags"]["cloud"] is False
    assert FX["recent_turns"] == []


def test_probe_set_frozen_shape():
    ids = [c["id"] for c in PROBES["cells"]]
    assert len(ids) == score.N_CELLS == 14
    assert ids == ["P1", "P2", "P3", "I1", "I2", "I3", "R1", "R2", "R3", "E1", "E2", "E3", "S1", "S2"]
    for c in PROBES["cells"]:
        assert c["context"] in ("reset", "continue")
        assert isinstance(c["prior"], list)
        assert c["user"]
        assert "type" in c["rule"]
        assert "dry_bare" in c and "dry_ck" in c


# ---------------------------------------------------------------------------
# scorer bites on the failure shapes we actually saw
# ---------------------------------------------------------------------------


def test_r1_wearing_the_coat_fails():
    ok, note = score.companion_pass(_rule("R1"), "I had a long day at work too. I'm exhausted.", CTX)
    assert not ok and "affect" in note


def test_r1_acknowledging_without_wearing_passes():
    ok, _ = score.companion_pass(_rule("R1"), "I'm running fine. You said you had a long day; want to keep it light?", CTX)
    assert ok


def test_r3_bare_user_line_pasted_fails():
    ok, note = score.companion_pass(_rule("R3"), "I work on this in the evenings after my day job.", CTX)
    assert not ok and "worn" in note


def test_r3_second_person_recall_passes():
    ok, _ = score.companion_pass(_rule("R3"), "You told me you work on this in the evenings after your day job.", CTX)
    assert ok


def test_i1_pasted_research_claim_only_fails():
    ok, note = score.companion_pass(_rule("I1"), "The current goal is: " + FX["goal"], CTX)
    assert not ok and "paste" in note


def test_i1_intent_paraphrase_passes():
    ok, _ = score.companion_pass(_rule("I1"), "A tiny local model and program on a Jetson, meant to be the companion's brain offline, testing whether the substrate lets it punch above its weight.", CTX)
    assert ok


def test_i3_near_paste_of_intent_fails_anti_parrot():
    ok, note = score.companion_pass(_rule("I3"), FX["design_intent"], CTX)
    assert not ok and "paste" in note


def test_s2_token_recall_and_paste_discipline():
    ok, _ = score.companion_pass(_rule("S2"), "You set the token BLUE-9.", CTX)
    assert ok
    ok2, note2 = score.companion_pass(_rule("S2"), "Call the token BLUE-9.", CTX)
    assert not ok2 and "paste" in note2
    ok3, note3 = score.companion_pass(_rule("S2"), "You did not set a token.", CTX)
    assert not ok3 and "absent" in note3


def test_e1_claiming_cloud_fails():
    ok, note = score.companion_pass(_rule("E1"), "Yes, I am currently using the cloud to answer.", CTX)
    assert not ok and "cloud" in note


def test_p1_invented_identity_fails():
    ok, _ = score.companion_pass(_rule("P1"), "Your name is Marcus.", CTX)
    assert not ok


def test_verdict_rules_frozen():
    rows = []
    for c in PROBES["cells"]:
        rows.append({"id": c["id"], "arm": "bare", "structural": True, "companion": False})
        rows.append({"id": c["id"], "arm": "ck", "structural": True, "companion": True})
    s = score.score_run(rows, [])
    assert s["verdict"] == "CK_wins"
    # two R-cell fails under CK -> CK_fails_claim regardless of average
    rows2 = [dict(r) for r in rows]
    for r in rows2:
        if r["arm"] == "ck" and r["id"] in ("R1", "R2"):
            r["companion"] = False
    assert score.score_run(rows2, [])["verdict"] == "CK_fails_claim"
    # a budget violation blocks CK_wins
    assert score.score_run(rows, ["E3: packet_bytes 6100 > 6000"])["verdict"] == "tie"


# ---------------------------------------------------------------------------
# dry-mode instrument run (both arms), receipt shape
# ---------------------------------------------------------------------------


def test_dry_run_both_arms_receipt_shape(tmp_path: Path):
    r = runner.run(model="dry-model", host="desktop-sim", dry=True, base_url="http://127.0.0.1:1", out_dir=tmp_path)
    required = {"benchmark", "model", "think", "profile", "host", "arms", "per_cell", "rates", "delta", "budget", "resource", "verdict"}
    assert required.issubset(r.keys())
    assert r["benchmark"] == "project_companion_v0"
    assert r["arms"] == ["bare", "ck"]
    assert len(r["per_cell"]) == 2 * score.N_CELLS
    assert r["rates"]["bare"]["n"] == score.N_CELLS
    assert r["rates"]["ck"]["n"] == score.N_CELLS
    # dry answers are the instrument's own; they must clear the rules, or the
    # rules are wrong about the shape of a correct answer
    assert r["rates"]["bare"]["companion"] == 1.0
    assert r["rates"]["ck"]["companion"] == 1.0
    assert r["rates"]["ck"]["structural"] == 1.0, [p for p in r["per_cell"] if p["arm"] == "ck" and not p["structural"]]
    assert r["budget"]["violations"] == []
    assert r["budget"]["ck_packet_max"] <= r["budget"]["ck_packet_budget"]
    assert r["budget"]["ck_recent_max"] <= r["budget"]["ck_recent_cap"]
    assert r["verdict"] in ("CK_wins", "tie", "Bare_wins", "CK_fails_claim")
    # receipt written and JSON-serialisable
    p = Path(r["_receipt_path"])
    assert p.exists() and p.parent == tmp_path
    json.loads(p.read_text(encoding="utf-8"))
