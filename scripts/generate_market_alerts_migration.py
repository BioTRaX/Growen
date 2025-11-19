#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: generate_market_alerts_migration.py
# NG-HEADER: Ubicación: scripts/generate_market_alerts_migration.py
# NG-HEADER: Descripción: Genera migración de Alembic para tabla market_alerts
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Script para generar migración de Alembic para el sistema de alertas de mercado.

Uso:
    python scripts/generate_market_alerts_migration.py

El script ejecutará:
    alembic revision --autogenerate -m "Add MarketAlert table for price variation alerts"

Requisitos:
    - Base de datos corriendo
    - Variables de entorno configuradas (.env)
    - Alembic configurado correctamente

Después de ejecutar este script:
    alembic upgrade head
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("=" * 60)
    print("GENERACIÓN DE MIGRACIÓN: MarketAlert")
    print("=" * 60)
    print()
    
    # Cambiar al directorio raíz del proyecto
    root_dir = Path(__file__).resolve().parents[1]
    print(f"📁 Directorio raíz: {root_dir}")
    print()
    
    # Comando de Alembic
    cmd = [
        "alembic",
        "revision",
        "--autogenerate",
        "-m",
        "Add MarketAlert table for price variation alerts"
    ]
    
    print("🔧 Ejecutando comando:")
    print(f"   {' '.join(cmd)}")
    print()
    
    try:
        # Ejecutar comando
        result = subprocess.run(
            cmd,
            cwd=root_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Mostrar salida
        if result.stdout:
            print("📄 Salida estándar:")
            print(result.stdout)
        
        if result.stderr:
            print("⚠️ Salida de error:")
            print(result.stderr)
        
        if result.returncode == 0:
            print()
            print("✅ Migración generada exitosamente")
            print()
            print("📋 Próximos pasos:")
            print("   1. Revisar el archivo de migración generado en db/migrations/versions/")
            print("   2. Verificar que la migración incluya la tabla market_alerts")
            print("   3. Ejecutar: alembic upgrade head")
            print()
            print("💡 Para ver la migración sin aplicarla:")
            print("   alembic upgrade head --sql")
            print()
        else:
            print()
            print("❌ Error al generar migración")
            print(f"   Código de salida: {result.returncode}")
            print()
            print("🔍 Posibles causas:")
            print("   - Base de datos no está corriendo")
            print("   - Credenciales incorrectas en .env")
            print("   - Puerto ocupado o firewall bloqueando conexión")
            print()
            print("🛠️ Solución:")
            print("   1. Verificar que PostgreSQL esté corriendo:")
            print("      docker ps | grep postgres")
            print("   2. Verificar variables en .env:")
            print("      DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
            print("   3. Probar conexión manualmente:")
            print("      python scripts/db_port_probe.py")
            print()
            sys.exit(1)
            
    except FileNotFoundError:
        print()
        print("❌ Error: comando 'alembic' no encontrado")
        print()
        print("🛠️ Solución:")
        print("   pip install alembic")
        print()
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Error inesperado: {e}")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
