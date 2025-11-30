# NG-HEADER: Nombre de archivo: start_api_noquickedit.ps1
# NG-HEADER: Ubicación: scripts/start_api_noquickedit.ps1
# NG-HEADER: Descripción: Inicia la API deshabilitando QuickEdit Mode para evitar pausas accidentales
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#
.SYNOPSIS
    Inicia la API de Growen deshabilitando el modo QuickEdit de Windows.

.DESCRIPTION
    El modo QuickEdit de la consola de Windows puede causar que el servidor se pause
    si el usuario hace clic accidentalmente en la ventana de la terminal.
    
    Este script deshabilita QuickEdit antes de iniciar uvicorn, evitando este problema.

.EXAMPLE
    .\scripts\start_api_noquickedit.ps1
    
.EXAMPLE
    .\scripts\start_api_noquickedit.ps1 -Port 8080 -NoReload

.PARAMETER Port
    Puerto donde iniciar la API (default: 8000)

.PARAMETER NoReload
    Deshabilita hot-reload (útil para producción local)

.PARAMETER Host
    Host donde escuchar (default: 127.0.0.1, usar 0.0.0.0 para LAN)
#>

param(
    [int]$Port = 8000,
    [string]$Host = "127.0.0.1",
    [switch]$NoReload
)

# Función para deshabilitar QuickEdit Mode
function Disable-QuickEditMode {
    <#
    .SYNOPSIS
        Deshabilita QuickEdit Mode en la consola actual usando la API de Windows.
    #>
    
    $signature = @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern IntPtr GetStdHandle(int nStdHandle);

[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);

[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
'@

    try {
        $WinAPI = Add-Type -MemberDefinition $signature -Name WinAPI -Namespace QuickEdit -PassThru -ErrorAction SilentlyContinue
        
        $STD_INPUT_HANDLE = -10
        $ENABLE_QUICK_EDIT_MODE = 0x0040
        $ENABLE_EXTENDED_FLAGS = 0x0080
        
        $handle = $WinAPI::GetStdHandle($STD_INPUT_HANDLE)
        $mode = 0
        
        if ($WinAPI::GetConsoleMode($handle, [ref]$mode)) {
            # Deshabilitar QuickEdit y habilitar Extended Flags
            $newMode = ($mode -band (-bnot $ENABLE_QUICK_EDIT_MODE)) -bor $ENABLE_EXTENDED_FLAGS
            
            if ($WinAPI::SetConsoleMode($handle, $newMode)) {
                Write-Host "[OK] QuickEdit Mode deshabilitado - la terminal no se pausara por clicks accidentales" -ForegroundColor Green
                return $true
            }
        }
        
        Write-Host "[WARN] No se pudo deshabilitar QuickEdit Mode (esto puede no ser un problema)" -ForegroundColor Yellow
        return $false
    }
    catch {
        Write-Host "[WARN] Error al deshabilitar QuickEdit: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

# Cambiar al directorio raíz del proyecto
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

Write-Host ""
Write-Host "=== Growen API Startup (QuickEdit Disabled) ===" -ForegroundColor Cyan
Write-Host ""

# Deshabilitar QuickEdit
Disable-QuickEditMode

Write-Host ""

# Verificar virtual environment
$venvPath = Join-Path $rootDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "[INFO] Activando virtual environment..." -ForegroundColor Blue
    & $venvPath
} else {
    Write-Host "[WARN] Virtual environment no encontrado en .venv" -ForegroundColor Yellow
    Write-Host "       Usando Python del sistema..." -ForegroundColor Yellow
}

# Construir comando uvicorn
$uvicornArgs = @(
    "-m", "uvicorn",
    "services.api:app",
    "--host", $Host,
    "--port", $Port,
    "--log-level", "info"
)

if (-not $NoReload) {
    $uvicornArgs += "--reload"
    $uvicornArgs += "--reload-dir"
    $uvicornArgs += "services"
    $uvicornArgs += "--reload-dir"
    $uvicornArgs += "db"
    $uvicornArgs += "--reload-dir"
    $uvicornArgs += "workers"
    $uvicornArgs += "--reload-dir"
    $uvicornArgs += "ai"
}

Write-Host ""
Write-Host "[INFO] Iniciando API en http://${Host}:${Port}" -ForegroundColor Blue
Write-Host "[INFO] Swagger UI: http://${Host}:${Port}/docs" -ForegroundColor Blue
Write-Host "[INFO] Presiona Ctrl+C para detener" -ForegroundColor Blue
Write-Host ""

# Ejecutar uvicorn
try {
    python @uvicornArgs
}
catch {
    Write-Host "[ERROR] Error al iniciar la API: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}


