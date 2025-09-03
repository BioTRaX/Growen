$logPath = "logs\server.log"
if (!(Test-Path logs)) { New-Item -ItemType Directory -Path logs | Out-Null }
function Log($msg) {
    Add-Content -Path $logPath -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg)
}

Write-Host "Cerrando backend (puerto 8000)..."
$p8000 = netstat -ano | Select-String ":8000"
if ($p8000) {
    $procId = ($p8000 -split '\s+')[-1]
    Stop-Process -Id $procId -Force
    Log "STOP backend: proceso $procId cerrado."
} else {
    Log "STOP backend: no se encontró proceso."
}

Write-Host "Cerrando frontend (puerto 5173)..."
$p5173 = netstat -ano | Select-String ":5173"
if ($p5173) {
    $procId = ($p5173 -split '\s+')[-1]
    Stop-Process -Id $procId -Force
    Log "STOP frontend: proceso $procId cerrado."
} else {
    Log "STOP frontend: no se encontró proceso."
}

