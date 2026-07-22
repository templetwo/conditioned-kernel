"""Schema and admissibility guards for the continuity task corpus.

Does not touch the frozen measurement layer. Runner/scoring live elsewhere.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "experiments" / "probes" / "continuity_tasks.json"

CATEGORIES = frozenset(
    {
        "goal_recovery",
        "constraint_persistence",
        "thread_resume",
        "failure_avoidance",
    }
)

PROGRESS_KINDS = frozenset({"state_field", "thread_id", "named_artifact"})


@pytest.fixture(scope="module")
def tasks() -> list[dict]:
    assert CORPUS.is_file(), f"missing corpus: {CORPUS}"
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def test_corpus_size_in_target_band(tasks: list[dict]):
    assert 12 <= len(tasks) <= 20, f"expected 12-20 tasks, got {len(tasks)}"


def test_unique_ids(tasks: list[dict]):
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids)), f"duplicate ids: { [i for i,c in Counter(ids).items() if c>1] }"


def test_categories_valid_and_balanced(tasks: list[dict]):
    cats = [t["category"] for t in tasks]
    for c in cats:
        assert c in CATEGORIES, f"unknown category: {c}"
    counts = Counter(cats)
    # Spread across all four; none empty; max-min <= 2 for mild balance
    assert set(counts) == CATEGORIES
    assert max(counts.values()) - min(counts.values()) <= 2


def test_each_task_schema(tasks: list[dict]):
    for t in tasks:
        tid = t.get("id")
        assert isinstance(tid, str) and tid.startswith("cont_"), tid
        assert t["category"] in CATEGORIES

        ea = t["episode_a"]
        assert "prompt" in ea and ea["prompt"].strip()
        ss = ea["seed_state"]
        assert ss.get("goal")
        assert isinstance(ss.get("threads"), list) and ss["threads"]
        assert isinstance(ss.get("facts"), list) and ss["facts"]
        for th in ss["threads"]:
            assert th.get("id") and th.get("title")

        esw = ea["expected_state_writes"]
        assert isinstance(esw.get("thread_touch"), list)
        assert isinstance(esw.get("proposed_note_contains"), list)

        eb = t["episode_b"]
        assert eb.get("prompt")
        ak = eb["answer_key"]
        assert isinstance(ak.get("must_mention_any"), list) and ak["must_mention_any"]
        assert isinstance(ak.get("must_not_mention_any"), list)
        assert int(ak.get("min_words") or 0) >= 1

        gc = eb["grounded_claims"]
        assert gc.get("numeric_claims_must_appear_in_packet") is True
        fi = gc.get("forbidden_inventions")
        assert isinstance(fi, list) and len(fi) >= 1, f"{tid} missing forbidden_inventions"

        cna = eb["correct_next_action"]
        assert isinstance(cna.get("derivable_from"), list) and cna["derivable_from"]
        assert isinstance(cna.get("accept_any_of"), list) and cna["accept_any_of"]

        pt = eb["progress_trace"]
        assert pt.get("kind") in PROGRESS_KINDS, f"{tid} bad progress kind"
        assert pt.get("check")

        assert t.get("notes"), f"{tid} missing admissibility notes"


def test_every_task_declares_forbidden_inventions(tasks: list[dict]):
    for t in tasks:
        fi = t["episode_b"]["grounded_claims"]["forbidden_inventions"]
        assert all(isinstance(x, str) and x.strip() for x in fi), t["id"]


def test_edge_budget_seed_state_is_compact(tasks: list[dict]):
    """Rough packet-mass guard: seed JSON should stay well under 6KB alone."""
    for t in tasks:
        blob = json.dumps(t["episode_a"]["seed_state"], separators=(",", ":"))
        assert len(blob.encode("utf-8")) <= 3500, (
            f"{t['id']} seed_state {len(blob)} bytes — too heavy for edge packet room"
        )


def test_episode_b_prompts_are_not_general_knowledge_trivia(tasks: list[dict]):
    """Weak guard: Episode B should reference task-specific codes/ids when possible."""
    # At least half of tasks should put an opaque token from seed into episode_b prompt
    # or answer_key (session codes). Soft check: every task answer_key has a group.
    for t in tasks:
        groups = t["episode_b"]["answer_key"]["must_mention_any"]
        assert groups and all(isinstance(g, list) and g for g in groups), t["id"]


def test_failure_avoidance_includes_2gb_fabrication_task(tasks: list[dict]):
    """Worked example from the work order must appear in the corpus."""
    texts = json.dumps(tasks)
    assert "2GB" in texts or "2gb" in texts.lower()
    assert "DEADEND-2GB-CLAIM" in texts or "NO-FABRICATE" in texts
