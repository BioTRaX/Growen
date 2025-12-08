#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: c308b8798a79_migrate_to_canonical_sku_only.py
# NG-HEADER: Ubicación: db/migrations/versions/c308b8798a79_migrate_to_canonical_sku_only.py
# NG-HEADER: Descripción: Migración para usar exclusivamente formato canónico de SKU (XXX_####_YYY)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""migrate_to_canonical_sku_only

Revision ID: c308b8798a79
Revises: 20251130_sales_channels
Create Date: 2025-12-03 18:42:34.080505

Esta migración completa la refactorización a SKU canónico:
1. Migra productos existentes con sku_root canónico a canonical_sku
2. Genera SKUs canónicos para productos sin canonical_sku que tengan categoría
3. Documenta productos que no pueden migrarse (sin categoría)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from sqlalchemy.engine import Connection
import re

# revision identifiers, used by Alembic.
revision = 'c308b8798a79'
down_revision = '20251130_sales_channels'
branch_labels = None
depends_on = None

# Patrón regex para SKU canónico: XXX_####_YYY
CANONICAL_SKU_PATTERN = r'^[A-Z]{3}_[0-9]{4}_[A-Z0-9]{3}$'
CANONICAL_SKU_REGEX = re.compile(CANONICAL_SKU_PATTERN)


def normalize_code(name: str | None) -> str:
    """Normaliza nombre de categoría/subcategoría a bloque canónico de 3 chars A-Z."""
    if not name:
        return "XXX"
    import unicodedata
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    letters = [c for c in t.upper() if c.isalpha()]
    while len(letters) < 3:
        letters.append('X')
    return ("".join(letters)[:3]) or "XXX"


def is_canonical_sku(value: str | None) -> bool:
    """Valida si un SKU respeta el formato canónico."""
    if not value or len(value) > 32:
        return False
    return bool(CANONICAL_SKU_REGEX.fullmatch(value))


