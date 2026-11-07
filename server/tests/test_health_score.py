"""The server's health formula must stay identical to the agent's (Section 4.6)."""

from pathlib import Path

import pytest

from app.health import HealthInputs, compute

AGENT_COPY = Path(__file__).resolve().parents[2] / "agent" / "kinlan_agent" / "health.py"
SERVER_COPY = Path(__file__).resolve().parents[1] / "app" / "health.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.mark.skipif(not AGENT_COPY.exists(), reason="agent source not checked out")
def test_server_and_agent_use_the_same_formula():
    assert _text(SERVER_COPY) == _text(AGENT_COPY), (
        "server/app/health.py and agent/kinlan_agent/health.py differ; copy one over the other."
    )


def test_a_clean_network_scores_a():
    result = compute(HealthInputs(internet_avg_ms=25, loss_pct=0))
    assert (result.score, result.grade, result.deductions) == (100, "A", [])


def test_penalties_stack_and_cap():
    result = compute(
        HealthInputs(internet_avg_ms=250, loss_pct=10, outages=5, new_untrusted_devices=1)
    )
    points = {d.factor: d.points for d in result.deductions}
    assert points == {"latency": 20, "loss": 30, "outages": 15, "devices": 5}
    assert (result.score, result.grade) == (30, "F")
