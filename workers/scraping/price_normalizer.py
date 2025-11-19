#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: price_normalizer.py
# NG-HEADER: Ubicación: workers/scraping/price_normalizer.py
# NG-HEADER: Descripción: Normalización centralizada de precios con detección de moneda
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Normalización centralizada de valores de precio extraídos por scrapers.

Este módulo convierte strings de precios en diferentes formatos a valores
numéricos estandarizados (Decimal) con detección de moneda.

Uso:
    from workers.scraping.price_normalizer import normalize_price
    
    price, currency = normalize_price("ARS 4.500,00")
    # price = Decimal('4500.00'), currency = "ARS"
    
    price, currency = normalize_price("$ 1.299")
    # price = Decimal('1299.00'), currency = "ARS"
    
    price, currency = normalize_price("USD 30.50")
    # price = Decimal('30.50'), currency = "USD"
"""

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# Símbolos de moneda reconocidos
CURRENCY_SYMBOLS = {
    "$": "ARS",  # Por defecto $ es ARS en contexto argentino
    "US$": "USD",
    "U$S": "USD",
    "USD": "USD",
    "ARS": "ARS",
    "AR$": "ARS",
    "€": "EUR",
    "EUR": "EUR",
    "R$": "BRL",
    "BRL": "BRL",
    "£": "GBP",
    "GBP": "GBP",
    "¥": "JPY",
    "JPY": "JPY",
    "CNY": "CNY",
}


def detect_currency(price_text: str) -> str:
    """
    Detecta el código de moneda en un string de precio.
    
    Args:
        price_text: Texto del precio (ej: "USD 30", "$ 1.250", "ARS 4500")
        
    Returns:
        Código de moneda ISO 4217 (ej: "ARS", "USD", "EUR")
        Por defecto retorna "ARS" si no se detecta explícitamente
        
    Examples:
        >>> detect_currency("USD 30.50")
        'USD'
        >>> detect_currency("ARS 4.500,00")
        'ARS'
        >>> detect_currency("$ 1.299")
        'ARS'
        >>> detect_currency("€ 20,99")
        'EUR'
    """
    text_upper = price_text.upper().strip()
    
    # Buscar símbolos/códigos de moneda en orden de especificidad
    # Primero los códigos explícitos (USD, ARS, EUR, etc.)
    for symbol in ["USD", "US$", "U$S", "ARS", "AR$", "EUR", "BRL", "R$", "GBP", "JPY", "CNY"]:
        if symbol in text_upper or symbol.replace("$", r"\$") in price_text:
            return CURRENCY_SYMBOLS.get(symbol, "ARS")
    
    # Luego símbolos especiales (€, £, ¥)
    if "€" in price_text:
        return "EUR"
    if "£" in price_text:
        return "GBP"
    if "¥" in price_text:
        return "JPY"
    
    # Por defecto, $ se asume ARS en contexto argentino
    return "ARS"


def clean_price_text(price_text: str) -> str:
    """
    Limpia el texto de precio removiendo símbolos de moneda y texto extra.
    Extrae el primer precio válido usando regex si el texto contiene basura.
    
    Args:
        price_text: Texto crudo del precio
        
    Returns:
        Texto limpio con solo números y separadores (. ,)
        
    Examples:
        >>> clean_price_text("USD 30.50")
        '30.50'
        >>> clean_price_text("ARS $ 4.500,00")
        '4.500,00'
        >>> clean_price_text("Precio: $ 1.299")
        '1.299'
        >>> clean_price_text("$13.000En ofertaPrecio de lista$16.600")
        '13.000'
    """
    if not price_text:
        return ""
    
    clean = price_text.strip()
    
    # NUEVO: Primero intentar extraer un precio válido con regex
    # Esto maneja casos como "$13.000En ofertaPrecio de lista$16.600Ahorra22%"
    # Buscar patrones: número con separadores (. o ,) después de $ u otros símbolos
    price_patterns = [
        r'(?:US\$|U\$S|AR\$|R\$|\$|€|£|¥|ARS|USD|EUR|BRL|GBP|JPY|CNY)?\s?([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)',
        r'([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)'
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, clean)
        if match:
            # Extraer el grupo de números (puede ser grupo 1 o 0)
            price_num = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            # Limpiar símbolos de moneda que puedan quedar
            price_num = re.sub(r'[^\d.,]', '', price_num)
            if price_num:
                logger.debug(f"Precio extraído con regex: '{price_num}' de '{price_text}'")
                return price_num
    
    # FALLBACK: Si regex no funciona, usar limpieza tradicional
    # Primero remover códigos compuestos con $ (US$, U$S, R$, AR$) antes de $ solo
    # Orden importante: más específicos primero
    clean = re.sub(r'\bUS\$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bU\$S', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bAR\$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bR\$', '', clean, flags=re.IGNORECASE)
    
    # Luego remover códigos simples (USD, ARS, EUR, etc.)
    for currency_code in ["USD", "ARS", "EUR", "BRL", "GBP", "JPY", "CNY"]:
        clean = re.sub(rf'\b{currency_code}\b', '', clean, flags=re.IGNORECASE)
    
    # Finalmente remover símbolos de moneda restantes
    clean = clean.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
    
    # Remover texto común
    clean = re.sub(r"(?i)(precio|price|valor|value|cost|costo)s?:?\s*", "", clean)
    
    # Remover espacios extras
    clean = clean.strip()
    
    return clean


def normalize_decimal_separators(clean_text: str, currency: str) -> str:
    """
    Normaliza separadores de miles y decimales según la moneda.
    
    Args:
        clean_text: Texto limpio con números y separadores
        currency: Código de moneda (afecta convención de separadores)
        
    Returns:
        String normalizado listo para conversión a Decimal (formato: XXXX.XX)
        
    Examples:
        >>> normalize_decimal_separators("4.500,00", "ARS")
        '4500.00'
        >>> normalize_decimal_separators("1,250.50", "USD")
        '1250.50'
        >>> normalize_decimal_separators("1.250", "ARS")
        '1.250'
    """
    if not clean_text:
        return "0"
    
    # Convención por moneda
    # ARS, EUR, BRL: punto = miles, coma = decimal
    # USD, GBP, JPY, CNY: coma = miles, punto = decimal
    uses_comma_as_decimal = currency in ["ARS", "EUR", "BRL"]
    
    # Detectar formato: si hay punto Y coma, determinar cuál es decimal
    if "," in clean_text and "." in clean_text:
        last_comma = clean_text.rfind(",")
        last_dot = clean_text.rfind(".")
        
        if last_comma > last_dot:
            # Formato europeo: 1.250,00 (punto=miles, coma=decimal)
            clean_text = clean_text.replace(".", "").replace(",", ".")
        else:
            # Formato americano: 1,250.00 (coma=miles, punto=decimal)
            clean_text = clean_text.replace(",", "")
    
    elif "," in clean_text:
        # Solo coma: puede ser decimal o miles
        # Heurística: si hay 2 dígitos después de la coma, es decimal
        parts = clean_text.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            # Formato decimal: 1250,00 o 1.250,00
            clean_text = clean_text.replace(",", ".")
        elif len(parts) == 2 and len(parts[1]) == 3:
            # Coma con 3 dígitos: depende del contexto
            if uses_comma_as_decimal:
                # En ARS/EUR, coma con 3 dígitos es separador de MILES
                # Ejemplo: $1,232 = 1232 (mil doscientos treinta y dos)
                clean_text = clean_text.replace(",", "")
            else:
                # En USD, coma con 3 dígitos es separador de miles
                clean_text = clean_text.replace(",", "")
        elif len(parts) == 2 and len(parts[1]) == 1:
            # Coma con 1 dígito: es decimal truncado
            # Ejemplo: 1,2 = 1.2
            clean_text = clean_text.replace(",", ".")
        else:
            # Múltiples comas: separador de miles (ej: 1,000,000)
            clean_text = clean_text.replace(",", "")
    
    elif "." in clean_text:
        # Solo punto: puede ser decimal o miles
        parts = clean_text.split(".")
        if len(parts) == 2 and len(parts[1]) == 2:
            # Formato decimal americano: 1250.00
            # Ya está en formato correcto
            pass
        elif len(parts) == 2 and len(parts[1]) == 3:
            # Formato miles europeo: 1.250 → verificar contexto
            if uses_comma_as_decimal:
                # En ARS/EUR, punto con 3 dígitos es separador de miles
                clean_text = clean_text.replace(".", "")
            else:
                # En USD, punto con 3 dígitos después es raro (decimal mal formateado)
                # Asumir que está correcto
                pass
        else:
            # Múltiples puntos: separador de miles europeo (ej: 1.000.000)
            if uses_comma_as_decimal:
                clean_text = clean_text.replace(".", "")
            # else: ya está bien para USD
    
    return clean_text


def normalize_price(raw_price: str) -> Tuple[Optional[Decimal], str]:
    """
    Normaliza un string de precio a valor numérico con detección de moneda.
    
    Esta función es la interfaz principal del módulo. Toma un string crudo
    de precio en cualquier formato y lo convierte a:
    - Decimal: valor numérico normalizado (ej: Decimal('4500.00'))
    - str: código de moneda ISO 4217 (ej: "ARS", "USD", "EUR")
    
    Formatos soportados:
    - "ARS 4.500,00" → (Decimal('4500.00'), 'ARS')
    - "$ 1.299" → (Decimal('1299.00'), 'ARS')
    - "USD 30.50" → (Decimal('30.50'), 'USD')
    - "€ 20,99" → (Decimal('20.99'), 'EUR')
    - "Precio: $ 1.250,00" → (Decimal('1250.00'), 'ARS')
    - "US$ 45.00" → (Decimal('45.00'), 'USD')
    
    Convenciones regionales:
    - ARS, EUR, BRL: punto como separador de miles, coma como decimal
    - USD, GBP: coma como separador de miles, punto como decimal
    
    Args:
        raw_price: String crudo del precio (ej: "ARS 4.500,00", "USD 30")
        
    Returns:
        Tupla (precio_decimal, codigo_moneda)
        - precio_decimal: Decimal con el valor o None si no se pudo convertir
        - codigo_moneda: Código ISO 4217 de la moneda (default: "ARS")
        
    Raises:
        No lanza excepciones. En caso de error retorna (None, "ARS")
        
    Examples:
        >>> normalize_price("ARS 4.500,00")
        (Decimal('4500.00'), 'ARS')
        
        >>> normalize_price("$ 1.299")
        (Decimal('1299.00'), 'ARS')
        
        >>> normalize_price("USD 30.50")
        (Decimal('30.50'), 'USD')
        
        >>> normalize_price("€ 20,99")
        (Decimal('20.99'), 'EUR')
        
        >>> normalize_price("invalid")
        (None, 'ARS')
    """
    if not raw_price or not isinstance(raw_price, str):
        logger.warning(f"Precio inválido o vacío: {raw_price}")
        return None, "ARS"
    
    try:
        # 1. Detectar moneda
        currency = detect_currency(raw_price)
        logger.debug(f"Moneda detectada: {currency} en '{raw_price}'")
        
        # 2. Limpiar texto (remover símbolos y texto extra)
        clean_text = clean_price_text(raw_price)
        logger.debug(f"Texto limpio: '{clean_text}'")
        
        if not clean_text:
            logger.warning(f"No se pudo extraer precio numérico de: '{raw_price}'")
            return None, currency
        
        # 2.5 NUEVO: Detectar y rechazar precios cero temprano
        # Antes de normalizar separadores, verificar si es claramente 0
        if re.match(r'^0+[.,]?0*$', clean_text.replace(' ', '')):
            logger.warning(f"Precio cero rechazado: '{raw_price}' → '{clean_text}'")
            return None, currency
        
        # 3. Normalizar separadores según moneda
        normalized_text = normalize_decimal_separators(clean_text, currency)
        logger.debug(f"Texto normalizado: '{normalized_text}'")
        
        # 4. Convertir a Decimal
        price_decimal = Decimal(normalized_text)
        
        # 5. Validar que sea positivo
        if price_decimal <= 0:
            logger.warning(f"Precio no positivo: {price_decimal} de '{raw_price}'")
            return None, currency
        
        logger.info(f"Precio normalizado: {price_decimal} {currency} de '{raw_price}'")
        return price_decimal, currency
        
    except (InvalidOperation, ValueError, AttributeError) as e:
        logger.warning(f"Error normalizando precio '{raw_price}': {e}")
        return None, "ARS"
    except Exception as e:
        logger.error(f"Error inesperado normalizando precio '{raw_price}': {e}")
        return None, "ARS"
