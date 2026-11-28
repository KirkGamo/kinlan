# Section 9 test plan: results (Nov 29, 2026)

Issue #95. Each row of technical plan §9 with its measured result. Rows already recorded
elsewhere link to their own record. The scripts used are in [`scripts/`](scripts/).

## Summary

| Area | Target | Result | Status |
|---|---|---|---|
| Unit tests and coverage | ≥ 70 % line coverage, server and agent | Server **97 %** (176 tests), agent **88 %** (207 tests) | Pass |
| API integration | All endpoints, role matrix, isolation suite | 176 server tests pass in CI, including the 21-case role matrix | Pass |
| Discovery accuracy | ≥ 95 % of the router's DHCP clients found, 2 networks | | Pending (needs the router's client lists) |
| Latency accuracy | Average difference ≤ 2 ms over 100 samples | **1.50 ms** (hotspot) | Pass |
| Protocol validation | Every test step visible in Wireshark | Every step seen ([record](2026-11-07_wireshark_validation.md)) | Pass |
| Scan performance | ARP ≤ 10 s, fallback ≤ 30 s | ARP **9.5 s** average (one run of 3 took 10.2 s), fallback **15.4 s** | Pass, ARP at the limit |
| Outage handling | Detect ≤ 30 s, push ≤ 3 min, backlog ≤ 60 s, 0 lost samples | | Pending (WAN unplug at home) |
| Remote command delay | Diagnose result ≤ 15 s, 10 runs | | Pending (10 taps on a phone) |
| API performance | 50 concurrent `/summary`, p95 < 500 ms warm | With the summary cache (#126): locally p95 **442 ms**, on Render **3.8–4.1 s** (7.7 s before) | Pass locally, **fail on the free instance** (see below) |
| Multi-user | Each role can do exactly what §4.2 allows | All checks pass ([record](2026-11-29_roles_and_two_sites.md)) | Pass |
| Usability (SUS) | SUS ≥ 68, task success ≥ 80 % | | Issue #96 |
| Design quality | No critical findings at submission | | Issue #96 |

## Unit tests and coverage

`pytest --cov`, run on Nov 29 on the laptop (Python 3.12.1, `pytest-cov` 7.1.0, now pinned in both
`requirements-dev.txt` files). The plan names `services/`; the server keeps that logic in
`app/` modules (alerts, health, push, reports, jobs, …), so the whole `app` package is measured.

| Package | Statements | Missed | Coverage | Tests |
|---|---:|---:|---:|---:|
| `server/app` | 2,514 | 85 | **97 %** | 176 passed |
| `agent/kinlan_agent` | 2,067 | 250 | **88 %** | 207 passed |

Lowest modules. Server: `jobs.py` 67 % (the scheduler loop that starts the timed jobs; the jobs
themselves are tested). Agent: `main.py` 45 % (the command-line wiring), `winapi.py` 59 %
(Windows calls: tests use fakes), `icmp.py` 45 % (the non-Windows branch).

## Latency accuracy

`scripts/latency_vs_ping.py`: the agent's own ICMP echo (`icmp.echo`, Windows IcmpSendEcho)
sent to the router once a second, 100 times, while Windows `ping -n 100` ran against the same
router at the same time.

Network: the phone hotspot site, 10.48.65.0/24, router 10.48.65.69, Nov 29 00:4x.

| | Replies | Average | Median | Min | Max | p95 | Std. dev. |
|---|---:|---:|---:|---:|---:|---:|---:|
| KinLAN agent | 100/100 | 12.04 ms | 6.0 ms | 2 ms | 45 ms | 32 ms | 11.1 ms |
| `ping -n 100` | 100/100 | 13.54 ms | 5.5 ms | 2 ms | 172 ms | 35 ms | 19.9 ms |

**Average difference: 1.50 ms** (target ≤ 2 ms). The medians differ by 0.5 ms. Most of the
average gap is one 172 ms reply in `ping`'s run: a phone hotspot is a jittery link, and the two
probes never hit the same instant. A repeat on the home router (a steadier link) is planned
alongside the discovery check.

## Scan performance

`scripts/scan_timing.py`: three runs of each method on the hotspot network (/24), host names
off, 2 s between runs.

| Method | Run 1 | Run 2 | Run 3 | Average | Target |
|---|---:|---:|---:|---:|---|
| Scapy ARP (Npcap), the default | 9.47 s | 10.15 s | 8.94 s | **9.52 s** | ≤ 10 s |
| Windows SendARP, the fallback | 12.72 s | 16.73 s | 16.73 s | **15.39 s** | ≤ 30 s |

Every run found the same 2 devices (the laptop and the phone). The plan names an "ICMP
fallback"; the agent's fallback is Windows SendARP (64 parallel ARP lookups), used when Npcap
is missing. It doesn't need administrator rights.

The ARP scan sits at its limit by design: three passes with a 2 s wait each (the two resends
were added after a single pass missed sleeping phones, see the Wireshark record), plus Scapy's
start-up. One run of three went 0.15 s over. Dropping one resend would bring it near 7 s at the
cost of missing devices that answer late, so it stays.

## API performance

Target: 50 concurrent `GET /sites/{id}/summary`, p95 under 500 ms with the server warm.

Render requests were sent from the web app's own page in the browser, signed in as the viewer
account, to the Home site (three weeks of samples), after five warm-up requests. Local requests
used `scripts/summary_load.py`: the dev database seeded to the Home site's size (120,960
samples over 7 days) and one local uvicorn process, as Render runs it, with the rate limit off.

