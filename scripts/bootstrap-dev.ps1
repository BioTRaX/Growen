# NG-HEADER: Nombre de archivo: bootstrap-dev.ps1
# NG-HEADER: Ubicación: scripts/bootstrap-dev.ps1
# NG-HEADER: Descripción: Crea y valida el entorno Python 3.14.6+ para desarrollo local.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [switch]$RecreateVenv
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venv = Join-Path $root '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
$requirements = Join-Path $root 'requirements.txt'
$requirementsLock = Join-Path $root 'requirements-lock.txt'
$envFile = Join-Path $root '.env'
$envExample = Join-Path $root '.env.example'

function New-HexSecret {
    $bytes = [byte[]]::new(32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

function Ensure-LocalSecret {
    param([Parameter(Mandatory)][string]$Name)
    $content = Get-Content -LiteralPath $envFile -Raw
    $assignmentPattern = "(?m)^$([regex]::Escape($Name))=(.*)$"
    $blankPattern = "(?m)^$([regex]::Escape($Name))=\s*$"
    if ($content -match $blankPattern) {
        $content = [regex]::Replace($content, $blankPattern, "$Name=$(New-HexSecret)")
        Set-Content -LiteralPath $envFile -Value $content -Encoding utf8
        Write-Host "Se generó $Name en .env sin mostrar su valor." -ForegroundColor DarkGreen
    }
    elseif ($content -notmatch $assignmentPattern) {
        Add-Content -LiteralPath $envFile -Value "`n$Name=$(New-HexSecret)" -Encoding utf8
        Write-Host "Se agregó $Name a .env sin mostrar su valor." -ForegroundColor DarkGreen
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "El comando '$FilePath $($ArgumentList -join ' ')' falló con código $LASTEXITCODE."
    }
}

$basePython = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $previousErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $candidate = & py.exe -3.14 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            $basePython = ($candidate | Select-Object -First 1).Trim()
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }
}
if (-not $basePython) {
    $perUserPython = Join-Path $env:LocalAppData 'Programs\Python\Python314\python.exe'
    if (Test-Path -LiteralPath $perUserPython) {
        $basePython = $perUserPython
    }
}
if (-not $basePython) {
    throw 'Python 3.14.6 no está instalado.'
}
& $basePython -c "import sys; raise SystemExit(0 if (3, 14, 6) <= sys.version_info[:3] < (3, 15, 0) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw 'Se requiere Python 3.14.6 o una revisión posterior de la serie 3.14.'
}

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
}
Ensure-LocalSecret -Name 'INTERNAL_SERVICE_TOKEN'
Ensure-LocalSecret -Name 'MCP_PRODUCTS_SECRET_KEY'
Ensure-LocalSecret -Name 'MCP_WEB_SEARCH_SECRET_KEY'

if (Test-Path -LiteralPath $venv) {
    $venvWorks = $false
    if (Test-Path -LiteralPath $python) {
        try {
            $ErrorActionPreference = 'Continue'
            & $python -c "import sys; raise SystemExit(0 if (3, 14, 6) <= sys.version_info[:3] < (3, 15, 0) else 1)" 2>$null
            $venvWorks = $LASTEXITCODE -eq 0
        }
        catch {
            $venvWorks = $false
        }
        finally {
            $ErrorActionPreference = 'Stop'
        }
    }

    if (-not $venvWorks) {
        if (-not $RecreateVenv) {
            throw 'La venv existe pero no usa Python 3.14.6+ o está rota. Repetir con -RecreateVenv.'
        }
        Remove-Item -LiteralPath $venv -Recurse -Force
    }
    elseif ($RecreateVenv) {
        Remove-Item -LiteralPath $venv -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    Invoke-Checked -FilePath $basePython -ArgumentList @('-m', 'venv', $venv)
}

Invoke-Checked -FilePath $python -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel')
if (Test-Path -LiteralPath $requirementsLock) {
    Invoke-Checked -FilePath $python -ArgumentList @('-m', 'pip', 'install', '--require-hashes', '-r', $requirementsLock)
}
else {
    Invoke-Checked -FilePath $python -ArgumentList @('-m', 'pip', 'install', '-r', $requirements)
}
Invoke-Checked -FilePath $python -ArgumentList @(
    '-c',
    'import fastapi, httpx, mcp, openai, pytest, redis, sqlalchemy'
)
Invoke-Checked -FilePath $python -ArgumentList @('-m', 'pytest', '--version')

Write-Host "Entorno listo: $python" -ForegroundColor Green
