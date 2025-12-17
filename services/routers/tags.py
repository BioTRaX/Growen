# NG-HEADER: Nombre de archivo: tags.py
# NG-HEADER: Ubicación: services/routers/tags.py
# NG-HEADER: Descripción: Endpoints para gestión de tags y asignación a productos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para gestionar tags y su relación con productos."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Tag, Product, ProductTag
from db.session import get_session
from services.auth import require_csrf, require_roles, current_session, SessionData

router = APIRouter(tags=["tags"])


class TagResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    name: str


class ProductTagsAssign(BaseModel):
    tag_names: List[str]


class BulkTagsAssign(BaseModel):
    product_ids: List[int]
    tag_names: List[str]


@router.get(
    "",
    response_model=List[TagResponse],
    dependencies=[Depends(require_roles("cliente", "proveedor", "colaborador", "admin"))],
)
async def list_tags(
    q: Optional[str] = Query(None, description="Búsqueda por nombre (parcial, case-insensitive)"),
    session: AsyncSession = Depends(get_session),
) -> List[TagResponse]:
    """Lista todos los tags existentes, opcionalmente filtrados por búsqueda."""
    stmt = select(Tag)
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Tag.name.asc())
    result = await session.execute(stmt)
    tags = result.scalars().all()
    return [TagResponse(id=t.id, name=t.name) for t in tags]


@router.post(
    "",
    response_model=TagResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def create_tag(
    payload: TagCreate,
    session: AsyncSession = Depends(get_session),
) -> TagResponse:
    """Crea un nuevo tag. Si ya existe, retorna el existente."""
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name requerido")
    
    # Buscar si ya existe
    existing = await session.scalar(select(Tag).where(Tag.name == name))
    if existing:
        return TagResponse(id=existing.id, name=existing.name)
    
    # Crear nuevo
    tag = Tag(name=name)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return TagResponse(id=tag.id, name=tag.name)


@router.post(
    "products/{product_id}/tags",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def assign_tags_to_product(
    product_id: int,
    payload: ProductTagsAssign,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Asigna tags a un producto. Crea los tags si no existen."""
    # Verificar que el producto existe
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Normalizar nombres de tags (trim, sin duplicados)
    tag_names = list(set([t.strip() for t in payload.tag_names if t.strip()]))
    if not tag_names:
        raise HTTPException(status_code=400, detail="Se requiere al menos un tag")
    
    # Obtener o crear tags
    tags_to_assign = []
    for tag_name in tag_names:
        tag = await session.scalar(select(Tag).where(Tag.name == tag_name))
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
            await session.flush()
        tags_to_assign.append(tag)
    
    # Obtener tags actuales del producto
    existing_tags = (
        await session.execute(
            select(ProductTag).where(ProductTag.product_id == product_id)
        )
    ).scalars().all()
    existing_tag_ids = {pt.tag_id for pt in existing_tags}
    
    # Agregar solo los tags que no están ya asignados
    new_assignments = []
    for tag in tags_to_assign:
        if tag.id not in existing_tag_ids:
            pt = ProductTag(product_id=product_id, tag_id=tag.id)
            session.add(pt)
            new_assignments.append(tag.name)
    
    await session.commit()
    
    return {
        "product_id": product_id,
        "assigned_tags": [t.name for t in tags_to_assign],
        "new_assignments": new_assignments,
    }


@router.delete(
    "products/{product_id}/tags/{tag_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def remove_tag_from_product(
    product_id: int,
    tag_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Desvincula un tag de un producto."""
    # Verificar que el producto existe
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar que el tag existe
    tag = await session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    
    # Eliminar la relación
    result = await session.execute(
        delete(ProductTag).where(
            ProductTag.product_id == product_id,
            ProductTag.tag_id == tag_id
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="El tag no está asignado a este producto")
    
    await session.commit()
    
    return {
        "product_id": product_id,
        "tag_id": tag_id,
        "removed": True,
    }


@router.post(
    "products/bulk-tags",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def bulk_assign_tags(
    payload: BulkTagsAssign,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Asigna tags a múltiples productos a la vez."""
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un product_id")
    if not payload.tag_names:
        raise HTTPException(status_code=400, detail="Se requiere al menos un tag")
    
    # Normalizar nombres de tags
    tag_names = list(set([t.strip() for t in payload.tag_names if t.strip()]))
    
    # Obtener o crear tags
    tags_to_assign = []
    for tag_name in tag_names:
        tag = await session.scalar(select(Tag).where(Tag.name == tag_name))
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
            await session.flush()
        tags_to_assign.append(tag)
    
    # Verificar que todos los productos existen
    products = (
        await session.execute(
            select(Product).where(Product.id.in_(payload.product_ids))
        )
    ).scalars().all()
    found_ids = {p.id for p in products}
    missing_ids = set(payload.product_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Productos no encontrados: {sorted(missing_ids)}"
        )
    
    # Obtener relaciones existentes para evitar duplicados
    existing_relations = (
        await session.execute(
            select(ProductTag).where(
                ProductTag.product_id.in_(payload.product_ids),
                ProductTag.tag_id.in_([t.id for t in tags_to_assign])
            )
        )
    ).scalars().all()
    existing_pairs = {(pt.product_id, pt.tag_id) for pt in existing_relations}
    
    # Crear nuevas relaciones
    new_count = 0
    for product_id in payload.product_ids:
        for tag in tags_to_assign:
            if (product_id, tag.id) not in existing_pairs:
                pt = ProductTag(product_id=product_id, tag_id=tag.id)
                session.add(pt)
                new_count += 1
    
    await session.commit()
    
    return {
        "product_ids": payload.product_ids,
        "tag_names": tag_names,
        "tags_assigned": len(tags_to_assign),
        "new_relations_created": new_count,
        "existing_relations_skipped": len(existing_relations),
    }

