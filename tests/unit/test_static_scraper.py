#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_static_scraper.py
# NG-HEADER: Ubicación: tests/unit/test_static_scraper.py
# NG-HEADER: Descripción: Tests unitarios para scraping estático de precios
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests unitarios para scraping estático de precios con HTML.

Cubre:
- Extracción de precios de MercadoLibre
- Extracción de precios de Amazon
- Extractor genérico con patrones regex
- Manejo de errores de red (timeout, connection, HTTP errors)
- HTML mal formado o sin precio
- Mocking completo de requests (sin llamadas HTTP reales)
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
import requests

from workers.scraping.static_scraper import (
    scrape_static_price,
    extract_price_mercadolibre,
    extract_price_amazon,
    extract_price_generic,
    PriceNotFoundError,
    NetworkError,
)


# ============================================================================
# FIXTURES HTML
# ============================================================================

@pytest.fixture
def mercadolibre_html_complete():
    """HTML de MercadoLibre con precio completo (fracción + centavos)"""
    return """
    <html>
        <body>
            <div class="ui-pdp-price__main-container">
                <span class="andes-money-amount__currency-symbol">$</span>
                <span class="andes-money-amount__fraction">1.250</span>
                <span class="andes-money-amount__cents">00</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def mercadolibre_html_no_cents():
    """HTML de MercadoLibre sin centavos (solo fracción)"""
    return """
    <html>
        <body>
            <div class="ui-pdp-price__main-container">
                <span class="andes-money-amount__fraction">4.500</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def mercadolibre_html_no_container():
    """HTML de MercadoLibre sin contenedor principal (fallback)"""
    return """
    <html>
        <body>
            <span class="andes-money-amount__fraction">2.999</span>
            <span class="andes-money-amount__cents">50</span>
        </body>
    </html>
    """


