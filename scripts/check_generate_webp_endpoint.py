#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_generate_webp_endpoint.py
# NG-HEADER: Ubicación: scripts/check_generate_webp_endpoint.py
# NG-HEADER: Descripción: Verifica si el endpoint generate-webp está registrado
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Verifica si el endpoint generate-webp está disponible en el backend."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    from services.routers.images import router
    from fastapi import FastAPI
    
    print("=== Verificando endpoint generate-webp ===\n")
    
    # Buscar el endpoint
    found = False
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            path = getattr(route, 'path', '')
            methods = getattr(route, 'methods', set())
            
            if 'generate-webp' in str(path):
                print(f"✅ Endpoint encontrado:")
                print(f"   Métodos: {methods}")
                print(f"   Path: {path}")
                print(f"   Router prefix: {router.prefix}")
                print(f"   Ruta completa: {router.prefix}{path}")
                found = True
    
    if not found:
        print("❌ Endpoint generate-webp NO encontrado en el router")
        print("\nRutas disponibles en images.router:")
        for route in router.routes:
            if hasattr(route, 'path'):
                path = getattr(route, 'path', '')
                methods = getattr(route, 'methods', set()) if hasattr(route, 'methods') else set()
                print(f"   {methods} {path}")
    
    # Verificar que el router esté importado correctamente
    print(f"\n✅ Router importado correctamente")
    print(f"   Prefix: {router.prefix}")
    print(f"   Tags: {router.tags}")
    print(f"   Total rutas: {len(router.routes)}")
    
    # Crear app de prueba y verificar rutas
    print("\n=== Verificando rutas en aplicación FastAPI ===")
    app = FastAPI()
    app.include_router(router)
    
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            path = getattr(route, 'path', '')
            methods = getattr(route, 'methods', set())
            if 'generate-webp' in str(path):
                routes.append((methods, path))
    
    if routes:
        print("✅ Endpoint encontrado en aplicación FastAPI:")
        for methods, path in routes:
            print(f"   {methods} {path}")
    else:
        print("❌ Endpoint NO encontrado en aplicación FastAPI")
    
except Exception as e:
    print(f"❌ Error al verificar endpoint: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


