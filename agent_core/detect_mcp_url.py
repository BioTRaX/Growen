#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: detect_mcp_url.py
# NG-HEADER: Ubicación: agent_core/detect_mcp_url.py
# NG-HEADER: Descripción: Detecta automáticamente la URL correcta del MCP Web Search
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""
Detecta automáticamente si estamos en Docker o en el host y retorna
la URL correcta para conectarse al servicio MCP Web Search.

Uso:
    from agent_core.detect_mcp_url import get_mcp_web_search_url
    
    mcp_url = get_mcp_web_search_url()
"""
import os
import socket


def is_running_in_docker() -> bool:
    """
    Detecta si el código está corriendo dentro de un contenedor Docker.
    
    Returns:
        True si está en Docker, False si está en el host
    """
    # Método 1: Verificar archivo .dockerenv
    if os.path.exists('/.dockerenv'):
        return True
    
    # Método 2: Verificar cgroup (más confiable)
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            return 'docker' in content or 'kubepods' in content
    except (FileNotFoundError, PermissionError):
        pass
    
    # Método 3: Verificar hostname (contenedores suelen tener IDs como hostname)
    try:
        hostname = socket.gethostname()
        # Si el hostname es exactamente 12 caracteres hexadecimales, probablemente es Docker
        if len(hostname) == 12 and all(c in '0123456789abcdef' for c in hostname):
            return True
    except Exception:
        pass
    
    return False


def get_mcp_web_search_url() -> str:
    """
    Obtiene la URL correcta del servicio MCP Web Search dependiendo del contexto.
    
    Returns:
        URL del servicio MCP Web Search:
        - Si está en Docker: http://mcp_web_search:8002/invoke_tool (red interna)
        - Si está en host: http://localhost:8102/invoke_tool (puerto mapeado)
    """
    # Primero verificar si hay una URL explícita en variables de entorno
    env_url = os.getenv("MCP_WEB_SEARCH_URL")
    if env_url:
        return env_url
    
    # Si no, detectar automáticamente
    if is_running_in_docker():
        # Dentro de Docker: usar nombre del servicio y puerto interno
        return "http://mcp_web_search:8002/invoke_tool"
    else:
        # En el host: usar localhost y puerto mapeado
        return "http://localhost:8102/invoke_tool"


# Para uso como script standalone
if __name__ == "__main__":
    url = get_mcp_web_search_url()
    in_docker = is_running_in_docker()
    
    print(f"Contexto: {'Docker' if in_docker else 'Host local'}")
    print(f"URL MCP Web Search: {url}")
