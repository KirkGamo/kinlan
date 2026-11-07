"""The network health score (0-100) and grade (A-F).

Starts at 100 and subtracts points for each problem (docs/KinLAN_Technical_Plan.md,
Section 4.6). The server uses the same formula, so the agent's own view and the app
always agree. Every deduction carries a plain-language reason for the app's
"Why this grade?" panel and the PDF report's security recommendations.

| Factor (last 24 h)                         | Deduction                                  |
|--------------------------------------------|--------------------------------------------|
| Internet average latency                   | over 100 ms: 10; over 200 ms: 20           |
| Packet loss                                | 5 per 1 % (proportional), at most 30       |
| Outages                                    | 5 each, at most 15                         |
| Untrusted devices first seen after baseline| 5 each, at most 15                         |
| Risky open ports                           | 10 each, at most 20                        |
"""

from __future__ import annotations

from dataclasses import dataclass, field

GRADES = ((90, "A"), (80, "B"), (70, "C"), (60, "D"))


@dataclass(frozen=True)
class HealthInputs:
    """What the score is computed from. ``None`` means "not measured yet" (no deduction)."""

    internet_avg_ms: float | None = None
    loss_pct: float | None = None
    outages: int = 0
    new_untrusted_devices: int = 0
    risky_ports: int = 0


@dataclass(frozen=True)
class Deduction:
    factor: str  # latency, loss, outages, devices, ports
    points: int
    reason: str  # plain language, shown first
    detail: str  # the numbers behind it

    def to_dict(self) -> dict[str, object]:
        return {"factor": self.factor, "points": self.points, "reason": self.reason,
                "detail": self.detail}


@dataclass(frozen=True)
class HealthScore:
    score: int
    grade: str
    deductions: list[Deduction] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.deductions:
            return "No problems found."
        worst = max(self.deductions, key=lambda d: d.points)
        return worst.reason

    def to_dict(self) -> dict[str, object]:
        return {"score": self.score, "grade": self.grade, "summary": self.summary,
                "deductions": [d.to_dict() for d in self.deductions]}


def grade_for(score: int) -> str:
    for minimum, grade in GRADES:
        if score >= minimum:
            return grade
    return "F"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def compute(inputs: HealthInputs) -> HealthScore:
    """Score the network; deductions are listed largest first."""
    deductions: list[Deduction] = []

    ms = inputs.internet_avg_ms
    if ms is not None and ms > 100:
        points = 20 if ms > 200 else 10
        deductions.append(Deduction(
            "latency", points, "The internet connection is slow to respond.",
            f"Average internet latency {ms:.0f} ms (over {200 if ms > 200 else 100} ms)."))

    loss = inputs.loss_pct
    if loss is not None and loss > 0:
        points = min(30, round(loss * 5))
        if points:
            deductions.append(Deduction(
                "loss", points, "Some data is getting lost on the way to the internet.",
                f"Packet loss {loss:.1f}% (5 points per 1%, at most 30)."))

    if inputs.outages:
        deductions.append(Deduction(
            "outages", min(15, 5 * inputs.outages),
            f"The internet went down {_plural(inputs.outages, 'time')} in the last 24 hours.",
            f"{_plural(inputs.outages, 'outage')} (5 points each, at most 15)."))

    if inputs.new_untrusted_devices:
        n = inputs.new_untrusted_devices
        deductions.append(Deduction(
            "devices", min(15, 5 * n),
            f"{_plural(n, 'new device')} joined that nobody has marked as trusted.",
            f"{_plural(n, 'untrusted device')} first seen after the baseline scan "
            "(5 points each, at most 15)."))

    if inputs.risky_ports:
        n = inputs.risky_ports
        deductions.append(Deduction(
            "ports", min(20, 10 * n),
            f"{_plural(n, 'device')} on the network "
            f"{'has' if n == 1 else 'have'} a risky service open.",
            f"{_plural(n, 'risky open port')} such as Telnet, FTP, SMB, RDP or VNC "
            "(10 points each, at most 20)."))

    deductions.sort(key=lambda d: d.points, reverse=True)
    score = max(0, 100 - sum(d.points for d in deductions))
    return HealthScore(score=score, grade=grade_for(score), deductions=deductions)
