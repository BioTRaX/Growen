#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: source_validator.py
# NG-HEADER: Ubicación: workers/discovery/source_validator.py
# NG-HEADER: Descripción: Validación de fuentes sugeridas (detección rápida de precio)
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Validación de fuentes de precio sugeridas.

Este módulo implementa funciones para validar que una URL candidata
efectivamente contenga información de precio antes de agregarla como fuente.

Incluye:
- Detección rápida de precio en HTML (HEAD + regex)
- Validación de disponibilidad de URL
- Estimación de confiabilidad por dominio
"""

import logging
import re
from typing import Optional, Tuple
from urllib.parse import urlparse
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Dominios de alta confianza (no requieren validación estricta)
HIGH_CONFIDENCE_DOMAINS = [
    "mercadolibre.com.ar",
    "mercadolibre.com",
    "santaplanta.com",
    "cultivargrowshop.com",
]


# Patrones de precio comunes
PRICE_PATTERNS = [
    # $1234, $1,234, $1.234
    r'\$\s*\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?',
    # Precio: 1234
    r'precio\s*:?\s*\$?\s*\d{1,3}(?:[,\.]\d{3})*',
    # ARS 1234
    r'ARS\s*\$?\s*\d{1,3}(?:[,\.]\d{3})*',
    # class="price" ... >1234<
    r'price["\']?\s*>?\s*\$?\s*\d{1,3}(?:[,\.]\d{3})*',
]


class ValidationError(Exception):
    """Error de validación de fuente."""
    pass


class NetworkError(ValidationError):
    """Error de red al validar fuente."""
    pass


class PriceNotFoundError(ValidationError):
    """No se detectó precio en la URL."""
    pass


def get_domain(url: str) -> str:
    """
    Extrae el dominio de una URL.
    
    Args:
        url: URL completa
        
    Returns:
        Dominio sin 'www.' (ej: "mercadolibre.com.ar")
        
    Examples:
        >>> get_domain("https://www.mercadolibre.com.ar/producto")
        'mercadolibre.com.ar'
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Remover www.
    if domain.startswith("www."):
        domain = domain[4:]
    
    return domain


def is_high_confidence_domain(url: str) -> bool:
    """
    Verifica si la URL pertenece a un dominio de alta confianza.
    
    Los dominios de alta confianza se agregan sin validación estricta
    de precio (asumimos que siempre tienen precio si existen).
    
    Args:
        url: URL a verificar
        
    Returns:
        True si es dominio de alta confianza
    """
    domain = get_domain(url)
    return any(trusted in domain for trusted in HIGH_CONFIDENCE_DOMAINS)


