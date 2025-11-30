#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: text_utils.py
# NG-HEADER: Ubicación: db/text_utils.py
# NG-HEADER: Descripción: Utilidades para formateo de texto (nombres de productos, etc.)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Utilidades de formateo de texto para nombres de productos.

Funciones para estilizar nombres de productos aplicando Title Case
mientras se preservan unidades de medida y acrónimos comunes.
"""
from __future__ import annotations

import re
from typing import Optional

# Unidades de medida que deben mantenerse en mayúsculas
UNITS_UPPER = {
    "GR", "G", "KG", "MG",  # peso
    "L", "LT", "ML", "CC",  # volumen
    "OZ", "LB",  # sistema imperial
    "CM", "MM", "M",  # longitud
    "UN", "PZ", "PZA",  # unidades/piezas
}

# Acrónimos/siglas que deben mantenerse en mayúsculas
ACRONYMS_UPPER = {
    "LED", "UV", "PH", "EC", "NPK", "CO2",
    "HPS", "MH", "CMH", "LEC",
    "THC", "CBD",
    "PK", "NK",
}

# Palabras que típicamente van en minúsculas (conectores)
LOWERCASE_WORDS = {
    "de", "del", "la", "el", "las", "los", "en", "con", "para", "por", "y", "o", "a",
}


def stylize_product_name(name: Optional[str]) -> Optional[str]:
    """Convierte un nombre de producto a estilo Title Case estilizado.

    Transforma nombres en mayúsculas a un formato más legible:
    - Cada palabra inicia con mayúscula
    - Unidades de medida se mantienen en mayúsculas (GR, KG, L, ML, etc.)
    - Acrónimos comunes se mantienen en mayúsculas (LED, UV, NPK, etc.)
    - Conectores típicos en español van en minúsculas (de, la, el, etc.)
      excepto si son la primera palabra

    Ejemplos:
        "FEEDING BIO GROW (125 GR)" -> "Feeding Bio Grow (125 GR)"
        "FERTILIZANTE ORGANICO NPK 1 L" -> "Fertilizante Orgánico NPK 1 L"
        "LED GROW LIGHT 600W" -> "LED Grow Light 600w"
        "ACEITE DE NEEM 250 ML" -> "Aceite de Neem 250 ML"

    Args:
        name: Nombre del producto a estilizar. Puede ser None.

    Returns:
        Nombre estilizado o None si la entrada es None.
    """
    if not name:
        return name

    # Separar el contenido entre paréntesis del resto
    # Patrón: texto principal (contenido entre paréntesis)
    paren_pattern = r"^(.*?)(\s*\([^)]+\)\s*)$"
    match = re.match(paren_pattern, name)

    if match:
        main_part = match.group(1)
        paren_part = match.group(2)
        # Estilizar solo la parte principal
        styled_main = _stylize_text(main_part)
        # Mantener el contenido entre paréntesis, pero estilizar unidades
        styled_paren = _preserve_units_in_parens(paren_part)
        return styled_main + styled_paren
    else:
        return _stylize_text(name)


def _stylize_text(text: str) -> str:
    """Aplica Title Case estilizado a un texto."""
    if not text:
        return text

    words = text.split()
    result = []

    for i, word in enumerate(words):
        styled = _stylize_word(word, is_first=(i == 0))
        result.append(styled)

    return " ".join(result)


def _stylize_word(word: str, is_first: bool = False) -> str:
    """Estiliza una palabra individual.

    Args:
        word: Palabra a estilizar
        is_first: Si es la primera palabra de la oración

    Returns:
        Palabra estilizada
    """
    if not word:
        return word

    # Verificar si es una unidad de medida (posiblemente con números)
    # Ej: "125GR" -> "125GR", "GR" -> "GR"
    upper_word = word.upper()

    # Extraer número al inicio si existe
    num_match = re.match(r"^(\d+)(.*)$", word)
    if num_match:
        num_part = num_match.group(1)
        rest_part = num_match.group(2).upper()
        if rest_part in UNITS_UPPER:
            return num_part + rest_part
        # Si hay número + texto, estilizar el texto
        if rest_part:
            return num_part + rest_part.capitalize()
        return word

    # Verificar si es una unidad pura
    if upper_word in UNITS_UPPER:
        return upper_word

    # Verificar si es un acrónimo
    if upper_word in ACRONYMS_UPPER:
        return upper_word

    # Verificar si es un conector (minúscula, excepto si es primera palabra)
    lower_word = word.lower()
    if lower_word in LOWERCASE_WORDS and not is_first:
        return lower_word

    # Caso general: Title Case
    return word.capitalize()


def _preserve_units_in_parens(paren_text: str) -> str:
    """Preserva formato en texto entre paréntesis, estilizando unidades.

    Mantiene las unidades de medida en mayúsculas dentro de paréntesis.
    Ej: "(125 gr)" -> "(125 GR)"
    """
    if not paren_text:
        return paren_text

    # Buscar unidades dentro del paréntesis y convertirlas a mayúsculas
    def replace_unit(match: re.Match) -> str:
        num = match.group(1) or ""
        unit = match.group(2).upper()
        if unit in UNITS_UPPER:
            return num + unit
        return match.group(0)

    # Patrón para número + unidad
    pattern = r"(\d+\s*)([a-zA-Z]{1,3})\b"
    result = re.sub(pattern, replace_unit, paren_text, flags=re.IGNORECASE)

    return result

