# KinLAN — Technical Development Plan

**Project:** KinLAN: A Multi-User Network Monitoring and Performance Analysis Platform with Mobile Access
**Course:** CCS 234 – Communications and Networking (Final Project, individual)
**Plan date:** Nov 6, 2026 · **Final submission:** Fri Dec 4, 2026 · **Defense:** Dec 8–10, 2026

---

## 0. Name, positioning and scope

**Name:** **KinLAN** (written with a capital *LAN*; lower-case `kinlan` in code, packages and URLs). It comes from *"kin on the LAN"*.

**Tagline:** *Your people, your network.*

**Positioning:** a **Circle** is any group of people who share a network and look out for it together, not just families:
- a household
- roommates in a dorm
- coworkers in a small office
- staff of a school laboratory

The broad meaning has to show everywhere:
- **App wording:** "Create a Circle", "Invite to your Circle", "Circle members". Never "family" in UI copy, slides or the report; examples always mix home and work groups.
- **Demo data:** at least one household Circle and one office or lab Circle.
- **Defense line:** *"KinLAN means kin on the LAN: anyone who shares a network and watches over it together."*

### Definition of done

KinLAN is finished when all of these are true:

1. **A cloud API is live** at a public HTTPS address, backed by a managed PostgreSQL database.
2. **A Windows agent** can be downloaded as a single `.exe`, installed on any PC in a network, paired to an account with a 6-digit code, and keeps running after a reboot.
3. **An Android app (APK)** is installable on any phone. A **web version** of the same app is published as a static site.
4. **At least 2 real networks** are monitored by **at least 3 user accounts** with different roles (owner, admin, viewer).
5. All 5 required course features work end to end, in the app:
   1. Network Discovery
   2. Connectivity Testing
   3. Network Statistics
   4. Report Generator
   5. Security Recommendations
6. The test results in Section 9 are measured and recorded, and the deliverables in Section 12 are complete.

**Assumptions**
- Solo developer, about 4 weeks, Windows 11 laptop.
- Free tiers of Render, Neon, Expo/EAS and GitHub.
- Testing happens on networks you own or have permission to monitor, such as home or a relative's house. Don't scan the school network without IT approval.

---

## 1. System architecture

```
 LOCAL NETWORK (per site)                      CLOUD                               CLIENTS
┌──────────────────────────────┐        ┌──────────────────────────────┐     ┌─────────────────────┐
│ KinLAN Agent (Python 3.12) │        │ KinLAN API (FastAPI)       │     │ Mobile app (Expo)   │
│                              │ HTTPS  │  /api/v1/agent/*  (token)    │HTTPS│  Android APK        │
│  Discovery  (ARP + ICMP)     │───────▶│  /api/v1/*        (JWT)      │◀───▶│  Web build (static) │
│  Monitor    (ICMP every 10s) │ ingest │                              │     └─────────▲───────────┘
│  Diagnose   (layered tests)  │        │  Alert engine + scheduler    │               │
│  Port check (TCP connect)    │◀───────│  PDF report generator        │               │ push
│  SQLite buffer (offline)     │commands│  Expo push sender ───────────┼──▶ Expo Push ─┘ (FCM)
└──────────────────────────────┘ (poll) └──────────────┬───────────────┘
                                                       │ SQL (TLS)
                                               ┌───────▼────────┐
                                               │ PostgreSQL     │
                                               │ (Neon)         │
                                               └────────────────┘
```

### 1.1 Communication design decisions
| Link | Mechanism | Why |
|---|---|---|
| Agent → API (data) | HTTPS `POST /agent/ingest` every **30 s**, JSON batch, gzip | Outbound HTTPS works behind any home router (NAT) and needs no port forwarding. Batching keeps request counts low. |
| API → Agent (commands) | **Agent polls** `GET /agent/commands?wait=20` (long-poll; the server holds the request up to 20 s) | Simpler and more robust than WebSockets on free hosts that restart. Commands arrive within about 1 s. |
| App ↔ API | HTTPS REST + JSON. The app refetches live views every 5–10 s with TanStack Query. | Simple and cache-friendly. Documented automatically in OpenAPI at `/docs`. |
| API → Phone (alerts) | Expo Push API → FCM → device | Free. Alerts reach the phone even when the app is closed. |
| Agent → Network | ARP (layer 2), ICMP echo (layer 3), DNS over UDP 53 (layer 7), TCP connect (layer 4) | This is where the course's networking concepts are demonstrated. |

### 1.2 The outage path (important design point)
When a site's internet is down, its agent **cannot reach the cloud**, so it can't report the outage while it's happening. This is handled in two places:

1. **Server side:** every upload doubles as a heartbeat. If an agent is silent for **> 120 s**, the scheduler marks the site `unreachable` and sends a push: *"Home is unreachable — possible internet or power outage."*
2. **Agent side:**
   - The agent keeps measuring and writes everything to its **SQLite buffer**, including the exact start time of the outage and which layer failed.
   - When the connection returns, it uploads the backlog, oldest first.
   - The server then closes the outage with the exact duration and cause, and sends: *"Home is back online after 4 min 12 s (ISP outage)."*

---

## 2. Repository and environment setup

