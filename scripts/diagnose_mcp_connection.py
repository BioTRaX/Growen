#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: diagnose_mcp_connection.py
# NG-HEADER: Ubicación: scripts/diagnose_mcp_connection.py
# NG-HEADER: Descripción: Script de diagnóstico para verificar conectividad con MCP Web Search
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""
Script de diagnóstico para verificar conectividad con el servicio MCP Web Search.

Uso:
  # Desde el host (debe tener acceso a la red Docker)
  python scripts/diagnose_mcp_connection.py

  # Desde dentro del contenedor backend
  docker exec -it growen-api-1 python scripts/diagnose_mcp_connection.py
"""
import asyncio
import os
import socket
import sys
from typing import Optional

import httpx


# Colores para terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(msg: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(msg: str):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_error(msg: str):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def print_warning(msg: str):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def print_info(msg: str):
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")


async def test_dns_resolution(host: str) -> Optional[str]:
    """Prueba la resolución DNS del hostname."""
    print_header("Test 1: Resolución DNS")
    try:
        ip = socket.gethostbyname(host)
        print_success(f"Host '{host}' resuelve a IP: {ip}")
        return ip
    except socket.gaierror as e:
        print_error(f"No se pudo resolver '{host}': {e}")
        print_warning("Posibles causas:")
        print("  - El servicio no está en la misma red Docker")
        print("  - El nombre del servicio está mal escrito en docker-compose.yml")
        print("  - Docker DNS no está funcionando correctamente")
        return None


async def test_tcp_connection(host: str, port: int, timeout: float = 5.0) -> bool:
    """Prueba la conexión TCP al puerto."""
    print_header(f"Test 2: Conexión TCP a {host}:{port}")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        print_success(f"Conexión TCP exitosa a {host}:{port}")
        return True
    except asyncio.TimeoutError:
        print_error(f"Timeout al conectar a {host}:{port} (>{timeout}s)")
        print_warning("Posibles causas:")
        print("  - El servicio no está escuchando en ese puerto")
        print("  - Firewall bloqueando la conexión")
        print("  - El contenedor no está corriendo")
        return False
    except ConnectionRefusedError:
        print_error(f"Conexión rechazada a {host}:{port}")
        print_warning("Posibles causas:")
        print("  - El servicio no está corriendo")
        print("  - El puerto EXPOSE en Dockerfile es incorrecto")
        print("  - El comando CMD no inició el servidor correctamente")
        return False
    except Exception as e:
        print_error(f"Error inesperado: {type(e).__name__}: {e}")
        return False


async def test_http_health(base_url: str, timeout: float = 10.0) -> bool:
    """Prueba el endpoint /health del servicio."""
    print_header("Test 3: Endpoint HTTP /health")
    health_url = f"{base_url}/health"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print_info(f"Enviando GET request a: {health_url}")
            response = await client.get(health_url)
            
            print_info(f"Status code: {response.status_code}")
            print_info(f"Response body: {response.text[:200]}")
            
            if response.status_code == 200:
                print_success(f"Endpoint /health respondió correctamente")
                return True
            else:
                print_error(f"Endpoint /health respondió con código {response.status_code}")
                return False
    except httpx.ConnectTimeout:
        print_error(f"Timeout al conectar con {health_url}")
        print_warning("El servicio está escuchando pero no responde a tiempo")
        return False
    except httpx.ConnectError as e:
        print_error(f"Error de conexión: {e}")
        print_warning("El servicio no está accesible vía HTTP")
        return False
    except Exception as e:
        print_error(f"Error inesperado: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mcp_invoke_tool(base_url: str, timeout: float = 10.0) -> bool:
    """Prueba el endpoint /invoke_tool con una consulta de ejemplo."""
    print_header("Test 4: Endpoint /invoke_tool (búsqueda web)")
    invoke_url = f"{base_url}/invoke_tool"
    
    payload = {
        "tool_name": "web_search",
        "parameters": {
            "query": "test connectivity",
            "max_results": 1
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print_info(f"Enviando POST request a: {invoke_url}")
            print_info(f"Payload: {payload}")
            response = await client.post(invoke_url, json=payload)
            
            print_info(f"Status code: {response.status_code}")
            print_info(f"Response body: {response.text[:500]}")
            
            if response.status_code == 200:
                print_success("Endpoint /invoke_tool funciona correctamente")
                return True
            elif response.status_code == 404:
                print_error("Tool 'web_search' no encontrado")
                print_warning("El endpoint existe pero la tool no está registrada")
                return False
            else:
                print_error(f"Endpoint respondió con código {response.status_code}")
                return False
    except httpx.ConnectTimeout:
        print_error(f"Timeout al conectar con {invoke_url}")
        return False
    except httpx.ConnectError as e:
        print_error(f"Error de conexión: {e}")
        return False
    except Exception as e:
        print_error(f"Error inesperado: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_docker_environment():
    """Verifica si estamos corriendo dentro de Docker y muestra info del entorno."""
    print_header("Información del Entorno")
    
    # Verificar si estamos en Docker
    is_docker = os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')
    if is_docker:
        print_success("Ejecutando DENTRO de un contenedor Docker")
    else:
        print_warning("Ejecutando FUERA de Docker (host)")
        print_info("Si la conexión falla desde el host, intenta ejecutar dentro del contenedor:")
        print_info("  docker exec -it <container_name> python scripts/diagnose_mcp_connection.py")
    
    # Mostrar hostname
    hostname = socket.gethostname()
    print_info(f"Hostname: {hostname}")
    
    # Mostrar variables de entorno relevantes
    env_vars = [
        "MCP_WEB_SEARCH_URL",
        "AI_USE_WEB_SEARCH",
        "DOCKER_HOST"
    ]
    print_info("\nVariables de entorno relevantes:")
    for var in env_vars:
        value = os.getenv(var, "<no definida>")
        print(f"  {var}: {value}")


async def main():
    """Ejecuta todos los tests de diagnóstico."""
    print(f"{Colors.BOLD}Diagnóstico de Conectividad MCP Web Search{Colors.ENDC}")
    print(f"Python version: {sys.version}")
    
    await check_docker_environment()
    
    # Configuración (puede venir de variables de entorno)
    mcp_host = os.getenv("MCP_WEB_SEARCH_HOST", "mcp_web_search")
    mcp_port = int(os.getenv("MCP_WEB_SEARCH_PORT", "8002"))
    base_url = f"http://{mcp_host}:{mcp_port}"
    
    print_info(f"\nURL objetivo: {base_url}")
    
    # Ejecutar tests en orden
    results = {}
    
    # Test 1: DNS
    ip = await test_dns_resolution(mcp_host)
    results['dns'] = ip is not None
    
    if not results['dns']:
        print_header("DIAGNÓSTICO COMPLETO")
        print_error("El test de DNS falló. Los siguientes tests no se ejecutarán.")
        print_warning("\nSoluciones recomendadas:")
        print("1. Verificar que el servicio 'mcp_web_search' esté definido en docker-compose.yml")
        print("2. Verificar que los contenedores estén en la misma red Docker")
        print("3. Ejecutar: docker-compose ps  (para ver servicios activos)")
        print("4. Ejecutar: docker network inspect growen_default  (verificar red)")
        return
    
    # Test 2: TCP
    results['tcp'] = await test_tcp_connection(mcp_host, mcp_port)
    
    if not results['tcp']:
        print_header("DIAGNÓSTICO COMPLETO")
        print_error("El test de TCP falló. Los siguientes tests no se ejecutarán.")
        print_warning("\nSoluciones recomendadas:")
        print("1. Verificar que el contenedor mcp_web_search esté corriendo:")
        print("   docker ps --filter name=mcp_web_search")
        print("2. Verificar logs del servicio:")
        print("   docker logs growen-mcp-web-search --tail 50")
        print("3. Verificar el puerto expuesto en Dockerfile:")
        print("   EXPOSE 8002")
        print("4. Reiniciar el servicio:")
        print("   docker-compose restart mcp_web_search")
        return
    
    # Test 3: Health endpoint
    results['health'] = await test_http_health(base_url)
    
    # Test 4: Invoke tool
    results['invoke'] = await test_mcp_invoke_tool(base_url)
    
    # Resumen final
    print_header("RESUMEN DIAGNÓSTICO")
    print(f"DNS Resolution:       {'✓ PASS' if results['dns'] else '✗ FAIL'}")
    print(f"TCP Connection:       {'✓ PASS' if results['tcp'] else '✗ FAIL'}")
    print(f"HTTP Health Endpoint: {'✓ PASS' if results['health'] else '✗ FAIL'}")
    print(f"MCP Invoke Tool:      {'✓ PASS' if results['invoke'] else '✗ FAIL'}")
    
    if all(results.values()):
        print_success("\n🎉 Todos los tests pasaron! El servicio MCP Web Search está funcionando correctamente.")
    else:
        print_error("\n❌ Algunos tests fallaron. Revisa los detalles arriba para diagnosticar el problema.")
        print_warning("\nComandos útiles para debug:")
        print("  docker-compose ps")
        print("  docker logs growen-mcp-web-search")
        print("  docker exec -it growen-mcp-web-search curl http://localhost:8002/health")
        print("  docker network inspect growen_default")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDiagnóstico interrumpido por el usuario.")
        sys.exit(1)
