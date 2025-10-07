#!/usr/bin/env pwsh
# NG-HEADER: Nombre de archivo: cleanup-docker-images.ps1
# NG-HEADER: Ubicación: scripts/
# NG-HEADER: Descripción: Limpieza interactiva de imágenes Docker no utilizadas (dangling y sin contenedores asociados)
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#!
.SYNOPSIS
  Limpia imágenes Docker huérfanas o no usadas de forma interactiva y segura.

.DESCRIPTION
  Identifica:
    - Imágenes dangling (<none>:<none>)
    - Imágenes que no están referenciadas por ningún contenedor (en ejecución o detenido)

  Muestra un resumen y solicita confirmación:
    - Confirmación global (por defecto)
    - Confirmación por imagen con -PerImageConfirm
    - Solo listar con -DryRun

.NOTES
  El espacio liberado es estimado (capas compartidas pueden reducir el valor real).
  No usa 'docker image prune -a' para evitar borrar imágenes no mostradas inicialmente.

.PARAMETER PerImageConfirm
  Solicita confirmación para cada imagen individual luego de la confirmación global.

.PARAMETER DryRun
  Muestra lo que se eliminaría sin realizar ningún cambio.

.EXAMPLE
  .\cleanup-docker-images.ps1 -DryRun

.EXAMPLE
  .\cleanup-docker-images.ps1

.EXAMPLE
  .\cleanup-docker-images.ps1 -PerImageConfirm

#>
[CmdletBinding()]
param(
    [switch]$PerImageConfirm,
    [switch]$DryRun
)

# ==============================
# Funciones utilitarias de salida
# ==============================
function Write-Info($msg)  { Write-Host "[INFO ] $msg" -ForegroundColor Cyan }
function Write-Warn($msg)  { Write-Host "[WARN ] $msg" -ForegroundColor Yellow }
function Write-Err ($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Ok  ($msg)  { Write-Host "[OK   ] $msg" -ForegroundColor Green }

# ==============================
# Conversión de tamaños
# ==============================
function Convert-ToBytes {
    param([string]$size)
    # Docker devuelve tamaños como: "72.3MB", "1.07GB", "910kB"
    if (-not $size) { return 0 }
    if ($size -match '^(?<num>[\d\.]+)\s*(?<unit>[KMGTP]?B)$') {
        $n = [double]$matches.num
        switch ($matches.unit.ToUpper()) {
            "B"  { return [math]::Round($n,2) }
            "KB" { return [math]::Round($n * 1KB,2) }
            "MB" { return [math]::Round($n * 1MB,2) }
            "GB" { return [math]::Round($n * 1GB,2) }
            "TB" { return [math]::Round($n * 1TB,2) }
            "PB" { return [math]::Round($n * 1TB * 1024,2) } # muy raro
            default { return 0 }
        }
    }
    return 0
}

function Format-Size {
    param([double]$bytes)
    if ($bytes -ge 1PB) { return "{0:N2} PB" -f ($bytes / 1PB) }
    if ($bytes -ge 1TB) { return "{0:N2} TB" -f ($bytes / 1TB) }
    if ($bytes -ge 1GB) { return "{0:N2} GB" -f ($bytes / 1GB) }
    if ($bytes -ge 1MB) { return "{0:N2} MB" -f ($bytes / 1MB) }
    if ($bytes -ge 1KB) { return "{0:N2} KB" -f ($bytes / 1KB) }
    return "$bytes B"
}

# ==============================
# 1. Verificación de Docker
# ==============================
Write-Info "Verificando disponibilidad del comando 'docker'..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "El comando 'docker' no está disponible en el PATH. Aborta."
    exit 1
}

Write-Info "Comprobando que el daemon de Docker responde..."
try {
    # Forzar encoding UTF8 para evitar caracteres corruptos en mensajes (á/é, etc.)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker no respondió correctamente (exit=$LASTEXITCODE). Inicie Docker Desktop e intente nuevamente."
        exit 1
    }
} catch {
    Write-Err "No se pudo comunicar con Docker. Asegúrate que Docker Desktop esté iniciado. Detalle: $($_.Exception.Message)"
    exit 1
}

# ==============================
# 2. Imágenes dangling
# ==============================
Write-Info "Obteniendo imágenes dangling..."
$danglingRaw = docker images -f "dangling=true" --format "{{.ID}}|{{.Repository}}|{{.Tag}}|{{.Size}}" 2>$null

# ==============================
# 3. Imágenes no usadas por contenedores
# ==============================
Write-Info "Listando todas las imágenes y contenedores..."
$allImagesRaw = docker images --format "{{.ID}}|{{.Repository}}|{{.Tag}}|{{.Size}}"
$containerImageIDs = docker ps -a --format "{{.ImageID}}" | Sort-Object -Unique

$danglingIDs = @{}
$danglingList = @()
if ($danglingRaw) {
    foreach ($line in $danglingRaw) {
        $parts = $line.Split('|')
        if ($parts.Count -ne 4) { continue }
        $obj = [pscustomobject]@{
            Id        = $parts[0]
            Repository= $parts[1]
            Tag       = $parts[2]
            SizeRaw   = $parts[3]
            SizeBytes = Convert-ToBytes $parts[3]
            Category  = 'dangling'
        }
        $danglingList += $obj
        $danglingIDs[$obj.Id] = $true
    }
}

