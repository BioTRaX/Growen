# NG-HEADER: Nombre de archivo: check-quality.ps1
# NG-HEADER: Ubicación: scripts/check-quality.ps1
# NG-HEADER: Descripción: Quality gate local y reproducible para entorno agéntico, MCP y Vue.
# NG-HEADER: Lineamientos: Ver AGENTS.md

[CmdletBinding()]
param(
    [switch]$AgentOnly,
    [switch]$SkillsOnly,
    [ValidatePattern('^[a-z0-9-]+$')]
    [string]$SkillName,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'

function Invoke-QualityCommand {
    param([string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory = $root)
    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "Quality gate falló: $FilePath $($ArgumentList -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

$skillFiles = Get-ChildItem -LiteralPath (Join-Path $root '.agents\skills') -Filter SKILL.md -Recurse -File
if (-not $skillFiles) {
    throw 'No se encontraron skills canónicas en .agents/skills.'
}
if ($SkillName) {
    $skillFiles = @($skillFiles | Where-Object { $_.Directory.Name -eq $SkillName })
    if (-not $skillFiles) {
        throw "No existe la skill canónica solicitada: $SkillName"
    }
}
foreach ($skill in $skillFiles) {
    $content = Get-Content -LiteralPath $skill.FullName -Raw -Encoding UTF8
    if (-not $content.StartsWith("---`n") -and -not $content.StartsWith("---`r`n")) {
        throw "Frontmatter inválido: $($skill.FullName)"
    }
    if ($content -notmatch '(?m)^name: [a-z0-9-]+\r?$' -or $content -notmatch '(?m)^description: .+\r?$') {
        throw "Metadata incompleta: $($skill.FullName)"
    }
    if ($content -match '(?m)^\s*git add \.\s*$' -or $content -match '(?m)^\s*python(?:\.exe)?\s') {
        throw "Comando prohibido en skill canónica: $($skill.FullName)"
    }

    $skillName = Split-Path -Leaf $skill.DirectoryName
    $legacyAdapter = Join-Path $root ".agent\skills\$skillName\SKILL.md"
    if (Test-Path -LiteralPath $legacyAdapter) {
        $adapterContent = Get-Content -LiteralPath $legacyAdapter -Raw -Encoding UTF8
        $canonicalReference = ".agents/skills/$skillName/SKILL.md"
        if ($adapterContent -notlike "*$canonicalReference*" -or ($adapterContent -split "`r?`n").Count -gt 12) {
            throw "El adaptador legacy $legacyAdapter diverge o duplica instrucciones canónicas."
        }
    }
}
Write-Host 'Skills canónicas verificadas.' -ForegroundColor Green

if ($SkillsOnly) {
    exit 0
}

$requiredDocs = @('README.md', 'Roadmap.md', 'docs\MCP.md', 'docs\DEVELOPMENT_WORKFLOW.md')
foreach ($relativePath in $requiredDocs) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $relativePath))) {
        throw "Falta documentación obligatoria: $relativePath"
    }
}

