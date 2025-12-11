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
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from workers.scraping.price_normalizer import normalize_price as normalize_price_with_currency

logger = logging.getLogger(__name__)

# Precios mínimos por moneda para validación (en caso de extracción incorrecta)
MIN_PRICE_BY_CURRENCY = {
    'ARS': Decimal('600'),  # Precio mínimo razonable para productos en Argentina
    'USD': Decimal('1'),   # Precio mínimo razonable para productos en USD
    'EUR': Decimal('1'),   # Precio mínimo razonable para productos en EUR
}


def _is_price_valid(price: Decimal, currency: str) -> bool:
    """
    Valida si un precio es razonable según la moneda.
    
    Args:
        price: Precio a validar
        currency: Código de moneda (ARS, USD, EUR, etc.)
        
    Returns:
        True si el precio es válido, False si es sospechosamente bajo
    """
    if price is None:
        return False
    
    min_price = MIN_PRICE_BY_CURRENCY.get(currency.upper())
    if min_price is None:
        # Si no hay mínimo definido para la moneda, aceptar cualquier precio
        return True
    
    return price >= min_price

# Semáforo global para limitar browsers concurrentes (máximo 3)
# Esto evita saturación de memoria/CPU en operaciones de scraping masivo
_browser_semaphore = asyncio.Semaphore(3)

# Thread pool executor para ejecutar Playwright en Windows
# Usamos sync_playwright en lugar de async_playwright para evitar problemas con file descriptors
_playwright_executor = None

def _get_playwright_executor():
    """Obtiene o crea el thread pool executor para Playwright en Windows"""
    global _playwright_executor
    if _playwright_executor is None:
        _playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
    return _playwright_executor


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


