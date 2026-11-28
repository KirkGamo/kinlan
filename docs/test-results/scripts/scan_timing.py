"""Time the agent's two scan methods, 3 runs each, on the current network (plan §9).

Run from agent/ with PYTHONPATH=. : python ../docs/test-results/scripts/scan_timing.py out.json
"""

import json
import sys
import time
from pathlib import Path

from kinlan_agent import discovery, netinfo

info = netinfo.get_netinfo()
print(f"network {info.network} gateway {info.gateway} npcap {bool(info.pcap_iface)}")
rows = []
for method in ("scapy", "windows"):
    for run in range(1, 4):
        try:
            r = discovery.scan(info, method=method, with_hostnames=False)
            rows.append(
                {
                    "method": r.method,
                    "run": run,
                    "ms": r.duration_ms,
                    "devices": len(r.devices),
                    "ips": sorted(d.ip for d in r.devices),
                }
            )
            print(f"{method} run {run}: {r.duration_ms} ms, {len(r.devices)} devices")
        except Exception as exc:  # noqa: BLE001
            print(f"{method} run {run}: failed {type(exc).__name__}: {exc}")
        time.sleep(2)
Path(sys.argv[1]).write_text(
    json.dumps({"network": str(info.network), "rows": rows}, indent=1)
)
