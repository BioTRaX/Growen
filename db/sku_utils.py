#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: sku_utils.py
# NG-HEADER: Ubicación: db/sku_utils.py
# NG-HEADER: Descripción: Utilidades para validación y generación de SKU canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Helpers relacionados al SKU canónico.

Formato oficial (Sept 2025): XXX_####_YYY

- Primera sección (XXX): 3 letras A-Z (se sugiere derivar de categoría o nombre)
- Segunda sección (####): 4 dígitos 0-9 (secuencial dentro del prefijo de la primera sección)
- Tercera sección (YYY): 3 caracteres alfanuméricos (A-Z0-9) que pueden codificar sub‑familia / variante.

Ejemplos válidos:
  ABC_0001_DEF
  ROS_0123_RED
  SUP_0007_A1B

Casos NO válidos:
  abc_0001_def (minúsculas)
  AB_001_DEF   (falta una letra en primer bloque)
  ABC_12_DEF   (faltan dígitos)
  ABC_0001_DEFG (sobra un caracter en tercer bloque)

Nota: La generación automática se realizará en una migración / script separado.
Este módulo solo provee validación y un generador auxiliar reutilizable.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

CANONICAL_SKU_PATTERN = r"^[A-Z]{3}_[0-9]{4}_[A-Z0-9]{3}$"
CANONICAL_SKU_REGEX = re.compile(CANONICAL_SKU_PATTERN)


def is_canonical_sku(value: str | None) -> bool:
    """Valida si un SKU respeta el formato canónico.

    Args:
        value: SKU a validar.
    Returns:
        True si es canónico, False en cualquier otro caso (incluyendo None).
    """
    if not value or len(value) > 32:
        return False
    return bool(CANONICAL_SKU_REGEX.fullmatch(value))


def normalize_prefix(text: str) -> str:
    """Deriva un prefijo de 3 letras A-Z a partir de un texto.

    Reemplaza caracteres no alfabéticos por X y rellena/poda a longitud 3.
    """
    if not text:
        return "XXX"
    # Normalizar acentos
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    letters = [c for c in t.upper() if c.isalpha()]
    while len(letters) < 3:
        letters.append('X')
    return ("".join(letters)[:3]) or "XXX"


def normalize_code(name: str | None) -> str:
    """Normaliza nombre de categoría/subcategoría a bloque canónico de 3 chars A-Z.

    - Elimina diacríticos (NFKD)
    - Filtra no alfabéticos
    - Upper
    - Rellena con 'X' hasta 3 si es corto
    """
    if not name:
        return "XXX"
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    letters = [c for c in t.upper() if c.isalpha()]
    while len(letters) < 3:
        letters.append('X')
    return ("".join(letters)[:3]) or "XXX"


def build_canonical_sku(prefix: str, number: int, suffix_code: str) -> str:
    """Construye un SKU canónico dado un prefijo, número y sufijo.

    No valida unicidad – eso debe manejarse externamente.
    """
    return f"{prefix}_{number:04d}_{suffix_code}"


def iter_candidate_suffixes(base: str) -> Iterable[str]:
    """Genera sufijos candidatos (3 chars) a partir de una base.

    Estrategia simple: tomar caracteres alfanuméricos, completar con 'X', y luego
    enumerar variantes base + índice Base36.
    """
    base_clean = ''.join([c for c in base.upper() if c.isalnum()]) or 'XXX'
    base_clean = (base_clean + 'XXX')[:3]
    yield base_clean
    # Variaciones incrementales
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for i in range(1, 500):  # límite defensivo
        n = i
        chars = []
        while n > 0:
            n, r = divmod(n, 36)
            chars.append(alphabet[r])
        code = ''.join(chars)[-3:].rjust(3, '0')[-3:]
        yield code