async def _scrape_with_playwright_impl(
    url: str,
    selector: Optional[str] = None,
    timeout: int = 15000,
    wait_for_selector_timeout: int = 8000,
) -> dict:
    """
    Implementación interna del scraping con Playwright.
    Esta función debe ejecutarse en un event loop que soporte subprocesos (ProactorEventLoop en Windows).
    
    Args:
        url: URL completa del producto a scrapear
        selector: Selector CSS para el elemento del precio (opcional)
        timeout: Timeout en milisegundos para cargar la página
        wait_for_selector_timeout: Timeout en ms para esperar el selector
        
    Returns:
        Dict con claves:
        - price: Precio extraído como Decimal, o None si no se encontró
        - currency: Código de moneda ISO 4217 (ej: "ARS", "USD")
        - source: Origen de extracción ("dynamic")
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
                        # Validar que el precio sea razonable
                        if not _is_price_valid(price, currency):
                            min_price = MIN_PRICE_BY_CURRENCY.get(currency.upper(), Decimal('0'))
                            logger.warning(
                                f"[scraping] Precio extraído ({price} {currency}) es menor al mínimo válido "
                                f"({min_price} {currency}), intentando fallback con OpenAI/MCP"
                            )
                            # Intentar fallback con AI
                            ai_result = await _scrape_price_with_ai_fallback(url)
                            if ai_result and 'price' in ai_result:
                                ai_currency = ai_result.get('currency', 'ARS')
                                if _is_price_valid(ai_result['price'], ai_currency):
                                    logger.info(f"[scraping] ✓ Precio extraído con fallback AI: {ai_result['price']} {ai_currency}")
                                    return ai_result
                                else:
                                    ai_min_price = MIN_PRICE_BY_CURRENCY.get(ai_currency.upper(), Decimal('0'))
                                    logger.warning(
                                        f"[scraping] Precio de AI ({ai_result['price']} {ai_currency}) también es menor al mínimo válido "
                                        f"({ai_min_price} {ai_currency})"
                                    )
                            raise PriceExtractionError(
                                f"Precio extraído ({price} {currency}) es menor al mínimo válido ({min_price} {currency})"
                            )
                        
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
    
    En Windows, ejecuta Playwright en un thread separado con ProactorEventLoop
    porque el event loop principal usa WindowsSelectorEventLoopPolicy (requerido por psycopg).
    
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
        >>> result = await scrape_dynamic_price("https://www.example.com/product")
        >>> print(f"{result['price']} {result['currency']}")
        Decimal('1250.00') ARS
    """
    # En Windows, ejecutar Playwright en un proceso separado usando multiprocessing
    # Esto evita problemas con event loops y file descriptors
    if sys.platform == 'win32':
        from multiprocessing import Process, Queue
        
        # Ejecutar en proceso separado usando Queue para comunicación
        queue = Queue()
        process = Process(target=_run_playwright_worker, args=(queue, url, selector, timeout, wait_for_selector_timeout))
        logger.info(f"[scraping] Iniciando proceso separado para Playwright en Windows: {url}")
        process.start()
        process.join(timeout=60)  # Timeout de 60 segundos
        
        if process.is_alive():
            logger.error("[scraping] Timeout: proceso de Playwright no terminó en 60 segundos")
            process.terminate()
            process.join()
            raise DynamicScrapingError("Timeout ejecutando Playwright en proceso separado")
        
        if not queue.empty():
            result = queue.get()
            if 'error' in result:
                logger.warning(f"[scraping] Error en proceso de Playwright: {result['error']}, intentando fallback con OpenAI/MCP")
                try:
                    ai_result = await _scrape_price_with_ai_fallback(url)
                    if ai_result and 'price' in ai_result:
                        logger.info(f"[scraping] ✓ Precio extraído con fallback AI: {ai_result['price']} {ai_result.get('currency', 'ARS')}")
                        return ai_result
                except Exception as ai_error:
                    logger.warning(f"[scraping] Fallback AI también falló: {ai_error}")
                # Si AI falla, lanzar el error original de Playwright
                raise DynamicScrapingError(result['error'])
            # Convertir price de string a Decimal
            result['price'] = Decimal(result['price'])
            currency = result.get('currency', 'ARS')
            
            # Validar que el precio sea razonable
            if not _is_price_valid(result['price'], currency):
                min_price = MIN_PRICE_BY_CURRENCY.get(currency.upper(), Decimal('0'))
                logger.warning(
                    f"[scraping] Precio extraído ({result['price']} {currency}) es menor al mínimo válido "
                    f"({min_price} {currency}), intentando fallback con OpenAI/MCP"
                )
                try:
                    ai_result = await _scrape_price_with_ai_fallback(url)
                    if ai_result and 'price' in ai_result:
                        ai_currency = ai_result.get('currency', 'ARS')
                        # Validar también el precio de AI
                        if _is_price_valid(ai_result['price'], ai_currency):
                            logger.info(f"[scraping] ✓ Precio extraído con fallback AI: {ai_result['price']} {ai_currency}")
                            return ai_result
                        else:
                            ai_min_price = MIN_PRICE_BY_CURRENCY.get(ai_currency.upper(), Decimal('0'))
                            logger.warning(
                                f"[scraping] Precio de AI ({ai_result['price']} {ai_currency}) también es menor al mínimo válido "
                                f"({ai_min_price} {ai_currency})"
                            )
                except Exception as ai_error:
                    logger.warning(f"[scraping] Fallback AI también falló: {ai_error}")
                # Si AI falla o también es inválido, lanzar error
                raise DynamicScrapingError(
                    f"Precio extraído ({result['price']} {currency}) es menor al mínimo válido ({min_price} {currency})"
                )
            
            logger.info(f"[scraping] Proceso de Playwright completado exitosamente: {result['price']} {result['currency']}")
            return result
        else:
            logger.warning("[scraping] No se recibió resultado del proceso de Playwright (queue vacía), intentando fallback con OpenAI/MCP")
            try:
                ai_result = await _scrape_price_with_ai_fallback(url)
                if ai_result and 'price' in ai_result:
                    currency = ai_result.get('currency', 'ARS')
                    # Validar también el precio de AI
                    if _is_price_valid(ai_result['price'], currency):
                        logger.info(f"[scraping] ✓ Precio extraído con fallback AI: {ai_result['price']} {currency}")
                        return ai_result
                    else:
                        min_price = MIN_PRICE_BY_CURRENCY.get(currency.upper(), Decimal('0'))
                        logger.warning(f"[scraping] Precio de AI ({ai_result['price']} {currency}) es menor al mínimo válido ({min_price} {currency})")
            except Exception as ai_error:
                logger.warning(f"[scraping] Fallback AI también falló: {ai_error}")
            raise DynamicScrapingError("No se recibió resultado del proceso de Playwright")
    else:
        # En Linux/Mac, usar async directamente
        return await _scrape_with_playwright_impl(url, selector, timeout, wait_for_selector_timeout)


