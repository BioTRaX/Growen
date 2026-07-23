#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: telegram_polling.py
# NG-HEADER: Ubicación: workers/telegram_polling.py
# NG-HEADER: Descripción: Worker Telegram polling acotado, idempotente y privado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Long polling Telegram con deduplicación persistente y backpressure."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import signal
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agent_core.config import settings
from db.models import TelegramUpdate
from db.session import SessionLocal
from services.chat.external_identity import subject_hmac
from services.chat.telegram_handler import handle_telegram_message
from services.notifications.telegram import send_message as telegram_send

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
HEALTH_FILE = LOGS_DIR / "telegram_health.json"
OFFSET_FILE = LOGS_DIR / "telegram_offset.txt"

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOGS_DIR / "worker_telegram_polling.log", encoding="utf-8")],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("growen.telegram.polling")

API_BASE = "https://api.telegram.org"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
QUEUE_SIZE = max(1, int(os.getenv("TELEGRAM_POLLING_QUEUE_SIZE", "100")))
CONCURRENCY = max(1, int(os.getenv("TELEGRAM_POLLING_CONCURRENCY", "8")))
POLL_TIMEOUT = max(1, int(os.getenv("TELEGRAM_POLLING_TIMEOUT", "30")))
RETRY_DELAY = max(1, int(os.getenv("TELEGRAM_POLLING_RETRY_DELAY", "5")))


@dataclass
class WorkerHealth:
    status: str = "starting"
    last_poll_at: str | None = None
    last_success_at: str | None = None
    backlog: int = 0
    consecutive_errors: int = 0
    duplicates: int = 0
    processed: int = 0


health = WorkerHealth()


def _write_health() -> None:
    temp = HEALTH_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(asdict(health), ensure_ascii=False), encoding="utf-8")
    temp.replace(HEALTH_FILE)


def _read_offset() -> int | None:
    try:
        value = OFFSET_FILE.read_text(encoding="utf-8").strip()
        return int(value) if value.isdigit() else None
    except OSError:
        return None


def _write_offset(update_id: int) -> None:
    temp = OFFSET_FILE.with_suffix(".tmp")
    temp.write_text(str(update_id), encoding="utf-8")
    temp.replace(OFFSET_FILE)


