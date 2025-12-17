# NG-HEADER: Nombre de archivo: run_test.ps1
# NG-HEADER: Ubicación: scripts/run_test.ps1
# NG-HEADER: Descripción: Ejecuta tests de pytest con encoding UTF-8 configurado
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#
.SYNOPSIS
    Ejecuta tests de pytest con encoding UTF-8 configurado.

.DESCRIPTION
    Configura la consola para UTF-8 y ejecuta pytest con los argumentos proporcionados.
    Útil para evitar errores de encoding con caracteres Unicode en los tests.

.PARAMETER TestPath
    Ruta al test o archivo de test a ejecutar.
    Ejemplos:
    - tests/performance/test_market_scraping_perf.py::test_scraping_parallel_10_products
    - tests/performance/test_market_scraping_perf.py
    - tests/performance/

.PARAMETER Args
    Argumentos adicionales para pasar a pytest (ej: -v, -s, --tb=short)

.EXAMPLE
    .\scripts\run_test.ps1 -TestPath "tests/performance/test_market_scraping_perf.py::test_scraping_parallel_10_products" -Args "-v -s"

.EXAMPLE
    .\scripts\run_test.ps1 -TestPath "tests/performance/" -Args "-v -m performance"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$TestPath,
    
    [Parameter(Mandatory=$false)]
    [string[]]$Args = @("-v")
)

# Cambiar al directorio raíz del proyecto
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

# Configurar encoding UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host ""
Write-Host "=== Ejecutando Test con UTF-8 ===" -ForegroundColor Cyan
Write-Host "Test: $TestPath" -ForegroundColor Blue
Write-Host "Args: $($Args -join ' ')" -ForegroundColor Blue
Write-Host ""

# Verificar virtual environment
$venvPath = Join-Path $rootDir ".venv\Scripts\python.exe"
if (Test-Path $venvPath) {
    $pythonExe = $venvPath
} else {
    Write-Host "[WARN] Virtual environment no encontrado, usando Python del sistema" -ForegroundColor Yellow
    $pythonExe = "python"
}

# Construir comando pytest
$pytestArgs = @("-m", "pytest", $TestPath) + $Args

# Ejecutar pytest
try {
    & $pythonExe $pytestArgs
    exit $LASTEXITCODE
}
catch {
    Write-Host "[ERROR] Error al ejecutar pytest: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