async def check_url_availability(url: str, timeout: int = 5) -> bool:
    """
    Verifica que una URL sea accesible (HEAD request).
    
    Args:
        url: URL a verificar
        timeout: Timeout en segundos
        
    Returns:
        True si la URL responde con 200-399
        
    Raises:
        NetworkError: Si hay error de red o timeout
    """
    logger.info(f"[validator] Verificando disponibilidad: {url}")
    
    headers = {
        "User-Agent": "GrowenBot/1.0 (+https://growen.app)",
        "Accept": "text/html,application/xhtml+xml",
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.head(url, headers=headers)
            
            # Considerar 200-399 como disponible
            is_available = 200 <= response.status_code < 400
            
            if not is_available:
                logger.warning(f"[validator] URL {url} retornó status {response.status_code}")
            
            return is_available
            
    except httpx.TimeoutException:
        logger.error(f"[validator] Timeout al verificar {url}")
        raise NetworkError(f"Timeout al verificar URL")
    except httpx.RequestError as e:
        logger.error(f"[validator] Error de red al verificar {url}: {e}")
        raise NetworkError(f"Error de red: {str(e)}")


async def detect_price_in_html(url: str, timeout: int = 10) -> bool:
    """
    Detecta si existe un precio en el HTML de una URL.
    
    Realiza un GET request completo (no HEAD) y busca patrones
    de precio en el HTML usando regex y BeautifulSoup.
    
    Args:
        url: URL a analizar
        timeout: Timeout en segundos
        
    Returns:
        True si se detectó al menos un patrón de precio
        
    Raises:
        NetworkError: Si hay error de red o timeout
    """
    logger.info(f"[validator] Detectando precio en: {url}")
    
    headers = {
        "User-Agent": "GrowenBot/1.0 (+https://growen.app)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            html = response.text
            
            # Buscar patrones de precio en el HTML completo
            for pattern in PRICE_PATTERNS:
                if re.search(pattern, html, re.IGNORECASE):
                    logger.info(f"[validator] Precio detectado en {url} con patrón: {pattern}")
                    return True
            
            # Fallback: buscar en tags específicos con BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            # Buscar en meta tags de precio (schema.org)
            price_meta = soup.find("meta", {"property": "product:price:amount"})
            if price_meta and price_meta.get("content"):
                logger.info(f"[validator] Precio detectado en meta tag: {url}")
                return True
            
            # Buscar en clases/ids comunes de precio
            price_elements = soup.find_all(class_=re.compile(r"price|precio|valor", re.IGNORECASE))
            for elem in price_elements:
                text = elem.get_text()
                if re.search(r'\d{1,3}(?:[,\.]\d{3})*', text):
                    logger.info(f"[validator] Precio detectado en elemento: {url}")
                    return True
            
            logger.warning(f"[validator] No se detectó precio en {url}")
            return False
            
    except httpx.TimeoutException:
        logger.error(f"[validator] Timeout al obtener HTML de {url}")
        raise NetworkError(f"Timeout al obtener HTML")
    except httpx.HTTPStatusError as e:
        logger.error(f"[validator] Error HTTP {e.response.status_code} al obtener {url}")
        raise NetworkError(f"Error HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"[validator] Error de red al obtener {url}: {e}")
        raise NetworkError(f"Error de red: {str(e)}")
    except Exception as e:
        logger.error(f"[validator] Error inesperado al parsear HTML de {url}: {e}")
        return False


async def validate_source(url: str, quick: bool = False) -> Tuple[bool, str]:
    """
    Valida una fuente de precio sugerida.
    
    Proceso:
    1. Verifica disponibilidad de la URL (HEAD request)
    2. Si es dominio de alta confianza, retorna OK sin más validación
    3. Si no, busca precio en el HTML (GET request + regex)
    
    Args:
        url: URL a validar
        quick: Si True, solo verifica disponibilidad (skip detección de precio)
        
    Returns:
        Tupla (is_valid, reason):
        - is_valid: True si la fuente es válida
        - reason: Razón de validación ("price_found", "high_confidence") o error
        
    Examples:
        >>> valid, reason = await validate_source("https://mercadolibre.com.ar/...")
        >>> print(f"Valid: {valid}, Reason: {reason}")
        Valid: True, Reason: high_confidence
    """
    logger.info(f"[validator] Validando fuente: {url}")
    
    # 1. Verificar disponibilidad
    try:
        is_available = await check_url_availability(url, timeout=5)
        if not is_available:
            return False, "url_not_available"
    except NetworkError as e:
        logger.warning(f"[validator] Error de red al validar {url}: {e}")
        return False, f"network_error: {str(e)}"
    
    # 2. Si es dominio de alta confianza, aprobar directamente
    if is_high_confidence_domain(url):
        logger.info(f"[validator] Dominio de alta confianza: {url}")
        return True, "high_confidence"
    
    # 3. Si quick=True, detener aquí
    if quick:
        logger.info(f"[validator] Validación rápida OK: {url}")
        return True, "quick_check_passed"
    
    # 4. Buscar precio en HTML
    try:
        has_price = await detect_price_in_html(url, timeout=10)
        if has_price:
            return True, "price_found"
        else:
            return False, "price_not_found"
    except NetworkError as e:
        logger.warning(f"[validator] Error al buscar precio en {url}: {e}")
        return False, f"price_check_error: {str(e)}"


async def validate_multiple_sources(
    urls: list[str],
    quick: bool = False,
    max_concurrent: int = 3
) -> dict[str, Tuple[bool, str]]:
    """
    Valida múltiples fuentes en paralelo (limitado).
    
    Args:
        urls: Lista de URLs a validar
        quick: Si True, solo verificar disponibilidad
        max_concurrent: Máximo de validaciones concurrentes
        
    Returns:
        Dict con URL como key y (is_valid, reason) como value
        
    Examples:
        >>> results = await validate_multiple_sources(["url1", "url2"])
        >>> for url, (valid, reason) in results.items():
        ...     print(f"{url}: {valid} ({reason})")
    """
    import asyncio
    
    logger.info(f"[validator] Validando {len(urls)} fuentes (max_concurrent={max_concurrent})")
    
    results = {}
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def validate_with_semaphore(url: str):
        async with semaphore:
            try:
                valid, reason = await validate_source(url, quick=quick)
                results[url] = (valid, reason)
            except Exception as e:
                logger.error(f"[validator] Error inesperado validando {url}: {e}")
                results[url] = (False, f"unexpected_error: {str(e)}")
    
    await asyncio.gather(*[validate_with_semaphore(url) for url in urls])
    
    logger.info(f"[validator] Validación completa: {len([v for v, _ in results.values() if v])}/{len(urls)} válidas")
    
    return results
