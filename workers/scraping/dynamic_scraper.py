#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: dynamic_scraper.py
# NG-HEADER: Ubicación: workers/scraping/dynamic_scraper.py
# NG-HEADER: Descripción: Scraping de precios desde páginas dinámicas con Playwright
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Scraping de precios desde páginas dinámicas usando Playwright.

Este módulo implementa funciones para extraer precios de sitios web que
cargan contenido mediante JavaScript (SPAs, páginas con interacción, etc.).

Uso:
    from workers.scraping.dynamic_scraper import scrape_dynamic_price
    
    price = await scrape_dynamic_price("https://www.example.com/product")
    if price:
        print(f"Precio encontrado: ${price}")
"""

import asyncio
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from workers.scraping.price_normalizer import normalize_price as normalize_price_with_currency

logger = logging.getLogger(__name__)

# Semáforo global para limitar browsers concurrentes (máximo 3)
# Esto evita saturación de memoria/CPU en operaciones de scraping masivo
_browser_semaphore = asyncio.Semaphore(3)


class DynamicScrapingError(Exception):
    """Error genérico de scraping dinámico."""
    pass


class BrowserLaunchError(DynamicScrapingError):
    """Error al lanzar el navegador."""
    pass


class PageLoadError(DynamicScrapingError):
    """Error al cargar la página."""
    pass


class SelectorNotFoundError(DynamicScrapingError):
    """Selector no encontrado en la página."""
    pass


class PriceExtractionError(DynamicScrapingError):
    """Error cuando no se puede extraer o normalizar el precio."""
    pass


async def scrape_dynamic_price(
    url: str,
    selector: Optional[str] = None,
    timeout: int = 15000,
    wait_for_selector_timeout: int = 8000,
) -> dict:
    """
    Extrae el precio de una página web dinámica usando Playwright con detección de moneda.
    
    Esta función abre un navegador headless, navega a la URL, espera a que
    el contenido se cargue, localiza el elemento con el precio y extrae su valor.
    
    Args:
        url: URL completa del producto a scrapear
        selector: Selector CSS para el elemento del precio (opcional)
        timeout: Timeout en milisegundos para cargar la página (default: 15000)
        wait_for_selector_timeout: Timeout en ms para esperar el selector (default: 8000)
        
    Returns:
        Dict con claves:
        - price: Precio extraído como Decimal, o None si no se encontró
        - currency: Código de moneda ISO 4217 (ej: "ARS", "USD")
        - source: Origen de extracción ("dynamic")
        
    Raises:
        BrowserLaunchError: Si falla al lanzar el navegador
        PageLoadError: Si falla al cargar la página
        SelectorNotFoundError: Si el selector no se encuentra en el timeout
        
    Examples:
        >>> price, currency = await scrape_dynamic_price(
        ...     "https://www.example.com/product",
        ...     selector="span.price-value"
        ... )
        >>> print(f"{price} {currency}")
        Decimal('1250.00') ARS
    """
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    
    # Adquirir semáforo para limitar browsers concurrentes
    # Esto previene saturación de recursos en scraping masivo
    async with _browser_semaphore:
        logger.debug(f"Semáforo adquirido. Browsers activos: {3 - _browser_semaphore._value}")
        
        try:
            logger.info(f"Iniciando scraping dinámico: {url}")
            
            # 1. Lanzar navegador headless
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                        ]
                    )
                    logger.debug("Navegador Chromium lanzado exitosamente")
                except Exception as e:
                    logger.error(f"Error al lanzar navegador: {e}")
                    raise BrowserLaunchError(f"No se pudo lanzar el navegador: {e}")
                
                # 2. Crear contexto con configuración
                try:
                    context = await browser.new_context(
                        viewport={'width': 1280, 'height': 720},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        locale='es-AR',
                    )
                    context.set_default_timeout(timeout)
                    logger.debug("Contexto del navegador creado")
                except Exception as e:
                    logger.error(f"Error al crear contexto: {e}")
                    if browser:
                        await browser.close()
                    raise BrowserLaunchError(f"No se pudo crear contexto: {e}")
                
                # 3. Crear página y navegar
                try:
                    page = await context.new_page()
                    logger.debug(f"Navegando a: {url}")
                    
                    # Navegar con timeout
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                    
                    if not response or not response.ok:
                        status = response.status if response else "sin respuesta"
                        raise PageLoadError(f"Página respondió con status: {status}")
                    
                    logger.debug("Página cargada, esperando contenido dinámico")
                    
                    # Esperar a que termine de cargar JavaScript
                    await page.wait_for_load_state('networkidle', timeout=timeout)
                    
                except PlaywrightTimeout as e:
                    logger.error(f"Timeout al cargar página: {e}")
                    raise PageLoadError(f"Timeout al cargar {url}: {e}")
                except Exception as e:
                    logger.error(f"Error al cargar página: {e}")
                    raise PageLoadError(f"Error al navegar a {url}: {e}")
                
                # 4. Detectar dominio para usar extractor específico
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                
                # 5. Extraer precio según estrategia
                price_text = None
                
                if selector:
                    # Estrategia 1: Selector proporcionado por el usuario
                    try:
                        logger.debug(f"Esperando selector: {selector}")
                        await page.wait_for_selector(selector, timeout=wait_for_selector_timeout)
                        
                        element = await page.query_selector(selector)
                        if element:
                            price_text = await element.inner_text()
                            logger.debug(f"Texto extraído del selector: {price_text}")
                        else:
                            raise SelectorNotFoundError(f"Selector '{selector}' no encontrado")
                            
                    except PlaywrightTimeout:
                        logger.error(f"Timeout esperando selector: {selector}")
                        raise SelectorNotFoundError(f"Selector '{selector}' no apareció en {wait_for_selector_timeout}ms")
                
                else:
                    # Estrategia 2: Extractores específicos por dominio o genérico
                    price_text = await extract_price_from_page(page, domain)
                
                # 6. Cerrar navegador antes de procesar
                await browser.close()
                browser = None
                logger.debug("Navegador cerrado exitosamente")
                
                # 7. Normalizar precio con detección de moneda
                if price_text:
                    price, currency = normalize_price_with_currency(price_text)
                    if price:
                        logger.info(f"Precio extraído exitosamente: {price} {currency}")
                        return {
                            'price': price,
                            'currency': currency,
                            'source': 'dynamic',
                        }
                    else:
                        raise PriceExtractionError("No se pudo normalizar precio de la página")
                else:
                    raise PriceExtractionError("No se encontró texto de precio en la página")
        
        except (BrowserLaunchError, PageLoadError, SelectorNotFoundError, PriceExtractionError) as e:
            # Errores conocidos: propagar directamente
            logger.error(f"Error específico de scraping: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            # Error inesperado
            logger.error(f"Error inesperado durante scraping dinámico: {e}", exc_info=True)
            raise DynamicScrapingError(f"Error inesperado: {e}")
        finally:
            # Liberar semáforo
            logger.debug(f"Semáforo liberado. Browsers activos: {3 - _browser_semaphore._value - 1}")
            
            # Cleanup: cerrar navegador si quedó abierto
            if browser:
                try:
                    await browser.close()
                    logger.debug("Navegador cerrado en finally")
                except Exception as e:
                    logger.warning(f"Error al cerrar navegador en finally: {e}")


async def extract_price_from_page(page: Page, domain: str) -> Optional[str]:
    """
    Extrae precio de una página usando estrategias específicas por dominio.
    
    Args:
        page: Página de Playwright ya cargada
        domain: Dominio de la URL (ej: www.example.com)
        
    Returns:
        Texto del precio encontrado o None
    """
    # TODO: Implementar extractores específicos para sitios argentinos
    # Por ahora usa estrategia genérica
    
    logger.debug(f"Usando extractor genérico para dominio: {domain}")
    
    # Estrategia genérica: buscar elementos comunes de precio
    selectors = [
        "[class*='price']",
        "[id*='price']",
        "[class*='precio']",
        "[id*='precio']",
        "[itemprop='price']",
        "[data-testid*='price']",
        ".product-price",
        ".price-tag",
        "#product-price",
    ]
    
    for sel in selectors:
        try:
            element = await page.query_selector(sel)
            if element:
                text = await element.inner_text()
                # Validar que contenga dígitos y símbolo de precio
                if text and re.search(r'[\d$]', text):
                    logger.debug(f"Precio encontrado con selector '{sel}': {text}")
                    return text.strip()
        except Exception as e:
            logger.debug(f"Error con selector '{sel}': {e}")
            continue
    
    # Último recurso: buscar en todo el contenido
    try:
        content = await page.content()
        match = re.search(r'\$\s?([\d.,]+)', content)
        if match:
            logger.debug(f"Precio encontrado con regex en contenido: {match.group(0)}")
            return match.group(0)
    except Exception as e:
        logger.warning(f"Error buscando con regex en contenido: {e}")
    
    return None


def scrape_dynamic_price_sync(
    url: str,
    selector: Optional[str] = None,
    timeout: int = 15000,
    wait_for_selector_timeout: int = 8000,
) -> Tuple[Optional[Decimal], str]:
    """
    Versión sincrónica de scrape_dynamic_price para uso desde código no-async.
    
    Esta función es un wrapper que ejecuta scrape_dynamic_price en un loop asyncio.
    Útil para integrar con código legacy o workers síncronos.
    
    Args:
        url: URL completa del producto a scrapear
        selector: Selector CSS para el elemento del precio (opcional)
        timeout: Timeout en milisegundos para cargar la página
        wait_for_selector_timeout: Timeout en ms para esperar el selector
        
    Returns:
        Tupla (precio, moneda):
        - precio: Precio extraído como Decimal, o None si no se encontró
        - moneda: Código de moneda ISO 4217 (ej: "ARS", "USD")
        
    Examples:
        >>> price, currency = scrape_dynamic_price_sync("https://www.example.com/product")
        >>> print(f"{price} {currency}")
        Decimal('1250.00') ARS
    """
    return asyncio.run(
        scrape_dynamic_price(
            url,
            selector=selector,
            timeout=timeout,
            wait_for_selector_timeout=wait_for_selector_timeout,
        )
    )
