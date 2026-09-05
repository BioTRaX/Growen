#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: meli_sync.py
# NG-HEADER: Ubicación: workers/meli_sync.py
# NG-HEADER: Descripción: Actores Dramatiq exclusivos de sincronización transaccional Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Worker deliberadamente separado de las colas analíticas."""

from __future__ import annotations

import asyncio
import os
import threading
import time

import dramatiq
from dramatiq.middleware import Middleware
from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from agent_core.config import settings
from services import jobs as _jobs_bootstrap  # noqa: F401
from services.meli.client import MeliClient
from services.meli.crypto import TokenCipher
from db.models import MeliSyncJob
from services.meli.jobs import process_job
from services.meli.settings import load_meli_runtime_config


async def _run_job(job_id: str) -> None:
    config = load_meli_runtime_config()
    client = MeliClient(config)
    engine = create_async_engine(
        os.getenv("DB_URL") or settings.db_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            await process_job(
                db,
                job_id=job_id,
                client=client,
                cipher=TokenCipher.from_runtime(),
            )
    finally:
        await client.aclose()
        await engine.dispose()


class MeliHeartbeatMiddleware(Middleware):
    """Publica un heartbeat de consumidor aun cuando la cola esté ociosa."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def after_worker_boot(self, broker, worker) -> None:  # noqa: ANN001
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

        def pulse() -> None:
            client = Redis.from_url(redis_url, decode_responses=True)
            pulse_count = 0
            while not self._stop.wait(10):
                try:
                    client.set("growen:meli_sync:heartbeat", str(int(time.time())), ex=35)
                    pulse_count += 1
                    if pulse_count % 3 == 1:
                        reconcile_meli_jobs.send(limit=100)
                except Exception:
                    continue

        self._thread = threading.Thread(target=pulse, name="meli-heartbeat", daemon=True)
        self._thread.start()

    def before_worker_shutdown(self, broker, worker) -> None:  # noqa: ANN001
        self._stop.set()


dramatiq.get_broker().add_middleware(MeliHeartbeatMiddleware())


@dramatiq.actor(queue_name="meli_sync", max_retries=4, min_backoff=5_000, time_limit=120_000)
def process_meli_job(job_id: str) -> None:
    asyncio.run(_run_job(job_id))


async def _reconcile(limit: int) -> list[str]:
    engine = create_async_engine(os.getenv("DB_URL") or settings.db_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            return list(
                (
                    await db.execute(
                        select(MeliSyncJob.id)
                        .where(MeliSyncJob.status == "queued")
                        .order_by(MeliSyncJob.created_at.asc())
                        .limit(limit)
                    )
                ).scalars()
            )
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="meli_sync", max_retries=0, time_limit=60_000)
def reconcile_meli_jobs(limit: int = 100) -> int:
    job_ids = asyncio.run(_reconcile(limit))
    for job_id in job_ids:
        process_meli_job.send(job_id)
    return len(job_ids)
