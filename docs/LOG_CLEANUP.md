<!-- NG-HEADER: Nombre de archivo: LOG_CLEANUP.md -->
<!-- NG-HEADER: Ubicación: docs/LOG_CLEANUP.md -->
<!-- NG-HEADER: Descripción: Alcances, retención y operación de las alternativas de borrado de logs. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Limpieza de logs

## 1. Contexto

`scripts/start-dev.ps1` crea una carpeta independiente en `logs/dev/<YYYYMMDD_HHMMSS>/`. Una ejecución posterior puede reutilizar procesos que continúan escribiendo en la carpeta original. Por eso la limpieza no debe borrar archivos recursivamente sin reconocer ejecuciones activas.

## 2. Observaciones

| Superficie | Alcance | Persistencia | Restricción |
|---|---|---|---|
| Servicios → Workers → Eliminar historial DB | Registros `ServiceLog` del worker | PostgreSQL | Worker detenido; staff |
| Imágenes → Limpiar logs operativos | `ImageJobLog`, `logs/image_crawler.ndjson` y `tmp/crawl` | PostgreSQL + archivos | Admin + CSRF |
| Servicios → Mantenimiento de logs físicos | Logs legacy y carpetas completas de ejecuciones antiguas | Archivos | Admin + CSRF + previsualización |
| `scripts/cleanup_logs.py` | Misma política física que Servicios | Archivos | Venv obligatoria; soporta `--dry-run` |
| `scripts/clean_all_logs.ps1` | Adaptador PowerShell del script canónico | Archivos | No trunca logs internos de Docker |
| `scripts/clear_logs.py` | Alias legacy, retención cero | Archivos | Conservado sólo por compatibilidad |
| `scripts/clear_backend_log.py` | Trunca únicamente `logs/backend.log` | Archivo | No afecta carpetas dev |

## 3. Errores y/u outputs

- Una carpeta informada como `ejecución activa o más reciente` nunca se selecciona desde la UI.
- Un archivo bloqueado se devuelve en `errors`; no se informa como eliminado.
- `BugReport.log`, sus rotaciones, `bugreport_screenshots/` y `catalog/` o `catalogs/` quedan protegidos por política.
- Docker no ofrece un truncado mediante `docker logs --tail 0`; esa instrucción sólo consulta cero líneas. La retención Docker debe configurarse en el runtime.

## 4. Objetivo

Eliminar logs obsoletos sin dejar carpetas por ejecución vacías, sin interrumpir procesos que siguen escribiendo y sin mezclar historiales operativos de base de datos con archivos de diagnóstico.

## 5. Propuesta de código o pasos

Desde la UI, ingresar los días de retención, previsualizar y confirmar los objetivos. Desde consola:

```powershell
.\.venv\Scripts\python.exe scripts\cleanup_logs.py --dry-run --keep-days 7
.\.venv\Scripts\python.exe scripts\cleanup_logs.py --keep-days 7
.\scripts\clean_all_logs.ps1 -DryRun -KeepDays 7
```

`--keep-days 0` selecciona todo lo no protegido. `--include-latest-dev-run` sólo incorpora la carpeta más reciente si no contiene procesos activos. Las capturas de reportes se modifican únicamente al pasar explícitamente `--screenshots-keep-days` o `--screenshots-max-mb`.

## 6. Criterios de aceptación

- La previsualización y la ejecución calculan la misma política en backend y scripts.
- Las ejecuciones antiguas se eliminan como directorios completos.
- La ejecución activa o más reciente y los historiales protegidos sobreviven.
- Workers e Imágenes explican qué almacenamiento eliminan.
- Se documentan los cambios y se actualiza todo contenido desactualizado.
