#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: alerts.py
# NG-HEADER: Ubicación: services/market/alerts.py
# NG-HEADER: Descripción: Sistema de detección y gestión de alertas de precios de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Sistema de alertas por variación de precio de mercado.

Detecta cambios significativos en precios y genera alertas para
que administradores puedan reaccionar rápidamente.

Características:
- Detección automática post-scraping
- Múltiples tipos de alerta (venta vs mercado, cambio histórico, spikes)
- Umbrales configurables por tipo
- Prevención de duplicados
- Notificaciones por email
- Gestión de estados (activa/resuelta)
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CanonicalProduct, MarketAlert, User

# Configuración de logging
logger = logging.getLogger(__name__)

# ==================== CONFIGURACIÓN ====================

# Umbrales de detección (porcentajes como decimales: 0.15 = 15%)
THRESHOLD_SALE_VS_MARKET = float(os.getenv("ALERT_THRESHOLD_SALE_VS_MARKET", "0.15"))  # 15%
THRESHOLD_MARKET_VS_PREVIOUS = float(os.getenv("ALERT_THRESHOLD_MARKET_VS_PREVIOUS", "0.20"))  # 20%
THRESHOLD_SPIKE = float(os.getenv("ALERT_THRESHOLD_SPIKE", "0.30"))  # 30% (aumento repentino)
THRESHOLD_DROP = float(os.getenv("ALERT_THRESHOLD_DROP", "0.25"))  # 25% (caída repentina)

# Cooldown para evitar alertas duplicadas (horas)
ALERT_COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", "24"))

# Habilitar notificaciones por email
EMAIL_NOTIFICATIONS_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"


# ==================== FUNCIONES DE DETECCIÓN ====================

def calculate_percentage_change(old_value: Decimal, new_value: Decimal) -> Decimal:
    """
    Calcula el cambio porcentual entre dos valores.
    
    Args:
        old_value: Valor anterior
        new_value: Valor nuevo
        
    Returns:
        Cambio porcentual (0.15 = 15%)
    """
    if not old_value or old_value == 0:
        return Decimal("0")
    
    delta = new_value - old_value
    percentage = abs(delta / old_value)
    
    return Decimal(str(percentage))


def determine_severity(delta_percentage: float, alert_type: str) -> str:
    """
    Determina la severidad de una alerta basándose en el delta porcentual.
    
    Args:
        delta_percentage: Cambio porcentual (0.15 = 15%)
        alert_type: Tipo de alerta
        
    Returns:
        Severidad: 'low', 'medium', 'high', 'critical'
    """
    if alert_type in ["market_spike", "market_drop"]:
        if delta_percentage >= 0.50:  # 50%+
            return "critical"
        elif delta_percentage >= 0.35:  # 35-50%
            return "high"
        elif delta_percentage >= 0.25:  # 25-35%
            return "medium"
        else:
            return "low"
    
    elif alert_type == "sale_vs_market":
        if delta_percentage >= 0.30:  # 30%+
            return "high"
        elif delta_percentage >= 0.20:  # 20-30%
            return "medium"
        else:
            return "low"
    
    else:  # market_vs_previous
        if delta_percentage >= 0.40:  # 40%+
            return "high"
        elif delta_percentage >= 0.25:  # 25-40%
            return "medium"
        else:
            return "low"


async def check_recent_alert_exists(
    db: AsyncSession,
    product_id: int,
    alert_type: str,
    cooldown_hours: int = ALERT_COOLDOWN_HOURS
) -> bool:
    """
    Verifica si ya existe una alerta reciente del mismo tipo para el producto.
    
    Previene generación de alertas duplicadas dentro del período de cooldown.
    
    Args:
        db: Sesión de base de datos
        product_id: ID del producto
        alert_type: Tipo de alerta
        cooldown_hours: Horas de cooldown
        
    Returns:
        True si existe alerta reciente, False si no
    """
    cooldown_threshold = datetime.utcnow() - timedelta(hours=cooldown_hours)
    
    query = select(func.count()).select_from(MarketAlert).where(
        and_(
            MarketAlert.product_id == product_id,
            MarketAlert.alert_type == alert_type,
            MarketAlert.created_at > cooldown_threshold
        )
    )
    
    count = await db.scalar(query) or 0
    return count > 0