$consumerRoots = @('agent_core', 'ai', 'services')
$legacyConsumerReferences = Get-ChildItem -LiteralPath ($consumerRoots | ForEach-Object { Join-Path $root $_ }) `
    -Recurse -File |
    Where-Object { $_.Extension -eq '.py' } |
    Select-String -SimpleMatch '/invoke_tool'
if ($legacyConsumerReferences) {
    throw 'Hay consumidores nuevos que todavía dependen de /invoke_tool.'
}

$agentsContent = Get-Content -LiteralPath (Join-Path $root 'AGENTS.md') -Raw -Encoding UTF8
if ($agentsContent -match 'alembic/versions/' -or $agentsContent -notmatch 'db/migrations/versions/') {
    throw 'AGENTS.md contiene una ruta Alembic obsoleta.'
}

$workflowContent = Get-Content -LiteralPath (Join-Path $root '.github\workflows\quality-manual.yml') -Raw -Encoding UTF8
if ($workflowContent -notmatch '(?m)^\s*workflow_dispatch:\s*$' -or $workflowContent -match '(?m)^\s*(push|pull_request|schedule):\s*$') {
    throw 'El workflow de calidad debe ser exclusivamente manual.'
}
Write-Host 'Contratos, documentación y CI manual verificados.' -ForegroundColor Green

$lockFiles = @(
    'requirements-lock.txt',
    'requirements-api-lock.txt',
    'requirements-worker-lock.txt',
    'mcp_servers\products_server\requirements-lock.txt',
    'mcp_servers\web_search_server\requirements-lock.txt'
)
foreach ($lockFile in $lockFiles) {
    $lockPath = Join-Path $root $lockFile
    if (-not (Test-Path -LiteralPath $lockPath)) {
        throw "Falta lock de dependencias: $lockFile"
    }
    $lockContent = Get-Content -LiteralPath $lockPath -Raw
    if ($lockContent -notmatch '--hash=sha256:' -or $lockContent -notmatch 'NG-HEADER') {
        throw "Lock sin hashes o encabezado: $lockFile"
    }
}

$secretPatterns = @(
    '-----BEGIN [A-Z ]*PRIVATE KEY-----',
    'sk-(?:proj-)?[A-Za-z0-9_-]{20,}',
    'gh[pousr]_[A-Za-z0-9]{30,}'
)
$scanRoots = @('.env', '.env.example', 'agent_core', 'ai', 'mcp_servers', 'services', 'scripts', 'docs', 'tests')
$secretFiles = foreach ($scanRoot in $scanRoots) {
    $candidate = Join-Path $root $scanRoot
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { Get-Item -LiteralPath $candidate }
    elseif (Test-Path -LiteralPath $candidate -PathType Container) {
        Get-ChildItem -LiteralPath $candidate -Recurse -File |
            Where-Object { $_.FullName -notmatch '\\.venv|__pycache__|node_modules|\\logs\\' }
    }
}
foreach ($secretFile in $secretFiles) {
    $content = Get-Content -LiteralPath $secretFile.FullName -Raw -ErrorAction SilentlyContinue
    foreach ($pattern in $secretPatterns) {
        if ($content -match $pattern) {
            throw "Posible secreto detectado en $($secretFile.FullName)."
        }
    }
}

if ($AgentOnly) {
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) {
    throw 'No existe la venv. Ejecutar scripts\bootstrap-dev.ps1.'
}
Invoke-QualityCommand $python @('-c', 'import sys; raise SystemExit(0 if (3, 14, 6) <= sys.version_info[:3] < (3, 15, 0) else 1)')
Invoke-QualityCommand $python @('-m', 'ruff', 'check', 'agent_core/mcp_client.py', 'agent_core/tool_security.py', 'mcp_servers/security.py', 'mcp_servers/products_server', 'mcp_servers/web_search_server', 'services/auth.py', 'ai/providers/openai_provider.py')
Invoke-QualityCommand $python @('-m', 'bandit', '-q', '-r', 'agent_core/tool_security.py', 'mcp_servers/security.py', 'mcp_servers/web_search_server/tools.py', 'services/auth.py')
Invoke-QualityCommand $python @('-m', 'pip_audit', '--local', '--progress-spinner', 'off')
Invoke-QualityCommand 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $root 'scripts\generate-sbom.ps1'))
Invoke-QualityCommand $python @(
    '-m', 'pytest',
    'tests/test_ai_router.py',
    'tests/test_mcp_client.py',
    'tests/test_mcp_find_products.py',
    'tests/test_security_hardening.py',
    'tests/routers/test_chat_tool_call.py',
    'tests/routers/test_chat_http_product_tool.py',
    'mcp_servers/products_server/tests',
    'mcp_servers/web_search_server/tests',
    '-q', '--tb=short'
)

if (-not $SkipFrontend) {
    Invoke-QualityCommand 'npm.cmd' @('run', 'build') (Join-Path $root 'frontend')
    Invoke-QualityCommand 'npm.cmd' @('audit', '--audit-level=high') (Join-Path $root 'frontend')
    Invoke-QualityCommand 'npm.cmd' @('run', 'typecheck') (Join-Path $root 'frontend-vue')
    Invoke-QualityCommand 'npm.cmd' @('test') (Join-Path $root 'frontend-vue')
    Invoke-QualityCommand 'npm.cmd' @('run', 'test:e2e') (Join-Path $root 'frontend-vue')
    Invoke-QualityCommand 'npm.cmd' @('run', 'build') (Join-Path $root 'frontend-vue')
    Invoke-QualityCommand 'npm.cmd' @('audit', '--audit-level=high') (Join-Path $root 'frontend-vue')
}
Write-Host 'Quality gate completado.' -ForegroundColor Green