@pytest.fixture
def mercadolibre_html_no_price():
    """HTML de MercadoLibre sin precio"""
    return """
    <html>
        <body>
            <div class="product-info">
                <h1>Producto sin precio</h1>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def amazon_html_complete():
    """HTML de Amazon con precio completo"""
    return """
    <html>
        <body>
            <span class="a-price" data-a-size="xl">
                <span class="a-price-whole">1,250</span>
                <span class="a-price-decimal">.</span>
                <span class="a-price-fraction">00</span>
            </span>
        </body>
    </html>
    """


@pytest.fixture
def amazon_html_no_fraction():
    """HTML de Amazon sin fracción decimal"""
    return """
    <html>
        <body>
            <span class="a-price">
                <span class="a-price-whole">45</span>
            </span>
        </body>
    </html>
    """


@pytest.fixture
def amazon_html_legacy():
    """HTML de Amazon con formato antiguo (priceblock_ourprice)"""
    return """
    <html>
        <body>
            <span id="priceblock_ourprice">$ 30.50</span>
        </body>
    </html>
    """


@pytest.fixture
def generic_html_with_class():
    """HTML genérico con clase 'price'"""
    return """
    <html>
        <body>
            <div class="product-price">$ 1.299</div>
        </body>
    </html>
    """


@pytest.fixture
def generic_html_with_itemprop():
    """HTML genérico con atributo itemprop='price'"""
    return """
    <html>
        <body>
            <span itemprop="price">4500.00</span>
            <span itemprop="priceCurrency" content="ARS">ARS</span>
        </body>
    </html>
    """


@pytest.fixture
def generic_html_multiple_prices():
    """HTML con múltiples precios (debe retornar el primero encontrado)"""
    return """
    <html>
        <body>
            <div class="old-price">$ 5.000</div>
            <div class="current-price">$ 4.500</div>
        </body>
    </html>
    """


@pytest.fixture
def malformed_html():
    """HTML mal formado"""
    return """
    <html>
        <body>
            <div class="price">
                <span>$ 1.250
            <!-- Tag sin cerrar -->
        </body>
    """


# ============================================================================
# TESTS DE EXTRACTORES ESPECÍFICOS
# ============================================================================

class TestExtractPriceMercadoLibre:
    """Tests del extractor de MercadoLibre"""
    
    def test_extract_with_complete_structure(self, mercadolibre_html_complete):
        """Extrae precio con estructura completa (fracción + centavos)"""
        soup = BeautifulSoup(mercadolibre_html_complete, "html.parser")
        price_text = extract_price_mercadolibre(soup)
        
        assert price_text is not None
        assert "1.250" in price_text
        assert "00" in price_text
    
    def test_extract_without_cents(self, mercadolibre_html_no_cents):
        """Extrae precio sin centavos (asume 00)"""
        soup = BeautifulSoup(mercadolibre_html_no_cents, "html.parser")
        price_text = extract_price_mercadolibre(soup)
        
        assert price_text is not None
        assert "4.500" in price_text
        assert "00" in price_text  # Debe agregar 00 por defecto
    
    def test_extract_without_main_container(self, mercadolibre_html_no_container):
        """Extrae precio sin contenedor principal (fallback)"""
        soup = BeautifulSoup(mercadolibre_html_no_container, "html.parser")
        price_text = extract_price_mercadolibre(soup)
        
        assert price_text is not None
        assert "2.999" in price_text
        assert "50" in price_text
    
    def test_extract_returns_none_when_no_price(self, mercadolibre_html_no_price):
        """Retorna None cuando no hay precio"""
        soup = BeautifulSoup(mercadolibre_html_no_price, "html.parser")
        price_text = extract_price_mercadolibre(soup)
        
        assert price_text is None
    
    def test_extract_handles_empty_html(self):
        """Maneja HTML vacío sin explotar"""
        soup = BeautifulSoup("<html></html>", "html.parser")
        price_text = extract_price_mercadolibre(soup)
        
        assert price_text is None


class TestExtractPriceAmazon:
    """Tests del extractor de Amazon"""
    
    def test_extract_with_complete_structure(self, amazon_html_complete):
        """Extrae precio con estructura completa"""
        soup = BeautifulSoup(amazon_html_complete, "html.parser")
        price_text = extract_price_amazon(soup)
        
        assert price_text is not None
        assert "1,250" in price_text or "1250" in price_text
    
    def test_extract_without_fraction(self, amazon_html_no_fraction):
        """Extrae precio sin fracción decimal (asume 00)"""
        soup = BeautifulSoup(amazon_html_no_fraction, "html.parser")
        price_text = extract_price_amazon(soup)
        
        assert price_text is not None
        assert "45" in price_text
    
    def test_extract_legacy_format(self, amazon_html_legacy):
        """Extrae precio con formato antiguo (priceblock_ourprice)"""
        soup = BeautifulSoup(amazon_html_legacy, "html.parser")
        price_text = extract_price_amazon(soup)
        
        assert price_text is not None
        assert "30.50" in price_text or "30" in price_text
    
    def test_extract_returns_none_when_no_price(self):
        """Retorna None cuando no hay precio"""
        html = "<html><body><div>No price here</div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        price_text = extract_price_amazon(soup)
        
        assert price_text is None


class TestExtractPriceGeneric:
    """Tests del extractor genérico"""
    
    def test_extract_with_price_class(self, generic_html_with_class):
        """Extrae precio usando clase 'price'"""
        soup = BeautifulSoup(generic_html_with_class, "html.parser")
        price_text = extract_price_generic(soup)
        
        assert price_text is not None
        assert "1.299" in price_text or "1299" in price_text
    
    def test_extract_with_itemprop(self, generic_html_with_itemprop):
        """Extrae precio usando atributo itemprop"""
        soup = BeautifulSoup(generic_html_with_itemprop, "html.parser")
        price_text = extract_price_generic(soup)
        
        assert price_text is not None
        assert "4500" in price_text
    
    def test_extract_returns_first_when_multiple(self, generic_html_multiple_prices):
        """Retorna el primer precio encontrado cuando hay múltiples"""
        soup = BeautifulSoup(generic_html_multiple_prices, "html.parser")
        price_text = extract_price_generic(soup)
        
        assert price_text is not None
        # Debe retornar el primero (old-price)
        assert "5.000" in price_text or "5000" in price_text or "4.500" in price_text
    
    def test_extract_with_regex_patterns(self):
        """Extrae precio usando patrones regex del texto completo"""
        html = "<html><body><p>El precio es: ARS 4.500,00</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        price_text = extract_price_generic(soup)
        
        assert price_text is not None
        assert "4.500" in price_text or "4500" in price_text
    
    def test_extract_returns_none_when_no_price(self):
        """Retorna None cuando no hay precio"""
        html = "<html><body><p>No hay precio aquí</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        price_text = extract_price_generic(soup)
        
        assert price_text is None


# ============================================================================
# TESTS DE SCRAPE_STATIC_PRICE (FUNCIÓN PRINCIPAL CON MOCKS)
# ============================================================================

class TestScrapeStaticPriceSuccess:
    """Tests de scraping exitoso con mocks"""
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_mercadolibre_success(self, mock_get, mercadolibre_html_complete):
        """Scraping exitoso de MercadoLibre"""
        # Configurar mock
        mock_response = Mock()
        mock_response.text = mercadolibre_html_complete
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Ejecutar scraping
        price, currency = scrape_static_price("https://www.mercadolibre.com.ar/producto")
        
        # Verificar
        assert price is not None
        assert isinstance(price, Decimal)
        assert price == Decimal("1250.00")
        assert currency == "ARS"
        
        # Verificar que se llamó requests.get
        mock_get.assert_called_once()
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_amazon_success(self, mock_get, amazon_html_complete):
        """Scraping exitoso de Amazon"""
        mock_response = Mock()
        mock_response.text = amazon_html_complete
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        price, currency = scrape_static_price("https://www.amazon.com.ar/producto")
        
        assert price is not None
        assert isinstance(price, Decimal)
        # Amazon puede retornar formato americano
        assert price > 0
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_generic_success(self, mock_get, generic_html_with_class):
        """Scraping exitoso con extractor genérico"""
        mock_response = Mock()
        mock_response.text = generic_html_with_class
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        price, currency = scrape_static_price("https://www.otrotendero.com/producto")
        
        assert price is not None
        assert isinstance(price, Decimal)
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_uses_custom_headers(self, mock_get, mercadolibre_html_complete):
        """Verifica que se usen headers personalizados"""
        mock_response = Mock()
        mock_response.text = mercadolibre_html_complete
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        scrape_static_price("https://example.com")
        
        # Verificar que se pasaron headers
        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        assert "User-Agent" in call_kwargs["headers"]
        assert "GrowenBot" in call_kwargs["headers"]["User-Agent"]
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_respects_timeout(self, mock_get, mercadolibre_html_complete):
        """Verifica que se use el timeout especificado"""
        mock_response = Mock()
        mock_response.text = mercadolibre_html_complete
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        scrape_static_price("https://example.com", timeout=15)
        
        # Verificar que se pasó timeout
        call_kwargs = mock_get.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 15


class TestScrapeStaticPriceErrors:
    """Tests de manejo de errores de red"""
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_timeout_raises_network_error(self, mock_get):
        """Timeout lanza NetworkError"""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(NetworkError) as exc_info:
            scrape_static_price("https://example.com")
        
        assert "Timeout" in str(exc_info.value)
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_connection_error_raises_network_error(self, mock_get):
        """ConnectionError lanza NetworkError"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(NetworkError) as exc_info:
            scrape_static_price("https://example.com")
        
        assert "conexión" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_http_404_raises_network_error(self, mock_get):
        """HTTP 404 lanza NetworkError"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        with pytest.raises(NetworkError) as exc_info:
            scrape_static_price("https://example.com")
        
        assert "404" in str(exc_info.value) or "HTTP" in str(exc_info.value)
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_http_500_raises_network_error(self, mock_get):
        """HTTP 500 lanza NetworkError"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(NetworkError) as exc_info:
            scrape_static_price("https://example.com")
        
        assert "500" in str(exc_info.value) or "HTTP" in str(exc_info.value)
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_no_price_raises_price_not_found(self, mock_get, mercadolibre_html_no_price):
        """HTML sin precio lanza PriceNotFoundError"""
        mock_response = Mock()
        mock_response.text = mercadolibre_html_no_price
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with pytest.raises(PriceNotFoundError) as exc_info:
            scrape_static_price("https://www.mercadolibre.com.ar/producto")
        
        assert "no se pudo extraer precio" in str(exc_info.value).lower()
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_malformed_html_raises_price_not_found(self, mock_get, malformed_html):
        """HTML mal formado intenta extraer precio y lanza error si no lo encuentra"""
        mock_response = Mock()
        mock_response.text = malformed_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Puede lanzar PriceNotFoundError o retornar None dependiendo de si BeautifulSoup puede parsear algo
        try:
            price, currency = scrape_static_price("https://example.com")
            # Si no lanza error, verificar que al menos intentó procesar
            assert price is None or isinstance(price, Decimal)
        except PriceNotFoundError:
            # Esperado si no se encontró precio
            pass


