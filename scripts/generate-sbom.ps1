# NG-HEADER: Nombre de archivo: generate-sbom.ps1
# NG-HEADER: Ubicación: scripts/generate-sbom.ps1
# NG-HEADER: Descripción: Genera un SBOM CycloneDX reproducible desde la venv validada.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$outputDir = Join-Path $root 'security'
$output = Join-Path $outputDir 'sbom.cdx.json'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'No existe la venv. Ejecutar scripts\bootstrap-dev.ps1.'
}
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
& $python -m cyclonedx_py environment $python `
    --pyproject (Join-Path $root 'pyproject.toml') `
    --output-reproducible `
    --output-format JSON `
    --output-file $output `
    --validate
if ($LASTEXITCODE -ne 0) {
    throw 'No se pudo generar el SBOM.'
}
Write-Host "SBOM generado: $output" -ForegroundColor Green