def upgrade() -> None:
    """Migra productos a formato canónico de SKU."""
    bind: Connection = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Verificar que la columna canonical_sku existe
    cols = [c['name'] for c in inspector.get_columns('products')]
    if 'canonical_sku' not in cols:
        # Si no existe, la creamos (aunque debería existir desde migración anterior)
        op.add_column('products', sa.Column('canonical_sku', sa.String(length=32), nullable=True))
        bind.commit()
    
    # PASO 1: Migrar productos que ya tienen sku_root en formato canónico
    # pero canonical_sku es NULL
    print("PASO 1: Migrando productos con sku_root canónico a canonical_sku...")
    migrated_count = 0
    
    # Obtener productos con sku_root canónico pero canonical_sku NULL
    rows = bind.execute(text("""
        SELECT id, sku_root 
        FROM products 
        WHERE canonical_sku IS NULL 
        AND sku_root IS NOT NULL
        AND sku_root ~ :pattern
    """), {"pattern": CANONICAL_SKU_PATTERN}).fetchall()
    
    # Detectar duplicados para evitar violaciones de unique constraint
    seen_skus = {}
    duplicates = set()
    for row in rows:
        sku_upper = row.sku_root.upper()
        if sku_upper in seen_skus:
            duplicates.add(sku_upper)
        else:
            seen_skus[sku_upper] = row.id
    
    # Actualizar solo los no duplicados
    for row in rows:
        sku_upper = row.sku_root.upper()
        if sku_upper in duplicates:
            print(f"  ⚠ Omitiendo producto ID {row.id}: SKU '{sku_upper}' duplicado")
            continue
        if is_canonical_sku(sku_upper):
            try:
                bind.execute(
                    text("UPDATE products SET canonical_sku = :sku WHERE id = :id"),
                    {"sku": sku_upper, "id": row.id}
                )
                migrated_count += 1
            except Exception as e:
                print(f"  ✗ Error actualizando producto ID {row.id}: {e}")
    
    print(f"  ✓ Migrados {migrated_count} productos con sku_root canónico")
    bind.commit()
    
    # PASO 2: Generar SKUs canónicos para productos sin canonical_sku que tengan categoría
    print("\nPASO 2: Generando SKUs canónicos para productos con categoría...")
    generated_count = 0
    skipped_count = 0
    
    # Obtener productos sin canonical_sku que tengan categoría
    products_with_category = bind.execute(text("""
        SELECT p.id, p.title, c.name as category_name, c2.name as subcategory_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN categories c2 ON p.brand_id = c2.id
        WHERE p.canonical_sku IS NULL
        AND c.name IS NOT NULL
        ORDER BY p.id
    """)).fetchall()
    
    # Asegurar que la tabla sku_sequences existe
    try:
        bind.execute(text("""
            CREATE TABLE IF NOT EXISTS sku_sequences (
                category_code VARCHAR(3) PRIMARY KEY,
                next_seq INTEGER NOT NULL DEFAULT 1
            )
        """))
        bind.commit()
    except Exception:
        pass
    
    for prod in products_with_category:
        category_name = prod.category_name or "GEN"
        subcategory_name = prod.subcategory_name or category_name
        
        # Normalizar códigos
        prefix = normalize_code(category_name)
        suffix = normalize_code(subcategory_name)
        
        # Obtener o crear secuencia para el prefijo
        seq_row = bind.execute(
            text("SELECT next_seq FROM sku_sequences WHERE category_code = :code FOR UPDATE"),
            {"code": prefix}
        ).first()
        
        if not seq_row:
            # Crear secuencia inicial
            bind.execute(
                text("INSERT INTO sku_sequences (category_code, next_seq) VALUES (:code, 1)"),
                {"code": prefix}
            )
            seq_num = 1
        else:
            seq_num = seq_row[0]
        
        # Construir SKU canónico
        canonical_sku = f"{prefix}_{seq_num:04d}_{suffix}"
        
        # Verificar que no exista ya
        existing = bind.execute(
            text("SELECT id FROM products WHERE canonical_sku = :sku"),
            {"sku": canonical_sku}
        ).first()
        
        if existing:
            print(f"  ⚠ SKU '{canonical_sku}' ya existe, incrementando secuencia...")
            # Incrementar secuencia y reintentar
            bind.execute(
                text("UPDATE sku_sequences SET next_seq = next_seq + 1 WHERE category_code = :code"),
                {"code": prefix}
            )
            seq_num += 1
            canonical_sku = f"{prefix}_{seq_num:04d}_{suffix}"
        
        # Actualizar producto
        try:
            bind.execute(
                text("UPDATE products SET canonical_sku = :sku WHERE id = :id"),
                {"sku": canonical_sku, "id": prod.id}
            )
            # Incrementar secuencia para el siguiente
            bind.execute(
                text("UPDATE sku_sequences SET next_seq = next_seq + 1 WHERE category_code = :code"),
                {"code": prefix}
            )
            generated_count += 1
        except Exception as e:
            print(f"  ✗ Error generando SKU para producto ID {prod.id}: {e}")
            skipped_count += 1
    
    print(f"  ✓ Generados {generated_count} SKUs canónicos")
    if skipped_count > 0:
        print(f"  ⚠ Omitidos {skipped_count} productos por errores")
    bind.commit()
    
    # PASO 3: Reportar productos que no pudieron migrarse
    print("\nPASO 3: Verificando productos sin canonical_sku...")
    remaining = bind.execute(text("""
        SELECT COUNT(*) as count
        FROM products
        WHERE canonical_sku IS NULL
    """)).scalar()
    
    if remaining > 0:
        print(f"  ⚠ ADVERTENCIA: {remaining} productos sin canonical_sku (sin categoría o errores)")
        print("  Estos productos requerirán categoría para generar SKU canónico")
        
        # Listar algunos ejemplos
        examples = bind.execute(text("""
            SELECT id, title, sku_root
            FROM products
            WHERE canonical_sku IS NULL
            LIMIT 5
        """)).fetchall()
        
        if examples:
            print("  Ejemplos de productos sin canonical_sku:")
            for ex in examples:
                print(f"    - ID {ex.id}: '{ex.title}' (sku_root: {ex.sku_root})")
    
    print("\n✓ Migración completada")
    print(f"  - Migrados desde sku_root: {migrated_count}")
    print(f"  - Generados nuevos: {generated_count}")
    print(f"  - Sin canonical_sku: {remaining}")


def downgrade() -> None:
    """No se puede revertir automáticamente - los SKUs generados se perderían."""
    # No hacemos nada en downgrade para evitar pérdida de datos
    # Si se necesita revertir, debe hacerse manualmente
    pass
