# Roles and two sites: test record (Nov 26–29, 2026)

Issue #94 (definition of done item 4): a second network with its own agent, three accounts with
the owner, admin and viewer roles on both sites, and the role matrix of technical plan §4.2.

## Setup

| | |
|---|---|
| Circle | Gamo Home (household) |
| Sites | **Home**: 192.168.1.0/24, router 192.168.1.1 (`64:f8:8a:3a:ca:cf`). **Phone**: the owner's own phone hotspot, 10.48.65.0/24, router 10.48.65.69 (`06:b5:cb:3d:4b:83`) |
| Agent | KinLAN Agent 1.1.0 on one laptop, paired with both sites (#122), running as the SYSTEM startup task |
| Owner | the developer, on an Infinix (development build) |
| Admin | a second member, on an OPPO (standalone APK 1.0.0) |
| Viewer | a third account, on the web app (kinlan-web.onrender.com) |

The hotspot stands in for the office or lab network: it is the owner's own network, so the
consent rule is met. Account e-mail addresses are left out of this record.

## One laptop, two sites (agent log, Nov 29)

| Time | Event | Agent |
|---|---|---|
| 00:01:05 | Laptop joins the hotspot | Home: "isn't on Home's network right now (it's on 10.48.65.0/24)… Waiting" |
| 00:02:50 | Hotspot paired as a second site; the task restarts | Home waiting; Phone "on Phone's network… monitoring it" |
| 00:03:23 | First upload for Phone | 2 batches accepted (HTTP 200); the app shows "Phone is connected… We found 2 devices" |
| 00:03:24 | Home silent > 2 min | "Home is unreachable" push on both phones (as intended: the laptop left) |
| 00:04:40 | Laptop back on home Wi-Fi | Home monitoring; Phone waiting 3 s later |
| 00:08:11 | Hotspot turned off and on, laptop rejoins | Phone monitoring again, same router MAC: the phone keeps its hotspot MAC between sessions |

Also seen on Nov 27: a bed-and-breakfast Wi-Fi that uses 192.168.1.0/24 with router 192.168.1.1,
like Home. The agent treated it as another network (different router MAC) and skipped the port
check, so its devices never reached Home.

## Role matrix (plan §4.2)

Automated: `server/tests/test_role_matrix.py`, 21 cases (each row for each role against the API;
non-allowed roles get 403 `forbidden`). Passes in CI.

In the app, Nov 29, all three accounts in Gamo Home:

| Check | Owner | Admin | Viewer | Result |
|---|:-:|:-:|:-:|---|
| Both sites visible, with live status | ✅ | ✅ | ✅ | Pass |
| Diagnose on Overview | ✅ | ✅ | — | Pass |
| Acknowledge alerts | ✅ | ✅ | — | Pass |
| Scan, rename and ping devices | ✅ | ✅ | — | Pass |
| Add a site | ✅ | ✅ | — | Pass |
| Alert thresholds | edit | edit | read-only | Pass (the viewer's new-device switch is disabled) |
| Invite a member, change roles | ✅ | — | — | Pass |

## Found and fixed

- **Members and site statuses stayed stale** (#123): Settings showed 1 member after two had
  joined, and old site statuses after the laptop changed networks. The app now refetches when it
  returns to the foreground and when Settings is opened, and the Overview's live status updates
  the sites list. The OPPO's APK 1.0.0 predates the fix and still shows 2 members until the next
  APK build.
- **Viewer copy**: the Overview told a viewer to "acknowledge" alerts and "mark as trusted",
  which a viewer can't do, and Settings said "you're the viewer". Now: "Read them in Alerts",
  "An admin can name them and mark them as trusted", and "you're a viewer".
- **Waiting site noticed its network late** (#122): a site that wasn't active only checked the
  network once a minute; it now checks the route at every 10-second tick.
