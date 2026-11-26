# KinLAN

**Your people, your network.**

KinLAN is a multi-user network monitoring and performance analysis platform with mobile access. A small **agent** runs on a PC inside each network: it discovers devices, measures latency and packet loss, finds which network layer failed when the connection breaks, and checks for risky open ports. It reports to a **cloud API**, and the members of a **Circle** (a household, dorm, office or school lab) follow their networks from the **mobile app**, with shared alerts and reports.

Final project for CCS 234 – Communications and Networking, West Visayas State University.

## Repository layout

| Folder | What it is |
|---|---|
| `agent/` | Python 3.12 agent (discovery, monitoring, diagnosis, upload) |
| `server/` | FastAPI + PostgreSQL cloud API |
| `mobile/` | Expo (React Native, TypeScript) app, created in Sprint 3 |
| `docs/` | Technical plan, diagrams, screenshots, test results |

## Get the app

- **Android:** download **[KinLAN.apk](https://github.com/KirkGamo/kinlan/releases/download/app-v1.0.0/KinLAN.apk)** on the phone and open it. Android asks once to allow installs from your browser or Files app. Alerts arrive as notifications.
- **Web:** **[kinlan-web.onrender.com](https://kinlan-web.onrender.com)** works in any browser with the same account. It has no push notifications; the Alerts tab shows the same alerts. The first visit after a quiet spell can take up to a minute while the free API wakes up.

## Install the agent on a PC (Windows 10 or 11)

The agent runs on one PC that stays on inside the network you want to watch. Only monitor networks you own or are allowed to monitor.

1. In the app, add a site and choose **Pair the agent**; it shows a 6-digit code (valid for 10 minutes).
2. Download **[KinLAN-Agent.exe](https://github.com/KirkGamo/kinlan/releases/latest/download/KinLAN-Agent.exe)** and run it.
   - **SmartScreen:** the exe isn't code-signed, so Windows may say it "protected your PC". Choose **More info → Run anyway**.
   - Approve the **administrator** prompt: the agent sends ARP and ping packets and starts at boot, which need it.
3. Enter the code and accept the consent prompt. The agent then installs itself to start when the PC starts (as a Task Scheduler task running as SYSTEM, so nobody has to sign in) and starts monitoring. The app shows "Connected" within a minute.

**A laptop as the agent's PC:** the agent remembers the network it was paired on (by its router's MAC address) and only monitors while the PC is on it. Anywhere else it waits, so another network's devices never reach your site, and the app says the PC isn't on the site's network. An agent paired with version 1.0.0 asks once, the next time you run `KinLAN-Agent.exe`: "Is this Home's network?". Answer it while the PC is on that network.

**Npcap** (optional, recommended): with [Npcap](https://npcap.com/#download) installed (it also comes with Wireshark), a device scan takes about 7 s; without it the agent falls back to Windows' own ARP lookup, about 14 s per /24. Npcap's licence doesn't allow bundling it.

From an administrator terminal: `KinLAN-Agent.exe status` shows the pairing, the startup task and the last upload; `KinLAN-Agent.exe uninstall` removes the startup task (the pairing and history stay). Everything the agent keeps is in `%ProgramData%\KinLAN` (settings, the encrypted token, the offline buffer and `logs\`).

**Build the exe yourself:** `cd agent`, then `pyinstaller build/kinlan-agent.spec --noconfirm` (it lands in `agent/dist/`). A tag like `agent-v1.0.0` builds and publishes it as a GitHub Release automatically.

## Development setup (Windows 11)

Requirements: Python 3.12, PostgreSQL 15, Git, Node.js 22 (for the mobile app), and Npcap (installed with Wireshark) for ARP scanning.

**Agent**
```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

Try the agent on your own network, with no cloud connection (Ctrl+C to stop):
```bash
python -m kinlan_agent run --local
```
It shows this PC's network, the devices on it, a six-step diagnose, and a live monitor with the health grade. No administrator rights are needed; with Npcap installed (it comes with Wireshark) the device scan takes about 7 s instead of 14 s.

**Server**
```bash
cd server
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env        # then fill in your database password and a JWT secret
uvicorn app.main:app --reload # API docs at http://localhost:8000/docs
pytest
```

**Local databases** on PostgreSQL 15, which listens on port **5433** on this machine (PostgreSQL asks for your password):
```bash
createdb -U postgres -h localhost -p 5433 kinlan_dev
createdb -U postgres -h localhost -p 5433 kinlan_test
```

**Git hooks** (once per clone):
```bash
git config core.hooksPath .githooks
```

## Contributing

- Branches: `type/scope-short-description`, for example `feat/agent-arp-discovery`.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/), `type(scope): subject`, first line at most 72 characters. Scopes: `agent`, `server`, `mobile`, `db`, `design`, `docs`, `ci`, `repo`. The `commit-msg` hook checks this.
- Open a pull request to `main` and squash-merge after CI passes.

## Status

Sprint 4 (finish, test, document): every required feature works end to end. See [CHANGELOG.md](CHANGELOG.md).
