# Changelog

All notable changes to KinLAN are recorded here, one section per release tag.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Repository skeleton: agent and server packages, Git hooks, CI workflow, pull request template.
- Agent command-line stub (`pair`, `run`, `install`, `uninstall`, `status`).
- Server health check (`GET /healthz`) and OpenAPI docs page.
- Agent network info: local IP, subnet, gateway, DNS servers and adapter, without admin rights.
- Agent device discovery: ARP with Scapy/Npcap or Windows SendARP, manufacturer names, router hostnames.
- Agent ping test with loss and jitter, gateway/internet monitor with outage detection, and the six-step layered diagnose.
- Agent SQLite buffer for uploads and open outages.
- Agent health score (0-100, grade A-F) with plain-language reasons.
- `kinlan-agent run --local`: everything above in the terminal, with no cloud connection.
