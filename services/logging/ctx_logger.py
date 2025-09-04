from __future__ import annotations

"""Structured logging helpers for image crawling.

Provides:
- log_event_sync: append NDJSON events to logs/image_crawler.ndjson and print to stdout
- log_event_db: optional async write into ImageJobLog (best-effort)
- save_snapshot_html: store HTML snapshot for failed parses
- clean_logs: remove NDJSON and tmp snapshots
- log_step decorator: async decorator to log step start/end/errors
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Awaitable, Callable, Coroutine
import functools

from sqlalchemy.ext.asyncio import AsyncSession


LOG_DIR = Path("logs")
NDJSON_PATH = LOG_DIR / "image_crawler.ndjson"
TMP_DIR = Path("tmp") / "crawl"


def _ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def make_correlation_id() -> str:
    return uuid.uuid4().hex


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def log_event_sync(
    correlation_id: str,
    product_id: Optional[int],
    supplier_id: Optional[int],
    step: str,
    level: str = "INFO",
    message: Optional[str] = None,
    **fields: Any,
) -> None:
    _ensure_dirs()
    obj: Dict[str, Any] = {
        "created_at": _now_iso(),
        "correlation_id": correlation_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "step": step,
        "level": level,
        "message": message,
    }
    obj.update(fields or {})
    line = json.dumps(obj, ensure_ascii=False)
    try:
        with open(NDJSON_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


async def log_event_db(
    db: Optional[AsyncSession],
    *,
    level: str,
    correlation_id: str,
    product_id: Optional[int],
    step: str,
    **fields: Any,
) -> None:
    if db is None:
        return
    try:
        from db.models import ImageJobLog

        data = {"correlation_id": correlation_id, "product_id": product_id, **fields}
        db.add(ImageJobLog(job_name="imagenes_productos", level=level, message=step, data=data))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


def save_snapshot_html(correlation_id: str, slug: str, html: str) -> Optional[str]:
    try:
        _ensure_dirs()
        base = TMP_DIR / correlation_id
        base.mkdir(parents=True, exist_ok=True)
        # sanitize slug
        safe = "".join([c if c.isalnum() else "_" for c in slug])[:100]
        path = base / f"{safe}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return str(path)
    except Exception:
        return None


def save_snapshot_image(correlation_id: str, slug: str, data: bytes, ext: str = "png") -> Optional[str]:
    """Save binary image data under tmp/crawl/<correlation_id>/ and return path."""
    try:
        _ensure_dirs()
        base = TMP_DIR / correlation_id
        base.mkdir(parents=True, exist_ok=True)
        safe = "".join([c if c.isalnum() else "_" for c in slug])[:100]
        path = base / f"{safe}.{ext}"
        with open(path, "wb") as f:
            f.write(data)
        return str(path)
    except Exception:
        return None


def clean_logs() -> None:
    try:
        if NDJSON_PATH.exists():
            NDJSON_PATH.unlink()
    except Exception:
        pass
    try:
        import shutil

        if TMP_DIR.exists():
            shutil.rmtree(TMP_DIR)
    except Exception:
        pass


async def log_event(
    db: AsyncSession,
    *,
    level: str,
    correlation_id: str,
    product_id: Optional[int],
    step: str,
    **fields: Any,
) -> None:
    try:
        from db.models import ImageJobLog

        data = {"correlation_id": correlation_id, "product_id": product_id, **fields}
        db.add(ImageJobLog(job_name="imagenes_productos", level=level, message=step, data=data))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


def log_step(step: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            db: Optional[AsyncSession] = kwargs.get("db")
            cid: str = kwargs.get("correlation_id") or "unknown"
            product_id: Optional[int] = kwargs.get("product_id")
            t0 = datetime.utcnow()
            if db:
                await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step=f"{step}:start")
            try:
                res = await func(*args, **kwargs)
                dur = (datetime.utcnow() - t0).total_seconds() * 1000.0
                if db:
                    await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step=f"{step}:end", duration_ms=dur)
                return res
            except Exception as e:
                dur = (datetime.utcnow() - t0).total_seconds() * 1000.0
                if db:
                    await log_event(db, level="ERROR", correlation_id=cid, product_id=product_id, step=f"{step}:error", duration_ms=dur, error=str(e))
                raise

        return wrapper

    return decorator

