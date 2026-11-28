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
| API performance | 50 concurrent `/summary`, p95 < 500 ms warm | Render: p95 **7.7 s**. Same code locally: p95 **766 ms** | **Fail** (see below) |
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

### On Render (production)

Sent from the web app's own page in the browser, signed in as the viewer account, to the Home
site (a site with three weeks of samples). Five requests first to warm the server.

| Requests at once | Requests | p50 | p95 | Max |
|---:|---:|---:|---:|---:|
| 1 (one after another) | 20 | 275 ms | 367 ms | 398 ms |
| 5 | 5 | 724 ms | 839 ms | 839 ms |
| 10 | 10 | 1,633 ms | 1,765 ms | 1,765 ms |
| 20 | 20 | 2,751 ms | 3,281 ms | 3,282 ms |
| **50** | 50 | 5,704 ms | **7,687 ms** | 7,804 ms |

All 200 OK. The time grows by about 160 ms for each request in flight: the server answers
about **6 summaries a second**, one after another. Even the fastest of the 50 took 1.9 s, so
requests aren't waiting in a queue, they are sharing a CPU that is too small. Render's free
instance has 0.1 CPU.

### The same code locally

To separate the code from the hosting, `scripts/summary_load.py` seeded the local database to
the Home site's size (120,960 samples, 7 days) and ran the same test against one local uvicorn
process, the way Render runs it, with the rate limit off.

| Requests at once | Requests | p50 | p95 | Max |
|---:|---:|---:|---:|---:|
| 1 (one after another) | 20 | 18 ms | 21 ms | 24 ms |
| 10 | 10 | 205 ms | 237 ms | 237 ms |
| 50 (3 rounds) | 150 | 442 ms | **766 ms** | 824 ms |

A profile of 100 requests: about 15 ms each inside the handler, spent on 14 small queries
(authentication, the membership check, then the counts). The largest is the 24-hour ping
aggregate, 3.4 ms over about 8,600 rows through the `(site_id, target, ts)` index. No single
query is slow; one Python process can't overlap that many of them.

### What it means

The target fails, on Render by a factor of 15, and by 1.5 even on a full CPU. In use, the load
is far below this: three people with the Overview open poll it once every 5 s, about 0.6
requests a second, against a capacity of about 6 on the free instance. Single requests from the
Philippines take 275 ms, which is what a person sees.

Ways to meet the target, for the report's Future Work:

1. A short per-site cache of the summary (a few seconds; the agent uploads every 30 s), so 50
   readers of one site cost one computation plus the role check each.
2. One SQL statement for the counts instead of nine, which cuts per-request time.
3. A paid instance (Render Starter has 0.5 CPU) or more than one worker process.

## Pending rows

These need hands on the network or a phone:

- **Discovery accuracy**: the router's DHCP client list (home router admin page) and the
  hotspot's connected-devices list, each against an agent scan at the same time.
- **Outage handling**: unplug the home router's WAN cable for 5 minutes with the laptop on
  home Wi-Fi.
- **Remote command delay**: 10 Diagnose taps on the Overview. The server records each
  command's `created_at` and `finished_at`; the app checks for the result every second. Earlier
  manual runs (Nov 22, 26, 28) took 1.5 s, 1.8 s and 2.1 s on the server.