async def create_market_alert(
    db: AsyncSession,
    product_id: int,
    alert_type: str,
    old_value: Optional[Decimal],
    new_value: Decimal,
    delta_percentage: Decimal,
    message: str,
    skip_duplicate_check: bool = False
) -> Optional[MarketAlert]:
    """
    Crea una nueva alerta de mercado si no existe una reciente.
    
    Args:
        db: Sesión de base de datos
        product_id: ID del producto
        alert_type: Tipo de alerta
        old_value: Valor anterior (puede ser None)
        new_value: Valor nuevo
        delta_percentage: Cambio porcentual
        message: Mensaje descriptivo
        skip_duplicate_check: Si True, omite verificación de duplicados
        
    Returns:
        Alerta creada o None si se omitió por duplicado
    """
    # Verificar duplicados (a menos que se omita explícitamente)
    if not skip_duplicate_check:
        if await check_recent_alert_exists(db, product_id, alert_type):
            logger.debug(
                f"Alerta duplicada omitida: producto {product_id}, tipo {alert_type}"
            )
            return None
    
    # Determinar severidad
    severity = determine_severity(float(delta_percentage), alert_type)
    
    # Crear alerta
    alert = MarketAlert(
        product_id=product_id,
        alert_type=alert_type,
        severity=severity,
        old_value=old_value,
        new_value=new_value,
        delta_percentage=delta_percentage,
        message=message,
        resolved=False,
        email_sent=False
    )
    
    db.add(alert)
    await db.flush()  # Para obtener el ID
    
    logger.info(
        f"[ALERT] Creada alerta {alert_type} para producto {product_id}: "
        f"{old_value} → {new_value} ({delta_percentage*100:.1f}%) - Severidad: {severity}"
    )
    
    return alert


