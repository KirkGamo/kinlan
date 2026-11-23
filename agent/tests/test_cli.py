"""Tests for the agent's command-line interface."""

import pytest

from kinlan_agent import __version__
from kinlan_agent.main import build_parser, main


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.parametrize("command", ["pair", "run", "install", "uninstall", "status"])
def test_every_subcommand_is_registered(command):
    args = build_parser().parse_args([command])
    assert args.command == command


def test_run_accepts_local_flag():
    args = build_parser().parse_args(["run", "--local"])
    assert args.local is True


def test_install_and_uninstall_reach_the_installer(monkeypatch):
    """The real commands are covered in test_installer.py with a fake Task Scheduler."""
    from kinlan_agent import installer

    calls = []
    monkeypatch.setattr(installer, "install", lambda: calls.append("install") or 0)
    monkeypatch.setattr(installer, "uninstall", lambda: calls.append("uninstall") or 0)
    assert main(["install"]) == 0 and main(["uninstall"]) == 0
    assert calls == ["install", "uninstall"]
