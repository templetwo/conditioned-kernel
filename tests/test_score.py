from conditioned_kernel.score import score_free_text, substrate_gain, aggregate_condition


def test_score_free_text_goal():
    goal = "Demonstrate conditioned-kernel substrate gain under Jetson edge budgets."
    s = score_free_text(
        "We will demonstrate substrate conditioned-kernel gain on Jetson edge.",
        goal=goal,
        facts=["This system is fully local."],
    )
    assert s["has_content"] is True
    assert s["goal_referenced"] is True
    assert 0 <= s["structural_score"] <= 1


def test_substrate_gain_positive():
    ck = {"structural_score": 0.8, "semantic_score": 0.7, "parse_ok": 0.9, "accept": 0.8, "goal_referenced": 0.9}
    bare = {"structural_score": 0.2, "semantic_score": 0.3, "parse_ok": 0.1, "accept": 0.0, "goal_referenced": 0.4}
    g = substrate_gain(ck, bare)
    assert g["delta_structural"] > 0
    assert g["composite"] > 0


def test_aggregate():
    rows = [
        {"scores": {"structural_score": 1.0, "accept": True}},
        {"scores": {"structural_score": 0.0, "accept": False}},
    ]
    a = aggregate_condition(rows)
    assert a["n"] == 2
    assert a["structural_score"] == 0.5
    assert a["accept"] == 0.5