### 2.1 Monorepo layout
**Workspace:** `C:\Users\Acer\school\Network and Communications\kinlan\` is both the working folder for every coding session and the repository root (run `git init` there). It already contains `.claude/` (the design skills), `docs/` (this plan) and `course/` (the instructions and the proposal).

**Local-only files:** `.claude/`, `CLAUDE.md`, `.impeccable/` and `skills-lock.json` are coding-assistant files. They live in the repository folder on your laptop but are **git-ignored**, so they never appear in the commit history, on GitHub, or in the submission. `course/` is local too: the instruction PDFs, the proposal and the report drafts are submitted through Teams, not as source code.
```
kinlan/
├── .claude/skills/            # LOCAL ONLY (git-ignored): impeccable, ui-ux-pro-max, vercel-react-native-skills, web-design-guidelines
├── .github/workflows/ci.yml   # lint + tests for all three apps
├── .github/pull_request_template.md
├── .githooks/commit-msg       # commit message rules (Section 10.1)
├── .githooks/pre-commit       # blocks local-only files from being committed
├── .gitignore, .gitattributes, CHANGELOG.md
├── CLAUDE.md                  # LOCAL ONLY (git-ignored): rules for the coding agent (Appendix A)
├── course/                    # LOCAL ONLY (git-ignored): instruction PDFs, proposal, report drafts
├── PRODUCT.md                 # product truth (from /impeccable init)
├── DESIGN.md                  # design system, single source of truth (Section 8)
├── README.md                  # install, run, deploy instructions
├── agent/                     # Python agent
│   ├── kinlan_agent/ {main.py, config.py, netinfo.py, discovery.py, monitor.py, pingtest.py,
│   │                    diagnose.py, portcheck.py, health.py, buffer.py, uploader.py, commands.py}
│   ├── tests/
│   ├── requirements.txt, requirements-dev.txt   # pinned versions
│   ├── pyproject.toml           # ruff + pytest config only
│   └── build/kinlan-agent.spec   # PyInstaller
├── server/                    # FastAPI API
│   ├── app/ {main.py, config.py, db.py, security.py, deps.py,
│   │         models/, schemas/, routers/, services/ (alerts.py, push.py, reports.py, health.py), jobs.py}
│   ├── alembic/ + alembic.ini
│   ├── scripts/seed.py
│   ├── tests/
│   ├── requirements.txt, requirements-dev.txt   # pinned versions
│   └── pyproject.toml           # ruff + pytest config only
├── mobile/                    # Expo app (TypeScript)
│   ├── app/                   # Expo Router screens
│   ├── src/ {api/, components/, theme/, hooks/, lib/}
│   └── app.json, eas.json, package.json
└── docs/ {KinLAN_Technical_Plan.md, design/briefs/, diagrams/, screenshots/, test-results/}
```
For the final zip, `/SourceCode` = a clean copy of the repository. Make it with `git archive --format=zip -o SourceCode.zip v1.0.0`, which contains only committed files, so `.claude/`, `CLAUDE.md`, `.impeccable/`, `course/`, `node_modules`, `.venv` and `.env` are left out automatically.

### 2.2 One-time setup (Sprint 0)
| Step | Command / action |
|---|---|
| Install Python 3.12 | Download from python.org (keep 3.10 alongside), then use `py -3.12 -m venv .venv` in `agent/` and `server/` |
| Agent dependencies | `pip install scapy icmplib dnspython httpx psutil pywin32 pydantic-settings rich pyinstaller pytest ruff` |
| Server dependencies | `pip install "fastapi[standard]" "sqlalchemy>=2" alembic "psycopg[binary]" pyjwt "pwdlib[argon2]" pydantic-settings slowapi apscheduler reportlab matplotlib httpx pytest ruff` |
| Mobile app | `npx create-expo-app@latest mobile`, then `npx expo install expo-router react-native-paper react-native-svg expo-secure-store expo-notifications expo-device expo-dev-client expo-sharing expo-file-system` and `npm i @tanstack/react-query react-native-gifted-charts react-native-tcp-socket zod` |
| Pin versions | After installing, run `pip freeze > requirements.txt` in `agent/` and `server/`, and move pytest, ruff and pyinstaller into `requirements-dev.txt`. The mobile app is pinned by `package-lock.json`. Commit all of them. |
| Local database | Your PostgreSQL 15 is already running, on port **5433** (port 5432 is a separate EDB Postgres 17 install). Run `createdb -U postgres -h localhost -p 5433 kinlan_dev` and the same for `kinlan_test`. Done on Nov 7. |
| Accounts | GitHub (repo), Neon (database), Render (API + static web), Expo (EAS builds + push), Firebase (FCM for Android push, free) |
| Phone | Install the **development build** of the app (Section 6.6), not Expo Go. Expo Go no longer supports push notifications on Android (since SDK 53). |

---

## 3. Agent specification (Python)

### 3.1 Runtime model
- **Process:** a single `asyncio` process with independent periodic tasks.
- **Admin rights:** required for raw sockets (ARP and ICMP).
- **Installation:** `kinlan-agent.exe install` registers a Windows Task Scheduler task with `schtasks /Create /SC ONSTARTUP /RL HIGHEST /RU SYSTEM`, so the agent starts at boot without anyone logging in.
- **Files** under `%ProgramData%\KinLAN\`:
  - `config.toml`
  - `buffer.db` (SQLite)
  - `logs\agent.log` (rotating, 5 × 1 MB)
- **Secret storage:** the agent token is encrypted with Windows DPAPI in **machine scope** (`win32crypt.CryptProtectData` with `CRYPTPROTECT_LOCAL_MACHINE`, from `pywin32`) and saved as `%ProgramData%\KinLAN\agent.token`. The file's permissions allow only SYSTEM and Administrators. *Why not Credential Manager:* it stores secrets per user, so a token saved while you pair the agent couldn't be read by the agent running as SYSTEM.

### 3.2 Modules
| Module | Responsibility | Key techniques |
|---|---|---|
| `netinfo.py` | Local IP, subnet mask, CIDR range, default gateway, DNS servers, interface name/MAC | UDP-socket trick: `connect(("8.8.8.8", 80))` then `getsockname()` gives the outbound IP without sending packets. `psutil.net_if_addrs()` gives the netmask and adapter MAC, `ipaddress` the range, Windows `GetBestRoute` (iphlpapi, no admin rights needed) the gateway with Scapy's route table as fallback, and dnspython the DNS servers. Windows calls live in `winapi.py`. |
| `discovery.py` | Find active devices, with MAC, vendor and hostname | **Primary:** scapy ARP sweep `srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=cidr), timeout=2, retry=2)`. The two resends matter: in testing, a single pass missed phones in power-saving mode on 2 of 3 scans. **Fallback** (no Npcap): Windows `SendARP` for every host address, 64 in parallel (no admin rights needed). Vendor lookup from the bundled IEEE OUI list `kinlan_agent/data/oui.txt` (about 38,000 prefixes); randomized phone MACs (locally administered bit set) are labeled "Private address". Hostnames from reverse DNS **asked of the router**, which knows DHCP names; for private IPs only local-looking names are kept (no dot, or `.local`/`.lan`/`.home`), because ISP DNS servers answer with unrelated public names. Ranges larger than /22 are limited to the host's /24. **Interface:** scan only on the adapter whose IP equals the outbound IP from `netinfo`, so virtual adapters (Docker, Hyper-V, VirtualBox) are ignored. **Online rule:** a device is *online* if it answered in the latest scan, and *offline* after missing 2 scans in a row (about 10 min). |
| `monitor.py` | Continuous latency and packet-loss sampling | Windows `IcmpSendEcho` (iphlpapi: works without admin rights; icmplib on other systems), **1 echo per target every 10 s**. Targets are the gateway and `8.8.8.8`; a second public target, `9.9.9.9`, confirms an outage. **Target check at startup:** the agent pings each candidate (8.8.8.8, 9.9.9.9, 1.1.1.1, 208.67.222.222) and uses the first two that answer, **and repeats the check every hour**, because some networks block certain resolvers, sometimes only for a while: on the developer's home network, 1.1.1.1 and 1.0.0.1 were unreachable for both ICMP and TCP for over an hour on Nov 7, then answered 20 of 20 pings. Replies under 1 ms (common on a LAN) are timed with `perf_counter`, because Windows reports whole milliseconds. |
| `pingtest.py` | Ping test of one selected device (required Feature 2) | N echoes (default 10, interval 0.5 s). Returns sent/received, loss %, min/avg/max/jitter. |
| `diagnose.py` | Layered troubleshooter (on demand or automatic on outage) | Six ordered steps, each with a pass/fail result, a time in ms and an explanation (Section 3.3) |
| `portcheck.py` | Risky-port check for known devices | `asyncio.open_connection` with a 0.5 s timeout, 100 at a time. Ports: 21 FTP, 23 Telnet, 445 SMB, 3389 RDP, 5900 VNC, 80/8080 HTTP admin pages (shown as info). Runs on demand and once daily. |
| `health.py` | Local health snapshot | Same formula as the server (Section 4.6), so the agent's own window can show a grade |
| `buffer.py` | Offline queue | SQLite tables `outbox(id, kind, payload_json, created_at)` and `outages(...)`. Keeps at most 7 days or 50 MB, deleting the oldest first. |
| `uploader.py` | Batch upload with retry | Every 30 s, send up to 500 outbox rows. On failure, retry with exponential backoff (5 s → 5 min, with random jitter). Rows are deleted only after a `2xx` response. Every batch has a `batch_id`, so a resent batch is never stored twice. **Backlog mode:** after an outage, batches go out back-to-back (up to 30 per minute), oldest first, until the outbox is empty. |
| `commands.py` | Remote commands from the app | Long-poll `GET /agent/commands`. Command types: `scan`, `ping_test`, `diagnose`, `port_check`. Results go to `POST /agent/commands/{id}/result`. |
| `main.py` | CLI and scheduler | `kinlan-agent pair`, `run`, `run --local` (no cloud, prints tables), `install`, `uninstall`, `status` |

### 3.3 Diagnose algorithm (maps to OSI / TCP-IP layers)
| # | Test | Layer | Fail means |
|---|---|---|---|
| 1 | The adapter is up and has a non-APIPA IPv4 address (not 169.254.x.x) | Physical / Data link | Cable unplugged, Wi-Fi disconnected, or DHCP failed |
| 2 | ARP for the gateway resolves | Data link | Not really on the network (wrong Wi-Fi or VLAN) |
| 3 | ICMP to the gateway succeeds (3 echoes, ≤ 1 failure) | Network (LAN) | Router down or overloaded, weak Wi-Fi |
| 4 | ICMP to both internet targets, 8.8.8.8 **and** 9.9.9.9 by default (3 echoes each) | Network (WAN) | ISP outage, or the router's internet connection is down |
| 5 | DNS query for `example.com` to the system resolver, timed | Application (DNS) | DNS server problem. The internet works but names don't load. Suggest a public DNS server such as 8.8.8.8 or 9.9.9.9. |
| 6 | TCP connect to `8.8.8.8:443`, then an HTTPS `HEAD https://www.google.com/generate_204` | Transport / Application | Firewall or captive portal blocking the web |

The diagnosis stops at the **first failing step** and reports that step as the root cause. Later steps are shown as "skipped". The whole result is stored, so it appears in the history and in reports.

### 3.4 Outage detection (agent side)
- **Down:** 3 consecutive failed samples to the main internet target and the confirmation target also fails. The cause depends on the gateway:
  - gateway still OK → `cause = isp`
  - gateway failing too → `cause = lan`
- **Up:** 2 consecutive successes.
- The agent records `started_at`, `ended_at` and `cause` in `buffer.outages`, and runs `diagnose` automatically at the start of every outage.

