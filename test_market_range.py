#!/usr/bin/env python
"""
Script de prueba: Insertar precios de prueba en market_sources para verificar cálculo de rango
"""
import asyncio
from decimal import Decimal
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.models import MarketSource
from agent_core.config import settings
import os

# Usar DB_URL del entorno o del config
DB_URL = os.getenv("DB_URL") or settings.db_url

async def test_market_range():
    """Inserta precios de prueba en las fuentes del producto 45"""
    
    # Crear engine y session
    engine = create_async_engine(DB_URL, future=True)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as db:
        # 1. Obtener fuentes del producto 45
        query = select(MarketSource).where(MarketSource.product_id == 45)
        result = await db.execute(query)
        sources = result.scalars().all()
        
        if not sources:
            print("❌ No hay fuentes configuradas para el producto 45")
            return
        
        print(f"✅ Encontradas {len(sources)} fuentes para producto 45\n")
        
        # 2. Asignar precios de prueba
        test_prices = [1180.0, 1350.0, 1250.0, 1420.0]
        
        for i, source in enumerate(sources[:len(test_prices)]):
            price = Decimal(str(test_prices[i]))
            
            # Actualizar precio y timestamp
            await db.execute(
                update(MarketSource)
                .where(MarketSource.id == source.id)
                .values(
                    last_price=price,
                    last_checked_at=datetime.utcnow(),
                )
            )
            
            print(f"✅ Fuente '{source.source_name}' actualizada con precio $ {price}")
        
        await db.commit()
        
        print(f"\n✅ Precios de prueba insertados correctamente")
        print(f"📊 Rango esperado: $ {min(test_prices[:len(sources)])} - $ {max(test_prices[:len(sources)])}")
        print(f"\n🧪 Ahora prueba en la UI:")
        print(f"   1. Recarga el modal del producto 45")
        print(f"   2. Verifica que 'Rango de Mercado' muestre valores")

if __name__ == "__main__":
    asyncio.run(test_market_range())
