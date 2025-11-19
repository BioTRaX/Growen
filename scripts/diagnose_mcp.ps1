# NG-HEADER: Nombre de archivo: diagnose_mcp.ps1
# NG-HEADER: Ubicación: scripts/diagnose_mcp.ps1
# NG-HEADER: Descripción: Script PowerShell para ejecutar diagnóstico MCP Web Search
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#
.SYNOPSIS
    Ejecuta diagnóstico de conectividad con MCP Web Search

.DESCRIPTION
    Este script ejecuta el diagnóstico de conectividad MCP Web Search tanto desde
    el host como desde dentro del contenedor backend para comparar resultados.

.PARAMETER Mode
    Modo de ejecución:
    - 'host': Ejecuta desde el host (requiere Python local)
    - 'docker': Ejecuta dentro del contenedor backend
    - 'both': Ejecuta en ambos (default)

.EXAMPLE
    .\scripts\diagnose_mcp.ps1
    Ejecuta el diagnóstico en ambos contextos (host y docker)

.EXAMPLE
    .\scripts\diagnose_mcp.ps1 -Mode docker
    Ejecuta solo dentro del contenedor Docker
#>

param(
    [ValidateSet('host', 'docker', 'both')]
    [string]$Mode = 'both'
)

$ErrorActionPreference = "Continue"

function Write-Header {
    param([string]$Message)
    Write-Host "`n$('=' * 70)" -ForegroundColor Cyan
    Write-Host $Message.PadLeft(($Message.Length + 70) / 2) -ForegroundColor Cyan
    Write-Host "$('=' * 70)`n" -ForegroundColor Cyan
}

function Test-DockerRunning {
    try {
        $null = docker ps 2>&1
        return $true
    } catch {
        return $false
    }
}

# Verificar que Docker esté corriendo
if ($Mode -in @('docker', 'both')) {
    if (-not (Test-DockerRunning)) {
        Write-Host "❌ Docker no está corriendo o no está accesible" -ForegroundColor Red
        Write-Host "Por favor inicia Docker Desktop y vuelve a intentar" -ForegroundColor Yellow
        exit 1
    }
}

# Test desde el HOST
if ($Mode -in @('host', 'both')) {
    Write-Header "DIAGNÓSTICO DESDE HOST"
    Write-Host "Ejecutando desde el sistema host..." -ForegroundColor Yellow
    Write-Host "Nota: La URL será http://localhost:8102 (puerto mapeado)`n" -ForegroundColor Gray
    
    # Configurar variables de entorno para host
    $env:MCP_WEB_SEARCH_HOST = "localhost"
    $env:MCP_WEB_SEARCH_PORT = "8102"
    
    python scripts/diagnose_mcp_connection.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n⚠️  El diagnóstico desde host encontró problemas" -ForegroundColor Yellow
    }
    
    # Limpiar variables
    Remove-Item Env:\MCP_WEB_SEARCH_HOST -ErrorAction SilentlyContinue
    Remove-Item Env:\MCP_WEB_SEARCH_PORT -ErrorAction SilentlyContinue
}

# Test desde DOCKER
if ($Mode -in @('docker', 'both')) {
    Write-Header "DIAGNÓSTICO DESDE CONTENEDOR BACKEND"
    
    # Verificar que el contenedor backend esté corriendo
    $backendContainer = docker ps --filter "name=growen-api" --format "{{.Names}}" 2>$null
    
    if (-not $backendContainer) {
        # Buscar cualquier contenedor que pueda ser la API
        $backendContainer = docker ps --filter "name=api" --format "{{.Names}}" | Select-Object -First 1
    }
    
    if (-not $backendContainer) {
        Write-Host "❌ No se encontró un contenedor backend corriendo" -ForegroundColor Red
        Write-Host "Buscando contenedores disponibles..." -ForegroundColor Yellow
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        
        Write-Host "`nPara iniciar el stack completo ejecuta:" -ForegroundColor Yellow
        Write-Host "  docker-compose up -d" -ForegroundColor Cyan
        exit 1
    }
    
    Write-Host "Ejecutando dentro del contenedor: $backendContainer" -ForegroundColor Yellow
    Write-Host "Nota: La URL será http://mcp_web_search:8002 (red interna Docker)`n" -ForegroundColor Gray
    
    # Ejecutar dentro del contenedor
    docker exec -it $backendContainer python scripts/diagnose_mcp_connection.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n⚠️  El diagnóstico desde Docker encontró problemas" -ForegroundColor Yellow
        Write-Host "`nVerificando estado del servicio MCP Web Search..." -ForegroundColor Yellow
        
        $mcpContainer = docker ps --filter "name=mcp_web_search" --format "{{.Names}}"
        if ($mcpContainer) {
            Write-Host "✓ Contenedor MCP Web Search está corriendo: $mcpContainer" -ForegroundColor Green
            Write-Host "`nÚltimas líneas de log:" -ForegroundColor Yellow
            docker logs $mcpContainer --tail 20
        } else {
            Write-Host "❌ Contenedor MCP Web Search NO está corriendo" -ForegroundColor Red
            Write-Host "`nPara iniciarlo ejecuta:" -ForegroundColor Yellow
            Write-Host "  docker-compose up -d mcp_web_search" -ForegroundColor Cyan
        }
    }
}

Write-Header "COMANDOS ÚTILES PARA DEBUG"
Write-Host "Ver todos los contenedores:" -ForegroundColor Yellow
Write-Host "  docker-compose ps" -ForegroundColor Cyan

Write-Host "`nVer logs del MCP Web Search:" -ForegroundColor Yellow
Write-Host "  docker logs growen-mcp-web-search --tail 50" -ForegroundColor Cyan

Write-Host "`nReiniciar el servicio MCP:" -ForegroundColor Yellow
Write-Host "  docker-compose restart mcp_web_search" -ForegroundColor Cyan

Write-Host "`nInspeccionar la red Docker:" -ForegroundColor Yellow
Write-Host "  docker network inspect growen_default" -ForegroundColor Cyan

Write-Host "`nProbar endpoint desde el host:" -ForegroundColor Yellow
Write-Host "  Invoke-WebRequest http://localhost:8102/health" -ForegroundColor Cyan

Write-Host ""
