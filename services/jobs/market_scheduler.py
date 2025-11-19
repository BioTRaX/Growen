#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: market_scheduler.py
# NG-HEADER: Ubicación: services/jobs/market_scheduler.py
# NG-HEADER: Descripción: Scheduler para actualización automática de precios de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Scheduler para actualización automática periódica de precios de mercado.

Este módulo gestiona la programación y ejecución de tareas automáticas de 
scraping de precios de mercado usando APScheduler + Dramatiq.

Características:
- Ejecución periódica configurable (cron expression)
- Filtrado inteligente por antigüedad de precios
- Limitación de productos por tanda para evitar sobrecarga
- Priorización de productos obligatorios
- Logging detallado para auditoría
- Integración con Dramatiq workers
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from db.models import CanonicalProduct, MarketSource
from workers.market_scraping import refresh_market_prices_task
from agent_core.config import settings

# Configuración de logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ==================== CONFIGURACIÓN ====================

# Base de datos - usar settings como en db/session.py
DB_URL = os.getenv("DB_URL") or settings.db_url

# Frecuencia de actualización (días)
UPDATE_FREQUENCY_DAYS = int(os.getenv("MARKET_UPDATE_FREQUENCY_DAYS", "2"))

# Máximo de productos a procesar por ejecución
MAX_PRODUCTS_PER_RUN = int(os.getenv("MARKET_MAX_PRODUCTS_PER_RUN", "50"))

# Priorizar productos con fuentes obligatorias
PRIORITIZE_MANDATORY = os.getenv("MARKET_PRIORITIZE_MANDATORY", "true").lower() == "true"

# Horario de ejecución (cron expression)
# Default: todos los días a las 2:00 AM
CRON_SCHEDULE = os.getenv("MARKET_CRON_SCHEDULE", "0 2 * * *")

# Habilitar/deshabilitar scheduler
SCHEDULER_ENABLED = os.getenv("MARKET_SCHEDULER_ENABLED", "false").lower() == "true"

