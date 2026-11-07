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
    "install": "Sprint 4",
    "uninstall": "Sprint 4",
}


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="kinlan-agent",
        description="KinLAN Agent: watches your network and reports to your Circle.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    pair = sub.add_parser("pair", help="pair this PC with a KinLAN site")
    pair.add_argument("--code", help="the 6-digit code from the app (asked if omitted)")
    pair.add_argument("--api-url", help="server address (default: the KinLAN cloud)")
    run = sub.add_parser("run", help="start monitoring")
    run.add_argument(
        "--local",
        action="store_true",
        help="print results in the terminal without connecting to the cloud",
    )
    run.add_argument(
        "--ticks",
        type=int,
        default=None,
        help="with --local: stop after this many monitor ticks (default: until Ctrl+C)",
    )
    run.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="with --local: seconds between monitor ticks (default: 10)",
    )
    sub.add_parser("install", help="start the agent automatically at boot")
    sub.add_parser("uninstall", help="remove the startup task")
    sub.add_parser("status", help="show pairing and upload status")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the chosen subcommand. Returns an exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "run" and args.local:
        from kinlan_agent.local import run_local  # imported here: it loads Rich and Scapy

        run_local(ticks=args.ticks, interval_s=args.interval)
        return 0
    if args.command == "pair":
        from kinlan_agent import config, pairing

        return pairing.pair(args.api_url or config.load().api_url, args.code)
    if args.command == "status":
        from kinlan_agent import pairing

        return pairing.status()
    if args.command == "run":
        return _run_cloud()
    print(
        f"kinlan-agent {args.command}: not implemented yet "
        f"(planned for {_PLANNED_IN[args.command]}).",
        file=sys.stderr,
    )
    return 2


def _run_cloud() -> int:
    from kinlan_agent import config, tokenstore
    from kinlan_agent.logs import setup_logging

    problem = config.read_error()
    if problem:
        print(problem, "Fix the file (or delete it and pair again).", sep="\n", file=sys.stderr)
        return 1
    settings = config.load()
    token = tokenstore.load_token()
    if not settings.paired or token is None:
        print("This PC isn't paired yet. Run: kinlan-agent pair", file=sys.stderr)
        return 1
    setup_logging(settings.log_level)
    from kinlan_agent.runner import run  # imported here: it loads Scapy

    run(settings, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
