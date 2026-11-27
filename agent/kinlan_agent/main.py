"""Command-line entry point for the KinLAN Agent.

Subcommands (see docs/KinLAN_Technical_Plan.md, Section 3):
    pair       Pair this PC with a KinLAN site using a 6-digit code.
    run        Start monitoring and uploading (``--local`` prints results without the cloud).
    install    Register the agent to start at boot (Windows Task Scheduler).
    uninstall  Remove the startup task.
    status     Show pairing state, the startup task, last upload and buffer size.

Run with no subcommand (double-clicking KinLAN-Agent.exe does this) for guided setup: pair if
needed, then install the startup task.
"""

from __future__ import annotations

import argparse
import sys

from kinlan_agent import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="kinlan-agent",
        description="KinLAN Agent: watches your network and reports to your Circle.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

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
    if args.command is None:
        return _setup()
    if args.command == "install":
        from kinlan_agent import homenet, installer

        homenet.confirm()  # a PC paired before 1.0.1: is this the site's network?
        return installer.install()
    if args.command == "uninstall":
        from kinlan_agent import installer

        return installer.uninstall()
    if args.command == "run" and args.local:
        from kinlan_agent.local import run_local  # imported here: it loads Rich and Scapy

        run_local(ticks=args.ticks, interval_s=args.interval)
        return 0
    if args.command == "pair":
        from kinlan_agent import config, installer, pairing

        code = pairing.pair(args.api_url or config.load().api_url, args.code)
        if code == 0:
            installer.restart()  # a running agent reads its sites only when it starts
        return code
    if args.command == "status":
        from kinlan_agent import pairing

        return pairing.status()
    return _run_cloud()


def _setup(ask=input) -> int:
    """Guided setup for a double-clicked KinLAN-Agent.exe: pair, then start at boot. The window
    stays open at the end, so its messages can be read."""
    from kinlan_agent import config, homenet, installer, pairing

    print("KinLAN Agent setup", end="\n\n")
    code = 0
    if not config.load().paired:
        code = pairing.pair(config.load().api_url, None)
    elif homenet.confirm(ask):  # pairing records it; a PC paired before 1.0.1 is asked once
        code = _offer_another_site(ask)
    if code == 0 and installer.task_state() is None:
        code = installer.install()
    elif code == 0:
        print("This PC is paired and the agent starts at boot. Status:", end="\n\n")
        pairing.status()
    if installer.frozen():
        print()
        ask("Press Enter to close this window.")
    return code


def _offer_another_site(ask=input) -> int:
    """On a network none of this PC's sites use (a laptop in a lab), offer to pair it too."""
    from kinlan_agent import config, homenet, installer, pairing

    settings = config.load()
    network = homenet.current()
    sites = config.site_configs(settings)
    if not network.gateway_mac or any(
        homenet.where(site, network) is homenet.Where.HOME for site in sites
    ):
        return 0
    names = ", ".join(site.site_name or "a site" for site in sites)
    print(f"This PC is on {network.describe()}, which isn't the network of {names}.")
    print("To monitor this network too, add a site for it in the app and pair it here.")
    if ask('Pair it now? Type "yes" or "no": ').strip().lower() != "yes":
        print()
        return 0
    code = pairing.pair(settings.api_url, None)
    if code == 0:
        installer.restart()
    print()
    return code


def _run_cloud() -> int:
    from kinlan_agent import config, tokenstore
    from kinlan_agent.logs import setup_logging

    problem = config.read_error()
    if problem:
        print(problem, "Fix the file (or delete it and pair again).", sep="\n", file=sys.stderr)
        return 1
    settings = config.load()
    sites = []
    for site in config.site_configs(settings):
        token = tokenstore.load_token(config.token_file(site))
        if token is None:
            print(f"{site.site_name}: its token is missing or unreadable; pair again on its "
                  "network.", file=sys.stderr)
        else:
            sites.append((site, token))
    if not sites:
        print("This PC isn't paired yet. Run: kinlan-agent pair", file=sys.stderr)
        return 1
    from kinlan_agent import installer

    try:
        guard = installer.single_instance()
    except installer.AlreadyRunning:
        print("The KinLAN Agent is already running on this PC (the startup task, or another "
              "window). Check it with: kinlan-agent status", file=sys.stderr)
        return 1
    setup_logging(settings.log_level)
    from kinlan_agent.buffer import Buffer
    from kinlan_agent.runner import run_sites  # imported here: it loads Scapy

    run_sites([(site, token, Buffer(config.buffer_file(site))) for site, token in sites])
    del guard
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