# Motor de BD para el scheduler
engine = create_async_engine(DB_URL, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ==================== FUNCIONES DE NEGOCIO ====================

async def get_products_needing_update(
    session: AsyncSession,
    max_products: int = MAX_PRODUCTS_PER_RUN,
    days_threshold: int = UPDATE_FREQUENCY_DAYS,
    prioritize_mandatory: bool = PRIORITIZE_MANDATORY
) -> List[int]:
    """
    Obtiene IDs de productos cuyo precio de mercado necesita actualización.
    
    Criterios de selección:
    1. market_price_updated_at es NULL (nunca actualizado)
    2. market_price_updated_at > days_threshold días (desactualizado)
    3. Si prioritize_mandatory=True, productos con fuentes is_mandatory=True primero
    
    Args:
        session: Sesión de base de datos
        max_products: Límite de productos a retornar
        days_threshold: Días desde última actualización para considerar desactualizado
        prioritize_mandatory: Priorizar productos con fuentes obligatorias
        
    Returns:
        Lista de IDs de productos a actualizar
    """
    threshold_date = datetime.utcnow() - timedelta(days=days_threshold)
    
    # Query base: productos con fuentes de mercado
    query = (
        select(CanonicalProduct.id)
        .join(MarketSource, CanonicalProduct.id == MarketSource.product_id)
        .where(
            # Condición: nunca actualizado O desactualizado
            (CanonicalProduct.market_price_updated_at.is_(None)) |
            (CanonicalProduct.market_price_updated_at < threshold_date)
        )
        .distinct()
    )
    
    # Priorización por fuentes obligatorias
    if prioritize_mandatory:
        # Subquery: productos con al menos una fuente obligatoria
        mandatory_subquery = (
            select(MarketSource.product_id)
            .where(MarketSource.is_mandatory == True)
            .distinct()
            .subquery()
        )
        
        # Query prioritaria: primero productos con fuentes obligatorias
        priority_query = query.where(
            CanonicalProduct.id.in_(select(mandatory_subquery.c.product_id))
        ).limit(max_products)
        
        result = await session.execute(priority_query)
        product_ids = [row[0] for row in result.fetchall()]
        
        # Si no alcanzamos el límite, completar con productos no prioritarios
        if len(product_ids) < max_products:
            remaining = max_products - len(product_ids)
            non_priority_query = query.where(
                ~CanonicalProduct.id.in_(select(mandatory_subquery.c.product_id))
            ).limit(remaining)
            
            result = await session.execute(non_priority_query)
            product_ids.extend([row[0] for row in result.fetchall()])
    else:
        # Sin priorización: orden de creación (más antiguos primero)
        query = query.order_by(CanonicalProduct.created_at.asc()).limit(max_products)
        result = await session.execute(query)
        product_ids = [row[0] for row in result.fetchall()]
    
    return product_ids


async def schedule_market_updates() -> None:
    """
    Job principal: programa actualizaciones de precios de mercado.
    
    Flujo:
    1. Obtiene productos candidatos a actualización
    2. Encola tareas Dramatiq para cada producto
    3. Registra métricas para auditoría
    
    Esta función es invocada por APScheduler según la configuración de cron.
    """
    start_time = datetime.utcnow()
    logger.info("[MARKET SCHEDULER] Iniciando job de actualización automática de precios")
    
    try:
        async with SessionLocal() as session:
            # 1. Obtener productos candidatos
            product_ids = await get_products_needing_update(
                session,
                max_products=MAX_PRODUCTS_PER_RUN,
                days_threshold=UPDATE_FREQUENCY_DAYS,
                prioritize_mandatory=PRIORITIZE_MANDATORY
            )
            
            if not product_ids:
                logger.info("[MARKET SCHEDULER] No hay productos pendientes de actualización")
                return
            
            logger.info(
                f"[MARKET SCHEDULER] Productos seleccionados para actualización: {len(product_ids)}"
            )
            
            # 2. Obtener estadísticas adicionales
            total_sources_query = select(func.count()).select_from(MarketSource).where(
                MarketSource.product_id.in_(product_ids)
            )
            total_sources = await session.scalar(total_sources_query) or 0
            
            mandatory_sources_query = select(func.count()).select_from(MarketSource).where(
                MarketSource.product_id.in_(product_ids),
                MarketSource.is_mandatory == True
            )
            mandatory_sources = await session.scalar(mandatory_sources_query) or 0
            
            logger.info(
                f"[MARKET SCHEDULER] Total de fuentes a scrapear: {total_sources} "
                f"({mandatory_sources} obligatorias)"
            )
            
            # 3. Encolar tareas en Dramatiq
            enqueued_count = 0
            failed_count = 0
            
            for product_id in product_ids:
                try:
                    # Enviar tarea a cola de Dramatiq
                    refresh_market_prices_task.send(product_id)
                    enqueued_count += 1
                    logger.debug(f"[MARKET SCHEDULER] Tarea encolada: producto {product_id}")
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        f"[MARKET SCHEDULER] Error al encolar producto {product_id}: {e}",
                        exc_info=True
                    )
            
            # 4. Registrar métricas finales
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"[MARKET SCHEDULER] Job completado en {duration:.2f}s"
            )
            logger.info(
                f"[MARKET SCHEDULER] Resumen: "
                f"{enqueued_count} tareas encoladas, "
                f"{failed_count} fallos, "
                f"{total_sources} fuentes totales"
            )
            
            # 5. Métricas por configuración
            logger.info(
                f"[MARKET SCHEDULER] Configuración actual: "
                f"UPDATE_FREQUENCY_DAYS={UPDATE_FREQUENCY_DAYS}, "
                f"MAX_PRODUCTS_PER_RUN={MAX_PRODUCTS_PER_RUN}, "
                f"PRIORITIZE_MANDATORY={PRIORITIZE_MANDATORY}"
            )
            
    except Exception as e:
        logger.error(
            f"[MARKET SCHEDULER] Error crítico en job de actualización: {e}",
            exc_info=True
        )
        raise


async def get_scheduler_status() -> dict:
    """
    Obtiene el estado actual del scheduler y estadísticas de productos.
    
    Útil para endpoints de monitoreo o dashboards.
    
    Returns:
        Diccionario con métricas del scheduler
    """
    async with SessionLocal() as session:
        # Total de productos con fuentes de mercado
        total_products_query = (
            select(func.count(CanonicalProduct.id.distinct()))
            .join(MarketSource, CanonicalProduct.id == MarketSource.product_id)
        )
        total_products = await session.scalar(total_products_query) or 0
        
        # Productos nunca actualizados
        never_updated_query = (
            select(func.count(CanonicalProduct.id.distinct()))
            .join(MarketSource, CanonicalProduct.id == MarketSource.product_id)
            .where(CanonicalProduct.market_price_updated_at.is_(None))
        )
        never_updated = await session.scalar(never_updated_query) or 0
        
        # Productos desactualizados (> UPDATE_FREQUENCY_DAYS)
        threshold_date = datetime.utcnow() - timedelta(days=UPDATE_FREQUENCY_DAYS)
        outdated_query = (
            select(func.count(CanonicalProduct.id.distinct()))
            .join(MarketSource, CanonicalProduct.id == MarketSource.product_id)
            .where(
                CanonicalProduct.market_price_updated_at.is_not(None),
                CanonicalProduct.market_price_updated_at < threshold_date
            )
        )
        outdated = await session.scalar(outdated_query) or 0
        
        # Total de fuentes de mercado
        total_sources_query = select(func.count()).select_from(MarketSource)
        total_sources = await session.scalar(total_sources_query) or 0
        
        return {
            "scheduler_enabled": SCHEDULER_ENABLED,
            "cron_schedule": CRON_SCHEDULE,
            "update_frequency_days": UPDATE_FREQUENCY_DAYS,
            "max_products_per_run": MAX_PRODUCTS_PER_RUN,
            "prioritize_mandatory": PRIORITIZE_MANDATORY,
            "stats": {
                "total_products_with_sources": total_products,
                "never_updated": never_updated,
                "outdated": outdated,
                "pending_update": never_updated + outdated,
                "total_sources": total_sources,
            }
        }