### First run, before any change

| Requests at once | Render p50 | Render p95 | Local p50 | Local p95 |
|---:|---:|---:|---:|---:|
| 1 (20 one after another) | 275 ms | 367 ms | 18 ms | 21 ms |
| 5 | 724 ms | 839 ms | | |
| 10 | 1,633 ms | 1,765 ms | 205 ms | 237 ms |
| 20 | 2,751 ms | 3,281 ms | | |
| **50** | 5,704 ms | **7,687 ms** | 442 ms | **766 ms** |

All 200 OK. On Render each request in flight added about 160 ms: the free instance (0.1 CPU)
answered about 6 summaries a second. Even the fastest of the 50 took 1.9 s, so the requests
were sharing a CPU that is too small, not waiting in a queue for the database.

A profile of 100 local requests: about 15 ms each inside the handler, spent on 14 small queries
(authentication, the membership check, then the counts). The largest is the 24-hour ping
aggregate, 3.4 ms over about 8,600 rows through the `(site_id, target, ts)` index. No single
query is slow; there were simply many of them for every poll.

### The fix: a per-site summary cache (#126)

The summary is the same for every member, so it is now computed once per site and kept for up
to 10 s. Any committed write clears it (an ingest, an acknowledged alert, a trusted device), so
it never shows something older than the database. The role check still runs on every request.
A cached request runs 3 queries instead of 14.

| Requests at once | Render p50 | Render p95 | Local p50 | Local p95 |
|---:|---:|---:|---:|---:|
| 1 (20 one after another) | 206 ms | 256 ms | 9 ms | 10 ms |
| 10 | 987 ms | 1,082 ms | 157 ms | 186 ms |
| **50** | 2,936–3,295 ms | **3,834–4,100 ms** (two runs) | 264 ms | **442 ms** |

The cache halves the time on Render and meets the target on a full CPU.

### What's left is the instance

Two more measurements at 50 concurrent on Render show where the floor is:

| Request (50 at once) | Work on the server | p95 |
|---|---|---:|
| `GET /me` | token check, one query | 2,394 ms |
| `/summary` with an expired token (401) | token check only, no database | 856 ms |

Even a request that never reaches the database misses 500 ms when 50 arrive together on the
free instance. No change to the endpoint can meet the target there; a bigger instance can.

In use, the load is far below the test: three people with the Overview open poll it once every
5 s, about 0.6 requests a second, and one request takes about 206 ms from the Philippines.

For the report's Future Work: a paid instance (Render Starter, 0.5 CPU) or more worker
processes, with the cache moved to a shared store (such as Redis) once there is more than one
process.

## Pending rows

These need hands on the network or a phone:

- **Discovery accuracy**: the router's DHCP client list (home router admin page) and the
  hotspot's connected-devices list, each against an agent scan at the same time.
- **Outage handling**: unplug the home router's WAN cable for 5 minutes with the laptop on
  home Wi-Fi.
- **Remote command delay**: 10 Diagnose taps on the Overview. The server records each
  command's `created_at` and `finished_at`; the app checks for the result every second. Earlier
  manual runs (Nov 22, 26, 28) took 1.5 s, 1.8 s and 2.1 s on the server.
