# NG-HEADER: Nombre de archivo: sync-siyuan-widget.ps1
# NG-HEADER: Ubicación: scripts/sync-siyuan-widget.ps1
# NG-HEADER: Descripción: Compara y sincroniza de forma acotada un widget local con el workspace operativo de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9_-]+$')]
    [string]$WidgetName,
    [string]$RepositoryRoot,
    [string]$WorkspaceRoot,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$runtimeExtensions = @('.html', '.css', '.js', '.json')

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = if ($env:SIYUAN_WORKSPACE_DIR) {
        $env:SIYUAN_WORKSPACE_DIR
    } else {
        Join-Path $RepositoryRoot '..\growen-siyuan\workspace'
    }
}

function Resolve-Directory {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label no existe o no es un directorio: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Assert-ChildPath {
    param([string]$Candidate, [string]$Root, [string]$Label)
    $fullCandidate = [IO.Path]::GetFullPath($Candidate)
    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $fullCandidate.StartsWith($fullRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label queda fuera de la raíz autorizada: $fullCandidate"
    }
    return $fullCandidate
}

function Get-Sha256 {
    param([string]$Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '')
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Get-Drift {
    param([IO.FileInfo[]]$SourceFiles, [string]$TargetDirectory)
    $drift = @()
    foreach ($sourceFile in $SourceFiles) {
        $targetFile = Join-Path $TargetDirectory $sourceFile.Name
        if (-not (Test-Path -LiteralPath $targetFile -PathType Leaf)) {
            $drift += "$($sourceFile.Name): ausente"
            continue
        }
        $sourceHash = Get-Sha256 -Path $sourceFile.FullName
        $targetHash = Get-Sha256 -Path $targetFile
        if ($sourceHash -ne $targetHash) {
            $drift += "$($sourceFile.Name): hash diferente"
        }
    }
    return $drift
}

$repository = Resolve-Directory -Path $RepositoryRoot -Label 'RepositoryRoot'
$workspace = Resolve-Directory -Path $WorkspaceRoot -Label 'WorkspaceRoot'
$sourceDirectory = Assert-ChildPath `
    -Candidate (Join-Path $repository "siyuan-widgets\$WidgetName") `
    -Root $repository `
    -Label 'La fuente del widget'
$sourceDirectory = Resolve-Directory -Path $sourceDirectory -Label 'La fuente del widget'
$widgetsRoot = Assert-ChildPath `
    -Candidate (Join-Path $workspace 'data\widgets') `
    -Root $workspace `
    -Label 'La raíz operativa de widgets'
$targetDirectory = Assert-ChildPath `
    -Candidate (Join-Path $widgetsRoot $WidgetName) `
    -Root $workspace `
    -Label 'El destino operativo del widget'

$sourceFiles = @(
    Get-ChildItem -LiteralPath $sourceDirectory -File |
        Where-Object { $_.Extension.ToLowerInvariant() -in $runtimeExtensions }
)
if (-not $sourceFiles) {
    throw "No hay archivos runtime para sincronizar en $sourceDirectory"
}

$drift = if (Test-Path -LiteralPath $targetDirectory -PathType Container) {
    @(Get-Drift -SourceFiles $sourceFiles -TargetDirectory $targetDirectory)
} else {
    @('directorio operativo ausente')
}

if ($drift -and -not $Apply) {
    Write-Output "DESINCRONIZADO: $WidgetName"
    $drift | ForEach-Object { Write-Output "- $_" }
    exit 1
}

if ($drift) {
    New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
    foreach ($sourceFile in $sourceFiles) {
        Copy-Item -LiteralPath $sourceFile.FullName -Destination (Join-Path $targetDirectory $sourceFile.Name) -Force
    }
    $remainingDrift = @(Get-Drift -SourceFiles $sourceFiles -TargetDirectory $targetDirectory)
    if ($remainingDrift) {
        throw "La sincronización no convergió: $($remainingDrift -join '; ')"
    }
}

Write-Output "SINCRONIZADO: $WidgetName ($($sourceFiles.Count) archivos runtime)"
