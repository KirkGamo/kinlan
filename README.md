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

Sprint 0 (setup). See [CHANGELOG.md](CHANGELOG.md).
