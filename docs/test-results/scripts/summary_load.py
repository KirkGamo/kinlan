"""Plan §9 API performance, local run: seed the dev database to the size of the Home site,
then 50 concurrent GET /sites/{id}/summary against a local uvicorn (one process, as on Render).

Usage, from server/ (PYTHONPATH=.), with a local API started as
`ENV=test uvicorn app.main:app --port 8765` (ENV=test turns the rate limit off):
    python ../docs/test-results/scripts/summary_load.py seed
    python ../docs/test-results/scripts/summary_load.py run http://127.0.0.1:8765 out.json
Seeding adds 120 960 synthetic samples to the dev database; delete them afterwards.
"""

import asyncio
import json
import math
import random
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import get_engine, get_session_factory
from app.models import Site, User
from app.security import create_access_token
from sqlalchemy import select, text


def ids():
    with get_session_factory()() as db:
        return db.scalar(select(User.id)), db.scalar(select(Site.id))


def seed():
    _, site = ids()
    eng = get_engine()
    with eng.begin() as c:
        n = c.execute(
            text("select count(*) from ping_samples where site_id=:s"), {"s": site}
        ).scalar()
        if n > 100_000:
            print("already seeded", n)
            return
        now = datetime.now(UTC)
        rows = []
        for i in range(7 * 8640):  # 7 days, one sample per target every 10 s
            ts = now - timedelta(seconds=10 * i)
            rows.append(
                {
                    "s": site,
                    "t": "gateway",
                    "ip": "192.168.1.1",
                    "ts": ts,
                    "r": round(random.uniform(1, 8), 1),
                    "ok": True,
                }
            )
            ok = random.random() > 0.01
            rows.append(
                {
                    "s": site,
                    "t": "internet",
                    "ip": "8.8.8.8",
                    "ts": ts,
                    "r": round(random.uniform(20, 60), 1) if ok else None,
                    "ok": ok,
                }
            )
        c.execute(
            text(
                "insert into ping_samples (site_id, target, ip, ts, rtt_ms, ok) "
                "values (:s, :t, :ip, :ts, :r, :ok)"
            ),
            rows,
        )
        print("inserted", len(rows))


async def run(base, out):
    import httpx

    user, site = ids()
    h = {"Authorization": f"Bearer {create_access_token(user)}"}
    url = f"{base}/api/v1/sites/{site}/summary"
    async with httpx.AsyncClient(
        headers=h, timeout=30, limits=httpx.Limits(max_connections=100)
    ) as cl:

        async def one():
            t = time.perf_counter()
            r = await cl.get(url)
            return (time.perf_counter() - t) * 1000, r.status_code

        warm = [(await one())[0] for _ in range(5)]
        results = {}
        for conc in (1, 10, 50):
            ms, codes = [], []
            for _ in range(3 if conc == 50 else 1):  # three rounds of 50
                if conc == 1:  # 20 one after another
                    got = [await one() for _ in range(20)]
                else:
                    got = await asyncio.gather(*(one() for _ in range(conc)))
                ms += [g[0] for g in got]
                codes += [g[1] for g in got]
            ms.sort()
            results[conc] = {
                "n": len(ms),
                "codes": sorted(set(codes)),
                "p50": statistics.median(ms),
                "p95": ms[math.ceil(0.95 * len(ms)) - 1],
                "max": ms[-1],
                "mean": statistics.mean(ms),
            }
            print(
                conc,
                {
                    k: (round(v) if isinstance(v, float) else v)
                    for k, v in results[conc].items()
                },
            )
    Path(out).write_text(json.dumps({"warm": warm, "results": results}, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "seed":
        seed()
    else:
        asyncio.run(run(sys.argv[2], sys.argv[3]))
