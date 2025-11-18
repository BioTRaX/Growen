#!/usr/bin/env python
"""Script de diagnóstico de conectividad a PostgreSQL."""

import os
import sys
from pathlib import Path

# Agregar directorio raíz al path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar .env
env_path = root_dir / ".env"
print(f"📁 Cargando .env desde: {env_path}")
print(f"   Existe: {env_path.exists()}")
print()

load_dotenv(env_path, override=True)

# Obtener DB_URL
db_url = os.getenv("DB_URL")
print(f"🔗 DB_URL configurada:")
print(f"   {db_url}")
print()

# Intentar conectar
print("🔌 Intentando conectar a PostgreSQL...")
try:
    engine = create_engine(db_url, echo=False)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        version = result.scalar()
        
        print("✅ Conexión exitosa!")
        print()
        print(f"📊 Versión de PostgreSQL:")
        print(f"   {version}")
        print()
        
        # Verificar si existe la tabla market_alerts
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'market_alerts'
            );
        """))
        table_exists = result.scalar()
        
        print("🗄️ Estado de la tabla market_alerts:")
        if table_exists:
            print("   ✅ La tabla YA EXISTE")
            
            # Contar registros
            result = conn.execute(text("SELECT COUNT(*) FROM market_alerts;"))
            count = result.scalar()
            print(f"   📊 Registros: {count}")
        else:
            print("   ⚠️ La tabla NO EXISTE (necesita migración)")
        
        print()
        print("🎯 Próximo paso:")
        if table_exists:
            print("   La tabla ya existe. Puedes ejecutar la suite de pruebas.")
        else:
            print("   Ejecutar: alembic revision --autogenerate -m 'Add MarketAlert table'")
            print("   Luego:    alembic upgrade head")
        
except Exception as e:
    print(f"❌ Error de conexión:")
    print(f"   {type(e).__name__}: {e}")
    print()
    print("🔍 Posibles causas:")
    print("   1. PostgreSQL no está corriendo")
    print("      Verificar: docker ps | grep postgres")
    print("   2. Puerto incorrecto en DB_URL")
    print("      Debe ser 5433 si Docker mapea así")
    print("   3. Contraseña con caracteres especiales")
    print("      '=' debe ser '%3D' en URL")
    print("   4. Base de datos no existe")
    print("      Verificar: docker exec growen-postgres psql -U growen -l")
    sys.exit(1)
