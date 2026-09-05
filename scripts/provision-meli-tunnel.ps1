# NG-HEADER: Nombre de archivo: provision-meli-tunnel.ps1
# NG-HEADER: Ubicación: scripts/provision-meli-tunnel.ps1
# NG-HEADER: Descripción: Provisiona idempotentemente el túnel remoto Cloudflare exclusivo de MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)][string]$AccountId,
    [Parameter(Mandatory = $true)][string]$ZoneId,
    [Parameter(Mandatory = $true)][string]$Hostname,
    [Parameter(Mandatory = $true)][string]$ApiTokenFile,
    [Parameter(Mandatory = $true)][string]$OutputTokenFile,
    [string]$TunnelName = "growen-meli"
)

$ErrorActionPreference = "Stop"
$apiTokenPath = [IO.Path]::GetFullPath($ApiTokenFile)
$outputPath = [IO.Path]::GetFullPath($OutputTokenFile)
if (-not (Test-Path -LiteralPath $apiTokenPath -PathType Leaf)) {
    throw "cloudflare_api_token_file_missing"
}
if ([IO.Path]::GetExtension($outputPath) -eq ".example") {
    throw "cloudflare_output_path_invalid"
}
$apiToken = (Get-Content -LiteralPath $apiTokenPath -Raw).Trim()
if (-not $apiToken) { throw "cloudflare_api_token_empty" }
$headers = @{ Authorization = "Bearer $apiToken"; "Content-Type" = "application/json" }
$base = "https://api.cloudflare.com/client/v4"

function Invoke-Cf([string]$Method, [string]$Path, $Body = $null) {
    $parameters = @{ Method = $Method; Uri = "$base$Path"; Headers = $headers }
    if ($null -ne $Body) { $parameters.Body = ($Body | ConvertTo-Json -Depth 12 -Compress) }
    $response = Invoke-RestMethod @parameters
    if (-not $response.success) { throw "cloudflare_api_request_failed" }
    return $response.result
}

if (-not $PSCmdlet.ShouldProcess($Hostname, "Provisionar túnel Cloudflare $TunnelName")) {
    Write-Host "Validación completada; no se realizaron cambios."
    exit 0
}

$encodedName = [Uri]::EscapeDataString($TunnelName)
$tunnels = @(Invoke-Cf GET "/accounts/$AccountId/cfd_tunnel?name=$encodedName&is_deleted=false")
$tunnel = $tunnels | Select-Object -First 1
if ($null -eq $tunnel) {
    $tunnel = Invoke-Cf POST "/accounts/$AccountId/cfd_tunnel" @{ name = $TunnelName; config_src = "cloudflare" }
}
$configuration = @{
    config = @{
        ingress = @(
            @{ hostname = $Hostname; path = "^/integrations/meli/oauth/callback(?:\?.*)?$"; service = "http://meli_webhook_gateway:8080" },
            @{ hostname = $Hostname; path = "^/integrations/meli/webhook$"; service = "http://meli_webhook_gateway:8080" },
            @{ service = "http_status:404" }
        )
    }
}
Invoke-Cf PUT "/accounts/$AccountId/cfd_tunnel/$($tunnel.id)/configurations" $configuration | Out-Null

$records = @(Invoke-Cf GET "/zones/$ZoneId/dns_records?type=CNAME&name=$([Uri]::EscapeDataString($Hostname))")
$dnsBody = @{ type = "CNAME"; name = $Hostname; content = "$($tunnel.id).cfargotunnel.com"; proxied = $true; ttl = 1 }
if ($records.Count -gt 0) {
    Invoke-Cf PUT "/zones/$ZoneId/dns_records/$($records[0].id)" $dnsBody | Out-Null
} else {
    Invoke-Cf POST "/zones/$ZoneId/dns_records" $dnsBody | Out-Null
}

$tunnelToken = Invoke-Cf GET "/accounts/$AccountId/cfd_tunnel/$($tunnel.id)/token"
$parent = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
[IO.File]::WriteAllText($outputPath, [string]$tunnelToken, [Text.UTF8Encoding]::new($false))
if ($env:OS -eq "Windows_NT") {
    & icacls.exe $outputPath /inheritance:r /grant:r "$env:USERNAME`:R" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "cloudflare_output_acl_failed" }
}
Write-Host "Túnel y DNS configurados. Token guardado fuera del repositorio."
