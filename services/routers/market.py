#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: market.py
# NG-HEADER: Ubicación: services/routers/market.py
# NG-HEADER: Descripción: Endpoints del módulo Mercado (comparación de precios)
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field, field_validator, HttpUrl
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging
import traceback

from db.models import CanonicalProduct, Category, ProductEquivalence, SupplierProduct, MarketSource, MarketAlert
from db.session import get_session
from services.auth import require_roles, require_csrf

# Logger para errores del módulo
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])


# Schemas de respuesta
class MarketProductItem(BaseModel):
    """Item de producto para la lista del módulo Mercado"""
    product_id: int = Field(description="ID del producto canónico")
    preferred_name: str = Field(description="Nombre descriptivo del producto")
    product_sku: str = Field(description="SKU del producto (sku_custom, ng_sku o ID)")
    sale_price: Optional[float] = Field(None, description="Precio de venta actual")
    market_price_reference: Optional[float] = Field(None, description="Valor de mercado de referencia")
    market_price_min: Optional[float] = Field(None, description="Precio mínimo detectado en mercado")
    market_price_max: Optional[float] = Field(None, description="Precio máximo detectado en mercado")
    last_market_update: Optional[str] = Field(None, description="Fecha de última actualización del mercado (ISO 8601)")
    has_active_alerts: bool = Field(False, description="Indica si hay alertas activas de precio")
    active_alerts_count: int = Field(0, description="Número de alertas activas")
    category_id: Optional[int] = Field(None, description="ID de categoría")
    category_name: Optional[str] = Field(None, description="Nombre de categoría")
    supplier_id: Optional[int] = Field(None, description="ID del proveedor principal")
    supplier_name: Optional[str] = Field(None, description="Nombre del proveedor principal")

    class Config:
        from_attributes = True


class MarketProductsResponse(BaseModel):
    """Respuesta paginada de productos del módulo Mercado"""
    items: list[MarketProductItem]
    total: int
    page: int
    page_size: int
    pages: int


