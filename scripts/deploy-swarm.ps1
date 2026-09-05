# NG-HEADER: Nombre de archivo: deploy-swarm.ps1
# NG-HEADER: Ubicación: scripts/deploy-swarm.ps1
# NG-HEADER: Descripción: Preflight y despliegue reproducible del stack Growen en Docker Swarm.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$StackName = "growen",
    [string]$StackFile = "docker-stack.yml"
)

$ErrorActionPreference = "Stop"
$resolvedStack = (Resolve-Path -LiteralPath $StackFile).Path
$swarmState = (docker info --format '{{.Swarm.LocalNodeState}}').Trim()
if ($swarmState -ne "active") { throw "docker_swarm_not_active" }

$requiredEnvironment = @(
    "GROWEN_API_IMAGE", "GROWEN_FRONTEND_IMAGE", "GROWEN_DRAMATIQ_IMAGE",
    "GROWEN_MARKET_WORKER_IMAGE", "GROWEN_TELEGRAM_IMAGE",
    "GROWEN_MCP_PRODUCTS_IMAGE", "GROWEN_MCP_WEB_SEARCH_IMAGE",
    "GROWEN_MCP_SIYUAN_IMAGE", "GROWEN_MELI_IMAGE", "MELI_REDIRECT_URI"
)
foreach ($name in $requiredEnvironment) {
    if (-not [Environment]::GetEnvironmentVariable($name)) { throw "required_environment_missing:$name" }
}
if (-not $env:MELI_REDIRECT_URI.StartsWith("https://")) { throw "meli_redirect_uri_https_required" }

$requiredSecrets = @(
    "postgres_password", "secret_key", "internal_service_token", "telegram_bot_token",
    "telegram_identity_encryption_key", "telegram_identity_hmac_key",
    "telegram_canary_user_id", "siyuan_api_token", "mcp_siyuan_secret_key",
    "mcp_products_secret_key", "mcp_web_search_secret_key",
    "meli_app_id", "meli_client_secret", "meli_token_encryption_key",
    "cloudflare_meli_tunnel_token"
)
$availableSecrets = @(docker secret ls --format '{{.Name}}')
foreach ($name in $requiredSecrets) {
    if ($availableSecrets -notcontains $name) { throw "docker_secret_missing:$name" }
}
$statefulNodes = @(docker node ls --filter "node.label=growen_stateful=true" --format '{{.ID}}')
if ($statefulNodes.Count -eq 0) { throw "swarm_stateful_node_label_missing" }

docker stack config -c $resolvedStack | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker_stack_config_invalid" }
if ($PSCmdlet.ShouldProcess($StackName, "Desplegar stack Docker Swarm")) {
    docker stack deploy --with-registry-auth --prune -c $resolvedStack $StackName
    if ($LASTEXITCODE -ne 0) { throw "docker_stack_deploy_failed" }
}