def _run_playwright_worker(queue, url_param, selector_param, timeout_param, wait_for_selector_timeout_param):
    """
    Worker function para ejecutar Playwright en proceso separado.
    
    Esta función debe estar en el nivel de módulo para que multiprocessing pueda serializarla.
    """
    try:
        import re  # Asegurar que re esté disponible en el proceso separado
        from playwright.sync_api import sync_playwright, TimeoutError as SyncPlaywrightTimeout
        
        logger.info(f"Iniciando scraping dinámico (process) en Windows: {url_param}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                ]
            )
            
            try:
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='es-AR',
                )
                context.set_default_timeout(timeout_param)
                
                page = context.new_page()
                response = page.goto(url_param, wait_until='load', timeout=timeout_param)
                
                if not response or not response.ok:
                    status = response.status if response else "sin respuesta"
                    queue.put({'error': f"Página respondió con status: {status}"})
                    return
                
                # Esperar un poco más para que se carguen los elementos dinámicos
                # Usar 'load' en lugar de 'networkidle' porque MercadoLibre tiene muchas peticiones AJAX continuas
                page.wait_for_load_state('load', timeout=timeout_param)
                # Esperar un poco adicional para elementos dinámicos
                page.wait_for_timeout(2000)  # 2 segundos adicionales
                
                parsed_url = urlparse(url_param)
                domain = parsed_url.netloc.lower()
                
                price_text = None
                if selector_param:
                    page.wait_for_selector(selector_param, timeout=wait_for_selector_timeout_param)
                    element = page.query_selector(selector_param)
                    if element:
                        price_text = element.inner_text()
                else:
                    price_text = _extract_price_sync(page, domain)
                    logger.debug(f"[scraping] Texto de precio extraído: {price_text}")
                
                if price_text:
                    price, currency = normalize_price_with_currency(price_text)
                    if price:
                        logger.info(f"Precio extraído exitosamente (process): {price} {currency}")
                        queue.put({
                            'price': str(price),  # Serializar Decimal como string
                            'currency': currency,
                            'source': 'dynamic',
                        })
                    else:
                        queue.put({'error': "No se pudo normalizar precio de la página"})
                else:
                    queue.put({'error': "No se encontró texto de precio en la página"})
                    
            finally:
                browser.close()
                
    except Exception as e:
        logger.error(f"Error en scraping dinámico (process): {e}", exc_info=True)
        queue.put({'error': f"Error inesperado: {e}"})