@router.get(
    "/products",
    response_model=MarketProductsResponse,
    dependencies=[Depends(require_roles("colaborador", "admin"))],
    summary="Listar productos para módulo Mercado",
    description="""
    Retorna lista de productos con información de precios para el módulo Mercado.
    
    Incluye:
    - Precio de venta actual
    - Valor de mercado de referencia (ingresado manualmente)
    - Rango de precios de mercado (min-max, calculado desde fuentes cuando estén disponibles)
    - Fecha de última actualización
    
    Soporta filtros por nombre, categoría y proveedor.
    Resultados ordenados alfabéticamente por nombre.
    """,
)
async def list_market_products(
    q: Optional[str] = Query(None, description="Búsqueda por nombre (parcial, case-insensitive)"),
    category_id: Optional[int] = Query(None, description="Filtrar por ID de categoría"),
    supplier_id: Optional[int] = Query(None, description="Filtrar por ID de proveedor"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Tamaño de página"),
    db: AsyncSession = Depends(get_session),
):
    """
    Lista productos del módulo Mercado con filtros opcionales.
    
    La lógica de "preferred_name" se determina de la siguiente manera:
    1. Si existe nombre personalizado (sku_custom), usar ese nombre
    2. Si no, usar el nombre base del producto canónico
    
    El precio de venta proviene del campo `sale_price` del producto canónico.
    
    El valor de mercado de referencia proviene del campo `market_price_reference` del producto.
    
    Nota: Los campos market_price_min, market_price_max y last_market_update
    estarán disponibles cuando se implemente la tabla market_sources (Etapa 2).
    Por ahora retornan None.
    """
    
    # Query base: productos canónicos
    # Subquery para contar alertas activas por producto
    alert_subquery = (
        select(
            MarketAlert.product_id,
            func.count().label("alert_count")
        )
        .where(MarketAlert.resolved == False)
        .group_by(MarketAlert.product_id)
        .subquery()
    )
    
    # Query principal con join de alertas
    query = select(
        CanonicalProduct,
        func.coalesce(alert_subquery.c.alert_count, 0).label("alert_count")
    ).outerjoin(
        alert_subquery, CanonicalProduct.id == alert_subquery.c.product_id
    ).options(
        selectinload(CanonicalProduct.category),
        selectinload(CanonicalProduct.subcategory),
        selectinload(CanonicalProduct.equivalences).selectinload(ProductEquivalence.supplier),
    )
    
    # Filtros
    conditions = []
    
    # Filtro por nombre (búsqueda en name o sku_custom)
    if q:
        search_term = f"%{q}%"
        conditions.append(
            or_(
                func.lower(CanonicalProduct.name).like(func.lower(search_term)),
                func.lower(CanonicalProduct.sku_custom).like(func.lower(search_term)),
                func.lower(CanonicalProduct.ng_sku).like(func.lower(search_term)),
            )
        )
    
    # Filtro por categoría
    if category_id:
        conditions.append(
            or_(
                CanonicalProduct.category_id == category_id,
                CanonicalProduct.subcategory_id == category_id,
            )
        )
    
    # Filtro por proveedor (a través de ProductEquivalence)
    if supplier_id:
        # Subquery: IDs de productos canónicos que tienen equivalencias con este proveedor
        subq = (
            select(ProductEquivalence.canonical_product_id)
            .where(ProductEquivalence.supplier_id == supplier_id)
            .distinct()
        )
        conditions.append(CanonicalProduct.id.in_(subq))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Orden alfabético por nombre
    query = query.order_by(func.lower(CanonicalProduct.name))
    
    # Conteo total (necesitamos contar productos distintos)
    count_query = (
        select(func.count(func.distinct(CanonicalProduct.id)))
        .select_from(CanonicalProduct)
        .outerjoin(alert_subquery, CanonicalProduct.id == alert_subquery.c.product_id)
    )
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = await db.scalar(count_query) or 0
    
    # Paginación
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Ejecución
    result = await db.execute(query)
    rows = result.all()
    
    # Construcción de items
    items = []
    for row in rows:
        prod = row[0]  # CanonicalProduct
        alert_count = row[1] if len(row) > 1 else 0  # alert_count
        
        # preferred_name: siempre usar el nombre descriptivo (campo name)
        preferred_name = prod.name
        
        # SKU: priorizar sku_custom, luego ng_sku, finalmente el ID
        product_sku = prod.sku_custom or prod.ng_sku or f"ID-{prod.id}"
        
        # Determinar categoría principal
        category_id_val = prod.category_id
        category_name_val = None
        if prod.category:
            category_name_val = prod.category.name
        elif prod.subcategory:
            category_name_val = prod.subcategory.name
            category_id_val = prod.subcategory_id
        
        # Obtener proveedor principal (primera equivalencia)
        # TODO: Mejorar lógica para determinar "proveedor principal" cuando haya múltiples
        supplier_id_val = None
        supplier_name_val = None
        
        # Cargar equivalencias para obtener proveedor
        if hasattr(prod, 'equivalences') and prod.equivalences:
            first_eq = prod.equivalences[0]
            if hasattr(first_eq, 'supplier_id'):
                supplier_id_val = first_eq.supplier_id
                # Cargar nombre del proveedor si está disponible
                if hasattr(first_eq, 'supplier') and first_eq.supplier:
                    supplier_name_val = first_eq.supplier.name
        
        # Calcular market_price_min, market_price_max desde market_sources
        market_price_min_val = None
        market_price_max_val = None
        
        # Consultar precios de fuentes del producto
        query_prices = (
            select(MarketSource.last_price)
            .where(
                and_(
                    MarketSource.product_id == prod.id,
                    MarketSource.last_price.isnot(None)
                )
            )
        )
        result_prices = await db.execute(query_prices)
        prices = [float(p) for p in result_prices.scalars().all() if p is not None]
        
        if prices:
            market_price_min_val = min(prices)
            market_price_max_val = max(prices)
        
        # Usar market_price_updated_at del producto como last_market_update
        last_market_update_val = None
        if prod.market_price_updated_at:
            last_market_update_val = prod.market_price_updated_at.isoformat()
        
        item = MarketProductItem(
            product_id=prod.id,
            preferred_name=preferred_name,
            product_sku=product_sku,
            sale_price=float(prod.sale_price) if prod.sale_price else None,
            market_price_reference=float(prod.market_price_reference) if prod.market_price_reference else None,
            market_price_min=market_price_min_val,
            market_price_max=market_price_max_val,
            last_market_update=last_market_update_val,
            has_active_alerts=(alert_count > 0),
            active_alerts_count=int(alert_count),
            category_id=category_id_val,
            category_name=category_name_val,
            supplier_id=supplier_id_val,
            supplier_name=supplier_name_val,
        )
        items.append(item)
    
    # Calcular número total de páginas
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return MarketProductsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# Schemas para fuentes de precios
class MarketSourceItem(BaseModel):
    """Fuente de precio de mercado individual"""
    id: int = Field(description="ID de la fuente")
    source_name: str = Field(description="Nombre de la tienda o sitio")
    url: str = Field(description="URL de la fuente")
    currency: Optional[str] = Field(None, description="Moneda del precio (ARS, USD, etc.)")
    source_type: Optional[str] = Field(None, description="Tipo de fuente: 'static' o 'dynamic'")
    last_price: Optional[float] = Field(None, description="Último precio obtenido")
    last_checked_at: Optional[str] = Field(None, description="Timestamp de última actualización (ISO 8601)")
    is_mandatory: bool = Field(description="Indica si es fuente obligatoria")
    created_at: str = Field(description="Fecha de creación (ISO 8601)")
    updated_at: str = Field(description="Fecha de última modificación (ISO 8601)")

    class Config:
        from_attributes = True


class ProductSourcesResponse(BaseModel):
    """Respuesta con detalle de fuentes de un producto"""
    product_id: int
    product_name: str
    sale_price: Optional[float] = None
    market_price_reference: Optional[float] = None
    market_price_updated_at: Optional[str] = Field(None, description="Fecha de última actualización del precio de mercado (ISO 8601)")
    market_price_min: Optional[float] = Field(None, description="Precio mínimo calculado desde fuentes")
    market_price_max: Optional[float] = Field(None, description="Precio máximo calculado desde fuentes")
    mandatory: list[MarketSourceItem] = Field(description="Fuentes obligatorias")
    additional: list[MarketSourceItem] = Field(description="Fuentes adicionales")


@router.get(
    "/products/{product_id}/sources",
    response_model=ProductSourcesResponse,
    dependencies=[Depends(require_roles("colaborador", "admin"))],
    summary="Obtener fuentes de precio de un producto",
    description="""
    Retorna todas las fuentes de precio de mercado configuradas para un producto.
    
    Las fuentes se dividen en:
    - **Obligatorias**: Marcadas como is_mandatory=True, prioritarias para cálculo de rango
    - **Adicionales**: Fuentes opcionales agregadas por el usuario
    
    Incluye último precio obtenido y timestamp de última actualización para cada fuente.
    """,
)
async def get_product_sources(
    product_id: int,
    db: AsyncSession = Depends(get_session),
):
    """
    Obtiene las fuentes de precio de mercado de un producto.
    
    Args:
        product_id: ID del producto canónico
        db: Sesión de base de datos
    
    Returns:
        ProductSourcesResponse con fuentes obligatorias y adicionales
    
    Raises:
        HTTPException 404: Producto no encontrado
    """
    # Verificar que el producto exista
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto con ID {product_id} no encontrado")
    
    # Obtener fuentes de precio ordenadas por is_mandatory DESC, created_at ASC
    query_sources = (
        select(MarketSource)
        .where(MarketSource.product_id == product_id)
        .order_by(MarketSource.is_mandatory.desc(), MarketSource.created_at.asc())
    )
    result_sources = await db.execute(query_sources)
    sources = result_sources.scalars().all()
    
    # Separar fuentes obligatorias y adicionales
    mandatory_sources = []
    additional_sources = []
    prices = []  # Para calcular min/max
    
    for source in sources:
        item = MarketSourceItem(
            id=source.id,
            source_name=source.source_name,
            url=source.url,
            last_price=float(source.last_price) if source.last_price else None,
            last_checked_at=source.last_checked_at.isoformat() if source.last_checked_at else None,
            is_mandatory=source.is_mandatory,
            created_at=source.created_at.isoformat(),
            updated_at=source.updated_at.isoformat(),
        )
        
        # Recopilar precios válidos para cálculo de rango
        if source.last_price is not None:
            prices.append(float(source.last_price))
        
        if source.is_mandatory:
            mandatory_sources.append(item)
        else:
            additional_sources.append(item)
    
    # Calcular rango de precios de mercado
    market_price_min_val = min(prices) if prices else None
    market_price_max_val = max(prices) if prices else None
    
    # Usar siempre el nombre descriptivo del producto
    product_name = product.name
    
    return ProductSourcesResponse(
        product_id=product.id,
        product_name=product_name,
        sale_price=float(product.sale_price) if product.sale_price else None,
        market_price_reference=float(product.market_price_reference) if product.market_price_reference else None,
        market_price_updated_at=product.market_price_updated_at.isoformat() if product.market_price_updated_at else None,
        market_price_min=market_price_min_val,
        market_price_max=market_price_max_val,
        mandatory=mandatory_sources,
        additional=additional_sources,
    )


# Schema para actualizar precio de venta
class UpdateSalePriceRequest(BaseModel):
    """Request para actualizar precio de venta"""
    sale_price: float = Field(description="Nuevo precio de venta (debe ser > 0)", gt=0)
    
    @field_validator('sale_price')
    @classmethod
    def validate_sale_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El precio de venta debe ser mayor a cero")
        if v > 999999999:
            raise ValueError("El precio de venta es demasiado alto")
        return v


class UpdateSalePriceResponse(BaseModel):
    """Respuesta al actualizar precio de venta"""
    product_id: int
    product_name: str
    sale_price: float
    previous_price: Optional[float]
    updated_at: str


@router.patch(
    "/products/{product_id}/sale-price",
    response_model=UpdateSalePriceResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    summary="Actualizar precio de venta de un producto",
    description="""
    Actualiza el precio de venta (sale_price) de un producto canónico.
    
    Validaciones:
    - Producto debe existir (404 si no)
    - Precio debe ser numérico positivo > 0
    - Precio debe ser <= 999,999,999 (validación de rango)
    
    El cambio actualiza automáticamente el campo `updated_at` del producto.
    """,
)
async def update_product_sale_price(
    product_id: int,
    payload: UpdateSalePriceRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza el precio de venta de un producto.
    
    Args:
        product_id: ID del producto canónico
        payload: Objeto con nuevo sale_price
        db: Sesión de base de datos
    
    Returns:
        UpdateSalePriceResponse con precio actualizado
    
    Raises:
        HTTPException 404: Producto no encontrado
        HTTPException 422: Validación de precio fallida
    """
    # Verificar que el producto exista
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto con ID {product_id} no encontrado")
    
    # Guardar precio anterior para respuesta
    previous_price = float(product.sale_price) if product.sale_price else None
    
    # Actualizar precio
    product.sale_price = Decimal(str(payload.sale_price))
    product.updated_at = datetime.utcnow()
    
    # Guardar cambios
    await db.commit()
    await db.refresh(product)
    
    # Usar nombre descriptivo del producto
    product_name = product.name
    
    return UpdateSalePriceResponse(
        product_id=product.id,
        product_name=product_name,
        sale_price=float(product.sale_price),
        previous_price=previous_price,
        updated_at=product.updated_at.isoformat(),
    )


# ==================== PATCH /products/{id}/market-reference ====================

class UpdateMarketReferenceRequest(BaseModel):
    """Request para actualizar precio de mercado de referencia"""
    market_price_reference: float = Field(
        description="Nuevo precio de mercado de referencia (debe ser >= 0)",
        ge=0
    )
    
    @field_validator('market_price_reference')
    @classmethod
    def validate_market_price(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El precio de mercado debe ser mayor o igual a cero")
        if v > 999999999:
            raise ValueError("El precio de mercado es demasiado alto")
        return v


class UpdateMarketReferenceResponse(BaseModel):
    """Respuesta al actualizar precio de mercado de referencia"""
    product_id: int
    product_name: str
    market_price_reference: float
    previous_market_price: Optional[float]
    market_price_updated_at: str


@router.patch(
    "/products/{product_id}/market-reference",
    response_model=UpdateMarketReferenceResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    summary="Actualizar precio de mercado de referencia de un producto",
    description="""
    Actualiza el precio de mercado de referencia (market_price_reference) de un producto canónico.
    Este valor se usa para comparar con el precio de venta y detectar desviaciones de mercado.
    
    Validaciones:
    - Producto debe existir (404 si no)
    - Precio debe ser numérico >= 0
    - Precio debe ser <= 999,999,999 (validación de rango)
    
    El cambio actualiza automáticamente el campo `market_price_updated_at` del producto.
    
    Roles permitidos: admin, colaborador
    """,
)
async def update_product_market_reference(
    product_id: int,
    payload: UpdateMarketReferenceRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza manualmente el precio de mercado de referencia de un producto.
    
    Args:
        product_id: ID del producto canónico a actualizar
        payload: Datos con el nuevo precio de mercado
        db: Sesión de base de datos
        
    Returns:
        UpdateMarketReferenceResponse con el precio actualizado y timestamp
        
    Raises:
        HTTPException 404: Producto no encontrado
        HTTPException 422: Validación de precio fallida
    """
    # 1. Verificar que el producto existe
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # 2. Guardar precio anterior para respuesta
    previous_market_price = float(product.market_price_reference) if product.market_price_reference else None
    
    # 3. Actualizar precio de mercado y timestamp
    product.market_price_reference = Decimal(str(payload.market_price_reference))
    product.market_price_updated_at = datetime.utcnow()
    product.updated_at = datetime.utcnow()  # También actualizar updated_at general
    
    # 4. Guardar cambios
    await db.commit()
    await db.refresh(product)
    
    # 5. Calcular nombre preferido
    preferred_name = product.sku_custom if product.sku_custom else product.name
    
    return UpdateMarketReferenceResponse(
        product_id=product.id,
        product_name=preferred_name,
        market_price_reference=float(product.market_price_reference),
        previous_market_price=previous_market_price,
        market_price_updated_at=product.market_price_updated_at.isoformat(),
    )


# ==================== POST /products/{id}/refresh-market ====================

class RefreshMarketResponse(BaseModel):
    """Respuesta al iniciar actualización de precios de mercado"""
    status: str = Field(description="Estado del proceso: 'processing', 'enqueued'")
    message: str = Field(description="Mensaje descriptivo")
    product_id: int = Field(description="ID del producto")
    job_id: Optional[str] = Field(None, description="ID del job encolado (si disponible)")


@router.post(
    "/products/{product_id}/refresh-market",
    response_model=RefreshMarketResponse,
    status_code=202,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    summary="Iniciar actualización de precios de mercado",
    description="""
    Inicia el proceso asíncrono de scraping de precios de mercado para un producto.
    
    El proceso:
    1. Valida que el producto exista
    2. Encola una tarea de scraping en segundo plano
    3. Retorna inmediatamente con status 202 Accepted
    4. El worker procesa cada fuente de precio del producto
    5. Actualiza los precios en la base de datos
    
    La actualización puede demorar varios segundos dependiendo de la cantidad de fuentes
    y la latencia de los sitios externos. La UI debe mostrar un indicador de carga
    y refrescar los datos periódicamente.
    
    Roles permitidos: admin, colaborador
    """,
)
async def refresh_market_prices(
    product_id: int,
    db: AsyncSession = Depends(get_session),
):
    """
    Dispara actualización asíncrona de precios de mercado de un producto.
    
    Args:
        product_id: ID del producto canónico a actualizar
        db: Sesión de base de datos
        
    Returns:
        RefreshMarketResponse con status de encolado
        
    Raises:
        HTTPException 404: Producto no encontrado
        HTTPException 502: Error al comunicarse con el servicio de scraping
        HTTPException 500: Error interno del servidor
    """
    # 1. Verificar que el producto existe
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        logger.warning(f"[refresh_market] Producto {product_id} no encontrado")
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # 2. Encolar tarea de scraping en Dramatiq
    try:
        # Importar la tarea del worker
        from workers.market_scraping import refresh_market_prices_task
        
        logger.info(f"[refresh_market] Encolando tarea para producto {product_id}")
        
        # Enviar tarea a la cola (non-blocking)
        message = refresh_market_prices_task.send(product_id)
        
        # Extraer job_id del mensaje de Dramatiq
        job_id = message.message_id if hasattr(message, 'message_id') else None
        
        logger.info(f"[refresh_market] Tarea encolada exitosamente para producto {product_id}, job_id={job_id}")
        
        return RefreshMarketResponse(
            status="processing",
            message=f"Actualización de precios de mercado iniciada para producto {product_id}",
            product_id=product_id,
            job_id=job_id,
        )
        
    except ImportError as e:
        # Worker no disponible o mal configurado
        logger.error(f"[refresh_market] Error importando worker: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Servicio de actualización de precios no disponible"
        )
    except Exception as e:
        # Error inesperado al encolar
        logger.error(
            f"[refresh_market] Error inesperado al encolar tarea para producto {product_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Error interno al iniciar actualización de precios"
        )


# ==================== POST /products/{id}/sources ====================

class AddSourceRequest(BaseModel):
    """Request para agregar nueva fuente de precio"""
    source_name: str = Field(
        description="Nombre identificatorio de la fuente",
        min_length=3,
        max_length=200
    )
    url: str = Field(
        description="URL de la fuente (debe ser válida y única por producto)",
        min_length=10,
        max_length=500
    )
    is_mandatory: bool = Field(
        default=False,
        description="Si es fuente obligatoria para el producto"
    )
    currency: Optional[str] = Field(
        default="ARS",
        description="Moneda del precio (ARS, USD, etc.)",
        max_length=10
    )
    source_type: Optional[str] = Field(
        default="static",
        description="Tipo de fuente: 'static' (HTML estático) o 'dynamic' (requiere JavaScript)"
    )
    
    @field_validator('source_name')
    @classmethod
    def validate_source_name(cls, v: str) -> str:
        """Valida el nombre de la fuente"""
        v_stripped = v.strip()
        if len(v_stripped) < 3:
            raise ValueError("El nombre de la fuente debe tener al menos 3 caracteres")
        if len(v_stripped) > 200:
            raise ValueError("El nombre de la fuente no puede exceder 200 caracteres")
        # Verificar que no sea solo espacios
        if not v_stripped:
            raise ValueError("El nombre de la fuente no puede estar vacío")
        return v_stripped
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Valida formato de URL"""
        from urllib.parse import urlparse
        
        v_stripped = v.strip()
        
        # Validar longitud
        if len(v_stripped) < 10:
            raise ValueError("La URL debe tener al menos 10 caracteres")
        if len(v_stripped) > 500:
            raise ValueError("La URL no puede exceder 500 caracteres")
        
        # Validar que sea una URL bien formada
        try:
            result = urlparse(v_stripped)
        except Exception:
            raise ValueError("URL con formato inválido")
        
        if not all([result.scheme, result.netloc]):
            raise ValueError("URL debe incluir esquema (http/https) y dominio válido")
        if result.scheme not in ['http', 'https']:
            raise ValueError("URL debe usar protocolo http o https")
        
        # Validar que el dominio tenga al menos un punto (ej: example.com)
        if '.' not in result.netloc:
            raise ValueError("URL debe contener un dominio válido (ej: example.com)")
        
        return v_stripped
    
    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        """Valida que source_type sea 'static' o 'dynamic'"""
        if v is not None and v not in ['static', 'dynamic']:
            raise ValueError("source_type debe ser 'static' o 'dynamic'")
        return v
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato de moneda (códigos ISO 4217 comunes)"""
        if v is None:
            return "ARS"
        
        v_upper = v.strip().upper()
        
        # Lista de monedas comunes aceptadas
        valid_currencies = ['ARS', 'USD', 'EUR', 'BRL', 'CLP', 'UYU', 'PYG', 'BOB', 'MXN', 'COP', 'PEN']
        
        if v_upper not in valid_currencies:
            raise ValueError(
                f"Moneda '{v}' no soportada. Monedas válidas: {', '.join(valid_currencies)}"
            )
        
        return v_upper


class AddSourceResponse(BaseModel):
    """Respuesta al agregar fuente de precio"""
    id: int
    product_id: int
    source_name: str
    url: str
    is_mandatory: bool
    currency: Optional[str]
    source_type: Optional[str]
    last_price: Optional[float]
    last_checked_at: Optional[str]
    created_at: str


@router.post(
    "/products/{product_id}/sources",
    response_model=AddSourceResponse,
    status_code=201,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    summary="Agregar nueva fuente de precio a un producto",
    description="""
    Crea una nueva fuente de precio externa para un producto canónico.
    
    Validaciones:
    - Producto debe existir (404 si no)
    - URL debe ser válida (http/https con dominio)
    - URL debe ser única por producto (409 si ya existe)
    - Nombre de fuente requerido
    
    La fuente se crea sin precio inicial (last_price=null, last_checked_at=null).
    Para obtener precios, usar POST /products/{id}/refresh-market.
    
    Roles permitidos: admin, colaborador
    """,
)
async def add_market_source(
    product_id: int,
    payload: AddSourceRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Agrega una nueva fuente de precio de mercado a un producto.
    
    Args:
        product_id: ID del producto canónico
        payload: Datos de la fuente (nombre, URL, is_mandatory)
        db: Sesión de base de datos
        
    Returns:
        AddSourceResponse con la fuente creada
        
    Raises:
        HTTPException 404: Producto no encontrado
        HTTPException 409: URL ya existe para este producto
    """
    # 1. Verificar que el producto existe
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # 2. Verificar que la URL no esté duplicada para este producto
    query_duplicate = select(MarketSource).where(
        and_(
            MarketSource.product_id == product_id,
            MarketSource.url == payload.url
        )
    )
    result_duplicate = await db.execute(query_duplicate)
    existing_source = result_duplicate.scalar_one_or_none()
    
    if existing_source:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una fuente con la URL {payload.url} para este producto"
        )
    
    # 3. Crear nueva fuente
    new_source = MarketSource(
        product_id=product_id,
        source_name=payload.source_name,
        url=payload.url,
        is_mandatory=payload.is_mandatory,
        currency=payload.currency,
        source_type=payload.source_type,
        last_price=None,
        last_checked_at=None,
    )
    
    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)
    
    return AddSourceResponse(
        id=new_source.id,
        product_id=new_source.product_id,
        source_name=new_source.source_name,
        url=new_source.url,
        is_mandatory=new_source.is_mandatory,
        currency=new_source.currency,
        source_type=new_source.source_type,
        last_price=float(new_source.last_price) if new_source.last_price else None,
        last_checked_at=new_source.last_checked_at.isoformat() if new_source.last_checked_at else None,
        created_at=new_source.created_at.isoformat(),
    )


# ==================== DELETE /sources/{source_id} ====================

@router.delete(
    "/sources/{source_id}",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    summary="Eliminar fuente de precio",
    description="""
    Elimina una fuente de precio de mercado.
    
    Validaciones:
    - Fuente debe existir (404 si no)
    - Solo usuarios autorizados pueden eliminar
    
    La eliminación es permanente y no se puede deshacer.
    Si el producto tiene precios calculados desde esta fuente,
    se recomienda actualizar con POST /products/{id}/refresh-market
    después de eliminarla.
    
    Roles permitidos: admin, colaborador
    """,
)
async def delete_market_source(
    source_id: int,
    db: AsyncSession = Depends(get_session),
):
    """
    Elimina una fuente de precio de mercado.
    
    Args:
        source_id: ID de la fuente a eliminar
        db: Sesión de base de datos
        
    Returns:
        204 No Content (sin body)
        
    Raises:
        HTTPException 404: Fuente no encontrada
    """
    # 1. Verificar que la fuente existe
    query_source = select(MarketSource).where(MarketSource.id == source_id)
    result = await db.execute(query_source)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"Fuente con ID {source_id} no encontrada"
        )
    
    # 2. Eliminar fuente
    await db.delete(source)
    await db.commit()
    
    # 3. Retornar 204 No Content (FastAPI maneja automáticamente sin body)
    return None


# ==================== PATCH /sources/{source_id} ====================

class UpdateMarketSourceRequest(BaseModel):
    """Request para actualizar una fuente de precio."""
    source_name: Optional[str] = Field(None, description="Nuevo nombre de la fuente")
    url: Optional[str] = Field(None, description="Nueva URL de la fuente")
    last_price: Optional[float] = Field(None, description="Nuevo último precio detectado")
    is_mandatory: Optional[bool] = Field(None, description="Si es fuente obligatoria")


@router.patch(
    "/sources/{source_id}",
    status_code=200,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
    summary="Actualizar fuente de precio",
    description="""
    Actualiza los datos de una fuente de precio de mercado.
    
    Campos editables:
    - source_name: Nombre/título de la fuente
    - url: URL de la fuente
    - last_price: Último precio detectado manualmente
    - is_mandatory: Si es fuente obligatoria para cálculo de precio promedio
    
    Solo se actualizan los campos enviados (partial update).
    
    Roles permitidos: admin, colaborador
    """,
)
async def update_market_source(
    source_id: int,
    request: UpdateMarketSourceRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza una fuente de precio de mercado.
    
    Args:
        source_id: ID de la fuente a actualizar
        request: Datos a actualizar
        db: Sesión de base de datos
        
    Returns:
        Fuente actualizada
        
    Raises:
        HTTPException 404: Fuente no encontrada
        HTTPException 400: URL duplicada
    """
    # 1. Verificar que la fuente existe
    query_source = select(MarketSource).where(MarketSource.id == source_id)
    result = await db.execute(query_source)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"Fuente con ID {source_id} no encontrada"
        )
    
    # 2. Verificar URL duplicada si se está cambiando
    if request.url and request.url != source.url:
        query_duplicate = select(MarketSource).where(
            MarketSource.product_id == source.product_id,
            MarketSource.url == request.url,
            MarketSource.id != source_id
        )
        result_dup = await db.execute(query_duplicate)
        if result_dup.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe una fuente con URL '{request.url}' para este producto"
            )
    
    # 3. Actualizar campos (solo los enviados)
    if request.source_name is not None:
        source.source_name = request.source_name
    
    if request.url is not None:
        source.url = request.url
    
    if request.last_price is not None:
        from decimal import Decimal
        source.last_price = Decimal(str(request.last_price))
        source.last_checked_at = datetime.utcnow()
    
    if request.is_mandatory is not None:
        source.is_mandatory = request.is_mandatory
    
    # 4. Guardar cambios
    await db.commit()
    await db.refresh(source)
    
    # 5. Retornar fuente actualizada
    return {
        "id": source.id,
        "product_id": source.product_id,
        "source_name": source.source_name,
        "url": source.url,
        "last_price": float(source.last_price) if source.last_price else None,
        "last_checked_at": source.last_checked_at.isoformat() if source.last_checked_at else None,
        "is_mandatory": source.is_mandatory,
        "currency": source.currency,
        "source_type": source.source_type,
    }


# ==================== POST /products/{id}/discover-sources ====================

class DiscoveredSource(BaseModel):
    """Fuente descubierta automáticamente"""
    url: str = Field(description="URL de la fuente descubierta")
    title: str = Field(description="Título del resultado de búsqueda")
    snippet: str = Field(description="Snippet con contexto del resultado")


class DiscoverSourcesResponse(BaseModel):
    """Respuesta del descubrimiento automático de fuentes"""
    success: bool = Field(description="Si el descubrimiento fue exitoso")
    query: str = Field(description="Query de búsqueda utilizada")
    total_results: int = Field(description="Total de resultados obtenidos del buscador")
    valid_sources: int = Field(description="Cantidad de fuentes válidas encontradas")
    sources: list[DiscoveredSource] = Field(description="Fuentes descubiertas (no duplicadas)")
    error: Optional[str] = Field(None, description="Mensaje de error si hubo fallo")


@router.post(
    "/products/{product_id}/discover-sources",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))],
    response_model=DiscoverSourcesResponse,
    status_code=200,
)
async def discover_product_sources(
    product_id: int,
    max_results: int = Query(15, ge=5, le=30, description="Máximo de resultados a solicitar al buscador"),
    db: AsyncSession = Depends(get_session),
) -> DiscoverSourcesResponse:
    """
    Descubre automáticamente nuevas fuentes de precios para un producto usando MCP Web Search.
    
    **Proceso**:
    1. Construye query contextual: `{nombre_producto} precio {categoría} comprar`
    2. Consulta MCP Web Search (DuckDuckGo) con la query
    3. Filtra resultados:
       - Solo dominios de e-commerce conocidos (MercadoLibre, growshops, etc.)
       - Solo snippets con indicadores de precio ($, "precio", "comprar", etc.)
       - Excluye URLs ya existentes para el producto
    4. Retorna hasta 10 fuentes válidas sugeridas
    
    **Roles permitidos**: `admin`, `colaborador`
    
    **Variables de entorno**:
    - `MCP_WEB_SEARCH_URL`: URL del servicio MCP Web Search
    
    **Nota**: Las fuentes descubiertas son sugerencias. El usuario debe revisarlas y
    agregarlas manualmente mediante `POST /products/{id}/sources` si las considera válidas.
    
    **Errores**:
    - 404: Producto no encontrado
    - 500: Error del servicio MCP Web Search o red
    """
    # 1. Verificar que el producto existe y obtener datos
    query_product = (
        select(CanonicalProduct)
        .where(CanonicalProduct.id == product_id)
        .options(selectinload(CanonicalProduct.category))
    )
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # 2. Obtener fuentes existentes para evitar duplicados
    query_sources = select(MarketSource.url).where(MarketSource.product_id == product_id)
    result_sources = await db.execute(query_sources)
    existing_urls = [row[0] for row in result_sources.all()]
    
    # 3. Preparar datos para el descubrimiento
    product_name = product.name or ""
    category_name = product.category.name if product.category else ""
    sku = product.ng_sku or ""
    
    # 4. Llamar al descubridor automático
    from workers.discovery.source_finder import discover_price_sources
    
    discovery_result = await discover_price_sources(
        product_name=product_name,
        category=category_name,
        sku=sku,
        existing_urls=existing_urls,
        max_results=max_results,
        user_role="admin",  # Siempre usar admin para MCP (el endpoint ya valida roles)
    )
    
    # 5. Convertir a schema de respuesta
    return DiscoverSourcesResponse(
        success=discovery_result["success"],
        query=discovery_result["query"],
        total_results=discovery_result["total_results"],
        valid_sources=discovery_result["valid_sources"],
        sources=[
            DiscoveredSource(**source)
            for source in discovery_result.get("sources", [])
        ],
        error=discovery_result.get("error"),
    )


