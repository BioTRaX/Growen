#!/usr/bin/env pwsh
# NG-HEADER: Nombre de archivo: docker-compose-audit.ps1
# NG-HEADER: Ubicación: scripts/
# NG-HEADER: Descripción: Auditoría y actualización opcional de imágenes públicas en docker-compose.yml
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#!
.SYNOPSIS
  Audita servicios en docker-compose.yml, detecta imágenes públicas desactualizadas y opcionalmente sugiere actualización.

.DESCRIPTION
  Pasos:
    1. Verifica existencia de docker-compose.yml en el directorio actual.
    2. Analiza servicios: distingue servicios con build (locales) vs imágenes públicas (sin build).
    3. Para cada imagen pública (repo:tag) consulta Docker Hub para obtener tags.
       - Ignora tags: latest, edge, rc, beta, alpha, dev.
       - Considera sólo tags semánticos (n.n, n.n.n, n.n.n-nombre) extrayendo la porción numérica.
       - Escoge la versión estable más alta (orden semántico).
    4. Muestra tabla comparativa (Servicio, Imagen actual, Última estable, Estado).
    5. Ofrece crear backup y archivo actualizado (requiere confirmación 'si').
    6. Construye y levanta stack: docker compose up --build -d
    7. Muestra docker compose ps como verificación final.

.PARAMETER SkipBuild
  Si se especifica, no ejecuta docker compose up --build -d (solo auditoría / opcional actualización de archivo).

.PARAMETER OnlyReport
  Realiza auditoría, muestra tabla y NO modifica archivo ni levanta servicios.

.NOTES
  Requiere conectividad a Docker Hub API anónima. Limitado por rate-limiting público.
  No persigue autenticación privada.

.EXAMPLE
  .\\docker-compose-audit.ps1

.EXAMPLE
  .\\docker-compose-audit.ps1 -OnlyReport

.EXAMPLE
  .\\docker-compose-audit.ps1 -SkipBuild
#>
[CmdletBinding()]
param(
  [switch]$SkipBuild,
  [switch]$OnlyReport
)

function Write-Info($m){ Write-Host "[INFO ] $m" -ForegroundColor Cyan }
function Write-Warn($m){ Write-Host "[WARN ] $m" -ForegroundColor Yellow }
function Write-Err ($m){ Write-Host "[ERROR] $m" -ForegroundColor Red }
function Write-Ok  ($m){ Write-Host "[OK   ] $m" -ForegroundColor Green }

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

# 1. Verificar archivo
$composePath = Join-Path (Get-Location) 'docker-compose.yml'
if (-not (Test-Path $composePath)) {
  Write-Err "No se encontró docker-compose.yml en el directorio actual ($(Get-Location)). Aborta."; exit 1
}
Write-Info "Usando archivo: $composePath"

# 1b. Verificar docker compose disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Write-Err "Docker CLI no disponible"; exit 1 }
try { docker info --format '{{.ServerVersion}}' *> $null } catch { Write-Err "Daemon Docker no responde"; exit 1 }
if ($LASTEXITCODE -ne 0){ Write-Err "Docker no respondió (exit=$LASTEXITCODE)"; exit 1 }

# 2. Analizar YAML (sin dependencias externas): parse lineal
Write-Info "Analizando servicios..."
$lines = Get-Content $composePath -Raw -Encoding UTF8 -ErrorAction Stop | Select-String -Pattern '.*' -AllMatches | ForEach-Object { $_.Line }

# Implementación simple: detectar bloques service (nivel 2 bajo 'services:')
$services = @()
$current = $null
# Nota: Se asume indent de 2 espacios para nombres de servicio; variable auxiliar eliminada.
for ($i=0; $i -lt $lines.Count; $i++) {
  $line = $lines[$i]
  if ($line -match '^[ ]{2}([a-zA-Z0-9_-]+):\s*$' -and $line -notmatch 'services:') {
    # nuevo servicio
    $name = $matches[1]
    $current = [ordered]@{ name=$name; image=$null; build=$false; lineIndex=$i }
    $services += $current
    continue
  }
  if (-not $current) { continue }
  # fin de bloque si línea en blanco o nueva sección sin indent
  if ($line -match '^[^ ]' -and $line -notmatch '^services:') { $current = $null; continue }
  # detectar build
  if ($line -match '^[ ]{4}build:') { $current.build = $true }
  if ($line -match '^[ ]{4}image:\s*([^#]+)$') {
    $img = ($matches[1]).Trim()
    $current.image = $img
  }
}

# Filtrar servicios públicos (sin build y con image)
$publicServices = $services | Where-Object { -not $_.build -and $_.image }
if (-not $publicServices) { Write-Warn "No hay servicios con imágenes públicas a auditar." }

