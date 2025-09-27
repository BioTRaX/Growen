#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: sku_generator.py
# NG-HEADER: Ubicación: db/sku_generator.py
# NG-HEADER: Descripción: Generación transaccional de SKU canónico (XXX_####_YYY)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Generador transaccional de SKU canónico.

Uso:
    sku = await generate_canonical_sku(session, category_name, subcategory_name)

Reglas:
 - Prefijo XXX y sufijo YYY derivan de nombres normalizados.
 - Secuencia #### es por prefijo (XXX) y se incrementa de forma atómica.
 - Tabla sku_sequences(category_code PK, next_seq INT) almacena el próximo número a asignar.
 - Primer uso de un prefijo: next_seq=1 asignado y posteriormente incrementado.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.engine import Result

from .sku_utils import normalize_code, build_canonical_sku, CANONICAL_SKU_REGEX


class CanonicalSkuGenerationError(Exception):
    """Error en generación de SKU canónico."""


async def _lock_sequence_row(session: AsyncSession, category_code: str) -> int:
    """Obtiene y bloquea (SELECT FOR UPDATE) la fila de secuencia para category_code.

    Crea la fila si no existe con next_seq=1.
    Devuelve el número asignable actual (que se usará antes de incrementar)."""
    bind = session.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect == 'sqlite':
        # SQLite no soporta FOR UPDATE real; simulamos con UPSERT y lectura inmediata dentro de la misma transacción.
        await session.execute(text("INSERT OR IGNORE INTO sku_sequences(category_code, next_seq) VALUES (:c, 1)"), {"c": category_code})  # type: ignore[arg-type]
        row: Result = await session.execute(text("SELECT next_seq FROM sku_sequences WHERE category_code = :c"), {"c": category_code})  # type: ignore[arg-type]
        current = row.scalar_one()
        return current
    # Postgres / otros: FOR UPDATE
    row: Result = await session.execute(text("SELECT next_seq FROM sku_sequences WHERE category_code = :c FOR UPDATE"), {"c": category_code})  # type: ignore[arg-type]
    r = row.first()
    if not r:
        # Insertar y relanzar lock
        await session.execute(text("INSERT INTO sku_sequences(category_code, next_seq) VALUES (:c, 1)"), {"c": category_code})  # type: ignore[arg-type]
        row2: Result = await session.execute(text("SELECT next_seq FROM sku_sequences WHERE category_code = :c FOR UPDATE"), {"c": category_code})  # type: ignore[arg-type]
        r2 = row2.first()
        if not r2:
            raise CanonicalSkuGenerationError("No se pudo inicializar secuencia canónica")
        return int(r2[0])
    return int(r[0])


async def generate_canonical_sku(session: AsyncSession, category_name: str, subcategory_name: str) -> str:
    """Genera un SKU canónico único (no valida contra variants, sólo genera formato + secuencia).

    Lógica:
      1. Normaliza category_name -> XXX
      2. Normaliza subcategory_name -> YYY (si vacío => XXX se reutiliza como base de sufijo)
      3. Obtiene número secuencial #### (lock row)
      4. Construye SKU y devuelve.
    """
    prefix = normalize_code(category_name)
    suffix = normalize_code(subcategory_name) if subcategory_name else normalize_code(category_name)
    # Asegurar tabla en SQLite si no existe (tests sin migraciones)
    bind = session.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect == 'sqlite':  # creación perezosa para entorno de pruebas
        try:  # pragma: no cover - defensivo
            await session.execute(text("CREATE TABLE IF NOT EXISTS sku_sequences (category_code VARCHAR(3) PRIMARY KEY, next_seq INTEGER NOT NULL)"))  # type: ignore[arg-type]
        except Exception:  # silencioso, si falla lo captará luego el lock
            pass
    seq = await _lock_sequence_row(session, prefix)
    sku = build_canonical_sku(prefix, seq, suffix)
    if not CANONICAL_SKU_REGEX.fullmatch(sku):  # defensivo
        raise CanonicalSkuGenerationError(f"SKU generado inválido: {sku}")
    # Incrementar secuencia
    await session.execute(text("UPDATE sku_sequences SET next_seq = next_seq + 1 WHERE category_code = :c"), {"c": prefix})  # type: ignore[arg-type]
    # En SQLite liberar lock rápidamente para evitar 'database is locked' en tests.
    if dialect == 'sqlite':  # pragma: no cover
        try:
            await session.commit()
        except Exception:
            pass
    return sku
