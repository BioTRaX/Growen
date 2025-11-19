#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_scraping_manual.py
# NG-HEADER: Ubicación: scripts/test_scraping_manual.py
# NG-HEADER: Descripción: Script para probar scraping estático manualmente
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Script de prueba manual para scraping de precios estáticos.

Uso:
    python scripts/test_scraping_manual.py <URL>
    
Ejemplo:
    python scripts/test_scraping_manual.py https://www.mercadolibre.com.ar/...
"""

import sys
import logging
from workers.scraping import scrape_static_price
from workers.scraping.static_scraper import NetworkError, PriceNotFoundError

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_scraping_manual.py <URL>")
        print("\nEjemplos de URLs:")
        print("  - MercadoLibre: https://www.mercadolibre.com.ar/...")
        print("  - Amazon: https://www.amazon.com.ar/...")
        print("  - Cualquier sitio con precio visible en HTML")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print(f"\n{'='*60}")
    print(f"Scraping de: {url}")
    print(f"{'='*60}\n")
    
    try:
        price = scrape_static_price(url, timeout=30)
        
        if price:
            print(f"\n✅ ÉXITO: Precio encontrado")
            print(f"   Precio: ${price}")
            print(f"   Formato: {type(price).__name__}")
        else:
            print("\n⚠️  ADVERTENCIA: No se encontró precio")
            
    except NetworkError as e:
        print(f"\n❌ ERROR DE RED: {e}")
        print("   - Verifica tu conexión a internet")
        print("   - La URL puede estar bloqueada o no ser válida")
        
    except PriceNotFoundError as e:
        print(f"\n❌ PRECIO NO ENCONTRADO: {e}")
        print("   - El sitio puede usar JavaScript (requiere Playwright)")
        print("   - El selector puede haber cambiado")
        print("   - La página puede no tener precio visible")
        
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
