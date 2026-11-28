"""100 router samples with the agent's own ICMP echo, while Windows `ping -n 100` runs (plan §9).

Run from agent/ with PYTHONPATH=. : python ../docs/test-results/scripts/latency_vs_ping.py out.json
"""

import json
import re
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

from kinlan_agent import icmp, netinfo

gw = netinfo.get_netinfo().gateway
N = 100
out: dict = {}


def win_ping():
    p = subprocess.run(
        ["ping", "-n", str(N), gw], capture_output=True, text=True, check=False
    )
    out["ping_raw"] = p.stdout
    out["ping_rtts"] = [int(m) for m in re.findall(r"time[=<](\d+)ms", p.stdout)]


t = threading.Thread(target=win_ping)
t.start()
start = time.perf_counter()
agent = []
for i in range(N):
    r = icmp.echo(gw, 1000)
    agent.append(r.rtt_ms if r.ok else None)
    time.sleep(max(0, start + (i + 1) - time.perf_counter()))  # 1 per second, like ping
t.join()

a = [x for x in agent if x is not None]
w = out["ping_rtts"]
res = {
    "gateway": gw,
    "agent": {
        "sent": N,
        "replies": len(a),
        "avg": statistics.mean(a),
        "median": statistics.median(a),
        "min": min(a),
        "max": max(a),
        "samples": agent,
    },
    "ping": {
        "sent": N,
        "replies": len(w),
        "avg": statistics.mean(w),
        "median": statistics.median(w),
        "min": min(w),
        "max": max(w),
        "samples": w,
    },
}
res["avg_diff_ms"] = abs(res["agent"]["avg"] - res["ping"]["avg"])
Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
for k in ("agent", "ping"):
    s = res[k]
    print(
        f"{k}: {s['replies']}/{N} avg {s['avg']:.2f} median {s['median']} min {s['min']} max {s['max']}"
    )
print(f"average difference {res['avg_diff_ms']:.2f} ms")
print(out["ping_raw"].strip().splitlines()[-1])
