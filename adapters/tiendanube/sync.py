# NG-HEADER: Nombre de archivo: sync.py
# NG-HEADER: Ubicación: adapters/tiendanube/sync.py
# NG-HEADER: Descripción: Sincroniza catálogos y datos con Tiendanube.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Sincronización simulada con Tiendanube."""
from __future__ import annotations

from typing import Iterator


def pull(dry_run: bool = True) -> Iterator[str]:
    """Genera eventos de progreso para la descarga."""
    yield "conectando"
    yield "obteniendo productos"
    yield "finalizado" if dry_run else "aplicado"


def push(dry_run: bool = True) -> Iterator[str]:
    """Genera eventos de progreso para el envío."""
    yield "preparando datos"
    yield "enviando productos"
    yield "finalizado" if dry_run else "aplicado"
