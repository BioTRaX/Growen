#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: meli_worker_health.py
# NG-HEADER: Ubicación: scripts/meli_worker_health.py
# NG-HEADER: Descripción: Healthcheck del consumidor dedicado MeLi mediante heartbeat Redis.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os
import time

from redis import Redis


def main() -> int:
    client = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    heartbeat = client.get("growen:meli_sync:heartbeat")
    if heartbeat is None or time.time() - int(heartbeat) > 35:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
