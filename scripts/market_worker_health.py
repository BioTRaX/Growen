#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: market_worker_health.py
# NG-HEADER: Ubicación: scripts/market_worker_health.py
# NG-HEADER: Descripción: Healthcheck del broker y heartbeat específico del worker Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Finaliza con error si Redis o el heartbeat de Mercado no están vigentes."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

import redis


def main() -> int:
    client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    if not client.ping():
        return 1
    raw = client.get("growen:market_worker:heartbeat")
    if not raw:
        return 1
    payload = json.loads(raw)
    timestamp = datetime.fromisoformat(payload["timestamp"])
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - timestamp).total_seconds()
    return 0 if payload.get("queue") == "market" and age <= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
