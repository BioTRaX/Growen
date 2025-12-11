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
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

# FIX: Windows ProactorEventLoop no soporta psycopg async
# Debe ejecutarse ANTES de cualquier import que use asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import dramatiq  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from db.models import CanonicalProduct, MarketSource
from workers.scraping import scrape_static_price
from workers.scraping.static_scraper import NetworkError, PriceNotFoundError
from agent_core.config import settings

# Configuración de logging con formato detallado
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuración de base de datos - usar settings como en db/session.py
DB_URL = os.getenv("DB_URL") or settings.db_url
engine = create_async_engine(DB_URL, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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
                                await db.commit()
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
        
        # 2. Obtener todas las fuentes de mercado del producto
        query_sources = select(MarketSource).where(MarketSource.product_id == product_id)
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
        successful_prices = []
        
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
                    successful_prices.append(float(price))
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
            avg_price = sum(successful_prices) / len(successful_prices)
            market_price_ref = Decimal(str(round(avg_price, 2)))
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
                    currency="ARS"  # TODO: Obtener currency de las fuentes
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
        
        return {
            "success": True,
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
            
            return result
    
    import asyncio
    asyncio.run(run())