### 3.5 Schedules
| Task | Interval |
|---|---|
| Monitor ping (gateway + internet) | 10 s |
| Upload batch / heartbeat | 30 s |
| Device discovery scan | 5 min (plus on demand) |
| Port check | daily at 03:00 (plus on demand) |
| Command long-poll | continuous |
| Buffer cleanup | hourly |

### 3.6 Pairing flow
1. In the app, the owner creates a site. The API returns a **6-digit code** valid for 10 minutes, stored hashed.
2. On the PC, the user runs `kinlan-agent pair` and enters the code. The agent sends `POST /agent/pair {code, hostname, os, agent_version, network_cidr}`.
3. The API returns `{agent_id, agent_token}`. The token is 32 random bytes, encoded in base64url. The server stores only its SHA-256 hash. The agent saves the token as described in Section 3.1.
4. **Consent screen** in the agent: *"Only monitor networks you own or are authorized to monitor."* The user must type `yes`.
5. **Baseline scan:** the first scan after pairing is the site's *baseline*. Those devices are stored with `baseline = true`, raise **no** alerts, and aren't penalized in the health grade. The app shows a one-time *"Review the 14 devices we found"* card, so users can name them and mark them trusted. "New device" alerts start only after the baseline.

### 3.7 Configuration file (`%ProgramData%\KinLAN\config.toml`)
```toml
api_url = "https://kinlan-api.onrender.com"   # set at pairing
agent_id = "…"                                 # set at pairing
monitor_interval_s = 10
upload_interval_s = 30
scan_interval_s = 300
internet_targets = ["8.8.8.8", "9.9.9.9", "1.1.1.1", "208.67.222.222"]  # first two that answer are used
port_check_time = "03:00"
max_scan_prefix = 22
log_level = "INFO"
```
Every value has a default in `config.py` (pydantic-settings), so a missing key never crashes the agent.

### 3.8 Packaging
- **Build:** `pyinstaller build/kinlan-agent.spec --onefile` produces `KinLAN-Agent.exe`, with the OUI list bundled. It's published on **GitHub Releases**.
- **Npcap:** its free license doesn't allow bundling it in your installer. The README tells users to install Npcap (or Wireshark). Without it, the agent falls back to Windows `SendARP`, so it still works (about 14 s per /24 instead of 7 s).
- **Unsigned executable:** Windows SmartScreen will warn about the `.exe`. Document "More info → Run anyway" in the README and mention it in the defense.
- **Optional:** a small Tkinter status window that shows the pairing state, last upload, grade and a "Run diagnose" button, styled with the DESIGN.md colors.

---

## 4. Server specification (FastAPI)

### 4.1 Stack
- **Web framework:** FastAPI on Uvicorn.
- **Database:** SQLAlchemy 2 (sync engine, psycopg 3 driver), with Alembic migrations.
- **Settings:** Pydantic v2 schemas, `pydantic-settings` for environment variables.
- **Security libraries:** PyJWT, pwdlib (Argon2id), slowapi (rate limiting).
- **Other:** APScheduler (in-process jobs; there is one instance on Render), ReportLab + Matplotlib (PDF), httpx (Expo Push).

### 4.2 Authentication and authorization
- **Users:** email + password, hashed with Argon2id.
- **Access token:** JWT, HS256, **15 min** lifetime, with claims `sub` (user id) and `exp`.
- **Refresh token:** opaque, random, **30 days**, stored *hashed* in `refresh_tokens`, and **replaced with a new one every time it's used**. If an old token is reused, every session of that user is revoked.
- **Agents:** `Authorization: Bearer <agent_token>`. The server looks up the SHA-256 hash, so an agent can only write to its own site.
- **Authorization:** checked in a FastAPI dependency `require_role(circle_id, min_role)`. Every query touching site data joins through `memberships`, so cross-tenant reads are impossible by construction.

**Circle rules:**
- Any signed-in user can create a Circle and becomes its owner.
- Invite codes are 8 characters (no look-alike characters such as 0/O and 1/l), single-use, and expire after 7 days. The inviter picks the role.
- A Circle always has at least one owner. The last owner can't leave or be demoted, and must transfer ownership or delete the Circle.
- `DELETE /me` is refused while you're the last owner of any Circle.

| Action | Owner | Admin | Viewer |
|---|:-:|:-:|:-:|
| View sites, devices, charts, alerts, reports | ✅ | ✅ | ✅ |
| Run scan / ping test / diagnose / port check | ✅ | ✅ | — |
| Rename devices, mark trusted, acknowledge alerts | ✅ | ✅ | — |
| Create sites, pairing codes, alert thresholds | ✅ | ✅ | — |
| Invite or remove members, change roles, delete the Circle | ✅ | — | — |

