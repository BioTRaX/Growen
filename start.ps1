param()

# Ir a la raíz del repo (donde está este script)
Set-Location -LiteralPath $PSScriptRoot

# Verificar venv
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
  Write-Warning "No existe .venv. Cree el entorno: python -m venv .venv; luego active e instale deps."
  exit 1
}

# Activar venv
& ".\.venv\Scripts\Activate.ps1"

# Verificar .env y variables
if (-not (Test-Path ".\.env")) {
  Write-Error "Falta .env (copie .env.example a .env y complete DB_URL/IA)."
  exit 1
}

$envLines = Get-Content .\.env | Where-Object { $_ -match "=" -and -not $_.StartsWith("#") }
$dict = @{}
foreach ($l in $envLines) {
  $k,$v = $l -split "=",2
  $dict[$k.Trim()] = $v.Trim()
}
if (-not $dict.ContainsKey("DB_URL") -or [string]::IsNullOrWhiteSpace($dict["DB_URL"])) {
  Write-Error "Falta DB_URL en .env"
  exit 1
}
if (-not $dict.ContainsKey("OLLAMA_MODEL") -or [string]::IsNullOrWhiteSpace($dict["OLLAMA_MODEL"])) {
  Write-Warning "Falta OLLAMA_MODEL en .env"
}

# Lanzar backend en nueva ventana
Start-Process -WindowStyle Normal -FilePath "cmd.exe" -ArgumentList "/k","uvicorn services.api:app --reload"

# Frontend
Push-Location .\frontend
if (-not (Test-Path .\node_modules)) {
  Write-Host "[INFO] Instalando dependencias frontend..."
  npm install
}
Write-Host "[INFO] Iniciando frontend..."
npm run dev
Pop-Location
