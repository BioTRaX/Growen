Write-Host "Cerrando backend (puerto 8000)..."
$p8000 = netstat -ano | Select-String ":8000"
if ($p8000) {
    $pid = ($p8000 -split '\s+')[-1]
    Stop-Process -Id $pid -Force
} else {
    Write-Host "No se encontró proceso en puerto 8000."
}

Write-Host "Cerrando frontend (puerto 5173)..."
$p5173 = netstat -ano | Select-String ":5173"
if ($p5173) {
    $pid = ($p5173 -split '\s+')[-1]
    Stop-Process -Id $pid -Force
} else {
    Write-Host "No se encontró proceso en puerto 5173."
}

Read-Host "Presione Enter para continuar"
