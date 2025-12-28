# NG-HEADER: Nombre de archivo: mcp_admin.py
# NG-HEADER: Ubicación: services/routers/mcp_admin.py
# NG-HEADER: Descripción: Endpoints de administración para servidores MCP (Model Context Protocol)
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Endpoints de administración para monitoreo y control de servidores MCP."""
from __future__ import annotations

import asyncio
import subprocess
import logging
from typing import List, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth import require_roles
from agent_core.detect_mcp_url import is_running_in_docker, get_mcp_products_url, get_mcp_web_search_url

logger = logging.getLogger("growen.mcp_admin")

router = APIRouter(prefix="/admin/mcp", tags=["admin", "mcp"])

# Configuración de servidores MCP conocidos
MCP_SERVERS = [
    {
        "name": "mcp_products",
        "label": "MCP Products (Catálogo)",
        "container_name": "growen-mcp-products",
        "port": 8100,
        "health_url": "http://localhost:8100/health",
    },
    {
        "name": "mcp_web_search",
        "label": "MCP Web Search",
        "container_name": "growen-mcp-web-search",
        "port": 8102,
        "health_url": "http://localhost:8102/health",
    },
]


class MCPServerStatus(BaseModel):
    name: str
    label: str
    url: str
    resolved_url: str | None = None  # URL que realmente se usa (auto-detectada)
    port: int
    status: str  # running, stopped, error
    healthy: bool
    lastCheck: str | None = None
    error: str | None = None


class MCPHealthResponse(BaseModel):
    servers: List[MCPServerStatus]
    context: str  # "docker" or "local"
    detected_urls: Dict[str, str]  # URLs auto-detectadas por servicio


async def _check_docker_container(container_name: str) -> tuple[bool, str | None]:
    """Verifica si un contenedor Docker está corriendo."""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            is_running = result.stdout.strip().lower() == "true"
            return is_running, None
        return False, "Container not found"
    except subprocess.TimeoutExpired:
        return False, "Docker timeout"
    except FileNotFoundError:
        return False, "Docker not installed"
    except Exception as e:
        return False, str(e)


async def _check_health_endpoint(url: str) -> tuple[bool, str | None]:
    """Verifica si el endpoint de health responde."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return True, None
            return False, f"HTTP {resp.status_code}"
    except httpx.ConnectError:
        return False, "Connection refused"
    except httpx.TimeoutException:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


@router.get(
    "/health",
    response_model=MCPHealthResponse,
    dependencies=[Depends(require_roles("admin"))],
)
async def mcp_health():
    """Obtiene el estado de salud de todos los servidores MCP."""
    from datetime import datetime
    
    # Detectar contexto (Docker vs Local)
    in_docker = is_running_in_docker()
    context = "docker" if in_docker else "local"
    
    # Obtener URLs auto-detectadas
    detected_urls = {
        "mcp_products": get_mcp_products_url(),
        "mcp_web_search": get_mcp_web_search_url(),
    }
    
    servers: List[MCPServerStatus] = []
    
    for server_config in MCP_SERVERS:
        # Verificar si el contenedor Docker está corriendo
        container_running, docker_error = await _check_docker_container(
            server_config["container_name"]
        )
        
        # Si está corriendo, verificar health endpoint
        healthy = False
        health_error = None
        
        if container_running:
            healthy, health_error = await _check_health_endpoint(
                server_config["health_url"]
            )
        
        # Determinar estado final
        if container_running:
            status = "running"
        elif docker_error:
            status = "error"
        else:
            status = "stopped"
        
        error_msg = health_error or docker_error if not healthy else None
        
        # Obtener la URL resuelta para este servidor
        resolved_url = detected_urls.get(server_config["name"])
        
        servers.append(
            MCPServerStatus(
                name=server_config["name"],
                label=server_config["label"],
                url=server_config["health_url"],
                resolved_url=resolved_url,
                port=server_config["port"],
                status=status,
                healthy=healthy,
                lastCheck=datetime.utcnow().isoformat(),
                error=error_msg,
            )
        )
    
    return MCPHealthResponse(
        servers=servers,
        context=context,
        detected_urls=detected_urls,
    )


@router.post(
    "/{name}/start",
    dependencies=[Depends(require_roles("admin"))],
)
async def start_mcp_server(name: str) -> Dict[str, Any]:
    """Inicia un contenedor MCP específico usando docker compose."""
    # Validar que el servidor existe
    server_config = next((s for s in MCP_SERVERS if s["name"] == name), None)
    if not server_config:
        raise HTTPException(status_code=404, detail=f"Servidor MCP '{name}' no encontrado")
    
    try:
        logger.info(f"Iniciando contenedor MCP: {name}")
        result = await asyncio.to_thread(
            subprocess.run,
            ["docker", "compose", "up", "-d", name],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=None,  # Usar directorio actual (raíz del proyecto)
        )
        
        if result.returncode == 0:
            logger.info(f"Contenedor {name} iniciado correctamente")
            return {"ok": True, "message": f"Contenedor {name} iniciado"}
        else:
            error_msg = result.stderr or result.stdout or "Error desconocido"
            logger.error(f"Error iniciando {name}: {error_msg}")
            return {"ok": False, "message": error_msg[:200]}
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout al iniciar contenedor")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Docker no está instalado o no está en PATH")
    except Exception as e:
        logger.exception(f"Error inesperado iniciando {name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{name}/stop",
    dependencies=[Depends(require_roles("admin"))],
)
async def stop_mcp_server(name: str) -> Dict[str, Any]:
    """Detiene un contenedor MCP específico."""
    # Validar que el servidor existe
    server_config = next((s for s in MCP_SERVERS if s["name"] == name), None)
    if not server_config:
        raise HTTPException(status_code=404, detail=f"Servidor MCP '{name}' no encontrado")
    
    container_name = server_config["container_name"]
    
    try:
        logger.info(f"Deteniendo contenedor MCP: {container_name}")
        result = await asyncio.to_thread(
            subprocess.run,
            ["docker", "stop", container_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            logger.info(f"Contenedor {container_name} detenido")
            return {"ok": True, "message": f"Contenedor {name} detenido"}
        else:
            error_msg = result.stderr or "Error desconocido"
            logger.warning(f"Error deteniendo {container_name}: {error_msg}")
            return {"ok": False, "message": error_msg[:200]}
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout al detener contenedor")
    except Exception as e:
        logger.exception(f"Error inesperado deteniendo {container_name}")
        raise HTTPException(status_code=500, detail=str(e))
