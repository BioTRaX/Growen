#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: static_scraper.py
# NG-HEADER: Ubicación: workers/scraping/static_scraper.py
# NG-HEADER: Descripción: Scraping de precios desde páginas HTML estáticas
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Scraping de precios desde páginas HTML estáticas usando requests + BeautifulSoup.

Este módulo implementa funciones para extraer precios de sitios web que
renderizan el contenido directamente en HTML (no requieren JavaScript).

Uso:
    from workers.scraping import scrape_static_price
    
    price = scrape_static_price("https://www.example.com/product")
    if price:
        print(f"Precio encontrado: ${price}")
"""

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from workers.scraping.price_normalizer import normalize_price as normalize_price_with_currency

logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Error genérico de scraping."""
    pass


class PriceNotFoundError(ScrapingError):
    """No se pudo encontrar el precio en la página."""
    pass


class NetworkError(ScrapingError):
    """Error de red al acceder a la URL."""
    pass


def scrape_static_price(url: str, timeout: int = 10) -> Tuple[Optional[Decimal], str]:
    """
    Extrae el precio de una página HTML estática con detección de moneda.
    
    Esta función realiza una petición HTTP GET a la URL proporcionada,
    parsea el HTML resultante con BeautifulSoup y busca el precio usando
    extractores específicos por dominio o un fallback genérico.
    
    Args:
        url: URL completa del producto a scrapear
        timeout: Timeout en segundos para la petición HTTP
        
    Returns:
        Tupla (precio, moneda):
        - precio: Precio extraído como Decimal, o None si no se encontró
        - moneda: Código de moneda ISO 4217 (ej: "ARS", "USD")
        
    Raises:
        NetworkError: Si hay error de red o timeout
        PriceNotFoundError: Si no se encontró el precio en la página
        
    Examples:
        >>> price, currency = scrape_static_price("https://www.mercadolibre.com.ar/...")
        >>> print(f"{price} {currency}")
        Decimal('1250.00') ARS
    """
    logger.info(f"Scraping price from: {url}")
    
    # Headers para evitar bloqueos básicos
    headers = {
        "User-Agent": "GrowenBot/1.0 (+https://growen.app)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al acceder a {url}")
        raise NetworkError(f"Timeout al acceder a {url}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Error de conexión al acceder a {url}: {e}")
        raise NetworkError(f"Error de conexión: {e}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Error HTTP {response.status_code} al acceder a {url}: {e}")
        raise NetworkError(f"Error HTTP {response.status_code}: {e}")
    except Exception as e:
        logger.error(f"Error inesperado al acceder a {url}: {e}")
        raise NetworkError(f"Error inesperado: {e}")
    
    # Parsear HTML
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Detectar dominio para usar extractor específico
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # Diccionario de extractores por dominio
    extractors = {
        "mercadolibre.com.ar": extract_price_mercadolibre,
        "www.mercadolibre.com.ar": extract_price_mercadolibre,
        "articulo.mercadolibre.com.ar": extract_price_mercadolibre,
        "amazon.com.ar": extract_price_amazon,
        "www.amazon.com.ar": extract_price_amazon,
    }
    
    # Buscar extractor específico para el dominio
    extractor = None
    for domain_key, extractor_func in extractors.items():
        if domain_key in domain:
            extractor = extractor_func
            break
    
    # Intentar con extractor específico
    if extractor:
        try:
            price_text = extractor(soup)
            if price_text:
                price, currency = normalize_price_with_currency(price_text)
                if price:
                    logger.info(f"Precio extraído con extractor específico: {price} {currency}")
                    return price, currency
        except Exception as e:
            logger.warning(f"Extractor específico falló para {domain}: {e}")
    
    # Fallback: extractor genérico
    try:
        price_text = extract_price_generic(soup)
        if price_text:
            price, currency = normalize_price_with_currency(price_text)
            if price:
                logger.info(f"Precio extraído con extractor genérico: {price} {currency}")
                return price, currency
    except Exception as e:
        logger.warning(f"Extractor genérico falló: {e}")
    
    # No se encontró precio
    logger.error(f"No se pudo extraer precio de {url}")
    raise PriceNotFoundError(f"No se pudo extraer precio de {url}")