### 4.3 API endpoints (`/api/v1`)
| Group | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /me` · `DELETE /me` |
| Circles | `GET/POST /circles` · `GET /circles/{circle}/members` · `PATCH/DELETE /circles/{circle}/members/{user}` · `POST /circles/{circle}/invites` (returns an 8-character code, 7-day expiry) · `POST /invites/accept` |
| Sites | `GET/POST /circles/{circle}/sites` · `GET/PATCH/DELETE /sites/{site}` · `GET /sites/{site}/summary` (grade, status, current latency, counts) · `POST /sites/{site}/pairing-code` |
| Devices | `GET /sites/{site}/devices?status=online\|unknown` · `GET/PATCH /devices/{device}` (name, trusted) · `GET /devices/{device}/ping-tests` |
| Metrics | `GET /sites/{site}/latency?range=1h\|24h\|7d\|30d&target=gateway\|internet` (raw or hourly data, chosen automatically) · `GET /sites/{site}/outages` |
| Commands | `POST /sites/{site}/commands {type, params}` · `GET /commands/{id}` |
| Alerts | `GET /sites/{site}/alerts` · `POST /alerts/{id}/ack` · `GET/PATCH /sites/{site}/alert-settings` |
| Push | `POST /push-tokens` · `DELETE /push-tokens/{token}` |
| Reports | `POST /sites/{site}/reports {range}` → `GET /reports/{id}.pdf` |
| Agent | `POST /agent/pair` · `POST /agent/ingest` · `GET /agent/commands?wait=20` · `POST /agent/commands/{id}/result` |
| System | `GET /healthz` (for uptime checks) · `GET /docs` (OpenAPI) |

**API conventions (apply to every endpoint):**
- **Errors:** always `{"error": {"code": "site_not_found", "message": "…"}}` with the matching HTTP status: 400 validation, 401 not signed in, 403 wrong role, 404 not found (also for another Circle's data), 409 conflict, 429 rate limited.
- **Lists:** `?limit=50&cursor=<opaque>` (cursor pagination, newest first), with `next_cursor` in the response.
- **Time and units:** timestamps in ISO 8601 UTC; latency in milliseconds (float); loss in percent (0–100). The app converts times to the phone's time zone.
- **Agent checks:** samples stamped more than 5 min in the future are rejected, so a wrong PC clock is caught. Agents send `agent_version`; versions below the minimum get `426 Upgrade Required`.

**Command contracts:**

| Type | Params | Result | Timeout |
|---|---|---|---|
| `scan` | — | `{devices: [...], duration_ms}` | 60 s |
| `ping_test` | `{device_id, count: 10}` | `{sent, received, loss_pct, min_ms, avg_ms, max_ms, jitter_ms}` | 30 s |
| `diagnose` | — | `{steps: [{n, name, layer, status: pass\|fail\|skipped, ms, detail}], root_cause_step}` | 45 s |
| `port_check` | `{device_id?}` (omit for all devices) | `{findings: [{device_id, port, service}]}` | 120 s |

A command not picked up within 2 minutes becomes `expired`, and the app shows *"The agent didn't respond. Is the PC on?"*

**Ingest payload (example):**
```json
{
  "batch_id": "3f0c…", "agent_version": "1.0.0", "sent_at": "2026-11-20T10:00:30Z",
  "netinfo": {"local_ip": "192.168.1.23", "cidr": "192.168.1.0/24", "gateway": "192.168.1.1"},
  "samples": [{"ts": "2026-11-20T10:00:00Z", "target": "internet", "ip": "8.8.8.8", "rtt_ms": 18.4, "ok": true}],
  "devices": [{"mac": "a4:5e:60:…", "ip": "192.168.1.5", "hostname": "DESKTOP-ABC", "vendor": "Apple"}],
  "outages": [{"started_at": "…", "ended_at": "…", "cause": "isp"}],
  "port_findings": [{"mac": "…", "port": 23, "service": "telnet"}]
}
```

### 4.4 Alert engine
Rules are checked **during ingest** and by a **1-minute scheduled job**. Thresholds can be changed per site.

| Alert | Trigger (default) | Severity |
|---|---|---|
| New unknown device | MAC never seen before on this site, after the baseline scan | warning |
| Site unreachable | No contact from the agent for > 120 s | critical |
| Site back online | First upload after `unreachable`, or an outage closed | info |
| High latency | Internet average > 150 ms over 5 min | warning |
| Packet loss | Loss > 5 % over 5 min | warning |
| Risky port open | Port finding on a device | warning (Telnet/FTP: critical) |

- **Duplicate suppression:** an alert of the same type for the same site and subject won't fire again within 30 min while it's still open.
- **Push delivery:** each alert is pushed to every member with a registered token, based on their notification preferences. Invalid tokens reported back by Expo are deleted.

### 4.5 Scheduled jobs (APScheduler)
| Job | Interval | Work |
|---|---|---|
| `check_heartbeats` | 1 min | Mark silent agents unreachable and raise alerts |
| `rollup_hourly` | 1 h | Combine raw samples into `ping_hourly` (avg/max/min/loss/count) |
| `retention` | daily | Delete raw samples > 7 days old, hourly rows > 90 days, resolved alerts > 90 days, expired codes and tokens |
| `push_receipts` | 15 min | Fetch Expo push receipts and clean out dead tokens |

### 4.6 Health score (shared formula, documented in the report)
Start at 100 and subtract:

| Factor | Penalty |
|---|---|
| Internet average latency (24 h) | > 100 ms: −10 · > 200 ms: −20 |
| Packet loss (24 h) | −5 per 1 %, up to −30 |
| Outages (24 h) | −5 each, up to −15 |
| Untrusted devices first seen after the baseline | −5 each, up to −15 |
| Risky open ports | −10 each, up to −20 |

**Grades:** A ≥ 90 · B ≥ 80 · C ≥ 70 · D ≥ 60 · F < 60. Each penalty becomes one line in the app's "Why this grade?" panel and in the security recommendations of the PDF report.

### 4.7 PDF report (required Feature 4)
Generated by ReportLab, A4 or Letter. Contents:
1. **Header:** site name, date range, generated time.
2. **Network info:** CIDR, gateway, ISP-facing latency.
3. **Device table:** hostname, IP, MAC, vendor, trusted, last seen.
4. **Ping results table:** for each device ping-tested in the range, average/maximum latency and loss. Gateway and internet statistics are always included, even if no device was tested.
5. **Latency chart:** a Matplotlib PNG.
6. **Outage log.**
7. **Health grade** with its breakdown.
8. **Security recommendations:** the rules from Section 4.4, plus fixed advice such as changing the router admin password, using WPA3/WPA2-AES, disabling WPS and UPnP, and enabling the router firewall.

---

## 5. Database specification

### 5.1 Environments
| Environment | Database | Notes |
|---|---|---|
| Local development | `kinlan_dev` on your PostgreSQL 15 (port 5433) | Use `scripts/seed.py` for demo data |
| Automated tests | `kinlan_test` (local + CI service container) | Recreated on every test run |
| Production | Neon PostgreSQL, `main` branch | A Neon `staging` branch can be created for safe migration tests |

Use Neon's **pooled** connection string (the host containing `-pooler`) with SQLAlchemy `pool_pre_ping=True` and `pool_size=5`, so dropped idle connections are replaced automatically. The connection string is only ever read from `DATABASE_URL` (in `.env`, which is git-ignored, and in Render's environment settings).

### 5.2 Tables (UUID primary keys unless noted; all times are `timestamptz` in UTC)
| Table | Columns (main) | Indexes / constraints |
|---|---|---|
| `users` | id, email (unique, lower-case), password_hash, display_name, created_at | unique(email) |
| `refresh_tokens` | id, user_id → users, token_hash, expires_at, revoked_at, replaced_by | index(user_id) |
| `circles` | id, name, created_by → users, created_at | |
| `memberships` | circle_id, user_id, role enum(owner, admin, viewer), joined_at | PK(circle_id, user_id) |
| `invites` | id, circle_id, code_hash, role, expires_at, used_by, used_at | |
| `sites` | id, circle_id, name, timezone, status enum(online, degraded, unreachable, pending), last_seen_at, cidr, gateway_ip | index(circle_id) |
| `alert_settings` | site_id (PK), latency_ms, loss_pct, offline_seconds, notify_new_device bool | |
| `pairing_codes` | id, site_id, code_hash, expires_at, used_at | |
| `agents` | id, site_id, token_hash (unique), hostname, os, version, last_seen_at, revoked_at | |
| `devices` | id, site_id, mac, ip (inet), hostname, vendor, custom_name, trusted bool, baseline bool, first_seen_at, last_seen_at, online bool | unique(site_id, mac) |
| `ping_samples` | id bigserial, site_id, target enum(gateway, internet), ip inet, ts, rtt_ms real null, ok bool | index(site_id, target, ts desc) |
| `ping_hourly` | site_id, target, hour, avg_ms, min_ms, max_ms, loss_pct, samples | PK(site_id, target, hour) |
| `ping_tests` | id, device_id, ts, sent, received, loss_pct, min_ms, avg_ms, max_ms, jitter_ms | index(device_id, ts desc) |
| `outages` | id, site_id, started_at, ended_at null, cause enum(isp, lan, unknown), detected_by enum(agent, server) | index(site_id, started_at desc) |
| `port_findings` | id, device_id, port, service, first_seen_at, last_seen_at, resolved_at | unique(device_id, port) |
| `commands` | id, site_id, type, params jsonb, status enum(pending, running, done, failed, expired), requested_by, result jsonb, created_at, finished_at | index(site_id, status) |
| `alerts` | id, site_id, type, severity, title, body, subject_ref, created_at, acked_by, acked_at, resolved_at | index(site_id, created_at desc) |
| `push_tokens` | token (PK), user_id, platform, created_at, last_used_at | |
| `ingest_batches` | batch_id (PK), agent_id, received_at | Stops a resent batch from being stored twice. Kept 2 days. |
| `reports` | id, site_id, requested_by, range_start, range_end, created_at, pdf (bytea) | Deleted after 30 days by `retention` |

### 5.3 How the database is managed
- **Changes go through migrations only.**
  - Generate a migration with `alembic revision --autogenerate -m "..."`, review it by hand, and commit it.
  - Render runs `alembic upgrade head` before every deploy starts.
  - Never change the production schema by hand.
- **Size estimate:**
  - One sample every 10 s × 2 targets = 17,280 rows per site per day.
  - 3 sites × 7 days of raw data is about 363k rows, roughly 40–60 MB with indexes.
  - Hourly rollups add very little. This fits Neon's free storage (0.5 GB).
- **Backups:**
  - Neon can restore to an earlier point in time.
  - Run `pg_dump` manually before the progress report, before submission, and before the defense. Store the dumps in `docs/backups/`, which is git-ignored.
- **Data separation tests:** a pytest suite creates two Circles and checks that every read endpoint returns 403/404 across them.
- **Inspection:** use pgAdmin 4 (installed with PostgreSQL) or `psql`. Save screenshots of the database diagram and of sample rows for Chapter 3.
- **Database diagram:** draw it in draw.io from the table above, or generate it from the models with `eralchemy`.

---

## 6. Mobile app specification (Expo / React Native)

### 6.1 Stack
- **Framework:** Expo (latest SDK) with **TypeScript** and **Expo Router** (file-based navigation).
- **UI:** **React Native Paper** (Material Design 3) with `@expo/vector-icons` (MaterialCommunityIcons).
- **Data:** **TanStack Query** for API calls, caching and polling.
- **Types and validation:** API types generated with `openapi-typescript` from the server's `/openapi.json`; `zod` for forms.
- **Charts:** `react-native-gifted-charts` (built on react-native-svg, also works on web).
- **API address:** read from `EXPO_PUBLIC_API_URL` (`.env` locally, set per build profile in `eas.json`), so the same code points at the local server or production.
- **Device features:** `expo-secure-store` for tokens on the phone, `expo-notifications` + `expo-device` for push, `expo-sharing` + `expo-file-system` for PDFs.

### 6.2 Navigation and screens
```
(auth)        Welcome → Sign in / Sign up
(onboarding)  Create a Circle → Create first site → Pairing code + agent download link → "Waiting for agent…" (live)
(tabs)
  ├─ Overview   Site cards: grade, status chip, internet latency, unknown-device count, last seen
  ├─ Devices    Site picker · filter Online/Unknown/All · device cards (name, vendor, IP, trusted badge)
  ├─ Alerts     Grouped by site · severity chip · acknowledge (swipe or button)
  └─ Settings   Account · Circle & members · Invite code · Alert thresholds · Notifications · Theme · About