async def detect_price_alerts(
    db: AsyncSession,
    product_id: int,
    new_market_price: Decimal,
    currency: str = "ARS"
) -> List[MarketAlert]:
    """
    Detecta y genera alertas por variación de precio de mercado.
    
    Esta es la función principal llamada después de cada scraping exitoso.
    
    Tipos de alerta detectados:
    1. sale_vs_market: Precio venta vs nuevo precio mercado
    2. market_vs_previous: Precio mercado nuevo vs anterior
    3. market_spike: Aumento repentino (>30%)
    4. market_drop: Caída repentina (>25%)
    
    Args:
        db: Sesión de base de datos
        product_id: ID del producto
        new_market_price: Nuevo precio de mercado obtenido
        currency: Moneda del precio
        
    Returns:
        Lista de alertas generadas
    """
    alerts_created: List[MarketAlert] = []
    
    try:
        # Obtener producto
        query = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            logger.warning(f"Producto {product_id} no encontrado para detección de alertas")
            return alerts_created
        
        product_name = product.name or f"ID:{product_id}"
        
        # 1. Alerta: Precio venta vs mercado
        if product.sale_price and product.sale_price > 0:
            delta_vs_sale = calculate_percentage_change(product.sale_price, new_market_price)
            
            if delta_vs_sale > Decimal(str(THRESHOLD_SALE_VS_MARKET)):
                difference = new_market_price - product.sale_price
                direction = "mayor" if difference > 0 else "menor"
                
                message = (
                    f"El precio de mercado de '{product_name}' es {direction} al precio de venta "
                    f"en {delta_vs_sale*100:.1f}%. "
                    f"Venta: ${product.sale_price:,.2f} → Mercado: ${new_market_price:,.2f} {currency}"
                )
                
                alert = await create_market_alert(
                    db=db,
                    product_id=product_id,
                    alert_type="sale_vs_market",
                    old_value=product.sale_price,
                    new_value=new_market_price,
                    delta_percentage=delta_vs_sale,
                    message=message
                )
                
                if alert:
                    alerts_created.append(alert)
        
        # 2. Alerta: Precio mercado actual vs anterior
        if product.market_price_reference and product.market_price_reference > 0:
            delta_vs_prev = calculate_percentage_change(
                product.market_price_reference, 
                new_market_price
            )
            
            if delta_vs_prev > Decimal(str(THRESHOLD_MARKET_VS_PREVIOUS)):
                difference = new_market_price - product.market_price_reference
                
                message = (
                    f"El precio de mercado de '{product_name}' cambió {delta_vs_prev*100:.1f}%. "
                    f"Anterior: ${product.market_price_reference:,.2f} → "
                    f"Actual: ${new_market_price:,.2f} {currency}"
                )
                
                # Determinar si es spike o drop
                if difference > 0 and delta_vs_prev > Decimal(str(THRESHOLD_SPIKE)):
                    # Aumento repentino
                    alert_type = "market_spike"
                    message = (
                        f"⚠️ AUMENTO REPENTINO: '{product_name}' subió {delta_vs_prev*100:.1f}%. "
                        f"${product.market_price_reference:,.2f} → ${new_market_price:,.2f} {currency}"
                    )
                elif difference < 0 and delta_vs_prev > Decimal(str(THRESHOLD_DROP)):
                    # Caída repentina
                    alert_type = "market_drop"
                    message = (
                        f"⚠️ CAÍDA REPENTINA: '{product_name}' bajó {delta_vs_prev*100:.1f}%. "
                        f"${product.market_price_reference:,.2f} → ${new_market_price:,.2f} {currency}"
                    )
                else:
                    # Cambio normal
                    alert_type = "market_vs_previous"
                
                alert = await create_market_alert(
                    db=db,
                    product_id=product_id,
                    alert_type=alert_type,
                    old_value=product.market_price_reference,
                    new_value=new_market_price,
                    delta_percentage=delta_vs_prev,
                    message=message
                )
                
                if alert:
                    alerts_created.append(alert)
        
        # Commit de todas las alertas generadas
        if alerts_created:
            await db.commit()
            
            logger.info(
                f"[ALERT] Generadas {len(alerts_created)} alerta(s) para producto {product_id}"
            )
            
            # Programar notificaciones si están habilitadas
            if EMAIL_NOTIFICATIONS_ENABLED:
                for alert in alerts_created:
                    await schedule_alert_notification(db, alert)
        
        return alerts_created
        
    except Exception as e:
        logger.error(
            f"Error al detectar alertas para producto {product_id}: {e}",
            exc_info=True
        )
        await db.rollback()
        return []


# ==================== NOTIFICACIONES ====================

async def schedule_alert_notification(db: AsyncSession, alert: MarketAlert) -> None:
    """
    Programa el envío de notificación por email para una alerta.
    
    Esta función encola la tarea de envío de email sin bloquear
    el proceso principal de scraping.
    
    Args:
        db: Sesión de base de datos
        alert: Alerta a notificar
    """
    if not EMAIL_NOTIFICATIONS_ENABLED:
        return
    
    try:
        # TODO: Integrar con sistema de emails/queue
        # Por ahora solo registramos el intento
        logger.info(f"[ALERT] Programada notificación para alerta {alert.id}")
        
        # Marcar como enviada (placeholder)
        alert.email_sent = True
        alert.email_sent_at = datetime.utcnow()
        await db.commit()
        
    except Exception as e:
        logger.error(f"Error al programar notificación para alerta {alert.id}: {e}")


