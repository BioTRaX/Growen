#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: chat_rollout.py
# NG-HEADER: Ubicación: workers/chat_rollout.py
# NG-HEADER: Descripción: Controlador periódico de gates y transiciones de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import asyncio
import logging
import os
import sys

from db.session import SessionLocal
from services.chat.rollout import evaluate_auto_advance

logger = logging.getLogger("growen.chat.rollout")


async def run() -> None:
    interval = max(60, int(os.getenv("CHAT_ROLLOUT_INTERVAL_SECONDS", "300")))
    while True:
        try:
            async with SessionLocal() as db:
                result = await evaluate_auto_advance(db)
            logger.info("chat.rollout decision=%s phase=%s code=%s", result.get("decision"), result.get("phase"), result.get("code"))
        except Exception as exc:
            logger.error("chat.rollout evaluation_failed error=%s", type(exc).__name__)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run(), loop_factory=loop_factory)
