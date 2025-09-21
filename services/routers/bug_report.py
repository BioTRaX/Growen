# NG-HEADER: Nombre de archivo: bug_report.py
# NG-HEADER: Ubicación: services/routers/bug_report.py
# NG-HEADER: Descripción: Router para recibir reportes de errores desde el frontend y registrarlos en BugReport.log
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para reporte de bugs desde UI.

- POST /bug-report: recibe mensaje y metadatos y los registra en logs/BugReport.log
"""
from __future__ import annotations

import json
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any
import base64
import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from services.auth import current_session, SessionData
from services.integrations.notion_errors import ErrorEvent, create_or_update_card  # type: ignore
from services.integrations.notion_client import load_notion_settings  # type: ignore

MAX_SCREENSHOT_BYTES = 1_200_000  # ~1.2 MB, defensa adicional en servidor


router = APIRouter(prefix="/bug-report", tags=["bug-report"])  # no requiere CSRF, solo escritura de logs


_bug_logger: logging.Logger | None = None


def _get_bug_logger() -> logging.Logger:
    global _bug_logger
    if _bug_logger is not None:
        return _bug_logger
    logger = logging.getLogger("BugReport")
    logger.setLevel(logging.INFO)
    # Configurar handler a logs/BugReport.log con rotación
    root = Path(__file__).resolve().parents[2]
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "BugReport.log"
    try:
        # delay=True evita abrir el archivo hasta el primer log
        handler = RotatingFileHandler(str(path), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8", delay=True)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        # Evitar duplicar handlers si se importa más de una vez
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == handler.baseFilename for h in logger.handlers):
            logger.addHandler(handler)
        logger.propagate = False
    except Exception:
        # Si falla, quedará solo consola; no levantamos excepción para no romper UX
        pass
    _bug_logger = logger
    return logger


class BugReportIn(BaseModel):  # type: ignore
    message: str = Field(..., min_length=1, max_length=8000)
    url: str | None = None
    user_agent: str | None = None
    stack: str | None = None
    cid: str | None = None
    context: dict[str, Any] | None = None
    # Captura de pantalla opcional (data URL: image/png o image/jpeg)
    screenshot: str | None = None


@router.post("")
async def post_bug_report(payload: BugReportIn, request: Request, sess: SessionData = Depends(current_session)) -> dict[str, Any]:  # type: ignore
    """Recibe reportes desde el botón flotante y los persiste en BugReport.log.

    Responde 200 con un identificador simple para referencia.
    """
    logger = _get_bug_logger()
    try:
        # Construimos un registro JSON para facilitar parseo
        # Timestamp UTC y GMT-3 (Argentina) para trazabilidad
        utc_now = datetime.utcnow()
        gmt3 = utc_now.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=-3)))
        record = {
            "ts": utc_now.isoformat(timespec="seconds") + "Z",
            "ts_gmt3": gmt3.isoformat(timespec="seconds"),
            "message": (payload.message or "").strip()[:8000],
            "url": payload.url or request.headers.get("Referer"),
            "user_agent": payload.user_agent or request.headers.get("user-agent"),
            "stack": (payload.stack or "")[:8000] or None,
            "cid": payload.cid or request.headers.get("X-Correlation-Id") or request.headers.get("x-correlation-id"),
            "role": getattr(sess, "role", None),
            "ip": getattr(request.client, "host", None),
            "context": payload.context or {},
        }
        # Id simple derivado de timestamp para devolver al cliente
        rid = f"br-{int(datetime.utcnow().timestamp())}"
        record["id"] = rid

        # Guardar captura si se envió en data URL
        if payload.screenshot:
            try:
                m = re.match(r"^data:(image\/(png|jpeg));base64,(.+)$", payload.screenshot)
                if m:
                    mime = m.group(1)
                    b64 = m.group(3)
                    img = base64.b64decode(b64)
                    if len(img) > MAX_SCREENSHOT_BYTES:
                        record["screenshot_error"] = f"too_large>{MAX_SCREENSHOT_BYTES}"
                    else:
                        root = Path(__file__).resolve().parents[2]
                        outdir = root / "logs" / "bugreport_screenshots"
                        outdir.mkdir(parents=True, exist_ok=True)
                        ext = ".png" if mime.endswith("png") else ".jpg"
                        outpath = outdir / f"{rid}{ext}"
                        with open(outpath, "wb") as fh:
                            fh.write(img)
                        # No incluir la imagen en el log; solo metadatos
                        record["screenshot_file"] = f"bugreport_screenshots/{outpath.name}"
                        record["screenshot_bytes"] = len(img)
                        record["screenshot_mime"] = mime
                else:
                    record["screenshot_error"] = "invalid_data_url"
            except Exception as se:  # pragma: no cover
                record["screenshot_error"] = f"save_failed: {se}"
        logger.info(json.dumps(record, ensure_ascii=False))

        # Notion: crear/actualizar tarjeta si la feature está activada
        try:
            cfg = load_notion_settings()
            if cfg.enabled and cfg.errors_db:
                # Derivar sección a partir de la URL del cliente (Compras, Stock, Productos)
                url_val = record.get("url") or ""
                ev = ErrorEvent(
                    servicio="frontend" if (record.get("url") or "").startswith("http") else "api",
                    entorno=os.getenv("ENV", "dev"),
                    url=url_val,
                    codigo=None,
                    mensaje=record.get("message") or "",
                    stacktrace=record.get("stack"),
                    correlation_id=record.get("cid"),
                    etiquetas=["bugreport"],
                    seccion=(
                        "Compras" if ("/compras" in url_val or "/purchases" in url_val)
                        else "Stock" if ("/stock" in url_val or "/inventario" in url_val)
                        else "Productos" if ("/productos" in url_val or "/products" in url_val)
                        else None
                    ),
                )
                # ejecutar en background sin bloquear la respuesta
                import asyncio
                asyncio.create_task(asyncio.to_thread(create_or_update_card, ev))
        except Exception:
            logging.getLogger("growen").warning("No se pudo encolar tarjeta Notion para bug-report", exc_info=True)

        return {"status": "ok", "id": rid}
    except Exception as e:
        # fallback: loguear al root para no perder el reporte en caso de fallo de handler
        logging.getLogger("growen").exception("No se pudo registrar BugReport: %s", e)
        return {"status": "error", "detail": "No se pudo registrar el reporte"}
