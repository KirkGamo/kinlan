# Section 9 test plan: results (Nov 29, 2026)

Issue #95. Each row of technical plan §9 with its measured result. Rows already recorded
elsewhere link to their own record. The scripts used are in [`scripts/`](scripts/).

## Summary

| Area | Target | Result | Status |
|---|---|---|---|
| Unit tests and coverage | ≥ 70 % line coverage, server and agent | Server **97 %** (183 tests), agent **88 %** (220 tests) | Pass |
| API integration | All endpoints, role matrix, isolation suite | 183 server tests pass in CI, including the 21-case role matrix | Pass |
| Discovery accuracy | ≥ 95 % of the connected devices found, 2 networks | **4 of 4** clients (100 %) on two phone hotspots, plus both hotspots, nothing extra | Pass (small networks; see below) |
| Latency accuracy | Average difference ≤ 2 ms over 100 samples | **1.50 ms** (hotspot) | Pass |
| Protocol validation | Every test step visible in Wireshark | Every step seen ([record](2026-11-07_wireshark_validation.md)) | Pass |
| Scan performance | ARP ≤ 10 s, fallback ≤ 30 s | ARP **9.5 s** average (one run of 3 took 10.2 s), fallback **15.4 s** | Pass, ARP at the limit |
| Outage handling | Detect ≤ 30 s, push ≤ 3 min, backlog ≤ 60 s, 0 lost samples | Detected in **26 s**, push **2 min 5 s**, backlog **18 s**, **0 lost** (third run, agent 1.1.2) | Pass, after three agent fixes |
| Remote command delay | Diagnose result ≤ 15 s, 10 runs | 10 of 10 done: **1.53 s** average on the server (0.95–2.36 s), at most about 4 s on screen | Pass |
| API performance | 50 concurrent `/summary`, p95 < 500 ms warm | With the summary cache (#126): locally p95 **442 ms**, on Render **3.8–4.1 s** (7.7 s before) | Pass locally, **fail on the free instance** (see below) |
| Multi-user | Each role can do exactly what §4.2 allows | All checks pass ([record](2026-11-29_roles_and_two_sites.md)) | Pass |
| Usability (SUS) | SUS ≥ 68, task success ≥ 80 % | | Issue #96 |
| Design quality | No critical findings at submission | | Issue #96 |

## Unit tests and coverage

`pytest --cov`, run on Nov 29 on the laptop against `main` after agent 1.1.3 and the summary cache (Python 3.12.1, `pytest-cov` 7.1.0, now pinned in both
`requirements-dev.txt` files). The plan names `services/`; the server keeps that logic in
`app/` modules (alerts, health, push, reports, jobs, …), so the whole `app` package is measured.

| Package | Statements | Missed | Coverage | Tests |
|---|---:|---:|---:|---:|
| `server/app` | 2,571 | 85 | **97 %** | 183 passed |
| `agent/kinlan_agent` | 2,137 | 266 | **88 %** | 220 passed |

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

## Remote command delay

Ten Diagnose runs on the Home site, Nov 29 01:16–01:19 (UTC+8), from the Overview's Diagnose
button on the Infinix (owner, development build). The laptop agent was on home Wi-Fi.
Each run was given 12 s before the next; a screenshot after each shows "Finished … all six
passed".

The server records when the app created the command and when the agent's result arrived:

| Run | Created (UTC) | Finished (UTC) | Server time | Checks passed |
|---:|---|---|---:|---|
| 1 | 17:16:36.007 | 17:16:38.370 | 2.36 s | 6 of 6 |
| 2 | 17:16:59.475 | 17:17:00.754 | 1.28 s | 6 of 6 |
| 3 | 17:17:14.764 | 17:17:15.979 | 1.22 s | 6 of 6 |
| 4 | 17:17:30.073 | 17:17:31.101 | 1.03 s | 6 of 6 |
| 5 | 17:17:45.255 | 17:17:46.204 | 0.95 s | 6 of 6 |
| 6 | 17:18:00.571 | 17:18:02.385 | 1.81 s | 6 of 6 |
| 7 | 17:18:15.801 | 17:18:17.559 | 1.76 s | 6 of 6 |
| 8 | 17:18:31.069 | 17:18:32.771 | 1.70 s | 6 of 6 |
| 9 | 17:18:46.373 | 17:18:47.992 | 1.62 s | 6 of 6 |
| 10 | 17:19:01.951 | 17:19:03.571 | 1.62 s | 6 of 6 |

**Average 1.53 s, longest 2.36 s** (target ≤ 15 s). What the person sees adds the app's own
steps: sending the command (about 0.2 s to Render) and the Diagnose screen's check for the
result, once a second while a run is in progress. So a result is on screen at most about 1.5 s
after the server has it: under 4 s for every run here. Most of the server time is the agent
noticing the command and running the six checks.

## Outage handling

Nov 29, Home site, laptop agent on the home Wi-Fi extender, the Infinix on mobile data so the
push could arrive. A cable was pulled for about 5 minutes, three times. A watcher on the laptop
logged once a second whether 8.8.8.8 and the router (192.168.1.1) answered, and the size of the
agent's outbox; the agent log, the Windows Wi-Fi log and the server's alerts, outages and
per-minute sample counts give the rest.

In every run the router stopped answering too, so from the laptop's side this was the link to
the router going down, not only the provider's line; the agent records it as cause "lan".

### Run 3 (agent 1.1.2): the result

| Check | Measured | Target | |
|---|---|---|---|
| Agent detects the outage | Cut at 18:05:57 UTC (last answer 18:05:56); agent declared it at 18:06:23, start backdated to 18:06:00: **26 s** | ≤ 30 s | Pass |
| "Home is unreachable" push | Alert at 18:08:02: **2 min 5 s** after the cut | ≤ 3 min | Pass |
| Backlog uploaded | Network back 18:11:34; outbox (84 samples, a diagnose, 2 scans) empty by 18:11:52: **18 s** | ≤ 60 s | Pass |
| Lost samples | Every minute of the cut on the server: 6 router samples and 12 internet samples (the backup target is pinged too while the main one fails) | 0 lost | **0 lost**, pass |

Detection takes three failed 10-second ticks by design, so 20–30 s. The agent also ran a
diagnose at once, which uploaded with the backlog.

### Runs 1 and 2: what they found

Each earlier run failed a row, and each failure was an agent bug, fixed and released before the
next run:

| Run | Agent | What happened | Fix |
|---|---|---|---|
| 1, 01:24–01:38 | 1.1.0 | The laptop dropped off the extender for 14 min. Back on Home at 01:37:57, it uploaded only at 01:39:18 (**81 s**): the uploader's backoff had grown to 5 min during the outage, and the command poller's to 1 min. Push: alert 2 min 2 s after the cut. | 1.1.1 (#127): the network or the internet coming back wakes the uploader and the command poller, and the backoff starts over |
| 2, 01:50–01:55 | 1.1.1 | The laptop stayed on the extender ("No internet"). With the router silent, Windows routed through the **Radmin VPN** adapter, whose gateway has a MAC, so the agent decided the laptop had left Home and recorded nothing. Push: 2 min 13 s. Backlog after return: under 1 s (the 1.1.1 fix). | 1.1.2 (#128): if another adapter still holds an address in the site's recorded subnet, the PC hasn't left |
| 3, 02:05–02:11 | 1.1.2 | All four rows pass (above). But the 5-minute scan ran while the VPN had the route: it scanned the VPN's network as Home's, added the laptop's VPN address as a new device, and pointed router pings at 26.0.0.1. | 1.1.3 (#129): scans run only through the site's own router, and a drifted gateway is put back at the next network check |

## Discovery accuracy

The plan compares a scan with the router's DHCP client list on two networks. The home router's
admin password isn't available, so two phone hotspots were used instead: Android lists every
device connected to its hotspot with its MAC address, which makes an exact reference.
`scripts/discovery_snapshot.py` ran the agent's own scan (`discovery.scan`, as the agent runs
it) while the hotspot's connected-devices screen was open, Nov 29.

**Network 1, the Infinix's hotspot** (10.48.65.0/24), 18:35:13 UTC, Scapy ARP, 8.1 s:

| Hotspot's list | Agent's scan | |
|---|---|---|
| PABIBO (the OPPO), `4a:64:0d:4e:7a:3a` | 10.48.65.189, same MAC | Found |
| Korkkk (the laptop), `50:84:92:ee:32:66` | 10.48.65.236, same MAC | Found |
| (the hotspot itself isn't in its own list) | 10.48.65.69, `62:4e:31:ef:e4:17`, marked as the router | Found |

**Network 2, the OPPO's hotspot** (10.185.60.0/24, no SIM, so no internet), 18:39:06 UTC,
Scapy ARP, 8.8 s:

| Hotspot's list | Agent's scan | |
|---|---|---|
| Korkkk (the laptop), `50:84:92:ee:32:66` | 10.185.60.236, same MAC | Found |
| Infinix-GT-30-Pro, `56:1f:2e:0a:86:e1` | 10.185.60.20, same MAC | Found |
| (the hotspot itself) | 10.185.60.210, `22:1e:bb:ed:22:d4`, marked as the router | Found |

**4 of 4 connected devices found (100 %)**, both hotspots identified as the router, and no
device the hotspot didn't list. A scan works without internet, as network 2 shows.

Limits of this result:

- The networks are small (the Infinix's hotspot allows 2 devices, the OPPO's 3), so one missed
  device would have cost 50 %. The ARP sweep asks every address three times, which is what
  makes small and large networks alike; the Wireshark record shows it on the 255-address home
  network.
- Both phones use private (randomised) Wi-Fi MACs, and the scan reported them exactly as the
  hotspots did.
- The agent named only the laptop. The hotspots know the phones' names from DHCP, which the
  agent can't see; it asks the network's DNS for names (PTR), and phone hotspots don't answer
  that. In the app, the person names such devices.

### Found while testing: a phone hotspot can change its MAC

The "Phone" site was paired on Nov 29 with the Infinix's hotspot router at `06:b5:cb:3d:4b:83`.
In this test the same hotspot answered as `62:4e:31:ef:e4:17`, so the agent no longer
recognised it and waited ("isn't on Phone's network"). Earlier the same night the MAC stayed the
same across hotspot restarts; Android can still randomise it. A site on a phone hotspot may
need pairing again after such a change.
