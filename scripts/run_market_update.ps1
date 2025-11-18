# NG-HEADER: Nombre de archivo: run_market_update.ps1
# NG-HEADER: Ubicación: scripts/run_market_update.ps1
# NG-HEADER: Descripción: Script PowerShell para actualización de precios de mercado en Windows
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#
.SYNOPSIS
    Ejecuta actualización manual de precios de mercado.

.DESCRIPTION
    Script de PowerShell para ejecutar actualización de precios de mercado
    desde Task Scheduler de Windows o línea de comandos.

.PARAMETER MaxProducts
    Máximo de productos a procesar (override de configuración)

.PARAMETER DaysThreshold
    Días desde última actualización para considerar desactualizado

.PARAMETER StatusOnly
    Solo muestra el estado sin ejecutar actualización

.PARAMETER Verbose
    Modo verbose con más detalles

.EXAMPLE
    .\scripts\run_market_update.ps1
    Ejecuta con configuración por defecto

.EXAMPLE
    .\scripts\run_market_update.ps1 -MaxProducts 100 -DaysThreshold 7
    Ejecuta con parámetros personalizados

.EXAMPLE
    .\scripts\run_market_update.ps1 -StatusOnly
    Solo muestra estado actual

.NOTES
    Requiere Python 3.11+ y dependencias instaladas
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [int]$MaxProducts,
    
    [Parameter(Mandatory=$false)]
    [int]$DaysThreshold,
    
    [Parameter(Mandatory=$false)]
    [switch]$StatusOnly,
    
    [Parameter(Mandatory=$false)]
    [switch]$Verbose
)

# Configuración
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$PythonScript = Join-Path $RootDir "scripts\run_market_update.py"
$LogFile = Join-Path $RootDir "logs\market_update.log"

# Crear directorio de logs si no existe
$LogDir = Join-Path $RootDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Función para escribir log con timestamp
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    
    # Escribir a consola
    switch ($Level) {
        "ERROR" { Write-Host $LogMessage -ForegroundColor Red }
        "WARN"  { Write-Host $LogMessage -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $LogMessage -ForegroundColor Green }
        default { Write-Host $LogMessage }
    }
    
    # Escribir a archivo
    Add-Content -Path $LogFile -Value $LogMessage
}

# Verificar Python
try {
    $PythonVersion = & python --version 2>&1
    Write-Log "Python detectado: $PythonVersion"
} catch {
    Write-Log "ERROR: Python no encontrado en PATH" -Level "ERROR"
    Write-Log "Instale Python 3.11+ y agregue al PATH" -Level "ERROR"
    exit 1
}

# Verificar script Python
if (-not (Test-Path $PythonScript)) {
    Write-Log "ERROR: Script no encontrado: $PythonScript" -Level "ERROR"
    exit 1
}

# Construir argumentos para el script Python
$PythonArgs = @()

if ($MaxProducts) {
    $PythonArgs += "--max-products", $MaxProducts
}

if ($DaysThreshold) {
    $PythonArgs += "--days-threshold", $DaysThreshold
}

if ($StatusOnly) {
    $PythonArgs += "--status-only"
}

if ($Verbose) {
    $PythonArgs += "--verbose"
}

# Ejecutar script Python
Write-Log "Iniciando actualización de precios de mercado..."
Write-Log "Directorio: $RootDir"

try {
    # Cambiar al directorio raíz
    Push-Location $RootDir
    
    # Ejecutar script
    $Output = & python $PythonScript $PythonArgs 2>&1
    $ExitCode = $LASTEXITCODE
    
    # Mostrar output
    $Output | ForEach-Object {
        Write-Host $_
        Add-Content -Path $LogFile -Value $_
    }
    
    # Verificar resultado
    if ($ExitCode -eq 0) {
        Write-Log "Actualización completada exitosamente" -Level "SUCCESS"
    } else {
        Write-Log "Actualización falló con código $ExitCode" -Level "ERROR"
    }
    
    Pop-Location
    exit $ExitCode
    
} catch {
    Write-Log "ERROR: $_" -Level "ERROR"
    Write-Log $_.Exception.Message -Level "ERROR"
    Pop-Location
    exit 1
}