def _get_html_worker(queue, url_param):
    """
    Worker function para obtener HTML de una URL usando Playwright en proceso separado.
    
    Esta función debe estar en el nivel de módulo para que multiprocessing pueda serializarla.
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            try:
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                )
                page = context.new_page()
                page.goto(url_param, wait_until='load', timeout=15000)
                page.wait_for_load_state('load', timeout=15000)
                # Esperar un poco adicional para elementos dinámicos
                page.wait_for_timeout(2000)  # 2 segundos adicionales
                html = page.content()
                queue.put({'html': html})
            finally:
                browser.close()
    except Exception as e:
        queue.put({'error': str(e)})


def _extract_price_sync(page, domain: str) -> Optional[str]:
    """
    Extrae precio de una página usando estrategias específicas por dominio (versión síncrona).
    
    Args:
        page: Página de Playwright (sync) ya cargada
        domain: Dominio de la URL
        
    Returns:
        Texto del precio encontrado o None
    """
    import re  # Asegurar que re esté disponible cuando se ejecuta en proceso separado
    logger.debug(f"Usando extractor (sync) para dominio: {domain}")
    
    # Extractores específicos para MercadoLibre
    if 'mercadolibre' in domain:
        logger.debug("Usando extractor específico de MercadoLibre")
        try:
            # Selector principal de MercadoLibre - buscar el precio completo
            # El precio en MercadoLibre está en: div.ui-pdp-price__main-container
            main_container = page.query_selector("div.ui-pdp-price__main-container")
            if main_container:
                # Buscar TODOS los elementos de precio en el container para encontrar el principal
                all_fractions_in_container = main_container.query_selector_all("span.andes-money-amount__fraction")
                logger.debug(f"Encontrados {len(all_fractions_in_container)} elementos de precio en container principal")
                
                if all_fractions_in_container:
                    # El precio principal generalmente es el más grande (más dígitos)
                    best_fraction = None
                    best_fraction_text = ""
                    max_numeric_chars = 0
                    
                    for fraction in all_fractions_in_container:
                        fraction_text = fraction.inner_text().strip()
                        # Contar caracteres numéricos (sin contar puntos/commas)
                        numeric_chars = len([c for c in fraction_text if c.isdigit()])
                        logger.debug(f"  - Elemento encontrado: '{fraction_text}' ({numeric_chars} dígitos)")
                        
                        if numeric_chars > max_numeric_chars:
                            max_numeric_chars = numeric_chars
                            best_fraction = fraction
                            best_fraction_text = fraction_text
                    
                    if best_fraction and max_numeric_chars >= 3:  # Precio principal debe tener al menos 3 dígitos
                        # IMPORTANTE: En MercadoLibre, el precio principal suele ser el que está más arriba y visible
                        # No el precio por kilo que puede tener más dígitos. 
                        # El precio principal generalmente está en el PRIMER elemento visible, no necesariamente el más grande
                        
                        container_text = main_container.inner_text()
                        
                        # Verificar si hay un precio "por kilo" o similar que debemos ignorar
                        # Si el container tiene texto "por kilo", el precio principal suele estar ANTES de ese texto
                        if "por kilo" in container_text.lower() or "por kg" in container_text.lower():
                            # Buscar el precio que está ANTES del texto "por kilo"
                            # El precio principal suele ser el primero que aparece
                            logger.debug("[scraping] Detectado precio 'por kilo', buscando precio principal antes de ese texto")
                            # Usar el primer precio (más prominente visualmente)
                            main_price_fraction = all_fractions_in_container[0]
                            main_price_text = main_price_fraction.inner_text().strip()
                        else:
                            # Si no hay "por kilo", usar el mejor precio encontrado (el más grande)
                            main_price_text = best_fraction_text
                        
                        # Buscar centavos asociados al precio principal
                        cents_text = ""
                        # Buscar centavos en el mismo container
                        cents_candidates = main_container.query_selector_all("span.andes-money-amount__cents")
                        if cents_candidates:
                            # Tomar el primero (generalmente corresponde al precio principal)
                            cents_text = cents_candidates[0].inner_text().strip()
                        
                        if cents_text:
                            price_text = f"$ {main_price_text},{cents_text}"
                        else:
                            price_text = f"$ {main_price_text}"
                        
                        logger.info(f"[scraping] Precio principal encontrado en container: {price_text} (fraction: {main_price_text}, {max_numeric_chars} dígitos)")
                        return price_text
                    else:
                        logger.warning(f"[scraping] No se encontró precio válido (mejor match tenía {max_numeric_chars} dígitos, mínimo requerido: 3)")
                
                # Alternativa: buscar directamente el texto del precio en el container
                container_text = main_container.inner_text()
                logger.debug(f"Texto completo del container: {container_text[:200]}...")
                # Buscar patrón de precio: $ seguido de números con punto o coma (priorizar números grandes)
                price_matches = re.findall(r'\$\s*([\d.,]+)', container_text)
                if price_matches:
                    # Tomar el precio más grande (más dígitos)
                    best_match = max(price_matches, key=lambda x: len([c for c in x if c.isdigit()]))
                    price_text = f"$ {best_match}"
                    logger.debug(f"Precio encontrado con regex en container: {price_text} (de {len(price_matches)} matches)")
                    return price_text
            
            # Selector alternativo: buscar el precio principal (el más grande/prominente)
            # En MercadoLibre, el precio principal suele estar en el primer span.andes-money-amount__fraction
            # dentro del contenedor de precio principal
            all_fractions = page.query_selector_all("span.andes-money-amount__fraction")
            if all_fractions:
                # Buscar el precio principal: generalmente es el que tiene más dígitos o está en el contenedor principal
                best_fraction = None
                best_fraction_text = ""
                
                for fraction in all_fractions:
                    fraction_text = fraction.inner_text().strip()
                    # El precio principal generalmente tiene más de 3 dígitos (ej: "2.699" tiene 4 caracteres numéricos)
                    # y no es solo un número pequeño
                    numeric_chars = len([c for c in fraction_text if c.isdigit()])
                    if numeric_chars > len(best_fraction_text.replace(".", "").replace(",", "")):
                        best_fraction = fraction
                        best_fraction_text = fraction_text
                
                if best_fraction:
                    # Buscar centavos cerca del precio principal
                    cents_elements = page.query_selector_all("span.andes-money-amount__cents")
                    cents_text = ""
                    if cents_elements:
                        # Tomar el primer elemento de centavos (generalmente corresponde al precio principal)
                        cents_text = cents_elements[0].inner_text().strip()
                    
                    if cents_text:
                        price_text = f"$ {best_fraction_text},{cents_text}"
                    else:
                        price_text = f"$ {best_fraction_text}"
                    
                    logger.debug(f"Precio encontrado usando mejor match: {price_text} (de {len(all_fractions)} elementos)")
                    return price_text
        except Exception as e:
            logger.warning(f"Error con extractor específico de MercadoLibre: {e}", exc_info=True)
    
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
            element = page.query_selector(sel)
            if element:
                text = element.inner_text()
                # Validar que contenga dígitos y símbolo de precio
                if text and re.search(r'[\d$]', text):
                    logger.debug(f"Precio encontrado con selector '{sel}': {text}")
                    return text.strip()
        except Exception as e:
            logger.debug(f"Error con selector '{sel}': {e}")
            continue
    
    # Último recurso: buscar en todo el contenido
    try:
        content = page.content()
        match = re.search(r'\$\s?([\d.,]+)', content)
        if match:
            logger.debug(f"Precio encontrado con regex en contenido: {match.group(0)}")
            return match.group(0)
    except Exception as e:
        logger.warning(f"Error buscando con regex en contenido: {e}")
    
    return None


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


async def _scrape_price_with_ai_fallback(url: str) -> Optional[dict]:
    """
    Fallback usando OpenAI para extraer precio cuando Playwright falla o extrae precio inválido.
    
    Obtiene el HTML de la URL usando Playwright y lo envía a OpenAI para extraer el precio.
    
    Args:
        url: URL del producto (debe ser una URL de las fuentes configuradas)
        
    Returns:
        Dict con 'price' (Decimal), 'currency' (str), 'source' ('ai_fallback')
        o None si falla
    """
    try:
        from ai.providers.openai_provider import OpenAIProvider
        import json
        
        logger.info(f"[scraping] Intentando extraer precio con AI fallback (OpenAI) para: {url}")
        
        # Forzar uso de OpenAI directamente
        try:
            openai_provider = OpenAIProvider()
            if not openai_provider.api_key:
                logger.warning("[scraping] OpenAI API key no configurada, no se puede usar AI fallback")
                return None
        except Exception as init_error:
            logger.error(f"[scraping] Error inicializando OpenAIProvider: {init_error}")
            return None
        
        # Obtener HTML de la URL usando Playwright (en proceso separado en Windows)
        page_html = None
        try:
            logger.debug(f"[scraping] Obteniendo HTML de la URL para análisis con AI: {url}")
            # Usar la misma lógica de Playwright pero solo para obtener HTML
            if sys.platform == 'win32':
                from multiprocessing import Process, Queue
                
                html_queue = Queue()
                html_process = Process(target=_get_html_worker, args=(html_queue, url))
                html_process.start()
                html_process.join(timeout=30)
                
                if html_process.is_alive():
                    html_process.terminate()
                    html_process.join(timeout=5)
                    logger.warning("[scraping] Proceso de obtención de HTML excedió timeout")
                elif not html_queue.empty():
                    html_result = html_queue.get()
                    if 'html' in html_result:
                        page_html = html_result['html']
                        logger.debug(f"[scraping] HTML obtenido exitosamente ({len(page_html)} caracteres)")
                    else:
                        logger.warning(f"[scraping] Error obteniendo HTML: {html_result.get('error', 'unknown')}")
            else:
                # Linux/Mac: usar async directamente
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
                    try:
                        context = await browser.new_context(
                            viewport={'width': 1280, 'height': 720},
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        )
                        page = await context.new_page()
                        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        page_html = await page.content()
                        logger.debug(f"[scraping] HTML obtenido exitosamente ({len(page_html)} caracteres)")
                    finally:
                        await browser.close()
        except Exception as e:
            logger.warning(f"[scraping] Error obteniendo HTML de la URL: {e}")
            # Continuar sin HTML, solo con la URL
            page_html = None
        
        # Extraer información relevante del HTML (solo la parte del precio)
        html_context = ""
        if page_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(page_html, 'html.parser')
                
                # Buscar elementos relacionados con precio en MercadoLibre
                price_elements = []
                
                # Selectores específicos de MercadoLibre
                price_container = soup.select_one("div.ui-pdp-price__main-container")
                if price_container:
                    price_elements.append(price_container.get_text(strip=True))
                
                # Buscar spans con clase de precio
                price_spans = soup.select("span.andes-money-amount__fraction, span.andes-money-amount__cents")
                if price_spans:
                    price_text = " ".join([span.get_text(strip=True) for span in price_spans[:5]])
                    if price_text:
                        price_elements.append(price_text)
                
                # Buscar cualquier elemento con "precio" o "price"
                price_keywords = soup.select("[class*='price'], [id*='price'], [class*='precio'], [id*='precio']")
                if price_keywords:
                    for elem in price_keywords[:3]:
                        text = elem.get_text(strip=True)
                        if text and re.search(r'[\d$]', text):
                            price_elements.append(text)
                
                if price_elements:
                    html_context = "\n\nContenido HTML relevante extraído de la página:\n" + "\n".join(price_elements[:5])
                    logger.debug(f"[scraping] Extraídos {len(price_elements)} elementos de precio del HTML")
            except Exception as e:
                logger.debug(f"[scraping] Error procesando HTML: {e}")
        
        # Construir prompt con HTML extraído
        user_prompt = f"""Analiza el siguiente contenido de una página de MercadoLibre y extrae SOLO el precio de venta principal (unitario).

