"""Command-line entry point for the KinLAN Agent.

Subcommands (see docs/KinLAN_Technical_Plan.md, Section 3):
    pair       Pair this PC with a KinLAN site using a 6-digit code.
    run        Start monitoring and uploading (``--local`` prints results without the cloud).
    install    Register the agent to start at boot (Windows Task Scheduler).
    uninstall  Remove the startup task.
    status     Show pairing state, last upload and buffer size.
"""

from __future__ import annotations

import argparse
import sys

from kinlan_agent import __version__

# Sprint in which each subcommand gets implemented, shown until it exists.
_PLANNED_IN = {
    "pair": "Sprint 2",
    "run": "Sprint 1",
    "install": "Sprint 4",
    "uninstall": "Sprint 4",
    "status": "Sprint 2",
}


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="kinlan-agent",
        description="KinLAN Agent: watches your network and reports to your Circle.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("pair", help="pair this PC with a KinLAN site")
    run = sub.add_parser("run", help="start monitoring")
    run.add_argument(
        "--local",
        action="store_true",
        help="print results in the terminal without connecting to the cloud",
    )
    sub.add_parser("install", help="start the agent automatically at boot")
    sub.add_parser("uninstall", help="remove the startup task")
    sub.add_parser("status", help="show pairing and upload status")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the chosen subcommand. Returns an exit code."""
    args = build_parser().parse_args(argv)
    print(
        f"kinlan-agent {args.command}: not implemented yet "
        f"(planned for {_PLANNED_IN[args.command]}).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
