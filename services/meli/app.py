#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: app.py
# NG-HEADER: Ubicación: services/meli/app.py
# NG-HEADER: Descripción: Gateway FastAPI público y mínimo para callback y webhooks de Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Superficie exclusiva publicada por Cloudflare Tunnel."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from services.meli.client import MeliClient
from services.meli.crypto import TokenCipher
from services.meli.oauth import MeliOAuthError, complete_authorization
from services.meli.settings import MeliRuntimeConfig, load_meli_runtime_config
from services.meli.webhooks import MeliWebhookError, ingest_notification


logger = logging.getLogger(__name__)


def _dispatch_job(job_id: str) -> None:
    """Entrega best-effort posterior al response; el outbox cubre fallos de Redis."""
    try:
        from workers.meli_sync import process_meli_job

        process_meli_job.send(job_id)
    except Exception:
        pass


def create_meli_app(
    *,
    config: MeliRuntimeConfig | None = None,
    cipher: TokenCipher | None = None,
    client: Any | None = None,
) -> FastAPI:
    """Crea el gateway; en runtime carga secretos antes de comenzar a escuchar."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime_config = config or load_meli_runtime_config()
        runtime_cipher = cipher or TokenCipher.from_runtime()
        runtime_client = client or MeliClient(runtime_config)
        app.state.meli_config = runtime_config
        app.state.meli_cipher = runtime_cipher
        app.state.meli_client = runtime_client
        yield
        if client is None:
            await runtime_client.aclose()

    app = FastAPI(
        title="Growen MeLi Gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    # ASGITransport sin gestión de lifespan se usa en unit tests focales.
    if config is not None:
        app.state.meli_config = config
        app.state.meli_cipher = cipher
        app.state.meli_client = client

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready(db: AsyncSession = Depends(get_session)) -> dict[str, str]:
        await db.execute(text("SELECT 1"))
        if not getattr(app.state, "meli_config", None):
            raise HTTPException(status_code=503, detail="meli_configuration_unavailable")
        return {"status": "ready"}

    @app.get("/integrations/meli/oauth/callback", response_class=HTMLResponse)
    async def oauth_callback(
        request: Request,
        code: str,
        state: str,
        db: AsyncSession = Depends(get_session),
    ) -> HTMLResponse:
        try:
            await complete_authorization(
                db,
                state=state,
                code=code,
                config=request.app.state.meli_config,
                cipher=request.app.state.meli_cipher,
                client=request.app.state.meli_client,
            )
        except (MeliOAuthError, KeyError, ValueError) as exc:
            # Lista cerrada: nunca registrar argumentos arbitrarios, códigos ni tokens.
            reason = "invalid_response"
            if isinstance(exc, MeliOAuthError) and str(exc) in {
                "meli_oauth_state_invalid", "meli_oauth_state_already_used",
                "meli_oauth_state_expired", "meli_oauth_seller_mismatch",
            }:
                reason = str(exc)
            elif isinstance(exc, KeyError) and exc.args and exc.args[0] in {
                "access_token", "refresh_token", "expires_in", "id",
            }:
                reason = "missing_" + exc.args[0]
            logger.warning("meli_oauth_callback_failed reason=%s", reason)
            message = "<h1>No se pudo completar la autorización</h1>"
            if reason == "missing_refresh_token":
                message = (
                    "<h1>Falta autorizar el acceso sin conexión</h1>"
                    "<p>Mercado Libre no entregó el token de renovación. "
                    "Habilita Acceso Offline en la aplicación y vuelve a autorizar "
                    "desde un enlace nuevo de Growen.</p>"
                )
            elif reason == "meli_oauth_state_expired":
                message = "<h1>Autorización vencida</h1><p>Solicita un enlace nuevo en Growen.</p>"
            elif reason == "meli_oauth_state_already_used":
                message = "<h1>Este enlace ya fue utilizado</h1>"
            return HTMLResponse(
                message,
                status_code=400,
                headers={"Cache-Control": "no-store"},
            )
        return HTMLResponse(
            "<h1>Mercado Libre fue conectado correctamente</h1>",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/integrations/meli/webhook")
    async def webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_session),
    ) -> dict[str, bool]:
        content_type = request.headers.get("content-type", "").lower()
        if not content_type.startswith("application/json"):
            raise HTTPException(status_code=415, detail="content_type_not_supported")
        maximum = request.app.state.meli_config.webhook_max_bytes
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > maximum:
            raise HTTPException(status_code=413, detail="webhook_too_large")
        body = await request.body()
        if len(body) > maximum:
            raise HTTPException(status_code=413, detail="webhook_too_large")
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError
            result = await ingest_notification(
                db, payload=payload, config=request.app.state.meli_config
            )
        except (json.JSONDecodeError, ValueError, MeliWebhookError):
            raise HTTPException(status_code=400, detail="webhook_invalid") from None
        if result.job_id and not result.duplicate:
            background_tasks.add_task(_dispatch_job, result.job_id)
        return {"accepted": True, "duplicate": result.duplicate}

    return app


app = create_meli_app()
