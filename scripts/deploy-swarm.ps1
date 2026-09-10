# NG-HEADER: Nombre de archivo: deploy-swarm.ps1
# NG-HEADER: Ubicación: scripts/deploy-swarm.ps1
# NG-HEADER: Descripción: Preflight y despliegue por fases del stack productivo Growen.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$StackName = "growen",
    [string]$StackFile = "docker-stack.yml",
    [string]$BootstrapFile = "docker-stack.bootstrap.yml",
    [string]$SingleNodeFile = "docker-stack.single-node.yml",
    [ValidateSet("Preflight", "Bootstrap", "Application")][string]$Phase = "Preflight",
    [ValidateSet("SingleNode", "HA")][string]$Topology = "SingleNode"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RequiredFile([string]$Path) {
    return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
}

function Invoke-StackConfig([string[]]$Files) {
    $arguments = @("stack", "config")
    foreach ($file in $Files) { $arguments += @("-c", $file) }
    & docker @arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker_stack_config_invalid" }
}

$resolvedStack = Resolve-RequiredFile $StackFile
$resolvedBootstrap = Resolve-RequiredFile $BootstrapFile
$resolvedSingleNode = Resolve-RequiredFile $SingleNodeFile
$swarmState = (docker info --format '{{.Swarm.LocalNodeState}}').Trim()
if ($swarmState -ne "active") { throw "docker_swarm_not_active" }

$imageEnvironment = @(
    "GROWEN_POSTGRES_IMAGE", "GROWEN_REDIS_IMAGE", "GROWEN_API_IMAGE",
    "GROWEN_FRONTEND_IMAGE", "GROWEN_DRAMATIQ_IMAGE", "GROWEN_MARKET_WORKER_IMAGE",
    "GROWEN_TELEGRAM_IMAGE", "GROWEN_MCP_PRODUCTS_IMAGE", "GROWEN_MCP_WEB_SEARCH_IMAGE",
    "GROWEN_SIYUAN_IMAGE", "GROWEN_MCP_SIYUAN_IMAGE", "GROWEN_MELI_IMAGE",
    "GROWEN_CLOUDFLARED_IMAGE"
)
$requiredEnvironment = $imageEnvironment + @("MELI_REDIRECT_URI", "LAN_TLS_CERT_SECRET", "LAN_TLS_KEY_SECRET")
foreach ($name in $requiredEnvironment) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if (-not $value) { throw "required_environment_missing:$name" }
}
foreach ($name in $imageEnvironment) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value -notmatch '@sha256:[0-9a-f]{64}$') { throw "immutable_image_digest_required:$name" }
}
if (-not $env:MELI_REDIRECT_URI.StartsWith("https://")) { throw "meli_redirect_uri_https_required" }
if ($env:LAN_TLS_CERT_SECRET -notmatch '^lan_tls_cert_[0-9]{8,}$') {
    throw "versioned_tls_secret_required:LAN_TLS_CERT_SECRET"
}
if ($env:LAN_TLS_KEY_SECRET -notmatch '^lan_tls_key_[0-9]{8,}$') {
    throw "versioned_tls_secret_required:LAN_TLS_KEY_SECRET"
}

$requiredSecrets = @(
    "postgres_password", "secret_key", "admin_pass", "internal_service_token", "telegram_bot_token",
    "telegram_identity_encryption_key", "telegram_identity_hmac_key", "telegram_canary_user_id",
    "siyuan_api_token", "mcp_siyuan_secret_key", "mcp_products_secret_key",
    "mcp_web_search_secret_key", "meli_app_id", "meli_client_secret",
    "meli_token_encryption_key", "cloudflare_meli_tunnel_token",
    $env:LAN_TLS_CERT_SECRET, $env:LAN_TLS_KEY_SECRET
)
$availableSecrets = @(docker secret ls --format '{{.Name}}')
foreach ($name in $requiredSecrets) {
    if ($availableSecrets -notcontains $name) { throw "docker_secret_missing:$name" }
}

$statefulNodes = @(docker node ls --filter "node.label=growen_stateful=true" --format '{{.ID}}')
if ($statefulNodes.Count -eq 0) { throw "swarm_stateful_node_label_missing" }
$nodeStates = @(docker node ls --format '{{.ID}}|{{.Status}}')
if ($LASTEXITCODE -ne 0) { throw "docker_node_inventory_failed" }
$readyNodes = @($nodeStates | Where-Object { $_ -match '\|Ready$' })
if ($Topology -eq "HA" -and $readyNodes.Count -lt 2) { throw "ha_requires_two_ready_nodes" }

Invoke-StackConfig @($resolvedBootstrap)
$applicationFiles = @($resolvedStack)
if ($Topology -eq "SingleNode") { $applicationFiles += $resolvedSingleNode }
Invoke-StackConfig $applicationFiles

if ($Phase -eq "Preflight") {
    Write-Output "swarm_preflight_ok topology=$Topology"
    return
}

if ($Phase -eq "Bootstrap") {
    $applicationServices = @(docker service ls --format '{{.Name}}' | Where-Object {
        $_ -in @("${StackName}_api", "${StackName}_frontend")
    })
    if ($applicationServices.Count -gt 0) { throw "bootstrap_refuses_active_application" }
    if ($PSCmdlet.ShouldProcess($StackName, "Desplegar infraestructura y migración Alembic")) {
        docker stack deploy --with-registry-auth -c $resolvedBootstrap $StackName
        if ($LASTEXITCODE -ne 0) { throw "docker_stack_bootstrap_failed" }
        $migrationService = "${StackName}_migrate"
        $completed = $false
        for ($attempt = 0; $attempt -lt 180; $attempt++) {
            $states = @(docker service ps $migrationService --no-trunc --format '{{.CurrentState}}|{{.Error}}' 2>$null)
            if ($states | Where-Object { $_ -match '^Complete' }) { $completed = $true; break }
            if ($states | Where-Object { $_ -match '^(Failed|Rejected)' -or $_ -match '\|.+' }) {
                throw "alembic_migration_task_failed"
            }
            Start-Sleep -Seconds 1
        }
        if (-not $completed) { throw "alembic_migration_task_timeout" }
        Write-Output "swarm_bootstrap_ok"
    }
    return
}

if ($PSCmdlet.ShouldProcess($StackName, "Desplegar aplicación productiva")) {
    $arguments = @("stack", "deploy", "--with-registry-auth", "--prune")
    foreach ($file in $applicationFiles) { $arguments += @("-c", $file) }
    $arguments += $StackName
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw "docker_stack_deploy_failed" }
    Write-Output "swarm_application_deployed topology=$Topology"
}
