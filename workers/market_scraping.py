#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: market_scraping.py
# NG-HEADER: Ubicación: workers/market_scraping.py
# NG-HEADER: Descripción: Worker para scraping de precios de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os
import sys
import logging
import asyncio
import json
import hashlib
import re
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from urllib.parse import urlparse

# FIX: Windows ProactorEventLoop no soporta psycopg async
# Debe ejecutarse ANTES de cualquier import que use asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import dramatiq  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

# Inicializa el RedisBroker antes de registrar los actores de este módulo.
from services import jobs as _jobs_bootstrap  # noqa: F401
from db.models import (
    CanonicalKnowledgeAsset,
    CanonicalKnowledgeAssetCapability,
    CanonicalKnowledgeLabel,
    CanonicalKnowledgeLocation,
    CanonicalProduct,
    MarketSource,
    MarketUpdateJob,
    MarketUpdateSourceResult,
)
from services.market.jobs import claim_item, complete_item, expire_stale_items
from services.market.pipeline import discover_candidates_for_item
from services.market.pricing import persist_source_observation, recompute_market_reference
from workers.scraping import scrape_static_price
from workers.scraping.static_scraper import NetworkError, PriceNotFoundError
from agent_core.config import settings

# Configuración de logging con formato detallado
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuración de base de datos - usar settings como en db/session.py
DB_URL = os.getenv("DB_URL") or settings.db_url
# Cada actor Dramatiq ejecuta su propio event loop dentro de un thread. Un pool
# async global conserva locks ligados al loop que abrió la conexión anterior;
# NullPool crea una conexión por sesión y evita compartir estado entre loops.
engine = create_async_engine(DB_URL, future=True, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_CURRENT_ITEM_ID: int | None = None


def _http_status_from_error(error: str | None) -> int | None:
    """Extrae un HTTP seguro del error normalizado de los scrapers."""
    if not error:
        return None
    match = re.search(r"\bHTTP\s+([1-5][0-9]{2})\b", error, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _source_failure(
    *,
    price: Decimal | None,
    currency_is_ars: bool,
    is_candidate: bool,
    delivery_confirmed: bool,
    error: str | None,
) -> tuple[str, str, bool, int | None]:
    """Prioriza la causa técnica que impidió obtener un precio efectivo."""
    http_status = _http_status_from_error(error)
    if price is None:
        code = f"http_{http_status}" if http_status else "scrape_failed"
        retryable = http_status is None or http_status in {408, 425, 429} or http_status >= 500
        return code, (error or "No se pudo obtener el precio")[:1000], retryable, http_status
    if not currency_is_ars:
        return "currency_not_ars", "La fuente devolvió una moneda distinta de ARS", False, http_status
    if is_candidate and not delivery_confirmed:
        return (
            "argentina_delivery_unconfirmed",
            "No se confirmó entrega en Argentina",
            False,
            http_status,
        )
    return "validation_failed", "La fuente no superó la validación", False, http_status


def _eligible_market_sources_query(product_id: int):
    """Selecciona sólo conocimiento confirmado y habilitado para precios."""
    return (
        select(MarketSource)
        .join(CanonicalKnowledgeAsset, CanonicalKnowledgeAsset.id == MarketSource.asset_id)
        .join(
            CanonicalKnowledgeLocation,
            and_(
                CanonicalKnowledgeLocation.asset_id == CanonicalKnowledgeAsset.id,
                CanonicalKnowledgeLocation.is_primary.is_(True),
            ),
        )
        .join(
            CanonicalKnowledgeLabel,
            and_(
                CanonicalKnowledgeLabel.asset_id == CanonicalKnowledgeAsset.id,
                CanonicalKnowledgeLabel.label == "market",
            ),
        )
        .join(
            CanonicalKnowledgeAssetCapability,
            and_(
                CanonicalKnowledgeAssetCapability.asset_id == CanonicalKnowledgeAsset.id,
                CanonicalKnowledgeAssetCapability.capability_code == "price",
                CanonicalKnowledgeAssetCapability.enabled.is_(True),
            ),
        )
        .where(
            CanonicalKnowledgeAsset.canonical_product_id == product_id,
            CanonicalKnowledgeAsset.status == "confirmed",
            MarketSource.is_active.is_(True),
            MarketSource.validation_status != "rejected",
            MarketSource.currency == "ARS",
            MarketSource.ars_confirmed.is_(True),
            MarketSource.argentina_delivery_confirmed.is_(True),
            MarketSource.source_type != "manual",
            CanonicalKnowledgeLocation.url.is_not(None),
        )
        .order_by(MarketSource.is_mandatory.desc(), MarketSource.id)
    )


def _redis_client():
    import redis
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def _domain_lock(url: str):
    hostname = (urlparse(url).hostname or "unknown").lower()
    digest = hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:24]
    return _redis_client().lock(
        f"growen:market_worker:domain:{digest}",
        timeout=90,
        blocking_timeout=60,
    )


def _structured_event(event: str, **fields: Any) -> None:
    print(json.dumps({
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "market_worker",
        "event": event,
        **fields,
    }, ensure_ascii=False, default=str), flush=True)


def _heartbeat_loop() -> None:
    if os.getenv("MARKET_HEARTBEAT_ENABLED", "0") != "1":
        return
    client = _redis_client()
    cycles = 0
    while True:
        try:
            client.set(
                "growen:market_worker:heartbeat",
                json.dumps({
                    "timestamp": datetime.now(UTC).isoformat(),
                    "queue": "market",
                    "current_item_id": _CURRENT_ITEM_ID,
                    "version": "market-v1",
                }),
                ex=120,
            )
        except Exception as exc:
            logger.warning("No se pudo publicar heartbeat de Mercado: %s", exc)
        cycles += 1
        if cycles % 2 == 0:
            try:
                reconcile_market_jobs_task.send()
            except Exception as exc:
                logger.warning("No se pudo encolar reconciliación de Mercado: %s", exc)
        time.sleep(30)


if os.getenv("MARKET_HEARTBEAT_ENABLED", "0") == "1":
    threading.Thread(target=_heartbeat_loop, name="market-heartbeat", daemon=True).start()


async def scrape_market_source(
    source: MarketSource,
    product_name: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> tuple[Optional[Decimal], Optional[str], Optional[str], bool]:
    """
    Ejecuta scraping de una fuente de precio de mercado con manejo robusto de errores.
    
    Detecta el tipo de fuente y aplica el método de scraping apropiado:
    - type='static': usa requests + BeautifulSoup
    - type='dynamic': usa Playwright
    
    Si el scraping estático falla, automáticamente intenta con dynamic (fallback).
    Si el fallback funciona, actualiza el source_type en la BD.
    
    Args:
        source: Fuente de mercado a scrapear
        product_name: Nombre del producto (para logging contextual)
        db: Sesión de base de datos (opcional, necesario para actualizar source_type)
        
    Returns:
        Tuple (precio encontrado, código de moneda, error si ocurrió, usado_fallback)
        - precio: Decimal con el valor o None
        - moneda: Código ISO 4217 (ej: "ARS", "USD") o None
        - error: String con descripción del error o None
        - usado_fallback: bool indicando si se usó fallback de static a dynamic
        
    Nota:
        Esta función nunca lanza excepciones, siempre retorna un resultado
        controlado para permitir que el proceso continúe con otras fuentes.
    """
    product_label = f"producto '{product_name}'" if product_name else f"producto_id={source.product_id}"
    source_label = f"fuente '{source.source_name}' (ID: {source.id})"
    
    try:
        logger.info(
            f"[scraping] Iniciando scraping para {product_label} - "
            f"{source_label} - Tipo: {source.source_type or 'static'} - URL: {source.url}"
        )
        
        # Determinar método de scraping según el tipo
        source_type = source.source_type or "static"
        
        if source_type == "static":
            # Scraping de páginas estáticas con requests + BeautifulSoup
            static_error = None
            try:
                logger.debug(f"[scraping] Usando scraper estático para {source_label}")
                price, currency = scrape_static_price(source.url, timeout=15)
                
                if price is not None:
                    logger.info(
                        f"[scraping] ✓ Precio extraído exitosamente de {source_label}: "
                        f"{price} {currency}"
                    )
                    return price, currency, None, False
                else:
                    static_error = "Precio no encontrado en la página"
                    logger.warning(
                        f"[scraping] ⚠ {static_error} - {source_label} - {product_label}"
                    )
                    
            except NetworkError as e:
                static_error = f"Error de red: {str(e)}"
                logger.error(
                    f"[scraping] ✗ {static_error} - {source_label} - {product_label}",
                    exc_info=False
                )
                
            except PriceNotFoundError as e:
                static_error = f"Precio no encontrado: {str(e)}"
                logger.warning(
                    f"[scraping] ⚠ {static_error} - {source_label} - {product_label}"
                )
                
            except Exception as e:
                static_error = f"Error inesperado en scraping estático: {type(e).__name__}: {str(e)}"
                logger.error(
                    f"[scraping] ✗ {static_error} - {source_label} - {product_label}",
                    exc_info=True  # Include full traceback for unexpected errors
                )
            
            # Si el scraping estático falló, intentar con dynamic como fallback
            if static_error:
                logger.info(
                    f"[scraping] 🔄 Scraping estático falló, intentando con dynamic como fallback - {source_label}"
                )
                
                try:
                    from workers.scraping.dynamic_scraper import (
                        scrape_dynamic_price,
                        BrowserLaunchError,
                        PageLoadError,
                        SelectorNotFoundError,
                        DynamicScrapingError,
                    )
                    
                    # Intentar con scraper dinámico (usar versión async directamente)
                    result = await scrape_dynamic_price(source.url, timeout=15000)
                    price = result.get("price")
                    currency = result.get("currency", "ARS")
                    
                    # Convertir price a Decimal si es necesario
                    if price is not None and not isinstance(price, Decimal):
                        price = Decimal(str(price))
                    
                    if price is not None:
                        logger.info(
                            f"[scraping] ✓ Precio extraído exitosamente con fallback dynamic de {source_label}: "
                            f"{price} {currency}"
                        )
                        
                        # Actualizar source_type en BD si se proporcionó sesión
                        if db is not None:
                            try:
                                # Refrescar el objeto source para asegurar que está sincronizado con la BD
                                await db.refresh(source)
                                source.source_type = "dynamic"
                                await db.flush()
                                logger.info(
                                    f"[scraping] ✓ source_type actualizado a 'dynamic' para {source_label}"
                                )
                            except Exception as db_error:
                                # Hacer rollback si hay error
                                try:
                                    await db.rollback()
                                except Exception:
                                    pass
                                logger.warning(
                                    f"[scraping] ⚠ No se pudo actualizar source_type en BD: {db_error}"
                                )
                        
                        return price, currency, None, True  # True = usado_fallback
                    else:
                        error_msg = f"Fallback dynamic también falló: Precio no encontrado"
                        logger.warning(
                            f"[scraping] ⚠ {error_msg} - {source_label} - {product_label}"
                        )
                        return None, None, static_error, False
                        
                except (BrowserLaunchError, PageLoadError, SelectorNotFoundError, DynamicScrapingError) as e:
                    error_msg = f"Fallback dynamic falló: {str(e)}"
                    logger.warning(
                        f"[scraping] ⚠ {error_msg} - {source_label} - {product_label}"
                    )
                    return None, None, static_error, False
                    
                except Exception as e:
                    error_msg = f"Error inesperado en fallback dynamic: {type(e).__name__}: {str(e)}"
                    logger.error(
                        f"[scraping] ✗ {error_msg} - {source_label} - {product_label}",
                        exc_info=True
                    )
                    return None, None, static_error, False
            
            # Si llegamos aquí, static falló pero no se pudo hacer fallback
            return None, None, static_error, False
        
        elif source_type == "dynamic":
            # Scraping dinámico con Playwright para páginas con JavaScript
            try:
                logger.debug(f"[scraping] Usando scraper dinámico (Playwright) para {source_label}")
                
                from workers.scraping.dynamic_scraper import (
                    scrape_dynamic_price,
                    BrowserLaunchError,
                    PageLoadError,
                    SelectorNotFoundError,
                    DynamicScrapingError,
                )
                
                # Usar la versión async directamente (no sync)
                result = await scrape_dynamic_price(source.url, timeout=15000)
                price = result.get("price")
                currency = result.get("currency", "ARS")
                
                # Convertir price a Decimal si es necesario
                if price is not None and not isinstance(price, Decimal):
                    price = Decimal(str(price))
                
                if price is not None:
                    logger.info(
                        f"[scraping] ✓ Precio extraído exitosamente con Playwright de {source_label}: "
                        f"{price} {currency}"
                    )
                    return price, currency, None, False
                else:
                    error_msg = "Precio no encontrado en página dinámica"
                    logger.warning(
                        f"[scraping] ⚠ {error_msg} - {source_label} - {product_label}"
                    )
                    return None, None, error_msg, False
                    
            except BrowserLaunchError as e:
                error_msg = f"Error lanzando navegador Playwright: {str(e)}"
                logger.error(
                    f"[scraping] ✗ {error_msg} - {source_label} - {product_label}",
                    exc_info=False
                )
                return None, None, error_msg, False
                
            except PageLoadError as e:
                error_msg = f"Error cargando página dinámica: {str(e)}"
                logger.error(
                    f"[scraping] ✗ {error_msg} - {source_label} - {product_label}",
                    exc_info=False
                )
                return None, None, error_msg, False
                
            except SelectorNotFoundError as e:
                error_msg = f"Selector no encontrado en página: {str(e)}"
                logger.warning(
                    f"[scraping] ⚠ {error_msg} - {source_label} - {product_label}"
                )
                return None, None, error_msg, False
                
            except DynamicScrapingError as e:
                error_msg = f"Error en scraping dinámico: {str(e)}"
                logger.error(
                    f"[scraping] ✗ {error_msg} - {source_label} - {product_label}",
                    exc_info=False
                )
                return None, None, error_msg, False
                
            except Exception as e:
                error_msg = f"Error inesperado en scraping dinámico: {type(e).__name__}: {str(e)}"
                logger.error(
                    f"[scraping] ✗ {error_msg} - {source_label} - {product_label}",
                    exc_info=True  # Include full traceback
                )
                return None, None, error_msg, False
        
        else:
            error_msg = f"Tipo de fuente desconocido: {source_type}"
            logger.error(
                f"[scraping] ✗ {error_msg} - {source_label} - {product_label}"
            )
            return None, None, error_msg, False
        
    except Exception as e:
        # Captura de último recurso para errores no previstos
        error_msg = f"Error crítico no capturado: {type(e).__name__}: {str(e)}"
        logger.critical(
            f"[scraping] ✗✗✗ {error_msg} - {source_label} - {product_label}",
            exc_info=True
        )
        return None, None, error_msg, False


async def update_market_prices_for_product(product_id: int, db: AsyncSession) -> Dict[str, Any]:
    """
    Actualiza precios de mercado de todas las fuentes de un producto con manejo robusto de errores.
    
    Cada fuente se procesa independientemente: si una falla, el proceso continúa
    con las demás. Se mantiene registro detallado de éxitos y fallos.
    
    Args:
        product_id: ID del producto canónico
        db: Sesión de base de datos
        
    Returns:
        Dict con resultado detallado del proceso:
        - success: bool - indica si el proceso general fue exitoso
        - product_id: int - ID del producto procesado
        - product_name: str - nombre del producto
        - sources_total: int - total de fuentes configuradas
        - sources_updated: int - fuentes actualizadas exitosamente
        - sources_failed: int - fuentes que fallaron
        - errors: List[Dict] - lista de errores con contexto
        - market_price_reference: Decimal - precio promedio calculado (si aplica)
        
    Nota:
        Esta función nunca lanza excepciones, siempre retorna un resultado
        controlado para mantener la estabilidad del worker.
    """
    start_time = datetime.utcnow()
    
    try:
        # 1. Verificar que el producto existe
        logger.info(f"[scraping] Iniciando actualización de precios para producto ID: {product_id}")
        
        query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
        result = await db.execute(query_product)
        product = result.scalar_one_or_none()
        
        if not product:
            error_msg = f"Producto {product_id} no encontrado en base de datos"
            logger.error(f"[scraping] ✗ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "product_id": product_id,
                "sources_total": 0,
                "sources_updated": 0,
                "sources_failed": 0,
                "errors": [],
            }
        
        product_name = product.name or f"ID:{product_id}"
        logger.info(f"[scraping] Producto encontrado: '{product_name}'")
        
        # 2. Obtener sólo activos canónicos habilitados explícitamente para Mercado.
        query_sources = _eligible_market_sources_query(product_id)
        result_sources = await db.execute(query_sources)
        sources = result_sources.scalars().all()
        
        sources_total = len(sources)
        
        if not sources:
            logger.warning(
                f"[scraping] ⚠ Producto '{product_name}' no tiene fuentes de mercado configuradas"
            )
            return {
                "success": True,
                "message": "Producto sin fuentes de mercado",
                "product_id": product_id,
                "product_name": product_name,
                "sources_total": 0,
                "sources_updated": 0,
                "sources_failed": 0,
                "errors": [],
            }
        
        logger.info(
            f"[scraping] Producto '{product_name}' tiene {sources_total} fuente(s) configurada(s)"
        )
        
        # 3. Scrapear cada fuente (continuar incluso si alguna falla)
        sources_updated = 0
        sources_failed = 0
        errors = []
        successful_prices: list[Decimal] = []
        
        logger.info(
            f"[scraping] ═══════════════════════════════════════════════════════════"
        )
        logger.info(
            f"[scraping] Iniciando scraping de {sources_total} fuente(s) para '{product_name}'"
        )
        logger.info(
            f"[scraping] ═══════════════════════════════════════════════════════════"
        )
        
        for idx, source in enumerate(sources, 1):
            try:
                logger.info(
                    f"[scraping] [{idx}/{sources_total}] Procesando fuente: '{source.source_name}'"
                )
                
                # Ejecutar scraping (nunca lanza excepciones)
                # Pasar db para permitir actualización de source_type si se usa fallback
                price, currency, error, usado_fallback = await scrape_market_source(source, product_name, db)
                
                # Actualizar timestamp de última revisión SIEMPRE (éxito o fallo)
                source.last_checked_at = datetime.utcnow()
                
                if price is not None:
                    # Éxito: actualizar precio
                    source.last_price = price
                    source.currency = currency or source.currency or "ARS"
                    if source.currency == "ARS":
                        successful_prices.append(price)
                    else:
                        logger.warning(
                            f"[scraping] Fuente '{source.source_name}' expresada en {source.currency}; "
                            "se persiste pero se excluye del promedio ARS hasta contar con conversión FX"
                        )
                    sources_updated += 1
                    
                    if usado_fallback:
                        logger.info(
                            f"[scraping] [{idx}/{sources_total}] ✓ Fuente '{source.source_name}' "
                            f"actualizada exitosamente con fallback dynamic: {price} {currency}"
                        )
                    else:
                        logger.info(
                            f"[scraping] [{idx}/{sources_total}] ✓ Fuente '{source.source_name}' "
                            f"actualizada exitosamente: {price} {currency}"
                        )
                else:
                    # Fallo: registrar error
                    sources_failed += 1
                    error_detail = {
                        "source_id": source.id,
                        "source_name": source.source_name,
                        "source_url": source.url,
                        "error": error or "Error desconocido",
                    }
                    errors.append(error_detail)
                    
                    logger.warning(
                        f"[scraping] [{idx}/{sources_total}] ✗ Fuente '{source.source_name}' falló: {error}"
                    )
                
                # Commit después de cada fuente para persistir cambios parciales
                try:
                    await db.commit()
                except Exception as commit_error:
                    # Si hay error en commit, hacer rollback y continuar
                    logger.warning(
                        f"[scraping] [{idx}/{sources_total}] Error en commit, haciendo rollback: {commit_error}"
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                
            except Exception as e:
                # Captura de errores inesperados en el loop
                # (no debería ocurrir porque scrape_market_source captura todo)
                sources_failed += 1
                error_detail = {
                    "source_id": source.id,
                    "source_name": source.source_name,
                    "source_url": source.url,
                    "error": f"Error crítico en loop: {type(e).__name__}: {str(e)}",
                }
                errors.append(error_detail)
                
                logger.critical(
                    f"[scraping] [{idx}/{sources_total}] ✗✗✗ Error crítico procesando "
                    f"fuente '{source.source_name}': {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                
                # Intentar commit incluso con error para guardar last_checked_at
                try:
                    source.last_checked_at = datetime.utcnow()
                    await db.commit()
                except Exception as commit_error:
                    logger.error(
                        f"[scraping] Error al hacer commit después de fallo: {commit_error}"
                    )
                    try:
                        await db.rollback()
                    except Exception:
                        pass
        
        # 4. Calcular market_price_reference (promedio de precios obtenidos)
        market_price_ref = None
        if successful_prices:
            previous_market_price = product.market_price_reference
            avg_price = sum(successful_prices, Decimal("0")) / Decimal(len(successful_prices))
            market_price_ref = avg_price.quantize(Decimal("0.01"))
            product.market_price_reference = market_price_ref
            product.market_price_updated_at = datetime.utcnow()
            
            logger.info(
                f"[scraping] Precio de referencia calculado para '{product_name}': "
                f"${market_price_ref} (promedio de {len(successful_prices)} fuente(s))"
            )
            
            # 4.1 Detectar alertas de variación de precio
            try:
                from services.market.alerts import detect_price_alerts
                
                alerts_created = await detect_price_alerts(
                    db=db,
                    product_id=product_id,
                    new_market_price=market_price_ref,
                    currency="ARS",
                    previous_market_price=previous_market_price,
                )
                
                if alerts_created:
                    logger.info(
                        f"[scraping] 🚨 Generadas {len(alerts_created)} alerta(s) de precio "
                        f"para '{product_name}'"
                    )
            except Exception as alert_error:
                # No fallar el scraping si falla la detección de alertas
                logger.error(
                    f"[scraping] Error al detectar alertas para '{product_name}': {alert_error}",
                    exc_info=True
                )
        else:
            logger.warning(
                f"[scraping] ⚠ No se obtuvo ningún precio válido para '{product_name}', "
                f"no se puede calcular market_price_reference"
            )
        
        # 5. Actualizar timestamp del producto
        product.updated_at = datetime.utcnow()
        await db.commit()
        
        # 6. Calcular duración y generar resumen
        duration = (datetime.utcnow() - start_time).total_seconds()
        success_rate = (sources_updated / sources_total * 100) if sources_total > 0 else 0
        
        logger.info(
            f"[scraping] ═══════════════════════════════════════════════════════════"
        )
        logger.info(
            f"[scraping] Finalizado scraping para '{product_name}' (ID: {product_id})"
        )
        logger.info(
            f"[scraping] ═══════════════════════════════════════════════════════════"
        )
        logger.info(
            f"[scraping] Resumen: {sources_updated}/{sources_total} fuentes actualizadas "
            f"({success_rate:.1f}% éxito)"
        )
        logger.info(
            f"[scraping]   ✓ Exitosas: {sources_updated}"
        )
        
        if sources_failed > 0:
            logger.warning(
                f"[scraping]   ✗ Fallidas:  {sources_failed}"
            )
            for error_detail in errors:
                logger.warning(
                    f"[scraping]      • {error_detail['source_name']}: {error_detail['error']}"
                )
        
        if market_price_ref:
            logger.info(
                f"[scraping]   💰 Precio referencia: ${market_price_ref}"
            )
        
        logger.info(
            f"[scraping]   ⏱ Duración: {duration:.2f}s"
        )
        logger.info(
            f"[scraping] ═══════════════════════════════════════════════════════════"
        )
        
        completed_successfully = sources_updated > 0
        return {
            "success": completed_successfully,
            "status": "completed" if sources_failed == 0 else ("partial" if sources_updated else "failed"),
            "product_id": product_id,
            "product_name": product_name,
            "sources_total": sources_total,
            "sources_updated": sources_updated,
            "sources_failed": sources_failed,
            "success_rate": success_rate,
            "errors": errors,
            "market_price_reference": float(market_price_ref) if market_price_ref else None,
            "duration_seconds": duration,
        }
        
    except Exception as e:
        # Captura de último recurso para errores críticos no previstos
        error_msg = f"Error crítico en update_market_prices_for_product: {type(e).__name__}: {str(e)}"
        logger.critical(
            f"[scraping] ✗✗✗ {error_msg} para producto ID: {product_id}",
            exc_info=True
        )
        
        try:
            await db.rollback()
        except Exception:
            pass
        
        return {
            "success": False,
            "product_id": product_id,
            "error": error_msg,
            "sources_total": 0,
            "sources_updated": 0,
            "sources_failed": 0,
            "errors": [],
        }


async def process_market_item(item_id: int) -> dict[str, Any]:
    """Procesa un item persistente y guarda resultados por fuente exactamente una vez."""
    global _CURRENT_ITEM_ID
    _CURRENT_ITEM_ID = item_id
    _structured_event("item_received", item_id=item_id)
    async with SessionLocal() as db:
        item = await claim_item(db, item_id)
        if not item:
            _structured_event("item_skipped", item_id=item_id, reason="not_queued")
            _CURRENT_ITEM_ID = None
            return {"item_id": item_id, "status": "skipped"}
        product = await db.get(CanonicalProduct, item.product_id)
        if not product:
            await complete_item(
                db, item_id, status="failed", sources_total=0, sources_succeeded=0,
                sources_failed=0, market_price_reference=None,
                error_code="product_not_found", error_message="Producto no encontrado",
            )
            _CURRENT_ITEM_ID = None
            return {"item_id": item_id, "status": "failed"}
        job = await db.get(MarketUpdateJob, item.job_id)
        job_config = job.config_snapshot if job and job.config_snapshot else {}
        target_source_id = job_config.get("target_source_id")
        force_price_detection = target_source_id is not None
        discovery = None
        if force_price_detection:
            target_source = await db.scalar(
                select(MarketSource)
                .join(CanonicalKnowledgeAsset, CanonicalKnowledgeAsset.id == MarketSource.asset_id)
                .options(
                    selectinload(MarketSource.asset).selectinload(CanonicalKnowledgeAsset.locations),
                    selectinload(MarketSource.asset).selectinload(CanonicalKnowledgeAsset.labels),
                    selectinload(MarketSource.asset).selectinload(CanonicalKnowledgeAsset.capabilities),
                )
                .where(
                    MarketSource.id == int(target_source_id),
                    CanonicalKnowledgeAsset.canonical_product_id == product.id,
                    CanonicalKnowledgeAsset.status != "archived",
                    MarketSource.source_type != "manual",
                )
            )
            if not target_source or not target_source.url:
                await complete_item(
                    db, item.id, status="failed", sources_total=0, sources_succeeded=0,
                    sources_failed=0, market_price_reference=product.market_price_reference,
                    error_code="target_source_unavailable",
                    error_message="La fuente solicitada no está disponible para detectar precios",
                )
                _CURRENT_ITEM_ID = None
                return {"item_id": item.id, "status": "failed"}
            sources = [target_source]
        else:
            from workers.discovery.source_finder import discover_price_sources
            discovery = await discover_candidates_for_item(
                db,
                item=item,
                product=product,
                force_rediscovery=bool(job_config.get("force_rediscovery", False)),
                competitor_limit=int(job_config.get("competitor_limit", 3)),
                discover=discover_price_sources,
            )
            sources = list((await db.execute(_eligible_market_sources_query(product.id))).unique().scalars())
            known_ids = {source.id for source in sources}
            sources.extend(source for source in discovery.candidates if source.id not in known_ids)
        item.stage = "extracting"
        await db.commit()
        succeeded = 0
        failed = 0
        errors: list[str] = []
        previous_reference = product.market_price_reference
        try:
            for source in sources:
                started = time.monotonic()
                is_candidate = source.asset.origin == "market_discovery" and not source.is_active
                needs_validation = not source.is_active or source.validation_status != "verified"
                source_result = MarketUpdateSourceResult(
                    item_id=item.id,
                    source_id=source.id,
                    operation="validation" if is_candidate else "extraction",
                    status="running",
                )
                db.add(source_result)
                await db.flush()
                domain_lock = _domain_lock(source.url or "")
                if not domain_lock.acquire():
                    price, currency, error, used_browser = None, None, "dominio ocupado", False
                else:
                    try:
                        price, currency, error, used_browser = await scrape_market_source(source, product.name, db)
                    finally:
                        try:
                            domain_lock.release()
                        except Exception:
                            logger.warning("El lock del dominio expiró antes de liberarse")
                source_result.duration_ms = int((time.monotonic() - started) * 1000)
                # El scraper estático siempre intenta Playwright como fallback
                # cuando retorna error; registrar el intento aunque también falle.
                source_result.used_browser = bool(
                    used_browser
                    or source.source_type == "dynamic"
                    or (source.source_type == "static" and error is not None)
                )
                source_result.completed_at = datetime.utcnow()
                currency_is_ars = price is not None and (currency or "ARS").upper() == "ARS"
                delivery_confirmed = bool(source.argentina_delivery_confirmed)
                if currency_is_ars and (force_price_detection or not is_candidate or delivery_confirmed):
                    if needs_validation and delivery_confirmed and source.ars_confirmed is not False:
                        source.asset.status = "confirmed"
                        source.is_active = True
                        source.validation_status = "verified"
                        source.ars_confirmed = True
                        source.last_error_code = None
                        source.last_error_message = None
                    observation = await persist_source_observation(
                        db,
                        product_id=product.id,
                        source=source,
                        price=price,
                        capture_method="dynamic" if used_browser or source.source_type == "dynamic" else "static",
                        job_id=item.job_id,
                        job_item_id=item.id,
                    )
                    source_result.status = "succeeded"
                    source_result.observation_id = observation.id
                    succeeded += 1
                    if needs_validation and not delivery_confirmed:
                        source.asset.status = "pending"
                        source.is_active = False
                        source.validation_status = "warning"
                        source.ars_confirmed = True
                        source.last_error_code = "argentina_delivery_unconfirmed"
                        source.last_error_message = "Precio ARS detectado; falta confirmar entrega en Argentina"
                    _structured_event(
                        "source_succeeded", item_id=item.id, product_id=product.id,
                        source_id=source.id, duration_ms=source_result.duration_ms,
                    )
                else:
                    failed += 1
                    source_result.status = "failed"
                    failure_code, failure_message, retryable, http_status = _source_failure(
                        price=price,
                        currency_is_ars=currency_is_ars,
                        is_candidate=is_candidate,
                        delivery_confirmed=delivery_confirmed,
                        error=error,
                    )
                    source_result.error_code = failure_code
                    source_result.error_message = failure_message
                    source_result.retryable = retryable
                    source_result.http_status = http_status
                    if failure_code == "currency_not_ars":
                        source.validation_status = "rejected"
                        source.is_active = False
                        source.ars_confirmed = False
                    elif failure_code == "argentina_delivery_unconfirmed":
                        source.validation_status = "warning"
                        source.is_active = False
                        source.ars_confirmed = True
                    else:
                        source.validation_status = "warning"
                        source.is_active = False
                    source.last_error_at = datetime.utcnow()
                    source.last_error_code = source_result.error_code
                    source.last_error_message = source_result.error_message
                    errors.append(source_result.error_message or "Error de fuente")
                    _structured_event(
                        "source_failed", item_id=item.id, product_id=product.id,
                        source_id=source.id, error_code=source_result.error_code,
                    )
                await db.flush()

            counted_sources = sources if force_price_detection else discovery.candidates
            item.sources_confirmed = sum(
                1 for source in counted_sources if source.is_active and source.validation_status == "verified"
            )
            item.sources_quarantined = len(counted_sources) - item.sources_confirmed

            reference, coverage, snapshot = await recompute_market_reference(
                db,
                product_id=product.id,
                job_id=item.job_id,
                job_item_id=item.id,
            )
            if reference is not None:
                try:
                    from services.market.alerts import detect_price_alerts
                    await detect_price_alerts(
                        db=db,
                        product_id=product.id,
                        new_market_price=reference,
                        currency="ARS",
                        previous_market_price=previous_reference,
                    )
                except Exception as exc:
                    logger.exception("No se pudieron generar alertas del item %s: %s", item.id, exc)
            has_discovery_error = bool(discovery and discovery.error_code is not None)
            no_competitors = not sources and not has_discovery_error
            status = (
                "succeeded"
                if force_price_detection and succeeded > 0
                else "succeeded"
                if failed == 0 and not has_discovery_error and reference is not None
                else "partial"
                if reference is not None
                else "failed"
            )
            await complete_item(
                db,
                item.id,
                status=status,
                sources_total=len(sources),
                sources_succeeded=succeeded,
                sources_failed=failed,
                market_price_reference=reference,
                error_code=(
                    discovery.error_code
                    if has_discovery_error
                    else "no_competitors_found"
                    if no_competitors
                    else None if status != "failed" else "no_effective_prices"
                ),
                error_message=(
                    discovery.error_message
                    if has_discovery_error and not errors
                    else "No se encontraron competidores válidos para extraer precios"
                    if no_competitors
                    else "; ".join(errors[:5]) if errors else None
                ),
            )
            _structured_event(
                "item_finished", item_id=item.id, product_id=product.id, status=status,
                sources_total=len(sources), sources_succeeded=succeeded,
                sources_failed=failed, effective_sources=coverage.effective,
                reference_observation_id=snapshot.id if snapshot else None,
            )
            return {"item_id": item.id, "status": status, "market_price_reference": float(reference) if reference else None}
        except Exception as exc:
            await db.rollback()
            await complete_item(
                db,
                item.id,
                status="failed",
                sources_total=len(sources),
                sources_succeeded=succeeded,
                sources_failed=max(failed, len(sources) - succeeded),
                market_price_reference=None,
                error_code="unexpected_error",
                error_message=str(exc),
            )
            _structured_event("item_failed", item_id=item.id, product_id=product.id, error=str(exc))
            raise
        finally:
            _CURRENT_ITEM_ID = None


@dramatiq.actor(
    queue_name="market",
    max_retries=3,
    min_backoff=1000,
    max_backoff=10000,
    time_limit=300000,
)
def process_market_item_task(item_id: int) -> None:
    """Actor productivo para jobs persistentes de Mercado."""
    asyncio.run(process_market_item(item_id))


@dramatiq.actor(queue_name="market", max_retries=0, time_limit=60000)
def reconcile_market_jobs_task() -> None:
    """Cierra items sin lease vigente para que ningún job quede activo indefinidamente."""
    async def run() -> None:
        async with SessionLocal() as db:
            expired = await expire_stale_items(db)
            if expired:
                _structured_event("stale_items_expired", count=expired)

    asyncio.run(run())


@dramatiq.actor(queue_name="market", max_retries=3, time_limit=300000)  # 5 min timeout
def refresh_market_prices_task(product_id: int) -> None:
    """
    Tarea asíncrona de Dramatiq para actualizar precios de mercado de un producto.
    
    Se ejecuta en la cola 'market' para separar tareas de scraping de otras colas (images, etc.).
    
    Args:
        product_id: ID del producto canónico a actualizar
    """
    async def run():
        logger.info(f"Iniciando actualización de precios de mercado para producto {product_id}")
        
        async with SessionLocal() as db:
            result = await update_market_prices_for_product(product_id, db)
            
            if result["success"]:
                logger.info(
                    f"Actualización completada para producto {product_id}: "
                    f"{result['sources_updated']}/{result['sources_total']} fuentes actualizadas"
                )
            else:
                logger.error(f"Actualización fallida para producto {product_id}: {result.get('error')}")
                raise RuntimeError(
                    result.get("error")
                    or f"No se pudo actualizar ninguna fuente del producto {product_id}"
                )
            
            return result
    
    import asyncio
    asyncio.run(run())
