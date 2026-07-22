"""A timeout is not a score of zero — it is the absence of a measurement.

The invariant: the Qwen3.5 result was not incorrectly scored, it was
incorrectly *admitted* as a measurement. These tests pin the distinction at
both layers — the inference boundary, and paired aggregation.
"""

from conditioned_kernel.generate import InferenceResult, RunStatus
from conditioned_kernel.score import paired_gain, row_is_valid_measurement, row_status


def _result(status, output, error=None):
    return InferenceResult(
        status=status, output=output, error=error, elapsed_seconds=1.0, timeout_seconds=90.0
    )


def _row(probe, status, struct=0.0, sem=0.0, output=None):
    return {
        "probe_id": probe,
        "inference": _result(status, output).to_dict(),
        "scores": {"structural_score": struct, "semantic_score": sem},
    }


def _valid_pair(probe, delta):
    """CK scores `delta` above control on both components."""
    return (
        _row(probe, RunStatus.COMPLETED, 0.5 + delta, 0.5 + delta, output="a"),
        _row(probe, RunStatus.COMPLETED, 0.5, 0.5, output="b"),
    )


def test_timeout_has_no_output_and_is_not_a_measurement():
    r = _result(RunStatus.TIMEOUT, None, "timed out")
    d = r.to_dict()
    assert d["status"] == "timeout"
    assert d["output"] is None, "must be null, not empty string"
    assert d["valid_measurement"] is False
    assert r.observed is False


def test_observed_empty_output_is_not_a_timeout():
    """A model that answered with nothing legitimately scores zero."""
    r = _result(RunStatus.COMPLETED, "")
    d = r.to_dict()
    assert d["status"] == "completed"
    assert d["output"] == ""
    assert d["valid_measurement"] is True
    assert row_is_valid_measurement({"inference": d}) is True
    assert row_status({"inference": d}) == "completed"


def test_timeout_cannot_be_aggregated_as_zero():
    ck = [_row(f"p{i}", RunStatus.TIMEOUT) for i in range(4)]
    ctl = [_row(f"p{i}", RunStatus.TIMEOUT) for i in range(4)]
    g = paired_gain(ck, ctl)
    assert g["status"] == "incomplete"
    assert g["headline"] is None
    assert g["valid_pairs"] == 0
    assert g["expected_pairs"] == 4
    assert g["invalid_pairs"] == 4


def test_one_invalid_pair_invalidates_the_primary_headline():
    ck, ctl = [], []
    for probe, delta in (("p1", 0.25), ("p2", 0.0), ("p3", -0.25)):
        a, b = _valid_pair(probe, delta)
        ck.append(a)
        ctl.append(b)
    ck.append(_row("p4", RunStatus.TIMEOUT))
    ctl.append(_row("p4", RunStatus.TIMEOUT))

    g = paired_gain(ck, ctl)
    assert g["status"] == "incomplete"
    assert g["headline"] is None, "partial coverage must not produce a headline"
    assert g["valid_pairs"] == 3
    assert g["expected_pairs"] == 4
    assert g["coverage"] == 0.75
    # A descriptive value may exist, but only under a separate name.
    assert g["partial_observed_headline"] is not None


def test_complete_coverage_produces_a_headline():
    ck, ctl = [], []
    for probe, delta in (("p1", 0.25), ("p2", 0.25)):
        a, b = _valid_pair(probe, delta)
        ck.append(a)
        ctl.append(b)
    g = paired_gain(ck, ctl)
    assert g["status"] == "complete"
    assert g["coverage"] == 1.0
    assert g["headline"] == 0.25


def test_one_sided_timeout_also_invalidates():
    """Control observed, CK not — still no pair."""
    a, b = _valid_pair("p1", 0.25)
    g = paired_gain([_row("p1", RunStatus.TIMEOUT)], [b])
    assert g["status"] == "incomplete"
    assert g["headline"] is None
    assert "ck:timeout" in g["invalid_reasons"]


# --- missingness is not just a percentage -----------------------------------
# Coverage alone cannot separate random dropout from systematic one-sided
# failure. CK carries larger packets, so under a fixed wall clock it plausibly
# times out MORE than the control -- which biases surviving pairs in a
# direction that cannot be signed in advance.

from conditioned_kernel.score import (  # noqa: E402
    budget_conditional_gain,
    dropout_symmetry,
    missingness_bounds,
)


def test_missingness_bounds_widen_with_missing_data():
    # 4 expected, 3 observed at 0.0 -> the 4th is confined to [-1, 1]
    lo, hi = missingness_bounds([0.0, 0.0, 0.0], 4)
    assert lo == -0.25 and hi == 0.25
    # complete coverage collapses the interval onto the point estimate
    lo, hi = missingness_bounds([0.0, 0.0, 0.0, 0.0], 4)
    assert lo == hi == 0.0
    # nothing observed => the full range, i.e. we know nothing
    lo, hi = missingness_bounds([], 4)
    assert lo == -1.0 and hi == 1.0


def test_missingness_bounds_shrink_as_n_grows():
    """One dropout at n=4 is crippling; at n=30 it is bounded and visible."""
    _, hi_small = missingness_bounds([0.0] * 3, 4)
    _, hi_large = missingness_bounds([0.0] * 29, 30)
    assert hi_small > hi_large


def test_dropout_symmetry_flags_one_sided_failure():
    one_sided = dropout_symmetry({"ck:timeout": 5})
    assert one_sided["one_sided"] is True
    assert one_sided["symmetric"] is False
    assert one_sided["imbalance"] == 5

    balanced = dropout_symmetry({"ck:timeout": 3, "control:timeout": 3})
    assert balanced["symmetric"] is True
    assert balanced["one_sided"] is False
    assert balanced["imbalance"] == 0


def test_two_sided_failure_is_not_reported_as_one_sided():
    """Regression: paired_gain short-circuited on ck and hid control failures."""
    ck = [_row("p1", RunStatus.TIMEOUT)]
    ctl = [_row("p1", RunStatus.TIMEOUT)]
    sym = paired_gain(ck, ctl)["dropout_symmetry"]
    assert sym["ck_dropouts"] == 1
    assert sym["control_dropouts"] == 1, "both sides must be counted"
    assert sym["symmetric"] is True


def test_budget_conditional_scores_timeout_as_failure_not_missing():
    """Under the edge budget, exceeding it is a definitive result."""
    ck = [_row("p1", RunStatus.TIMEOUT), _row("p2", RunStatus.COMPLETED, 1.0, 1.0, output="x")]
    ctl = [_row("p1", RunStatus.COMPLETED, 0.5, 0.5, output="y"),
           _row("p2", RunStatus.COMPLETED, 0.5, 0.5, output="y")]
    g = budget_conditional_gain(ck, ctl)
    assert g["status"] == "complete", "complete by construction, no missingness"
    assert g["n_probes"] == 2
    assert g["ck_budget_failures"] == 1
    # p1: 0.0 - 0.5 = -0.5 ; p2: 1.0 - 0.5 = +0.5 -> mean 0.0
    assert g["headline"] == 0.0


def test_the_two_estimands_disagree_and_that_is_the_point():
    """Quality-conditional says 'no data'; budget-conditional says 'does not fit'."""
    ck = [_row(f"p{i}", RunStatus.TIMEOUT) for i in range(4)]
    ctl = [_row(f"p{i}", RunStatus.COMPLETED, 0.5, 0.5, output="y") for i in range(4)]
    assert paired_gain(ck, ctl)["headline"] is None
    bg = budget_conditional_gain(ck, ctl)
    assert bg["headline"] == -0.5
    assert bg["ck_budget_failures"] == 4
