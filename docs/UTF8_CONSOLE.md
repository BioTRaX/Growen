<!-- NG-HEADER: Nombre de archivo: UTF8_CONSOLE.md -->
<!-- NG-HEADER: Ubicación: docs/UTF8_CONSOLE.md -->
<!-- NG-HEADER: Descripción: Guía para configurar UTF-8 en consola de Windows -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Configurar UTF-8 en Consola de Windows

Este documento explica cómo configurar la consola de Windows para usar UTF-8 y evitar errores de encoding con caracteres Unicode (como ✓, ✗, etc.) en los tests.

## Opción 1: Script Helper (RECOMENDADO)

Usar el script `scripts/run_test.ps1` que configura UTF-8 automáticamente:

```powershell
# Ejecutar un test específico
.\scripts\run_test.ps1 -TestPath "tests/performance/test_market_scraping_perf.py::test_scraping_parallel_10_products" -Args "-v -s"

# Ejecutar todos los tests de un archivo
.\scripts\run_test.ps1 -TestPath "tests/performance/test_market_scraping_perf.py" -Args "-v"

# Ejecutar todos los tests de una carpeta
.\scripts\run_test.ps1 -TestPath "tests/performance/" -Args "-v -m performance"
```

## Opción 2: Configuración Manual (Sesión Actual)

Ejecutar estos comandos antes de correr pytest:

```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

# Luego ejecutar pytest normalmente
pytest tests/performance/test_market_scraping_perf.py::test_scraping_parallel_10_products -v
```

## Opción 3: Configuración Permanente en PowerShell

Agregar al perfil de PowerShell (`$PROFILE`):

```powershell
# Ver ubicación del perfil
$PROFILE

# Editar el perfil (si no existe, se crea)
notepad $PROFILE

# Agregar estas líneas:
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
```

Después de guardar, reiniciar PowerShell o ejecutar:
```powershell
. $PROFILE
```

## Opción 4: Variable de Entorno PYTHONIOENCODING

Configurar antes de ejecutar pytest:

```powershell
$env:PYTHONIOENCODING = "utf-8"
pytest tests/performance/test_market_scraping_perf.py::test_scraping_parallel_10_products -v
```

O configurar permanentemente en el sistema:
```powershell
[System.Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
```

## Opción 5: Configurar Terminal (Windows Terminal / PowerShell 7+)

Si usas **Windows Terminal** o **PowerShell 7+**, puedes configurar UTF-8 en el perfil:

1. Abrir configuración: `Ctrl + ,` o `Settings`
2. Ir a `Profiles` → `PowerShell` → `Advanced`
3. En `Appearance`, configurar:
   - Font: Una fuente que soporte Unicode (ej: "Cascadia Code", "Consolas")
   - Encoding: UTF-8

## Verificar Configuración

Para verificar que UTF-8 está activo:

```powershell
# Verificar código de página
chcp

# Debería mostrar: "Active code page: 65001" (UTF-8)

# Probar caracteres Unicode
Write-Host "✓ OK ✗ Error → ← ↑ ↓"
```

## Solución Rápida para Tests

Si solo necesitas ejecutar un test rápidamente sin configurar nada:

```powershell
# Usar el script helper (más fácil)
.\scripts\run_test.ps1 -TestPath "tests/performance/test_market_scraping_perf.py::test_scraping_parallel_10_products" -Args "-v -s"
```

## Troubleshooting

### Error: "charmap codec can't encode character"

**Causa**: La consola no está configurada para UTF-8.

**Solución**: Usar una de las opciones anteriores, preferiblemente el script helper o configuración permanente.

### Los caracteres Unicode no se muestran correctamente

**Causa**: La fuente de la consola no soporta Unicode.

**Solución**: 
1. Cambiar fuente de la consola a "Cascadia Code" o "Consolas"
2. En propiedades de la ventana: `Right-click` → `Properties` → `Font`

### La configuración no persiste entre sesiones

**Causa**: No se configuró el perfil de PowerShell.

**Solución**: Usar Opción 3 (Configuración Permanente).

---

**Recomendación**: Usar `scripts/run_test.ps1` para ejecutar tests individuales, o configurar el perfil de PowerShell para tener UTF-8 siempre disponible.