$unusedList = @()
foreach ($line in $allImagesRaw) {
    $parts = $line.Split('|')
    if ($parts.Count -ne 4) { continue }
    $id  = $parts[0]
    $rep = $parts[1]
    $tag = $parts[2]
    $size= $parts[3]

    if ($containerImageIDs -contains $id) { continue }
    if ($danglingIDs.ContainsKey($id)) { continue }

    $unusedList += [pscustomobject]@{
        Id        = $id
        Repository= $rep
        Tag       = $tag
        SizeRaw   = $size
        SizeBytes = Convert-ToBytes $size
        Category  = 'unused'
    }
}

# Consolidar
$allToRemove = @()
$allToRemove += $danglingList
$allToRemove += $unusedList

if (-not $allToRemove -or $allToRemove.Count -eq 0) {
    Write-Ok "No se encontraron imágenes huérfanas ni no utilizadas. Nada que hacer."
    exit 0
}

# Dedupe por ID
$allToRemove = $allToRemove | Group-Object -Property Id | ForEach-Object {
    if ($_.Group.Count -gt 1) {
        $d = $_.Group | Where-Object { $_.Category -eq 'dangling' }
        if ($d) { $d[0] } else { $_.Group[0] }
    } else { $_.Group[0] }
}

# ==============================
# 4. Presentar lista consolidada
# ==============================
Write-Host ""
Write-Info "Resumen de imágenes candidatas a eliminación:" 
$display = $allToRemove | Select-Object `
    @{n='ID';e={$_.Id.Substring(0,12)}},
    @{n='Repositorio';e={$_.Repository}},
    @{n='Tag';e={$_.Tag}},
    @{n='Categoría';e={$_.Category}},
    @{n='Tamaño';e={$_.SizeRaw}}

$display | Format-Table -AutoSize

$estimatedBytes = ($allToRemove | Measure-Object -Property SizeBytes -Sum).Sum
Write-Host ""
Write-Info ("Total imágenes: {0}" -f $allToRemove.Count)
Write-Info ("Espacio estimado potencial a liberar: {0}" -f (Format-Size $estimatedBytes))
Write-Warn "La estimación puede sobrestimar debido a capas compartidas."

if ($DryRun) {
    Write-Ok "Ejecutado en modo --DryRun. No se eliminaron imágenes."
    exit 0
}

# ==============================
# 5. Confirmación global
# ==============================
$confirmation = Read-Host "¿Desea eliminar TODAS estas imágenes? Escriba 'si' para confirmar (cualquier otra cosa cancela)"
if ($confirmation.ToLower() -ne 'si') {
    Write-Warn "Operación cancelada por el usuario. No se eliminaron imágenes."
    exit 0
}

# ==============================
# 6. Eliminación
# ==============================
$deleted   = @()
$failed    = @()

if ($PerImageConfirm) {
    Write-Info "Modo confirmación por imagen activado (-PerImageConfirm)."
}

foreach ($img in $allToRemove) {
    if ($PerImageConfirm) {
        $ans = Read-Host ("Eliminar imagen {0} ({1}:{2}) [{3}]? 'si' para confirmar" -f $img.Id.Substring(0,12), $img.Repository, $img.Tag, $img.Category)
        if ($ans.ToLower() -ne 'si') {
            Write-Warn ("Saltando {0}" -f $img.Id.Substring(0,12))
            continue
        }
    }

    Write-Info ("Eliminando {0} ({1}:{2}) ..." -f $img.Id.Substring(0,12), $img.Repository, $img.Tag)

    try {
        $output = docker image rm $img.Id 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok ("Eliminada {0}" -f $img.Id.Substring(0,12))
            $deleted += $img
        } else {
            Write-Err ("Fallo al eliminar {0}: {1}" -f $img.Id.Substring(0,12), ($output -join ' '))
            $failed += $img
        }
    } catch {
        Write-Err ("Excepción al eliminar {0}: {1}" -f $img.Id.Substring(0,12), $_.Exception.Message)
        $failed += $img
    }
}

# ==============================
# 7. Resumen final
# ==============================
Write-Host ""
Write-Host "========== RESUMEN ==========" -ForegroundColor Cyan
Write-Host ("Intentadas: {0}" -f $allToRemove.Count)
Write-Host ("Eliminadas correctamente: {0}" -f $deleted.Count) -ForegroundColor Green
Write-Host ("Fallidas / no eliminadas: {0}" -f $failed.Count) -ForegroundColor Yellow

if ($deleted.Count -gt 0) {
    $freedEstimate = ($deleted | Measure-Object -Property SizeBytes -Sum).Sum
    Write-Host ("Espacio estimado liberado: {0}" -f (Format-Size $freedEstimate)) -ForegroundColor Green
    Write-Warn  "El valor real puede ser menor por capas compartidas."
}

if ($failed.Count -gt 0) {
    Write-Warn "Algunas imágenes no se pudieron eliminar (dependencias, uso o permisos)."
}

Write-Ok "Proceso de limpieza finalizado."
exit 0