(stacks)
  Site detail      Latency chart (1h/24h/7d/30d, gateway vs internet), loss chart, outage log, "Why this grade?"
  Device detail    Info, rename/trust, "Ping test" (live result), ping history, open-port findings
  Diagnose         6-step list with live status (pending → running → pass/fail) and the root-cause card
  Report           Pick range → Generate → Preview/Share PDF
  Join             Enter invite code
  Phone test       "Test from this phone": TCP connect timing to the gateway and 8.8.8.8:443, compared with the agent
                   (uses react-native-tcp-socket, a native module: works in the dev build and APK, hidden on web)
```
**Required features in the app:**
- **Discovery:** the Devices tab and the site's network info.
- **Connectivity:** Ping test and Diagnose.
- **Statistics:** Device detail and Site detail.
- **Report:** the Report screen.
- **Security:** Alerts, port findings and the grade breakdown.

### 6.3 Data and state rules
- **The server is the source of truth.** Nothing is stored locally except auth tokens and the theme setting.
- **Polling:** the Overview refetches every 10 s while the screen is in view, and pauses in the background. A running command polls `GET /commands/{id}` every 1 s until it finishes.
- **Auth:** the access token is kept in memory and the refresh token in SecureStore. A single shared refresh request handles 401 responses, so several failing calls don't refresh at once.
- **Every screen designs four states:** loading (skeleton), empty (with a next step), error (retry), and stale/offline (a "Last updated 2 min ago" banner).

### 6.4 Push notifications
1. After login, ask for notification permission (Android 13+ needs it at runtime).
2. Get an `ExpoPushToken` and send it with `POST /push-tokens`.
3. Use Android notification channels `critical`, `warning` and `info` with different importance levels.
4. Tapping a notification opens the related screen through a link in its data, such as `/sites/{id}` or `/alerts`.
5. **Setup needed:** create a Firebase project, add its `google-services.json` to the app, and upload the FCM V1 service-account key to EAS credentials.

### 6.5 Web version
- **Build:** `npx expo export --platform web` creates a static site, deployed to Render.
- **Differences:** push isn't available on web, so alerts appear only in the app's Alerts tab. SecureStore isn't available on web, so tokens are kept in memory and the session lasts until the tab is closed.

### 6.6 Builds
| Profile | Use | Command |
|---|---|---|
| `development` | Daily development on your phone (supports push) | `eas build -p android --profile development` once, then `npx expo start --dev-client` |
| `preview` | APK for testers and submission | `eas build -p android --profile preview` (`buildType: apk`) |

**Fallback if the free EAS build quota runs out:** build locally with `npx expo run:android --variant release`. Your Android SDK is installed, but this may require JDK 17.

---

## 7. Security design (for the "Network Security Concepts" topic)
| Threat | Control |
|---|---|
| Eavesdropping | HTTPS everywhere (Render TLS, Neon TLS `sslmode=require`) |
| Password theft from the database | Argon2id hashes; refresh tokens and agent tokens stored only as hashes |
| Stolen tokens | 15-min access JWT; refresh tokens replaced on every use, with reuse detection; agents can be revoked |
| Password guessing / abuse | slowapi limits: login 5/min per IP+email, ingest 30/min per agent, others 120/min per user |
| One customer reading another's data | Every query filtered by membership; isolation test suite |
| Bad input | Pydantic schemas with max lengths; payload size limit of 1 MB on ingest |
| Leaked secrets | `.env` git-ignored; secrets only in Render environment settings and EAS secrets; GitHub secret scanning on |
| Misuse of the scanner | Agent scans only its own subnet; consent prompt at pairing; port list limited to 7 well-known ports |
| Cross-site web requests | CORS limited to the web app's own domain |

---

## 8. Design language and frontend-skills workflow

### 8.1 Roles of each skill (no overlap)
| Skill | Role in KinLAN | Output it owns |
|---|---|---|
| **impeccable** | Design director: product context, screen briefs, the design system file, reviews and polish | `PRODUCT.md`, `DESIGN.md`, review reports |
| **ui-ux-pro-max** | Research library: palettes, font pairings, chart choices, UX rules, React Native–specific rules | Nothing persisted. Its results feed into DESIGN.md. |
| **vercel-react-native-skills** | Engineering rules while writing React Native code (lists, animation, navigation, images, state) | Code that follows the rules |
| **web-design-guidelines** | Final check of the **web build** against Vercel's Web Interface Guidelines | A findings list (`file:line`) |
| **neon, neon-postgres** (from `npx neon skills -y`) | Neon CLI setup and PostgreSQL practice: pooled vs direct connections, migrations, branching, restore | Database setup and operations only |

**Neon skills scope:** KinLAN uses Neon **only as managed PostgreSQL**. The installed `neon-auth`, `neon-functions`, `neon-realtime`, `neon-object-storage` and `neon-ai-gateway` skills cover products the plan doesn't use: login is the API's own (Section 4.2), the API runs on Render (Section 10.2), and live views use polling (Section 6.3). CLAUDE.md tells the coding agent not to adopt them.

**Single source of truth: `DESIGN.md`.**
- Don't run ui-ux-pro-max with `--persist`. It would create a competing `design-system/MASTER.md`.
- `mobile/src/theme/` (the MD3 theme, status colors, spacing) is generated from the DESIGN.md tokens and must never disagree with them.
- **Path note:** ui-ux-pro-max's SKILL.md shows `${CLAUDE_PLUGIN_ROOT}/…`, which isn't set for a project install. Run it as `python .claude/skills/ui-ux-pro-max/scripts/search.py …` from the repository root.

### 8.2 Design language decisions (inputs to DESIGN.md)
- **Base:** Material Design 3 through React Native Paper. Impeccable's Android guide also says MD3 should govern structure and navigation on Android.
- **Mode:** Impeccable "Operate" (task-focused app UI): clear and consistent first, brand expressed in precise details.
- **Personality:** calm, trustworthy, technical but friendly. Warm, like people looking out for each other, but just as at home in an office as in a living room.
- **Group-neutral copy:** "Circle", "members" and "your people". Never "family" or "household" as the default. Run `/impeccable clarify` against this rule.
- **Status colors, the core of the system.** Each has a light and a dark value, and every one is always paired with an icon and a word:
  - `healthy` — check-circle — "Healthy"
  - `degraded` — alert — "Degraded"
  - `down` — close-octagon — "Down"
  - `offline` — help-circle — "Unknown"
  - `info` — information — "New"
- **Contrast:** text ≥ 4.5:1, icons and large text ≥ 3:1, checked in both themes.
- **Typography:** Roboto (MD3 type scale) or Inter. Use tabular figures (`fontVariant: ['tabular-nums']`) for all metrics. Sizes in sp/dp so they scale with the phone's text-size setting.
- **Spacing and shape:** 4/8 dp grid; corner radius from MD3 shape tokens. Touch targets ≥ 48 dp (Android) / 44 pt (iOS).
- **Motion:** subtle only (status changes, chart transitions, 150–250 ms). Respect the phone's Reduce Motion setting.
- **Charts:**
  - Use line charts for latency and bar charts for loss per hour.
  - Gateway vs internet use two colors that colorblind users can tell apart, plus different dash styles.
  - Use the same colors in every chart, the PDF report and the slides.
- **Theme:** light and dark, following the phone's setting, with a manual override in Settings.

### 8.3 Workflow by phase
| When | Step | Skill / command | Output |
|---|---|---|---|
| **Sprint 0** (Nov 6–8) | Capture product facts: users, roles, tasks, tone, platforms (Android + web), accessibility goals | `/impeccable init` | `PRODUCT.md` |
| **Sprint 1** (evenings) | Research direction | `python .claude/skills/ui-ux-pro-max/scripts/search.py "network monitoring dashboard real-time status mobile" --design-system --density 8 -p "KinLAN"` · `… "status indicator color blind" --domain ux` · `… "line chart time series latency" --domain chart` · `… "list performance navigation" --stack react-native` | Notes compared against MD3. Pick palette, type and density. |
| Sprint 1 | Brief each key screen before designing it: Overview, Device detail, Diagnose, Onboarding/Pairing, Alerts | `/impeccable shape overview` (and so on) | Confirmed briefs, saved in `docs/design/briefs/` |
| Sprint 1–2 | Create the design system | `/impeccable` new-work flow for the app's visual identity (writes DESIGN.md with YAML tokens and prose) | `DESIGN.md` |
| Sprint 1 (by Nov 15) | Wireframes and mockups of the 5 key screens | Figma, following DESIGN.md | Screenshots for the progress report and Chapter 2 |
| **Sprint 3** (Nov 22–28) | Generate the theme from DESIGN.md | Coding agent | `mobile/src/theme/{colors,typography,spacing,status}.ts` |
| Sprint 3, per screen | Build → check → fix | Code with **vercel-react-native-skills** loaded (FlatList/FlashList virtualization, memoized items, native stack, Pressable, safe areas, expo-image). Then `/impeccable audit <screen>` (native audit: accessibility, performance, theming, layout, platform). | A working screen with its audit findings fixed |
| Sprint 3 | Copy and empty/first-run states | `/impeccable clarify` (labels, errors) · `/impeccable onboard onboarding` (pairing flow, empty states) | Better text and first-run experience |
| **Sprint 4** (Nov 29–Dec 4) | Edge cases: offline, errors, long names, large text, 200 devices | `/impeccable harden` | A robust app |
| Sprint 4 | Design review with heuristic scoring | `/impeccable critique` on Overview, Device detail, Diagnose | Before/after scores (good evidence for Chapter 4) |
| Sprint 4 | Web build check | `/web-design-guidelines mobile/app/**/*.tsx` after `expo export --platform web` | Findings fixed |
| Sprint 4 | Final pass before the video | `/impeccable polish` | Ready for the demo |
| Sprint 4 | Usability evidence | 5 users do 5 tasks, then fill out the SUS survey | Score for Chapter 4 |

**Optional automatic checks:**
- `impeccable hooks on` adds a hook to `.claude/settings.local.json` that checks every UI file the coding agent edits.
- Turn it on in Sprint 3 if you want automatic checks, and leave it off otherwise. It only changes your local settings. `impeccable hooks off` disables it, and `impeccable hooks reset` removes its entries completely.

### 8.4 Rules for the coding agent (also in CLAUDE.md)
1. Read `DESIGN.md` before any UI change. Never hard-code a color, size or spacing value; import from `src/theme`.
2. Load `vercel-react-native-skills` for any work in `mobile/`.
3. Every new screen needs: a shape brief, all four states (loading, empty, error, stale), accessibility labels on icon buttons, and an `/impeccable audit` with no critical findings.
4. Status is never shown by color alone.
5. UI copy says "Circle" and "members", never "family" (see Section 0).
6. If a ui-ux-pro-max suggestion conflicts with DESIGN.md or MD3, DESIGN.md wins. Note the reason in the commit.

---

## 9. Testing and evaluation plan
| Area | Method | Target | Evidence |
|---|---|---|---|
| Unit tests | pytest (agent: parsers, health score, diagnose logic with mocked network; server: services, auth) | ≥ 70 % line coverage on `services/` and `kinlan_agent/` | Coverage report |
| API integration | pytest + FastAPI TestClient against `kinlan_test` | All endpoints; role matrix; isolation suite passes 100 % | CI logs |
| Discovery accuracy | Compare found devices with the router's DHCP client list, on 2 networks | ≥ 95 % of devices found | Table + screenshots |
| Latency accuracy | 100 samples: KinLAN vs `ping -n 100` at the same time | Average difference ≤ 2 ms | Table + chart |
| Protocol validation | Wireshark capture during a scan and a diagnose (filters `arp`, `icmp`, `dns`, `tcp.port==443`) | Every test step visible as the expected packets | Annotated screenshots (good Technical Implementation evidence) |
| Scan performance | Time a /24 ARP scan and the ICMP fallback | ARP ≤ 10 s · ICMP fallback ≤ 30 s | Table |
| Outage handling | Unplug the router's WAN cable for 5 min | Agent detects within 30 s; "unreachable" push ≤ 3 min; backlog uploaded ≤ 60 s after restore; **0 lost samples** | Video clip + database query |
| Remote command delay | Tap Diagnose → result shown | ≤ 15 s | Timed 10 runs |
| API performance | A small httpx script, 50 concurrent requests to `/sites/{id}/summary` | p95 < 500 ms (warm) | Table |
| Multi-user | 3 accounts (owner/admin/viewer) on 2 sites | Each role can do exactly what the matrix in 4.2 allows | Checklist |
| Usability | 5 participants, 5 tasks (pair a site, find an unknown device, run diagnose, invite a member, export a report) + SUS | SUS ≥ 68 (above average); task success ≥ 80 % | SUS sheet |
| Design quality | `/impeccable audit` + `critique` scores before and after polishing | No critical findings at submission | Report excerpts |

---

## 10. Git conventions, CI and deployment

### 10.1 Git conventions

**Repository setup (Sprint 0, once)**
- **Repository:** GitHub `kinlan`, default branch `main`.
- **Your identity:** set `git config user.name "<Your Name>"` and `git config user.email "<your email>"` so every commit is authored by you.
- **Commit hooks:** run `git config core.hooksPath .githooks` to turn on the repository's commit-message hook.
- **Line endings:** add a `.gitattributes` so Windows and Linux (CI, Render) agree on line endings:
  ```
  * text=auto
  *.sh text eol=lf
  .githooks/* text eol=lf
  *.png binary
  *.jpg binary
  *.pdf binary
  ```
- **Protect `main`** (Settings → Branches): require a pull request and passing CI before merging, and block force-pushes.
- **Track tasks in GitHub Issues:**
  - one issue per task
  - labels `agent`, `server`, `mobile`, `db`, `design`, `docs`, `bug`
  - milestones `Sprint 0` … `Sprint 4`

  The issue history is evidence for the Agile methodology in your report.

**Branches (GitHub Flow)**
- `main` is always deployable; Render deploys it automatically.
- All work happens on short-lived branches named `type/scope-short-description`:
  - `feat/agent-arp-discovery`
  - `fix/server-refresh-token-reuse`
  - `docs/report-chapter-2`
  - `chore/repo-setup`
- Merge through a pull request, even working solo: CI runs, and the PR keeps a record of the change. Use **squash merge**, so each PR becomes one clean commit on `main`. Delete the branch after merging.

**Commit messages: Conventional Commits**
```
<type>(<scope>): <subject>

<body: what changed and why, wrapped at 72 characters>

<footer: Refs #12, Closes #12, or BREAKING CHANGE: ...>
```
| Part | Rule |
|---|---|
| `type` | `feat` (new feature) · `fix` (bug fix) · `docs` · `style` (formatting only) · `refactor` · `perf` · `test` · `build` (dependencies, packaging) · `ci` · `chore` (maintenance) · `revert` |
| `scope` | `agent` · `server` · `mobile` · `db` · `design` · `docs` · `ci` · `repo` |
| `subject` | Imperative mood ("add", not "added"), lower case, no period, **whole first line ≤ 72 characters** |
| Body | Explain *why*, not just what. Optional for small changes. |
| Footer | Link the issue: `Refs #12` or `Closes #12` |

**Examples:**
```
feat(agent): add ARP sweep with ICMP fallback
fix(server): reject reused refresh tokens
feat(mobile): show diagnose steps with live status
feat(db): add baseline flag to devices
docs: add use case diagram to chapter 2
chore(repo): add commit-msg hook and PR template
```

**Commit habits**
- One logical change per commit. The code should run and pass its tests at every commit on `main`.
- Commit at least once per working session; push your branch at the end of every day as an off-site backup.
- Never commit:
  - secrets: `.env`, tokens, Firebase service-account keys
  - `.venv/` or `node_modules/`
  - build output (`dist/`, `build/`, `*.exe`, `*.apk`)
  - database dumps or videos
  - coding-assistant files: `.claude/`, `CLAUDE.md`, `CLAUDE.local.md`, `.impeccable/`, `skills-lock.json`

  APKs and the agent `.exe` go on **GitHub Releases**; the video goes only in the submission zip.

**No AI attribution in commits or pull requests**
- Every commit is authored by you alone. Commit messages and PR descriptions must **not** contain:
  - a `Co-Authored-By: Claude …` trailer
  - a `noreply@anthropic.com` address
  - a "Generated with Claude Code" line
- How this is enforced:
  1. **The commit-msg hook below rejects** any message containing those lines. It's the guaranteed check.
  2. **CLAUDE.md tells the coding agent** not to add them (Appendix A).
  3. **Claude Code's commit attribution can be switched off** in `.claude/settings.json`. In current versions the setting is `"includeCoAuthoredBy": false`; check Claude Code's settings documentation for the exact key, since it may have changed.

**`.githooks/commit-msg`** (works in Git for Windows):
```sh
#!/bin/sh
# Enforces Conventional Commits and blocks AI attribution lines.
msg_file="$1"
subject=$(head -n 1 "$msg_file")

# Let Git's own merge and revert messages through.
case "$subject" in
  "Merge "*|"Revert "*) exit 0 ;;
esac

pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\((agent|server|mobile|db|design|docs|ci|repo)\))?!?: [^ ].*[^.]$'
if ! printf '%s\n' "$subject" | grep -Eq "$pattern"; then
  echo "commit-msg: use 'type(scope): subject', e.g. 'feat(agent): add ARP discovery'" >&2
  exit 1
fi

if [ "${#subject}" -gt 72 ]; then
  echo "commit-msg: the first line is ${#subject} characters; keep it to 72 or fewer" >&2
  exit 1
fi

if grep -Eiq 'co-authored-by:.*(claude|anthropic)|noreply@anthropic\.com|generated with .*claude' "$msg_file"; then
  echo "commit-msg: AI attribution lines are not allowed in this repository" >&2
  exit 1
fi
```

**`.gitignore`** (repository root):
```gitignore
# Coding-assistant files: local only, never committed
.claude/
CLAUDE.md
CLAUDE.local.md
.impeccable/
skills-lock.json

# Course paperwork (submitted through Teams, not as source code)
course/

# Secrets and environments
.env
.env.*
!.env.example
*.token
.venv/

# Python
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Builds and releases
agent/build/*
!agent/build/kinlan-agent.spec
agent/dist/
*.exe
*.apk
*.aab

# Mobile
node_modules/
mobile/dist/
mobile/.expo/
mobile/android/
mobile/ios/

# Data and media
docs/backups/
*.dump
*.sql.gz
*.mp4
*.mov

# OS and editors
Thumbs.db
.DS_Store
.vscode/

# Logs
*.log
```
`mobile/android/` and `mobile/ios/` are generated by Expo when you build, so they're ignored too.

**`.githooks/pre-commit`** stops local-only files from slipping in, even with `git add -f`:
```sh
#!/bin/sh
# Refuses commits that stage coding-assistant files or obvious secrets.
blocked=$(git diff --cached --name-only --diff-filter=ACMR | grep -E '(^|/)(\.claude/|\.impeccable/|CLAUDE(\.local)?\.md$|skills-lock\.json$|\.env$|.*\.token$)')
if [ -n "$blocked" ]; then
  echo "pre-commit: these files must stay local and can't be committed:" >&2
  echo "$blocked" | sed 's/^/  /' >&2
  echo "Unstage them with: git restore --staged <file>" >&2
  exit 1
fi
```

**Pull request template (`.github/pull_request_template.md`)**
```markdown
## What
<!-- One or two sentences. -->

## Why
<!-- The problem or issue this solves. Closes #… -->

## How I tested it
- [ ] Unit tests pass (`pytest` / `tsc` / `eslint`)
- [ ] Tried it manually: <steps>

## Screenshots (UI changes)
```

**Versions and tags (Semantic Versioning, `MAJOR.MINOR.PATCH`)**
| Tag | Meaning |
|---|---|
| `agent-v1.0.0` | Agent release. Triggers the Windows build and attaches `KinLAN-Agent.exe` to a GitHub Release. |
| `app-v1.0.0` | The APK version submitted, matching `version` in `app.json` |
| `v1.0.0` | The whole platform as submitted on Dec 4. Tag it before you build the zip. |

Keep a short `CHANGELOG.md` with one section per tag (Added / Changed / Fixed), copied from the squash-merge titles.

### 10.2 CI and deployment
- **CI** (GitHub Actions, `.github/workflows/ci.yml`, runs on every push and PR):
  - **agent:** ruff + pytest on `windows-latest`, since the agent uses Windows-only APIs (DPAPI, `schtasks`); network calls are mocked in tests
  - **server:** ruff + pytest, with a PostgreSQL 15 service container
  - **mobile:** `npm ci`, `tsc --noEmit`, `eslint`
- **Server deploy** (Render web service, free):
  - Auto-deploy from `main`.
  - Build command: `pip install -r requirements.txt`.
  - Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  - Environment variables: `DATABASE_URL`, `JWT_SECRET`, `EXPO_ACCESS_TOKEN`, `CORS_ORIGINS`, `ENV=production`.
  - Health check path: `/healthz`.
- **Web deploy:** Render static site from `mobile/dist` (built in CI or locally).
- **Agent release:** a Git tag `agent-v1.0.0` triggers a GitHub Actions Windows runner that runs PyInstaller and attaches `KinLAN-Agent.exe` to a GitHub Release.
- **App release:** EAS `preview` APK. Put the download link in the README and on the onboarding screen.
- **Monitoring the system itself:**
  - Render logs.
  - An uptime check on `/healthz`, using a free monitor such as UptimeRobot. It also stops the free API from going to sleep before agents exist.
  - Agent logs in `%ProgramData%\KinLAN\logs`.

---

## 11. Sprint plan (today: Fri Nov 6)
Write each chapter of the report **at the end of the sprint it covers**, not in the last week.

### Sprint 0 — Setup (Fri Nov 6 – Sun Nov 8)
- [ ] Submit the proposal (Week 14).
- [ ] Create the `kinlan` GitHub repo and set it up as in Section 10.1:
  - monorepo skeleton, CLAUDE.md, `.gitignore`, `.gitattributes`, `CHANGELOG.md`
  - commit-msg and pre-commit hooks (`git config core.hooksPath .githooks`), PR template, branch protection on `main`
  - Issues with labels, and milestones Sprint 0–4
  - a CI workflow that runs on every push
  - run `git init` in the `kinlan` workspace, and create `CLAUDE.md` from Appendix A there. Check with `git status`: `.claude/`, `CLAUDE.md` and `course/` must not appear.
- [ ] Install Python 3.12 and both virtual environments; create the local databases; sign up for Neon, Render, Expo and Firebase.
- [ ] `/impeccable init` → PRODUCT.md.
- [ ] Draft Chapter 2 diagrams: architecture (Section 1), use case diagram (actors Owner, Admin, Viewer, Agent, Scheduler), and the main flowchart (agent loop + diagnose).

### Sprint 1 — Agent core (Mon Nov 9 – Sat Nov 14)
- [ ] `netinfo`, `discovery` (ARP + fallback), `monitor`, `pingtest`, `diagnose`, the local SQLite buffer, and `run --local`, which prints results with `rich` tables.
- [ ] Unit tests for the parsers, the diagnose decision logic and the health score.
- [ ] Wireshark captures of the scan and the diagnose.
- [ ] Design: ui-ux-pro-max research, `/impeccable shape` for the 5 key screens, first DESIGN.md draft.
- [ ] **By Sun Nov 15 (needed for the progress report):** Figma mockups of the 5 key screens, and the ERD from Section 5.2 drawn in draw.io.
- [ ] **Done when:** `kinlan-agent run --local` shows devices, latency, loss and a diagnose result on your home network.

### Sprint 2 — Server, database and connection (Sun Nov 15 – Sat Nov 21)
- [ ] **Sun–Mon, before the progress report:** SQLAlchemy models + first Alembic migration; auth (register/login/refresh), so the `/docs` page has real endpoints to screenshot.
- [ ] Circles, memberships, invites; sites and pairing.
- [ ] Agent pairing + ingest + heartbeat + command long-poll; uploader with backoff and resend-safe batches.
- [ ] Alert engine v1 (new device, unreachable, back online); scheduled jobs (heartbeat, rollup, retention).
- [ ] Deploy to Render + Neon; run the agent against production.
- [ ] Set up Firebase/FCM credentials in EAS now, so push isn't blocked in Sprint 3.
- [ ] **Tue Nov 17 — Progress Report (2–3 pages).** Contents:
  - system design (architecture, ERD, flowchart)
  - screenshots of the agent CLI, the Swagger `/docs` page, Wireshark captures and Figma mockups
  - sample code (`diagnose.py`, ingest endpoint)
  - accomplishments and remaining tasks
- [ ] **Done when:** two agents (home + a second network) upload to the live API and data is visible in `/docs` and in pgAdmin.

### Sprint 3 — Mobile app (Sun Nov 22 – Sat Nov 28)
- [ ] Theme from DESIGN.md; auth screens; onboarding/pairing; Overview; Devices + Device detail with ping test; Diagnose screen; Site detail charts; Alerts; Settings (members, invites, thresholds).
- [ ] Development build on your phone; push notifications end to end.
- [ ] Per screen: vercel-react-native-skills while coding, then `/impeccable audit`, `clarify` and `onboard` for the first-run flow.
- [ ] **Done when:** a second user joins with an invite code on another phone, sees the same site, and receives a "new device" push.

### Sprint 4 — Finish, test, document (Sun Nov 29 – Fri Dec 4)
- [ ] **Sun–Mon:**
  - PDF report, port check + findings, health grade breakdown, "Test from this phone"
  - agent `.exe` + `install` command
  - APK (`preview`) + web export
- [ ] **Tue:**
  - run the entire Section 9 test plan and record the results
  - `/impeccable harden`, `critique` and `polish`
  - `/web-design-guidelines` on the web build
  - SUS sessions with 5 users
- [ ] **Wed:**
  - finish the Final Technical Report (8–12 pages, Times New Roman 12, double-spaced, justified, on the page template)
  - slides (10–15)
- [ ] **Thu:**
  - record the demo video (5–10 min, formal attire): startup → features → testing results → final output
  - edit the video
- [ ] **Fri Dec 4 — Submit:**
  - `LASTNAME_FIRSTNAME_FINALPROJECT.zip` with `/SourceCode`, `/Presentation`, `/VideoDemo` and `README.txt`
  - the documentation separately via Teams

### Dec 5–7 — Defense preparation
- [ ] Rehearse a live demo plus a backup recording. Pre-seed demo data. Take a `pg_dump`.
- [ ] Prepare answers on:
  - why ARP finds devices that don't reply to ping
  - how the layered diagnose maps to the OSI model
  - why HTTPS polling instead of an inbound connection (NAT)
  - how passwords and tokens are protected
  - how outages are detected when the agent can't reach the cloud

---

## 12. Deliverables mapping
| Deliverable | Source in this plan |
|---|---|
| Ch. 1 Introduction | Proposal (problem, objectives) + Section 0 |
| Ch. 2 System Design | Section 1 architecture, use case diagram, flowcharts (agent loop, diagnose, outage path), Section 5 database diagram, DESIGN.md summary |
| Ch. 3 Implementation | Section 2 tools, Sections 3–7 module descriptions with short code excerpts |
| Ch. 4 Results & Testing | Section 9 tables, Wireshark screenshots, app screenshots, SUS score, audit scores |
| Ch. 5 Conclusions & Recommendations | What worked, limitations (Npcap licensing, unsigned exe, free-tier limits), future work (iOS release, WebSocket channel, SNMP for routers, router API integration to block devices) |
| Source code | Repository + README (install, run, deploy) + commented code (docstrings on every module and public function) |
| Slides (10–15) | Title · Overview · Problem · Objectives · Methodology (Agile sprints) · Architecture (Section 1 diagram) · Features · Demonstration · Results (Section 9) · Conclusion |
| Demo video | Script: agent install & pair → app login → devices/new-device alert → ping test → diagnose with the cable unplugged → charts → invite a viewer → PDF report → test results |

**Grading coverage:**
- **Functionality (30):** Sections 3–6.
- **Technical Implementation (20):** Sections 1.1, 3.3, 7 and 9, plus the Wireshark validation.
- **UI/Design (10):** Section 8.
- **Documentation (15):** Section 12.
- **Testing (10):** Section 9.
- **Presentation (10):** Section 11, defense preparation.
- **Innovation (5):**
  - multi-user cloud platform with a mobile app and push alerts
  - layered troubleshooter
  - offline buffer
  - health grade

---

## 13. Risks and fallbacks
| Risk | Likelihood | Fallback |
|---|---|---|
| Behind schedule | High | **Cut in this order:** web build → "Test from this phone" → port check → Tkinter agent window → PDF (keep a plain-text/CSV report). Never cut: the 5 required features, auth/roles, the live API, the APK. |
| Neon free compute limits (the database never idles because agents upload constantly) | Medium | Check the current free-tier limits when signing up. If they're exceeded, raise the upload interval to 60 s, or move to Supabase's free PostgreSQL. Only `DATABASE_URL` changes, because the schema is managed by Alembic. |
| Render free instance sleeps or restarts | Medium | Agents and the uptime check keep it awake. Agents buffer locally, so a restart loses nothing. |
| EAS free build quota | Low–Medium | Build locally with `expo run:android` (may need JDK 17) |
| Push setup (FCM) is time-consuming | Medium | Configured in Sprint 2, while the server is being built |
| Npcap missing on the test PC | Medium | Windows `SendARP` fallback, built and tested in Sprint 1 |
| ICMP blocked by some devices or Windows firewalls | High | ARP discovery finds them anyway. In the defense, explain why ARP is more reliable than ping inside a LAN. |
| Router or ISP blocks the outage test | Low | Simulate it by disabling the router's WAN, or by unplugging the router–modem cable |
| Local-only files lost (not in Git) | Low | The skills can be downloaded again from their GitHub repositories, and the `CLAUDE.md` text is in Appendix A. Optionally keep a copy of `.claude/` in a private cloud folder. |
| Live demo fails at the defense (school Wi-Fi) | Medium | Use a phone hotspot + the backup recording; demo data seeded beforehand |

---

## Appendix A — `CLAUDE.md` template (repository root, local only, never committed)
```markdown
# KinLAN — rules for the coding agent

## Project
Multi-user network monitoring platform: Python agent (agent/), FastAPI + PostgreSQL API (server/),
Expo React Native app (mobile/). Full plan: docs/KinLAN_Technical_Plan.md.
Course instructions and the proposal are in course/ (local only).

## Commands
- Agent:  cd agent && .venv\Scripts\activate && pytest && ruff check .
- Server: cd server && .venv\Scripts\activate && uvicorn app.main:app --reload ; pytest ; alembic upgrade head
- Mobile: cd mobile && npx expo start --dev-client ; npx tsc --noEmit ; npx eslint .

## Rules
- Database changes only through Alembic migrations; never edit the schema by hand.
- Every query on site data must be scoped by the caller's Circle membership. Add an isolation test for new endpoints.
- Never commit .env, tokens, Firebase credentials, or database dumps.
- Agent code must run on Windows 11 as admin and degrade gracefully without Npcap.
- Neon is used only as managed PostgreSQL. Use the neon and neon-postgres skills for database setup,
  connections and branching. Don't adopt Neon Auth, Functions, Realtime, Object Storage or AI Gateway:
  login is our FastAPI JWT auth, the API runs on Render, and live views use polling.
- Ask before installing anything globally (for example `npm i -g neon`).

## Git
- Conventional Commits: `type(scope): subject`, first line ≤ 72 characters (technical plan, Section 10.1). Scopes: agent, server, mobile, db, design, docs, ci, repo.
- Never add AI attribution to commits or PRs: no `Co-Authored-By: Claude …` trailer, no "Generated with Claude Code" line. The commit-msg hook rejects them.
- One logical change per commit. Never commit secrets, `.env`, `.venv`, `node_modules`, builds, APKs, videos or database dumps.
- Never commit `.claude/`, `CLAUDE.md`, `CLAUDE.local.md`, `.impeccable/` or `skills-lock.json`. They're git-ignored, and the pre-commit hook blocks them. Never use `git add -f` or `--no-verify` to get around this.
- Work on a branch named `type/scope-short-description`, open a PR to `main`, and squash-merge.

## Frontend / design
- DESIGN.md is the single source of truth for visual design. Read it before any UI change.
  Never hard-code colors/sizes; import from mobile/src/theme.
- Load the vercel-react-native-skills skill for any work in mobile/.
- New screen: /impeccable shape first; implement loading/empty/error/stale states;
  run /impeccable audit before calling it done.
- ui-ux-pro-max is research only: run `python .claude/skills/ui-ux-pro-max/scripts/search.py ...`
  from the repo root; never use --persist. DESIGN.md wins any conflict.
- Status is never conveyed by color alone (icon + label always).
- Groups are called "Circles"; never write "family" in UI copy (KinLAN serves homes, dorms, offices and labs).
- Web build review: /web-design-guidelines on mobile/app/**.
```