# ==================== INICIALIZACIÓN DEL SCHEDULER ====================

# Instancia global del scheduler (singleton)
scheduler: Optional[AsyncIOScheduler] = None


def create_scheduler() -> AsyncIOScheduler:
    """
    Crea y configura una instancia de APScheduler.
    
    Returns:
        Scheduler configurado pero no iniciado
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("[MARKET SCHEDULER] Scheduler ya existe, retornando instancia existente")
        return scheduler
    
    logger.info("[MARKET SCHEDULER] Creando nuevo scheduler")
    
    scheduler = AsyncIOScheduler(timezone="UTC")
    
    # Agregar job de actualización de precios
    scheduler.add_job(
        schedule_market_updates,
        trigger=CronTrigger.from_crontab(CRON_SCHEDULE),
        id="market_price_update",
        name="Actualización automática de precios de mercado",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hora de gracia para misfires
    )
    
    logger.info(
        f"[MARKET SCHEDULER] Job configurado: '{CRON_SCHEDULE}' "
        f"(cada {UPDATE_FREQUENCY_DAYS} días, máx {MAX_PRODUCTS_PER_RUN} productos)"
    )
    
    return scheduler


def start_scheduler() -> None:
    """
    Inicia el scheduler si está habilitado por configuración.
    
    Esta función debe ser llamada al arrancar la aplicación.
    """
    if not SCHEDULER_ENABLED:
        logger.info("[MARKET SCHEDULER] Scheduler deshabilitado por configuración (MARKET_SCHEDULER_ENABLED=false)")
        return
    
    global scheduler
    
    if scheduler is None:
        scheduler = create_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("[MARKET SCHEDULER] Scheduler iniciado correctamente")
        logger.info(f"[MARKET SCHEDULER] Próxima ejecución: {scheduler.get_job('market_price_update').next_run_time}")
    else:
        logger.warning("[MARKET SCHEDULER] Scheduler ya estaba en ejecución")


def stop_scheduler() -> None:
    """
    Detiene el scheduler de forma ordenada.
    
    Esta función debe ser llamada al apagar la aplicación.
    """
    global scheduler
    
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("[MARKET SCHEDULER] Scheduler detenido correctamente")
    else:
        logger.info("[MARKET SCHEDULER] Scheduler no estaba en ejecución")


# ==================== EJECUCIÓN MANUAL ====================

async def run_manual_update(
    max_products: Optional[int] = None,
    days_threshold: Optional[int] = None
) -> dict:
    """
    Ejecuta una actualización manual de precios sin esperar al scheduler.
    
    Útil para testing, correcciones manuales o ejecuciones ad-hoc.
    
    Args:
        max_products: Límite de productos (override de config)
        days_threshold: Días de antigüedad (override de config)
        
    Returns:
        Diccionario con resultado de la ejecución
    """
    logger.info("[MARKET SCHEDULER] Iniciando actualización MANUAL")
    
    start_time = datetime.utcnow()
    
    async with SessionLocal() as session:
        product_ids = await get_products_needing_update(
            session,
            max_products=max_products or MAX_PRODUCTS_PER_RUN,
            days_threshold=days_threshold or UPDATE_FREQUENCY_DAYS,
            prioritize_mandatory=PRIORITIZE_MANDATORY
        )
        
        if not product_ids:
            return {
                "success": True,
                "products_enqueued": 0,
                "message": "No hay productos pendientes de actualización"
            }
        
        enqueued = 0
        for product_id in product_ids:
            try:
                refresh_market_prices_task.send(product_id)
                enqueued += 1
            except Exception as e:
                logger.error(f"Error al encolar producto {product_id}: {e}")
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            f"[MARKET SCHEDULER] Actualización manual completada: "
            f"{enqueued} productos encolados en {duration:.2f}s"
        )
        
        return {
            "success": True,
            "products_enqueued": enqueued,
            "duration_seconds": duration,
            "message": f"Se encolaron {enqueued} productos para actualización"
        }
