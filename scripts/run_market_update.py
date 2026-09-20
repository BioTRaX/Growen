#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: run_market_update.py
# NG-HEADER: Ubicación: scripts/run_market_update.py
# NG-HEADER: Descripción: Script standalone para actualización de precios de mercado vía cron
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Script standalone para ejecutar actualización de precios de mercado.

Este script puede ejecutarse directamente desde cron o tarea programada
del sistema operativo, sin necesidad de APScheduler.

Uso:
    python scripts/run_market_update.py [--max-products N] [--days-threshold N]

Ejemplos:
    # Actualizar según configuración por defecto
    python scripts/run_market_update.py
    
    # Actualizar hasta 100 productos
    python scripts/run_market_update.py --max-products 100
    
    # Productos no actualizados en los últimos 7 días
    python scripts/run_market_update.py --days-threshold 7
    
    # Combinación de parámetros
    python scripts/run_market_update.py --max-products 50 --days-threshold 3

Cron entry ejemplo (todos los días a las 2 AM):
    0 2 * * * cd /app && /usr/bin/python scripts/run_market_update.py >> /var/log/market_cron.log 2>&1

Cron entry ejemplo (cada 12 horas):
    0 */12 * * * cd /app && /usr/bin/python scripts/run_market_update.py >> /var/log/market_cron.log 2>&1
"""

import sys
import os
import asyncio
import argparse
from datetime import UTC, datetime

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.jobs.market_scheduler import run_manual_update, get_scheduler_status


def parse_args():
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Ejecuta actualización manual de precios de mercado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  %(prog)s
  %(prog)s --max-products 100
  %(prog)s --days-threshold 7
  %(prog)s --max-products 50 --days-threshold 3
  %(prog)s --status-only
        """
    )
    
    parser.add_argument(
        "--max-products",
        type=int,
        default=None,
        help="Máximo de productos a procesar (default: desde MARKET_MAX_PRODUCTS_PER_RUN)"
    )
    
    parser.add_argument(
        "--days-threshold",
        type=int,
        default=None,
        help="Días desde última actualización para considerar desactualizado (default: desde MARKET_UPDATE_FREQUENCY_DAYS)"
    )
    
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Solo mostrar estado del scheduler sin ejecutar actualización"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Modo verbose: mostrar más detalles"
    )
    
    return parser.parse_args()


async def main():
    """Función principal del script."""
    args = parse_args()
    
    print("=" * 70)
    print("ACTUALIZACIÓN AUTOMÁTICA DE PRECIOS DE MERCADO")
    print("=" * 70)
    print(f"Ejecutado: {datetime.now(UTC).isoformat()}")
    print()
    
    # Modo status only
    if args.status_only:
        print("Obteniendo estado del scheduler...")
        status = await get_scheduler_status()
        
        print("\n📊 ESTADO DEL SCHEDULER:")
        print(f"  • Habilitado: {status['scheduler_enabled']}")
        print(f"  • Cron: {status['cron_schedule']}")
        print(f"  • Frecuencia: cada {status['update_frequency_days']} días")
        print(f"  • Máx productos/ejecución: {status['max_products_per_run']}")
        print(f"  • Priorizar obligatorios: {status['prioritize_mandatory']}")
        
        print("\n📈 ESTADÍSTICAS:")
        stats = status['stats']
        print(f"  • Total productos con fuentes: {stats['total_products_with_sources']}")
        print(f"  • Nunca actualizados: {stats['never_updated']}")
        print(f"  • Desactualizados: {stats['outdated']}")
        print(f"  • Pendientes actualización: {stats['pending_update']}")
        print(f"  • Total fuentes: {stats['total_sources']}")
        
        print("\n" + "=" * 70)
        return 0
    
    # Modo actualización
    print("🚀 Iniciando actualización de precios...")
    
    if args.max_products:
        print(f"  • Límite de productos: {args.max_products}")
    if args.days_threshold:
        print(f"  • Umbral de días: {args.days_threshold}")
    
    print()
    
    try:
        result = await run_manual_update(
            max_products=args.max_products,
            days_threshold=args.days_threshold
        )
        
        if result["success"]:
            print("✅ Actualización completada exitosamente")
            print(f"  • Productos encolados: {result['products_enqueued']}")
            print(f"  • Duración: {result['duration_seconds']:.2f}s")
            print(f"  • Mensaje: {result['message']}")
            
            if args.verbose:
                print("\n📝 Detalles:")
                print(f"  • Las tareas se enviaron a la cola 'market' de Dramatiq")
                print(f"  • Los workers procesarán los productos en segundo plano")
                print(f"  • Revise los logs de workers para ver el progreso")
            
            print("\n" + "=" * 70)
            return 0
        else:
            print("❌ Error durante la actualización")
            print(f"  • Mensaje: {result.get('message', 'Error desconocido')}")
            print("\n" + "=" * 70)
            return 1
            
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        if args.verbose:
            import traceback
            print("\nTraceback:")
            traceback.print_exc()
        print("\n" + "=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