def extract_price_mercadolibre(soup: BeautifulSoup) -> Optional[str]:
    """
    Extrae precio de MercadoLibre Argentina.
    
    MercadoLibre estructura el precio en varios spans:
    - span.andes-money-amount__currency-symbol: símbolo $
    - span.andes-money-amount__fraction: parte entera
    - span.andes-money-amount__cents: centavos
    
    Args:
        soup: BeautifulSoup object con el HTML parseado
        
    Returns:
        Texto del precio o None si no se encontró
    """
    logger.debug("Usando extractor de MercadoLibre")
    
    # Buscar contenedor principal del precio
    # Intentar selector más específico primero
    price_container = soup.select_one("div.ui-pdp-price__main-container")
    
    if price_container:
        # Buscar fracción (parte entera)
        fraction = price_container.select_one("span.andes-money-amount__fraction")
        
        if fraction:
            fraction_text = fraction.get_text(strip=True)
            
            # Buscar centavos (opcional)
            cents = price_container.select_one("span.andes-money-amount__cents")
            cents_text = cents.get_text(strip=True) if cents else "00"
            
            # Combinar para normalización posterior
            # Formato: $ 1.250,00 (típico de MercadoLibre AR)
            price_text = f"$ {fraction_text},{cents_text}"
            return price_text
    
    # Fallback: buscar cualquier andes-money-amount__fraction
    fraction = soup.select_one("span.andes-money-amount__fraction")
    if fraction:
        fraction_text = fraction.get_text(strip=True)
        cents = soup.select_one("span.andes-money-amount__cents")
        cents_text = cents.get_text(strip=True) if cents else "00"
        price_text = f"$ {fraction_text},{cents_text}"
        return price_text
    
    return None


def extract_price_amazon(soup: BeautifulSoup) -> Optional[str]:
    """
    Extrae precio de Amazon Argentina.
    
    Amazon usa varios selectores dependiendo del tipo de página:
    - span.a-price-whole: parte entera
    - span.a-price-decimal: separador decimal
    - span.a-price-fraction: centavos
    
    Args:
        soup: BeautifulSoup object con el HTML parseado
        
    Returns:
        Texto del precio o None si no se encontró
    """
    logger.debug("Usando extractor de Amazon")
    
    # Buscar contenedor de precio principal
    price_container = soup.select_one("span.a-price[data-a-size='xl']")
    
    if not price_container:
        # Fallback: cualquier a-price
        price_container = soup.select_one("span.a-price")
    
    if price_container:
        whole = price_container.select_one("span.a-price-whole")
        fraction = price_container.select_one("span.a-price-fraction")
        
        if whole:
            whole_text = whole.get_text(strip=True)
            fraction_text = fraction.get_text(strip=True) if fraction else "00"
            # Amazon AR usa formato americano: 1,250.00
            price_text = f"$ {whole_text}.{fraction_text}"
            return price_text
    
    # Fallback: buscar en id priceblock_ourprice (páginas antiguas)
    price_block = soup.select_one("#priceblock_ourprice")
    if price_block:
        price_text = price_block.get_text(strip=True)
        return price_text
    
    return None


def extract_price_generic(soup: BeautifulSoup) -> Optional[str]:
    """
    Extractor genérico de precios usando patrones regex.
    
    Busca patrones comunes de precios en el texto completo de la página:
    - $ 1.250,00
    - ARS 1250.50
    - AR$ 1,250
    
    Este es un fallback cuando no hay extractor específico para el dominio.
    Recolecta múltiples candidatos y retorna el más probable (ignorando $0).
    
    Args:
        soup: BeautifulSoup object con el HTML parseado
        
    Returns:
        Texto del precio o None si no se encontró
    """
    logger.debug("Usando extractor genérico")
    
    # Recolectar múltiples candidatos
    price_candidates = []
    
    # Buscar en clases/ids comunes
    for selector in [
        "[class*='price']",
        "[id*='price']",
        "[class*='precio']",
        "[id*='precio']",
        "[itemprop='price']",
        "[class*='amount']",
    ]:
        elements = soup.select(selector)
        for elem in elements:
            text = elem.get_text(strip=True)
            if text and re.search(r'[\d$]', text):
                # Filtrar candidatos sospechosos (Total, Subtotal, etc.)
                text_lower = text.lower()
                if any(word in text_lower for word in ['total:', 'subtotal:', 'envío:', 'descuento:']):
                    continue
                # Filtrar precios cero o muy bajos (probablemente errores)
                if re.match(r'^\$?\s?0[.,]?0*$', text.replace(',', '.').replace('$', '').strip()):
                    continue
                price_candidates.append(text)
    
    # Si encontramos candidatos, retornar el primero válido
    if price_candidates:
        logger.debug(f"Candidatos de precio encontrados: {price_candidates[:3]}")  # Log primeros 3
        return price_candidates[0]
    
    # Fallback: buscar patrones en texto completo
    patterns = [
        # $ 1.250,00 o $ 1,250.00 (al menos 3 dígitos)
        r'\$\s?[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?',
        # ARS 1250 o AR$ 1250
        r'(?:ARS|AR\$)\s?[\d.,]+',
        # USD 30.50
        r'USD\s?[\d.,]+',
        # Precio: 1250.50
        r'(?:precio|price):\s?\$?\s?[\d.,]+',
    ]
    
    # Buscar en todo el texto
    full_text = soup.get_text()
    for pattern in patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        for match in matches:
            # Filtrar $0 y valores muy bajos
            if re.match(r'^\$?\s?0[.,]?0*$', match.replace(',', '.').replace('$', '').strip()):
                continue
            logger.debug(f"Precio encontrado con regex: {match}")
            return match
    
    return None
