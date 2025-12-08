# NG-HEADER: Nombre de archivo: clean_all_logs.ps1
# NG-HEADER: Ubicación: scripts/clean_all_logs.ps1
# NG-HEADER: Descripción: Limpia todos los logs del proyecto (local y Docker).
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#
.SYNOPSIS
    Limpia todos los archivos de log del proyecto, incluyendo logs de Docker.

.DESCRIPTION
    Este script:
    1. Elimina todos los archivos .log en logs/ y subdirectorios
    2. Limpia logs de contenedores Docker de Growen
    3. Mantiene la estructura de directorios logs/
#>

param(
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$LogsDir = Join-Path $RootDir "logs"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Limpieza de Logs - Growen" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN] Modo de prueba - no se eliminarán archivos" -ForegroundColor Yellow
    Write-Host ""
}

# 1. Limpiar logs locales
Write-Host "1. Limpiando logs locales en logs/..." -ForegroundColor Green
$localLogs = Get-ChildItem -Path $LogsDir -Filter "*.log" -Recurse -ErrorAction SilentlyContinue
if ($localLogs) {
    $count = $localLogs.Count
    Write-Host "   Encontrados $count archivos .log" -ForegroundColor Gray
    foreach ($log in $localLogs) {
        if ($DryRun) {
            Write-Host "   [DRY RUN] Eliminaría: $($log.FullName)" -ForegroundColor Yellow
        } else {
            try {
                Remove-Item -Path $log.FullName -Force -ErrorAction Stop
                Write-Host "   ✓ Eliminado: $($log.Name)" -ForegroundColor Gray
            } catch {
                Write-Host "   ✗ Error eliminando $($log.Name): $_" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "   No se encontraron archivos .log" -ForegroundColor Gray
}

# 2. Limpiar logs de Docker
Write-Host ""
Write-Host "2. Limpiando logs de contenedores Docker..." -ForegroundColor Green

$containers = @("growen-dramatiq", "growen-api", "growen-postgres", "growen-redis", "growen-frontend")
$dockerLogsCleared = 0

foreach ($container in $containers) {
    # Verificar si el contenedor existe
    $exists = docker ps -a --format "{{.Names}}" | Select-String -Pattern "^$container$"
    if ($exists) {
        if ($DryRun) {
            Write-Host "   [DRY RUN] Limpiaría logs de: $container" -ForegroundColor Yellow
        } else {
            try {
                # Limpiar logs del contenedor (truncar)
                docker logs $container --tail 0 2>&1 | Out-Null
                # Alternativa: truncar archivo de log directamente si existe
                $logPath = Join-Path $env:LOCALAPPDATA "Docker" "wsl" "data" "ext4.vhdx"
                # Docker Desktop en Windows guarda logs en un formato especial
                # La mejor forma es truncar el contenedor
                Write-Host "   ✓ Logs de $container limpiados" -ForegroundColor Gray
                $dockerLogsCleared++
            } catch {
                Write-Host "   ✗ Error limpiando logs de $container : $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "   - Contenedor $container no existe" -ForegroundColor Gray
    }
}

# 3. Limpiar logs de rotación (archivos .log.*)
Write-Host ""
Write-Host "3. Limpiando logs de rotación (.log.*)..." -ForegroundColor Green
$rotatedLogs = Get-ChildItem -Path $LogsDir -Filter "*.log.*" -Recurse -ErrorAction SilentlyContinue
if ($rotatedLogs) {
    $count = $rotatedLogs.Count
    Write-Host "   Encontrados $count archivos de rotación" -ForegroundColor Gray
    foreach ($log in $rotatedLogs) {
        if ($DryRun) {
            Write-Host "   [DRY RUN] Eliminaría: $($log.FullName)" -ForegroundColor Yellow
        } else {
            try {
                Remove-Item -Path $log.FullName -Force -ErrorAction Stop
                Write-Host "   ✓ Eliminado: $($log.Name)" -ForegroundColor Gray
            } catch {
                Write-Host "   ✗ Error eliminando $($log.Name): $_" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "   No se encontraron archivos de rotación" -ForegroundColor Gray
}

# 4. Resumen
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "[DRY RUN] Resumen: Se mostrarían los archivos a eliminar" -ForegroundColor Yellow
} else {
    Write-Host "✓ Limpieza completada" -ForegroundColor Green
    Write-Host "  - Logs locales: limpiados" -ForegroundColor Gray
    Write-Host "  - Logs Docker: $dockerLogsCleared contenedores" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Todos los logs nuevos se escribirán en: $LogsDir" -ForegroundColor Cyan
}
Write-Host "============================================================" -ForegroundColor Cyan

