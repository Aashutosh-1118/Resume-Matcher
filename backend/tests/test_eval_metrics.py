import pytest

from eval.metrics import mean, spearman, stdev


def test_mean_and_stdev():
    assert mean([2, 4, 6]) == 4
    assert stdev([5]) == 0.0
    assert stdev([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.0)


def test_spearman_perfect_and_reversed():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_handles_ties_and_edge_cases():
    assert spearman([1, 1, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9487, abs=1e-3)
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([5, 5, 5], [1, 2, 3]) is None