async def send_alert_email(
    alert: MarketAlert,
    admin_emails: List[str]
) -> bool:
    """
    Envía email de notificación de alerta a administradores.
    
    Args:
        alert: Alerta a notificar
        admin_emails: Lista de emails de administradores
        
    Returns:
        True si se envió exitosamente, False si falló
    """
    # TODO: Implementar envío real de email
    # Placeholder para integración futura
    logger.info(
        f"[ALERT] Enviando email para alerta {alert.id} a {len(admin_emails)} admin(s)"
    )
    return True


# ==================== GESTIÓN DE ALERTAS ====================

async def resolve_alert(
    db: AsyncSession,
    alert_id: int,
    user_id: int,
    resolution_note: Optional[str] = None
) -> Optional[MarketAlert]:
    """
    Marca una alerta como resuelta.
    
    Args:
        db: Sesión de base de datos
        alert_id: ID de la alerta
        user_id: ID del usuario que resuelve
        resolution_note: Nota opcional de resolución
        
    Returns:
        Alerta resuelta o None si no existe
    """
    query = select(MarketAlert).where(MarketAlert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()
    
    if not alert:
        return None
    
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = user_id
    alert.resolution_note = resolution_note
    
    await db.commit()
    await db.refresh(alert)
    
    logger.info(f"[ALERT] Alerta {alert_id} resuelta por usuario {user_id}")
    
    return alert


async def bulk_resolve_alerts(
    db: AsyncSession,
    alert_ids: List[int],
    user_id: int,
    resolution_note: Optional[str] = None
) -> int:
    """
    Marca múltiples alertas como resueltas en lote.
    
    Args:
        db: Sesión de base de datos
        alert_ids: Lista de IDs de alertas
        user_id: ID del usuario que resuelve
        resolution_note: Nota opcional de resolución
        
    Returns:
        Número de alertas resueltas
    """
    if not alert_ids:
        return 0
    
    query = select(MarketAlert).where(MarketAlert.id.in_(alert_ids))
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    count = 0
    for alert in alerts:
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user_id
        alert.resolution_note = resolution_note
        count += 1
    
    await db.commit()
    
    logger.info(f"[ALERT] {count} alertas resueltas en lote por usuario {user_id}")
    
    return count


async def get_active_alerts_count(db: AsyncSession, product_id: int) -> int:
    """
    Obtiene el número de alertas activas para un producto.
    
    Args:
        db: Sesión de base de datos
        product_id: ID del producto
        
    Returns:
        Número de alertas activas
    """
    query = select(func.count()).select_from(MarketAlert).where(
        and_(
            MarketAlert.product_id == product_id,
            MarketAlert.resolved == False
        )
    )
    
    count = await db.scalar(query) or 0
    return count


async def get_alert_statistics(db: AsyncSession) -> Dict[str, Any]:
    """
    Obtiene estadísticas globales de alertas.
    
    Returns:
        Diccionario con métricas
    """
    # Total de alertas activas
    active_query = select(func.count()).select_from(MarketAlert).where(
        MarketAlert.resolved == False
    )
    active_count = await db.scalar(active_query) or 0
    
    # Total de alertas resueltas
    resolved_query = select(func.count()).select_from(MarketAlert).where(
        MarketAlert.resolved == True
    )
    resolved_count = await db.scalar(resolved_query) or 0
    
    # Alertas críticas activas
    critical_query = select(func.count()).select_from(MarketAlert).where(
        and_(
            MarketAlert.resolved == False,
            MarketAlert.severity == "critical"
        )
    )
    critical_count = await db.scalar(critical_query) or 0
    
    # Alertas de las últimas 24 horas
    last_24h = datetime.utcnow() - timedelta(hours=24)
    recent_query = select(func.count()).select_from(MarketAlert).where(
        MarketAlert.created_at > last_24h
    )
    recent_count = await db.scalar(recent_query) or 0
    
    return {
        "active_alerts": active_count,
        "resolved_alerts": resolved_count,
        "critical_alerts": critical_count,
        "alerts_last_24h": recent_count,
        "total_alerts": active_count + resolved_count
    }
