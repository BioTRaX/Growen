# NG-HEADER: Nombre de archivo: __init__.py
# NG-HEADER: Ubicación: services/jobs/__init__.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker


_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
if os.getenv("RUN_INLINE_JOBS", "0") == "1":
	# Development mode: avoid touching Redis entirely
	dramatiq.set_broker(StubBroker())
else:
	broker = RedisBroker(url=_redis_url)
	dramatiq.set_broker(broker)