# ==================== POST /products/{id}/sources/from-suggestion ====================

class AddSuggestedSourceRequest(BaseModel):
    """Request para agregar una fuente desde sugerencia"""
    url: str = Field(
        description="URL de la fuente sugerida",
        min_length=10,
        max_length=500
    )
    source_name: Optional[str] = Field(
        None,
        description="Nombre de la fuente (opcional, se detecta del dominio si falta)",
        min_length=3,
        max_length=200
    )
    validate_price: bool = Field(
        True,
        description="Si True, valida que exista precio antes de agregar"
    )
    source_type: Optional[str] = Field(
        "static",
        description="Tipo de fuente: 'static' o 'dynamic'"
    )
    is_mandatory: bool = Field(
        False,
        description="Si es fuente obligatoria"
    )
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Valida formato de URL"""
        from urllib.parse import urlparse
        
        v_stripped = v.strip()
        
        if len(v_stripped) < 10:
            raise ValueError("La URL debe tener al menos 10 caracteres")
        if len(v_stripped) > 500:
            raise ValueError("La URL no puede exceder 500 caracteres")
        
        try:
            result = urlparse(v_stripped)
        except Exception:
            raise ValueError("URL con formato inválido")
        
        if not all([result.scheme, result.netloc]):
            raise ValueError("URL debe incluir esquema (http/https) y dominio válido")
        if result.scheme not in ['http', 'https']:
            raise ValueError("URL debe usar protocolo http o https")
        if '.' not in result.netloc:
            raise ValueError("URL debe contener un dominio válido")
        
        return v_stripped
    
    @field_validator('source_name')
    @classmethod
    def validate_source_name(cls, v: Optional[str]) -> Optional[str]:
        """Valida el nombre de la fuente si está presente"""
        if v is None:
            return None
        
        v_stripped = v.strip()
        if len(v_stripped) < 3:
            raise ValueError("El nombre de la fuente debe tener al menos 3 caracteres")
        if len(v_stripped) > 200:
            raise ValueError("El nombre de la fuente no puede exceder 200 caracteres")
        
        return v_stripped
    
    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        """Valida que source_type sea 'static' o 'dynamic'"""
        if v is not None and v not in ['static', 'dynamic']:
            raise ValueError("source_type debe ser 'static' o 'dynamic'")
        return v if v else "static"


class AddSuggestedSourceResponse(BaseModel):
    """Respuesta al agregar fuente sugerida"""
    success: bool = Field(description="Si la fuente se agregó exitosamente")
    source_id: Optional[int] = Field(None, description="ID de la fuente creada")
    message: str = Field(description="Mensaje descriptivo del resultado")
    validation_result: Optional[dict] = Field(None, description="Resultado de la validación si se ejecutó")


@router.post(
    "/products/{product_id}/sources/from-suggestion",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))],
    response_model=AddSuggestedSourceResponse,
    status_code=201,
)
async def add_source_from_suggestion(
    product_id: int,
    request: AddSuggestedSourceRequest,
    db: AsyncSession = Depends(get_session),
) -> AddSuggestedSourceResponse:
    """
    Agrega una fuente de precio desde una sugerencia del sistema con validación automática.
    
    **Proceso**:
    1. Verifica que el producto existe
    2. Verifica que la URL no esté duplicada
    3. Si `validate_price=True`:
       - Dominios de alta confianza: agrega directamente
       - Otros: valida que exista precio en la URL
    4. Crea el registro de `MarketSource`
    
    **Roles permitidos**: `admin`, `colaborador`
    
    **Validación de precio**:
    - Dominios de alta confianza (MercadoLibre, SantaPlanta, etc.): aprobación automática
    - Otros dominios: scraping rápido para detectar patrones de precio ($, "precio", meta tags)
    - Timeout: 10 segundos
    
    **Errores**:
    - 400: URL duplicada o precio no detectado
    - 404: Producto no encontrado
    - 500: Error de validación o red
    
    **Nota**: Si `validate_price=False`, la fuente se agrega sin validar (útil para
    fuentes que requieren JS o login, pero usar con precaución).
    """
    from urllib.parse import urlparse
    from workers.discovery.source_validator import validate_source
    
    # 1. Verificar que el producto existe
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # 2. Verificar que la URL no esté duplicada
    query_existing = select(MarketSource).where(
        and_(
            MarketSource.product_id == product_id,
            MarketSource.url == request.url
        )
    )
    result_existing = await db.execute(query_existing)
    existing_source = result_existing.scalar_one_or_none()
    
    if existing_source:
        logger.warning(
            f"[add_source_from_suggestion] URL duplicada: {request.url} ya existe para producto {product_id}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una fuente con esta URL para el producto"
        )
    
    # 3. Validar precio si está habilitado
    validation_result = None
    if request.validate_price:
        try:
            from workers.discovery.source_validator import validate_source
            
            logger.info(f"[add_source_from_suggestion] Validando precio en {request.url}")
            is_valid, reason = await validate_source(request.url, quick=False)
            validation_result = {"is_valid": is_valid, "reason": reason}
            
            if not is_valid:
                logger.warning(
                    f"[add_source_from_suggestion] Validación falló para {request.url}: {reason}"
                )
                return AddSuggestedSourceResponse(
                    success=False,
                    source_id=None,
                    message=f"No se pudo validar la fuente: {reason}",
                    validation_result=validation_result,
                )
        except ImportError as e:
            logger.error(
                f"[add_source_from_suggestion] Módulo de validación no disponible: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=502,
                detail="Servicio de validación de fuentes no disponible"
            )
        except Exception as e:
            logger.error(
                f"[add_source_from_suggestion] Error inesperado al validar {request.url}: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail="Error interno al validar la fuente"
            )
    
    # 4. Generar nombre de la fuente si no se proporcionó
    source_name = request.source_name
    if not source_name:
        try:
            parsed = urlparse(request.url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            source_name = domain.capitalize()
        except Exception:
            source_name = "Fuente externa"
    
    # 5. Crear la fuente
    try:
        new_source = MarketSource(
            product_id=product_id,
            source_name=source_name,
            url=request.url,
            source_type=request.source_type or "static",
            is_mandatory=request.is_mandatory,
            currency="ARS",  # Default para Argentina
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        db.add(new_source)
        await db.commit()
        await db.refresh(new_source)
        
        logger.info(
            f"[add_source_from_suggestion] Fuente agregada: ID={new_source.id}, "
            f"URL={request.url}, Product={product_id}"
        )
        
        return AddSuggestedSourceResponse(
            success=True,
            source_id=new_source.id,
            message=f"Fuente '{source_name}' agregada exitosamente",
            validation_result=validation_result,
        )
    except Exception as e:
        logger.error(
            f"[add_source_from_suggestion] Error al crear fuente en DB: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Error interno al crear la fuente"
        )


# ==================== POST /products/{id}/sources/batch-from-suggestions ====================

class BatchAddSuggestedSourcesRequest(BaseModel):
    """Request para agregar múltiples fuentes desde sugerencias"""
    sources: list[AddSuggestedSourceRequest] = Field(description="Lista de fuentes a agregar")
    stop_on_error: bool = Field(False, description="Si True, detiene el proceso al primer error")


class BatchSourceResult(BaseModel):
    """Resultado de agregar una fuente individual en un lote"""
    url: str
    success: bool
    source_id: Optional[int] = None
    message: str
    validation_result: Optional[dict] = None


class BatchAddSuggestedSourcesResponse(BaseModel):
    """Respuesta al agregar múltiples fuentes"""
    total_requested: int = Field(description="Total de fuentes solicitadas")
    successful: int = Field(description="Cantidad de fuentes agregadas exitosamente")
    failed: int = Field(description="Cantidad de fuentes que fallaron")
    results: list[BatchSourceResult] = Field(description="Resultados individuales por cada fuente")


@router.post(
    "/products/{product_id}/sources/batch-from-suggestions",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))],
    response_model=BatchAddSuggestedSourcesResponse,
    status_code=201,
)
async def batch_add_sources_from_suggestions(
    product_id: int,
    request: BatchAddSuggestedSourcesRequest,
    db: AsyncSession = Depends(get_session),
) -> BatchAddSuggestedSourcesResponse:
    """
    Agrega múltiples fuentes de precio desde sugerencias con validación en paralelo.
    
    **Proceso**:
    1. Verifica que el producto existe
    2. Para cada fuente:
       - Valida precio (si está habilitado)
       - Verifica duplicados
       - Agrega si es válida
    3. Retorna resumen con éxitos y fallos
    
    **Roles permitidos**: `admin`, `colaborador`
    
    **Parámetros**:
    - `stop_on_error`: Si True, detiene al primer error; si False, continúa con las demás
    
    **Uso recomendado**: Agregar todas las fuentes seleccionadas por el usuario desde
    el modal de "Fuentes sugeridas" en un solo request.
    
    **Errores**:
    - 404: Producto no encontrado
    - 207 Multi-Status: Si hay éxitos parciales (no lanza excepción, ver `results`)
    """
    from urllib.parse import urlparse
    from workers.discovery.source_validator import validate_source
    
    # 1. Verificar que el producto existe
    query_product = select(CanonicalProduct).where(CanonicalProduct.id == product_id)
    result = await db.execute(query_product)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # 2. Obtener URLs existentes para verificar duplicados
    query_existing = select(MarketSource.url).where(MarketSource.product_id == product_id)
    result_existing = await db.execute(query_existing)
    existing_urls = {row[0] for row in result_existing.all()}
    
    # 3. Procesar cada fuente
    results = []
    successful_count = 0
    failed_count = 0
    
    for source_req in request.sources:
        # 3.1. Verificar duplicado
        if source_req.url in existing_urls:
            results.append(BatchSourceResult(
                url=source_req.url,
                success=False,
                message="URL duplicada, ya existe para este producto",
            ))
            failed_count += 1
            if request.stop_on_error:
                break
            continue
        
        # 3.2. Validar precio si está habilitado
        validation_result = None
        if source_req.validate_price:
            try:
                is_valid, reason = await validate_source(source_req.url, quick=False)
                validation_result = {"is_valid": is_valid, "reason": reason}
                
                if not is_valid:
                    results.append(BatchSourceResult(
                        url=source_req.url,
                        success=False,
                        message=f"Validación fallida: {reason}",
                        validation_result=validation_result,
                    ))
                    failed_count += 1
                    if request.stop_on_error:
                        break
                    continue
            except Exception as e:
                logger.error(f"Error al validar fuente {source_req.url}: {e}")
                results.append(BatchSourceResult(
                    url=source_req.url,
                    success=False,
                    message=f"Error de validación: {str(e)}",
                ))
                failed_count += 1
                if request.stop_on_error:
                    break
                continue
        
        # 3.3. Generar nombre si falta
        source_name = source_req.source_name
        if not source_name:
            parsed = urlparse(source_req.url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            source_name = domain.capitalize()
        
        # 3.4. Crear la fuente
        try:
            new_source = MarketSource(
                product_id=product_id,
                source_name=source_name,
                url=source_req.url,
                source_type=source_req.source_type or "static",
                is_mandatory=source_req.is_mandatory,
                currency="ARS",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            db.add(new_source)
            await db.flush()  # Flush para obtener el ID sin hacer commit completo aún
            
            # Agregar a set de existentes para evitar duplicados en el mismo batch
            existing_urls.add(source_req.url)
            
            results.append(BatchSourceResult(
                url=source_req.url,
                success=True,
                source_id=new_source.id,
                message=f"Fuente '{source_name}' agregada exitosamente",
                validation_result=validation_result,
            ))
            successful_count += 1
            
        except Exception as e:
            logger.error(f"Error al crear fuente {source_req.url}: {e}")
            results.append(BatchSourceResult(
                url=source_req.url,
                success=False,
                message=f"Error al crear fuente: {str(e)}",
            ))
            failed_count += 1
            if request.stop_on_error:
                break
    
    # 4. Commit final si hubo al menos un éxito
    if successful_count > 0:
        await db.commit()
        logger.info(f"Batch add completado: {successful_count} fuentes agregadas para producto {product_id}")
    else:
        await db.rollback()
    
    return BatchAddSuggestedSourcesResponse(
        total_requested=len(request.sources),
        successful=successful_count,
        failed=failed_count,
        results=results,
    )
