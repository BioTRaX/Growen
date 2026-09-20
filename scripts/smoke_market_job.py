#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_market_job.py
# NG-HEADER: Ubicación: scripts/smoke_market_job.py
# NG-HEADER: Descripción: Smoke idempotente de job persistente y consumo del worker Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import SessionLocal
from services.market.jobs import TERMINAL_STATUSES, create_update_job
from db.models import MarketUpdateItem
from workers.market_scraping import process_market_item_task


async def main() -> None:
    async with SessionLocal() as db:
        first = await create_update_job(db, [1], trigger="smoke")
        second = await create_update_job(db, [1], trigger="smoke_duplicate")
    first_item = first.items[0]
    second_item = second.items[0]
    if first_item.item_id is None or first_item.deduplicated:
        raise RuntimeError("El primer pedido no creó un item procesable")
    if not second_item.deduplicated or second_item.item_id != first_item.item_id:
        raise RuntimeError("El pedido duplicado no referenció el trabajo activo")

    process_market_item_task.send(first_item.item_id)
    for _ in range(45):
        await asyncio.sleep(1)
        async with SessionLocal() as db:
            item = await db.get(MarketUpdateItem, first_item.item_id)
            if item and item.status in TERMINAL_STATUSES:
                print(
                    f"[OK] item={item.id} deduplicated=true terminal={item.status} "
                    f"sources={item.sources_total}"
                )
                return
    raise TimeoutError("El worker Mercado no llevó el item a estado terminal")


if __name__ == "__main__":
    asyncio.run(main())
