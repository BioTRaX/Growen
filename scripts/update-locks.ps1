# NG-HEADER: Nombre de archivo: update-locks.ps1
# NG-HEADER: Ubicación: scripts/update-locks.ps1
# NG-HEADER: Descripción: Regenera locks con hashes para local, API, worker y MCP.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'No existe la venv. Ejecutar scripts\bootstrap-dev.ps1.'
}

function Invoke-Compile {
    param([string]$Output, [string[]]$Inputs)
    & $python -m piptools compile --generate-hashes --allow-unsafe --strip-extras `
        --resolver=backtracking --output-file=$Output @Inputs
    if ($LASTEXITCODE -ne 0) {
        throw "Falló la generación de $Output"
    }
}

function Add-LockMetadata {
    param(
        [string]$Path,
        [string]$Description,
        [switch]$AddLinuxMagic
    )
    $absolute = Join-Path $root $Path
    $content = Get-Content -LiteralPath $absolute -Raw
    $header = @"
# NG-HEADER: Nombre de archivo: $(Split-Path -Leaf $Path)
# NG-HEADER: Ubicación: $($Path.Replace('\', '/'))
# NG-HEADER: Descripción: $Description
# NG-HEADER: Lineamientos: Ver AGENTS.md
"@
    $content = $header + $content
    # pip-tools resuelve en Windows y puede perder el marcador transitivo de MCP.
    # Reponerlo evita que las imágenes Linux intenten instalar pywin32.
    $content = $content -replace '(?m)^pywin32==([0-9.]+) \\$', 'pywin32==$1 ; sys_platform == "win32" \'
    if ($AddLinuxMagic) {
        $linuxMagic = @"
python-magic==0.4.27 ; platform_system != "Windows" \
    --hash=sha256:c212960ad306f700aa0d01e5d7a325d20548ff97eb9920dcd29513174f0294d3
    # via -r requirements-base.txt
"@
        $content = $content.Replace('python-magic-bin==', $linuxMagic + 'python-magic-bin==')
    }
    $content = $content.TrimEnd() + [Environment]::NewLine
    Set-Content -LiteralPath $absolute -Value $content -Encoding utf8 -NoNewline
}

Push-Location $root
try {
    Invoke-Compile 'requirements-lock.txt' @('requirements.txt')
    Invoke-Compile 'requirements-api-lock.txt' @('requirements-base.txt', 'requirements-ml.txt', 'requirements-pdf.txt')
    Invoke-Compile 'requirements-worker-lock.txt' @('requirements-worker.txt')
    Invoke-Compile 'requirements-market-worker-lock.txt' @('requirements-market-worker.txt')
    Invoke-Compile 'mcp_servers/products_server/requirements-lock.txt' @('mcp_servers/products_server/requirements.txt')
    Invoke-Compile 'mcp_servers/web_search_server/requirements-lock.txt' @('mcp_servers/web_search_server/requirements.txt')
    Add-LockMetadata 'requirements-lock.txt' 'Lock reproducible multiplataforma con hashes para Python 3.14.' -AddLinuxMagic
    Add-LockMetadata 'requirements-api-lock.txt' 'Lock con hashes para la imagen API Python 3.14.' -AddLinuxMagic
    Add-LockMetadata 'requirements-worker-lock.txt' 'Lock con hashes para workers Python 3.14.' -AddLinuxMagic
    Add-LockMetadata 'requirements-market-worker-lock.txt' 'Lock con hashes para el worker Mercado Python 3.14.'
    Add-LockMetadata 'mcp_servers/products_server/requirements-lock.txt' 'Lock con hashes del MCP Products Python 3.14.'
    Add-LockMetadata 'mcp_servers/web_search_server/requirements-lock.txt' 'Lock con hashes del MCP Web Search Python 3.14.'
}
finally {
    Pop-Location
}

Write-Host 'Locks con hashes y NG-HEADER regenerados.' -ForegroundColor Green
