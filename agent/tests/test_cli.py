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


def test_unimplemented_command_exits_with_code_2(capsys):
    assert main(["install"]) == 2
    assert "not implemented yet" in capsys.readouterr().err