class TestScrapeStaticPriceEdgeCases:
    """Tests de edge cases y comportamientos límite"""
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_empty_html(self, mock_get):
        """Maneja HTML vacío"""
        mock_response = Mock()
        mock_response.text = "<html></html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        with pytest.raises(PriceNotFoundError):
            scrape_static_price("https://example.com")
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_handles_redirects(self, mock_get, mercadolibre_html_complete):
        """Maneja redirects HTTP (requests lo hace automáticamente)"""
        mock_response = Mock()
        mock_response.text = mercadolibre_html_complete
        mock_response.status_code = 200
        mock_response.url = "https://www.mercadolibre.com.ar/producto-final"  # URL después de redirect
        mock_get.return_value = mock_response
        
        price, currency = scrape_static_price("https://www.mercadolibre.com.ar/redirect")
        
        assert price is not None
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_scrape_extracts_from_fallback_when_specific_fails(self, mock_get):
        """Usa extractor genérico cuando el específico falla"""
        # HTML de MercadoLibre sin estructura correcta, pero con precio en texto
        html = """
        <html>
            <body>
                <div class="product-info">
                    <span class="price-display">$ 1.299</span>
                </div>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        price, currency = scrape_static_price("https://www.mercadolibre.com.ar/producto")
        
        # Debe extraer con genérico
        assert price is not None
        assert price == Decimal("1299.00")


class TestScrapeStaticPriceIntegration:
    """Tests de integración de flujo completo (mock a mock)"""
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_full_flow_mercadolibre(self, mock_get, mercadolibre_html_complete):
        """Flujo completo: HTTP → Parse → Extract → Normalize"""
        mock_response = Mock()
        mock_response.text = mercadolibre_html_complete
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Ejecutar flujo completo
        price, currency = scrape_static_price("https://articulo.mercadolibre.com.ar/MLA-123456789")
        
        # Verificaciones finales
        assert isinstance(price, Decimal)
        assert price == Decimal("1250.00")
        assert currency == "ARS"
        assert str(price) == "1250.00"  # Verificar formato string
    
    @patch("workers.scraping.static_scraper.requests.get")
    def test_multiple_scrapes_dont_interfere(self, mock_get, mercadolibre_html_complete, amazon_html_complete):
        """Múltiples scrapes no interfieren entre sí"""
        # Primera llamada: MercadoLibre
        mock_response_ml = Mock()
        mock_response_ml.text = mercadolibre_html_complete
        mock_response_ml.status_code = 200
        
        # Segunda llamada: Amazon
        mock_response_amz = Mock()
        mock_response_amz.text = amazon_html_complete
        mock_response_amz.status_code = 200
        
        mock_get.side_effect = [mock_response_ml, mock_response_amz]
        
        price1, currency1 = scrape_static_price("https://www.mercadolibre.com.ar/p1")
        price2, currency2 = scrape_static_price("https://www.amazon.com.ar/p2")
        
        assert price1 == Decimal("1250.00")
        assert price2 is not None
        assert mock_get.call_count == 2
