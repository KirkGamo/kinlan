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
- Design: research, screen briefs, the Status Lights direction, the yellow/orange/black theme with motion, an interactive prototype of every screen, the brand system (mark, icon, wordmark, voice), type roles and spacing scale, and the account sheet with Circle switching.
- Server data model: 20 PostgreSQL tables and the first Alembic migration.
- Server accounts: register, login, rotating refresh tokens with reuse detection, logout, `GET/DELETE /me`, one error format, rate-limited sign-in.
- Server Circles, members and single-use invite codes, with isolation between Circles.
- Server sites, the site summary with the shared health grade, and 6-digit pairing codes.
- Agent API: pairing, resend-safe gzip ingest that doubles as the heartbeat, commands with a long-poll and results.
- Agent cloud mode: `pair` (with consent first), `run`, `status`, DPAPI token storage, `config.toml`, and an uploader with backoff that resends the same batch after a failure.
- Alert engine (new device, risky port, unreachable, back online, high latency, packet loss) with 30-minute duplicate suppression; alert list, acknowledge and per-site alert settings.
- Scheduled jobs: heartbeats, hourly rollups and retention.
- Deployment: Render blueprint and Neon support (pooled and direct connections); the API is live at https://kinlan-api.onrender.com.

### Fixed
- ARP sweeps no longer ask the network and broadcast addresses (found with Wireshark).
- Every database connection uses UTC, so timestamps are always ISO 8601 UTC.
- `/docs` listed `GET` and `DELETE /me` twice.
