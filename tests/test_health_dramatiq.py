#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_health_dramatiq.py
# NG-HEADER: Ubicación: tests/test_health_dramatiq.py
# NG-HEADER: Descripción: Verifica el mapeo de claves Redis de Dramatiq 2.x.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import time

import pytest

from services.routers import health
from services.routers.health import _dramatiq_health_details


class FakeRedis:
    def __init__(self):
        self.lists = {"dramatiq:market": 2}
        self.sorted_sets = {
            "dramatiq:market.DQ": 1,
            "dramatiq:__heartbeats__": [int(time.time() * 1000)],
        }

    def llen(self, key):
        return self.lists.get(key, 0)

    def zcard(self, key):
        value = self.sorted_sets.get(key, [])
        return len(value) if isinstance(value, list) else value

    def exists(self, key):
        return key in self.lists or key in self.sorted_sets

    def zcount(self, key, minimum, _maximum):
        return sum(score >= minimum for score in self.sorted_sets.get(key, []))


@pytest.mark.no_db
def test_dramatiq_health_uses_v2_queue_and_heartbeat_keys():
    details = _dramatiq_health_details(FakeRedis())

    assert details["queues"]["market"] == {
        "exists": True,
        "size": 3,
        "ready": 2,
        "delayed": 1,
    }
    assert details["workers"]["count"] == 1


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_generic_service_health_routes_market_worker_to_dedicated_probe(monkeypatch):
    expected = {"service": "market_worker", "ok": True, "broker_ok": True}

    async def fake_market_health():
        return expected

    monkeypatch.setattr(health, "health_market_worker", fake_market_health)

    assert await health.health_service("market_worker") == expected