async def _telegram_call(method: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API_BASE}/bot{TOKEN}/{method}"
    delay = RETRY_DELAY
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 10, trust_env=False) as client:
                response = await client.get(url, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = int(response.headers.get("Retry-After", delay))
                await asyncio.sleep(retry_after + random.random())
                delay = min(delay * 2, 60)
                continue
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError("telegram_api_rejected")
            return payload
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == 4:
                raise
            await asyncio.sleep(delay + random.random())
            delay = min(delay * 2, 60)
    raise RuntimeError("telegram_retry_exhausted")


async def _verify_polling_mode() -> str:
    me = (await _telegram_call("getMe")).get("result") or {}
    bot_id = me.get("id")
    if bot_id is None:
        raise RuntimeError("telegram_bot_identity_missing")
    webhook = (await _telegram_call("getWebhookInfo")).get("result") or {}
    if webhook.get("url"):
        raise RuntimeError("telegram_webhook_active")
    return subject_hmac("telegram_bot", bot_id)


async def _claim_update(bot_hash: str, update_id: int) -> bool:
    async with SessionLocal() as db:
        existing = await db.scalar(
            select(TelegramUpdate).where(
                TelegramUpdate.bot_id_hash == bot_hash,
                TelegramUpdate.update_id == update_id,
            )
        )
        if existing and existing.status in {"succeeded", "failed", "skipped"}:
            health.duplicates += 1
            return False
        if existing:
            existing.status = "processing"
            existing.attempts += 1
            existing.processing_at = datetime.utcnow()
            existing.error_code = None
        else:
            db.add(
                TelegramUpdate(
                    bot_id_hash=bot_hash,
                    update_id=update_id,
                    status="processing",
                    attempts=1,
                    processing_at=datetime.utcnow(),
                )
            )
        try:
            await db.commit()
            return True
        except IntegrityError:
            await db.rollback()
            health.duplicates += 1
            return False


async def _finish_update(bot_hash: str, update_id: int, status: str, error_code: str | None = None) -> None:
    async with SessionLocal() as db:
        record = await db.scalar(
            select(TelegramUpdate).where(
                TelegramUpdate.bot_id_hash == bot_hash,
                TelegramUpdate.update_id == update_id,
            )
        )
        if record:
            record.status = status
            record.error_code = error_code
            record.completed_at = datetime.utcnow()
            await db.commit()


async def _process_update(update: dict[str, Any], bot_hash: str) -> None:
    update_id = update.get("update_id")
    if not isinstance(update_id, int) or not await _claim_update(bot_hash, update_id):
        return
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = chat.get("id")
    sender_id = sender.get("id")
    text = str(message.get("text") or "").strip()
    photo = message.get("photo") or []
    image_file_id = photo[-1].get("file_id") if isinstance(photo, list) and photo else None
    if not chat_id or not sender_id or (not text and not image_file_id):
        await _finish_update(bot_hash, update_id, "skipped", "unsupported_payload")
        return
    try:
        async with SessionLocal() as db:
            answer = await handle_telegram_message(
                text=text,
                chat_id=str(chat_id),
                telegram_user_id=sender_id,
                chat_type=str(chat.get("type") or "private"),
                db=db,
                image_file_id=image_file_id,
            )
        if not await telegram_send(answer, chat_id=str(chat_id)):
            raise RuntimeError("telegram_send_failed")
        await _finish_update(bot_hash, update_id, "succeeded")
        health.processed += 1
        health.last_success_at = datetime.utcnow().isoformat()
    except (PermissionError, ValueError):
        await _finish_update(bot_hash, update_id, "failed", "request_rejected")
    except Exception as exc:
        logger.warning("Update no completado error=%s", type(exc).__name__)
        await _finish_update(bot_hash, update_id, "failed", "processing_failure")


async def _queue_worker(
    queue: asyncio.Queue[dict[str, Any] | None],
    bot_hash: str,
    subject_locks: dict[str, asyncio.Lock],
) -> None:
    while True:
        update = await queue.get()
        try:
            if update is None:
                return
            message = update.get("message") or update.get("edited_message") or {}
            sender_id = (message.get("from") or {}).get("id")
            lock_key = subject_hmac("telegram", sender_id) if sender_id is not None else "invalid"
            lock = subject_locks.setdefault(lock_key, asyncio.Lock())
            async with lock:
                await _process_update(update, bot_hash)
        finally:
            queue.task_done()


async def run_polling() -> None:
    if not settings.telegram_enabled or not settings.telegram_public_bot_enabled:
        logger.warning("Worker Telegram deshabilitado por feature flag")
        return
    if settings.telegram_transport != "polling" or not TOKEN:
        raise RuntimeError("telegram_polling_configuration_invalid")

    bot_hash = await _verify_polling_mode()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=QUEUE_SIZE)
    subject_locks: dict[str, asyncio.Lock] = {}
    workers = [asyncio.create_task(_queue_worker(queue, bot_hash, subject_locks)) for _ in range(CONCURRENCY)]
    offset = _read_offset()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    health.status = "running"
    _write_health()
    logger.info("Worker Telegram polling iniciado queue=%s concurrency=%s", QUEUE_SIZE, CONCURRENCY)
    try:
        while not stop.is_set():
            try:
                result = await _telegram_call(
                    "getUpdates",
                    params={
                        "timeout": POLL_TIMEOUT,
                        "offset": offset + 1 if offset is not None else None,
                        "allowed_updates": json.dumps(["message", "edited_message"]),
                    },
                )
                health.last_poll_at = datetime.utcnow().isoformat()
                updates = result.get("result") or []
                for update in updates:
                    await queue.put(update)
                    health.backlog = queue.qsize()
                if updates:
                    await queue.join()
                    terminal_ids = [item.get("update_id") for item in updates if isinstance(item.get("update_id"), int)]
                    if terminal_ids:
                        offset = max(terminal_ids)
                        _write_offset(offset)
                health.consecutive_errors = 0
                health.backlog = queue.qsize()
                _write_health()
            except Exception as exc:
                health.consecutive_errors += 1
                health.status = "degraded"
                _write_health()
                logger.warning("Fallo de polling error=%s", type(exc).__name__)
                await asyncio.sleep(min(RETRY_DELAY * (2 ** min(health.consecutive_errors, 4)) + random.random(), 60))
                health.status = "running"
    finally:
        await queue.join()
        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers, return_exceptions=True)
        health.status = "stopped"
        _write_health()


def main() -> None:
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.error("Worker Telegram detenido error=%s", type(exc).__name__)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
