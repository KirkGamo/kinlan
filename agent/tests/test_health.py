"""Tests for the health score: every factor, its cap, and the grade boundaries."""

import pytest

from kinlan_agent.health import HealthInputs, compute, grade_for


def test_healthy_network_scores_100_a():
    result = compute(HealthInputs(internet_avg_ms=25, loss_pct=0))
    assert (result.score, result.grade, result.deductions) == (100, "A", [])
    assert result.summary == "No problems found."


def test_nothing_measured_yet_means_no_deductions():
    assert compute(HealthInputs()).score == 100


@pytest.mark.parametrize(("ms", "points"), [(100, 0), (101, 10), (200, 10), (201, 20), (900, 20)])
def test_latency_deduction(ms, points):
    assert 100 - compute(HealthInputs(internet_avg_ms=ms)).score == points


@pytest.mark.parametrize(
    ("loss", "points"), [(0, 0), (0.05, 0), (0.4, 2), (1, 5), (3, 15), (6, 30), (50, 30)]
)
def test_loss_deduction_is_proportional_and_capped(loss, points):
    assert 100 - compute(HealthInputs(loss_pct=loss)).score == points


@pytest.mark.parametrize(
    ("field", "value", "points"),
    [
        ("outages", 1, 5), ("outages", 3, 15), ("outages", 9, 15),
        ("new_untrusted_devices", 2, 10), ("new_untrusted_devices", 5, 15),
        ("risky_ports", 1, 10), ("risky_ports", 4, 20),
    ],
)
def test_count_deductions_are_capped(field, value, points):
    assert 100 - compute(HealthInputs(**{field: value})).score == points


@pytest.mark.parametrize(
    ("score", "grade"),
    [(100, "A"), (90, "A"), (89, "B"), (80, "B"), (79, "C"), (70, "C"), (69, "D"), (60, "D"),
     (59, "F"), (0, "F")],
)
def test_grade_boundaries(score, grade):
    assert grade_for(score) == grade


def test_worst_network_cannot_go_below_zero_and_lists_largest_deduction_first():
    result = compute(HealthInputs(internet_avg_ms=300, loss_pct=20, outages=5,
                                  new_untrusted_devices=5, risky_ports=5))
    assert result.score == 0 and result.grade == "F"
    assert [d.points for d in result.deductions] == [30, 20, 20, 15, 15]
    assert result.summary == result.deductions[0].reason


def test_reasons_are_plain_and_details_carry_numbers():
    result = compute(HealthInputs(outages=1, risky_ports=1))
    reasons = {d.factor: d for d in result.deductions}
    assert reasons["outages"].reason == "The internet went down 1 time in the last 24 hours."
    assert reasons["ports"].reason == "1 device on the network has a risky service open."
    assert "Telnet" in reasons["ports"].detail
    assert result.score == 85 and result.grade == "B"


def test_to_dict():
    data = compute(HealthInputs(loss_pct=1)).to_dict()
    assert data["score"] == 95 and data["grade"] == "A"
    assert data["deductions"][0]["factor"] == "loss"
