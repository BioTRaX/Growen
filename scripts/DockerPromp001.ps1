#!/usr/bin/env pwsh
# NG-HEADER: Nombre de archivo: DockerPromp001.ps1
# NG-HEADER: Ubicación: scripts/
# NG-HEADER: Descripción: Wrapper que preserva el prompt original y redirige al script principal de limpieza Docker
# NG-HEADER: Lineamientos: Ver AGENTS.md

<#!
Este archivo conserva el prompt original (requerimientos) utilizado para generar el script
`cleanup-docker-images.ps1`. Sirve como envoltorio (wrapper) para invocar a dicho script y
mantener trazabilidad del origen funcional.

USO DIRECTO:
	.\scripts\DockerPromp001.ps1            # Ejecuta el limpiador interactivo
	.\scripts\DockerPromp001.ps1 -DryRun    # Solo listar
	.\scripts\DockerPromp001.ps1 -PerImageConfirm

Los parámetros se pasan transparentemente al script principal.

Prompt original:
--------------------------------------------------------------------------------
[Contexto]
Soy un desarrollador que utiliza Docker Desktop en Windows. Con el tiempo, he acumulado una gran cantidad de imágenes de Docker y sospecho que muchas de ellas ya no están en uso, ocupando espacio innecesario en mi disco.
Mi objetivo es limpiar estas imágenes "basura" o "huérfanas" (dangling) y aquellas que no están asociadas a ningún contenedor existente (ni activo ni detenido).
Quiero un script de PowerShell que me ayude a identificar y eliminar estas imágenes de forma segura. La seguridad es clave: el script NO debe eliminar nada sin mi confirmación explícita para cada imagen o para el lote completo.

[Objetivo]
Generar un script de PowerShell que realice las siguientes tareas en orden:
1. Detectar si el servicio de Docker está corriendo. Si no lo está, notificar al usuario y detenerse.
2. Obtener una lista de todas las imágenes "dangling" (las que aparecen como <none>:<none>).
3. Obtener una lista de todas las imágenes que no están siendo utilizadas por ningún contenedor (ni en ejecución ni detenido).
4. Presentar al usuario una lista consolidada y clara de todas las imágenes que se pueden eliminar.
5. Preguntar al usuario si desea proceder con la eliminación. La confirmación debe ser clara (ej: "Escriba 'si' para confirmar").
6. Si el usuario confirma, ejecutar el comando `docker image prune` con los filtros adecuados o eliminar las imágenes individualmente.
7. Al finalizar, mostrar un mensaje de resumen indicando cuántas imágenes se eliminaron y el espacio liberado.

[Criterios de Aceptación]
- El script debe estar completamente comentado para que yo pueda entender cada paso.
- Debe usar buenas prácticas de PowerShell, como el manejo de errores básicos.
- El output en la consola debe ser limpio y fácil de leer, usando `Write-Host` para guiar al usuario.
- La parte de la confirmación es obligatoria y no debe ser omitida.
--------------------------------------------------------------------------------
#>

[CmdletBinding()] param(
	[switch]$DryRun,
	[switch]$PerImageConfirm
)

$scriptPath = Join-Path -Path $PSScriptRoot -ChildPath 'cleanup-docker-images.ps1'
if (-not (Test-Path $scriptPath)) {
	Write-Host "[ERROR] No se encontró cleanup-docker-images.ps1 en $PSScriptRoot" -ForegroundColor Red
	exit 1
}

# Re-ensamblar args dinámicos
$invokeParams = @{}
if ($DryRun) { $invokeParams["DryRun"] = $true }
if ($PerImageConfirm) { $invokeParams["PerImageConfirm"] = $true }

Write-Host "[INFO ] Invocando script principal de limpieza Docker..." -ForegroundColor Cyan
if ($invokeParams.Count -gt 0) {
	& $scriptPath @invokeParams
} else {
	& $scriptPath
}
exit $LASTEXITCODE