URL: {url}{html_context}

Instrucciones CRÍTICAS:
1. Busca el precio PRINCIPAL del producto (el precio unitario de venta, NO el precio por kilo, por litro, ni descuentos)
2. En MercadoLibre, el precio principal suele estar en formato como "$ 6.999" o "6.999" (con punto como separador de miles)
3. IGNORA precios que digan "por kilo", "por kg", "por litro", "por unidad de medida" - esos NO son el precio principal
4. El precio principal es el que está más prominente y visible, generalmente el primero que aparece
5. El precio debe estar en formato numérico (ej: 6999, 2699, 1250.50, etc.) - SIN puntos ni comas como separadores de miles
6. Si el precio tiene formato "$ 6.999", el valor numérico debe ser 6999 (sin el punto)
7. Identifica la moneda (ARS para Argentina)
8. Responde SOLO con un JSON válido en este formato exacto:
{{"price": 6999, "currency": "ARS"}}

EJEMPLOS:
- Si ves "$ 6.999" → {{"price": 6999, "currency": "ARS"}}
- Si ves "$ 2.699" → {{"price": 2699, "currency": "ARS"}}
- Si ves "$ 27.996 por kilo" → IGNORA este, busca el precio unitario principal

Si no encuentras el precio principal, responde: {{"error": "No se pudo extraer precio"}}"""

        system_prompt = "Eres un asistente especializado en extraer precios de productos desde páginas de MercadoLibre. Analiza el contenido HTML proporcionado y extrae el precio principal. Responde siempre con JSON válido."
        
        # Llamar directamente a OpenAI con formato JSON forzado
        response = await openai_provider.generate_async(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            user_context={"role": "admin"}
        )
        
        logger.debug(f"[scraping] Respuesta de OpenAI: {response[:300]}")
        
        # Intentar parsear la respuesta como JSON con múltiples estrategias
        data = None
        
        # Estrategia 1: Buscar JSON completo con llaves balanceadas
        try:
            start = response.find('{')
            if start != -1:
                depth = 0
                end = start
                for i in range(start, len(response)):
                    if response[i] == '{':
                        depth += 1
                    elif response[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end > start:
                    json_str = response[start:end]
                    data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Estrategia 2: Buscar JSON simple con regex
        if data is None:
            try:
                json_match = re.search(r'\{\s*"price"\s*:\s*(\d+(?:\.\d+)?)\s*,\s*"currency"\s*:\s*"([^"]+)"\s*\}', response)
                if json_match:
                    data = {
                        "price": float(json_match.group(1)),
                        "currency": json_match.group(2)
                    }
            except (ValueError, AttributeError):
                pass
        
        # Estrategia 3: Buscar números en la respuesta
        if data is None:
            try:
                # Buscar el número más grande (probablemente el precio principal)
                numbers = re.findall(r'\b(\d{3,}(?:\.\d+)?)\b', response)
                if numbers:
                    # Tomar el número más grande (excluyendo números muy grandes que podrían ser IDs)
                    valid_numbers = [float(n) for n in numbers if 100 <= float(n) <= 1000000]
                    if valid_numbers:
                        price_value = max(valid_numbers)
                        currency = "ARS" if "ARS" in response or "peso" in response.lower() else "ARS"
                        data = {"price": price_value, "currency": currency}
                        logger.debug(f"[scraping] Extraído precio usando regex: {price_value} {currency}")
            except (ValueError, AttributeError):
                pass
        
        if data:
            if 'error' in data:
                logger.warning(f"[scraping] AI fallback reportó error: {data['error']}")
                return None
            
            price = data.get('price')
            currency = data.get('currency', 'ARS')
            
            if price:
                price_decimal = Decimal(str(price))
                logger.info(f"[scraping] AI fallback extrajo: {price_decimal} {currency}")
                return {
                    'price': price_decimal,
                    'currency': currency,
                    'source': 'ai_fallback',
                }
        
        logger.warning(f"[scraping] AI fallback no pudo extraer precio válido de respuesta: {response[:300]}")
        return None
        
    except Exception as e:
        logger.error(f"[scraping] Error en AI fallback: {e}", exc_info=True)
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
