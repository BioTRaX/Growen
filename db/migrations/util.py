# NG-HEADER: Nombre de archivo: util.py
# NG-HEADER: Ubicación: db/migrations/util.py
# NG-HEADER: Descripción: Utilidades compartidas para scripts de migración.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection


def _insp(bind: Connection) -> sa.Inspector:
    return sa.inspect(bind)


def has_table(bind: Connection, name: str) -> bool:
    """Devuelve True si la tabla existe."""
    return _insp(bind).has_table(name)


def has_column(bind: Connection, table: str, col: str) -> bool:
    """Verifica si una columna existe en una tabla."""
    return any(c["name"] == col for c in _insp(bind).get_columns(table))


def index_exists(bind: Connection, table: str, name: str) -> bool:
    """Chequea si un índice existe."""
    return any(ix["name"] == name for ix in _insp(bind).get_indexes(table))


def fk_exists(bind: Connection, table: str, name: str) -> bool:
    """Chequea si una clave foránea existe."""
    return any(fk["name"] == name for fk in _insp(bind).get_foreign_keys(table))


def unique_constraint_exists(bind: Connection, table: str, name: str) -> bool:
    """Chequea si una restricción UNIQUE existe."""
    return any(uc["name"] == name for uc in _insp(bind).get_unique_constraints(table))