# 3. Consultar Docker Hub para cada imagen
function Get-SemVerObject {
  param([string]$tag)
  # Extraer secuencia numérica principal (ej 3.19.1, 3.20, 1.2.3-r0 -> 3.19.1 / 3.20 / 1.2.3)
  if ($tag -notmatch '^[0-9]+(\.[0-9]+){0,2}') { return $null }
  $core = $matches[0]
  $parts = $core.Split('.')
  while ($parts.Count -lt 3) { $parts += '0' } # normalizar a X.Y.Z
  return [pscustomobject]@{ tag=$tag; major=[int]$parts[0]; minor=[int]$parts[1]; patch=[int]$parts[2]; core=$core }
}

function Test-UnwantedTag { param([string]$tag)
  $l = $tag.ToLower()
  return ($l -in @('latest','edge')) -or ($l -match 'rc') -or ($l -match 'beta') -or ($l -match 'alpha') -or ($l -match 'dev')
}

function Get-LatestStableTag {
  param([string]$repository)
  # repository esperado form: 'alpine'
  $url = "https://registry.hub.docker.com/v2/repositories/$repository/tags?page_size=100"
  try {
    $resp = Invoke-RestMethod -Uri $url -Method GET -ErrorAction Stop
  } catch {
  Write-Warn "Fallo al consultar tags para ${repository}: $($_.Exception.Message)"
    return $null
  }
  if (-not $resp.results) { return $null }
  $candidates = @()
  foreach ($r in $resp.results) {
    $name = $r.name
  if (Test-UnwantedTag $name) { continue }
    $sem = Get-SemVerObject -tag $name
    if ($sem) { $candidates += $sem }
  }
  if (-not $candidates) { return $null }
  $latest = $candidates | Sort-Object -Property major,minor,patch -Descending | Select-Object -First 1
  return $latest.tag
}

$results = @()
foreach ($svc in $publicServices) {
  $image = $svc.image
  # separar repo:tag
  $repo = $image
  $tag  = 'latest'
  if ($image -match ':') { $repo = $image.Split(':')[0]; $tag = $image.Split(':')[1] }
  Write-Info "Consultando tags para $repo (servicio $($svc.name))..."
  $latest = Get-LatestStableTag -repository $repo
  $state = 'actualizado'
  if ($latest -and $latest -ne $tag) { $state = 'desactualizado' }
  $results += [pscustomobject]@{ Servicio=$svc.name; ImagenActual=$image; UltimaEstable=$latest; Estado=$state }
}

if ($results) {
  Write-Host ''
  Write-Info 'Resultado auditoría:'
  $results | Format-Table -AutoSize
} else {
  Write-Info 'No hubo resultados de auditoría (sin imágenes públicas).'
}

if ($OnlyReport) {
  Write-Ok 'Modo OnlyReport: finaliza sin modificar archivos ni levantar stack.'
  exit 0
}

# 4. Actualización opcional
$toUpdate = $results | Where-Object { $_.Estado -eq 'desactualizado' -and $_.UltimaEstable }
if ($toUpdate) {
  Write-Warn "Se encontraron $($toUpdate.Count) imágenes desactualizadas.";
  $ans = Read-Host "¿Desea generar un docker-compose.yml actualizado? Escriba 'si' para confirmar"
  if ($ans.ToLower() -eq 'si') {
    $backupPath = "$composePath.bak"
    Copy-Item $composePath $backupPath -Force
    Write-Ok "Backup creado: $backupPath"
    $newContent = Get-Content $composePath -Raw -Encoding UTF8
    foreach ($row in $toUpdate) {
      $old = $row.ImagenActual
      $repo = $old.Split(':')[0]
  $new = "${repo}:$($row.UltimaEstable)"
      Write-Info "Reemplazando $old -> $new"
      $newContent = $newContent -replace [regex]::Escape($old), $new
    }
    Set-Content -Path $composePath -Value $newContent -Encoding UTF8
    Write-Ok "docker-compose.yml actualizado con nuevas versiones."
  } else {
    Write-Warn 'No se actualizó el archivo (usuario canceló).'
  }
} else {
  Write-Info 'No hay imágenes públicas desactualizadas.'
}

if ($SkipBuild) {
  Write-Warn 'SkipBuild activo: no se ejecutará docker compose up.'
  exit 0
}

# 5. Construir y levantar stack
Write-Info 'Ejecutando docker compose up --build -d'
try {
  docker compose up --build -d
  if ($LASTEXITCODE -ne 0) { Write-Err "docker compose up retornó código $LASTEXITCODE"; exit $LASTEXITCODE }
} catch {
  Write-Err "Fallo al levantar el stack: $($_.Exception.Message)"; exit 1
}

# 6. Verificación final
Write-Info 'Estado de contenedores:'
docker compose ps

Write-Ok 'Auditoría y (opcional) actualización finalizadas.'
exit 0
