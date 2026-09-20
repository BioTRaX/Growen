<!-- NG-HEADER: Nombre de archivo: BUG_REPORTS.md -->
<!-- NG-HEADER: Ubicación: docs/development/BUG_REPORTS.md -->
<!-- NG-HEADER: Descripción: Reportes de errores locales y seguimiento documental en SiYuan -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Reportes de errores desde la UI

## Contexto

Growen permite registrar desde la interfaz incidentes funcionales observados por los usuarios. El sistema conserva la evidencia operativa dentro de la instalación y no la publica automáticamente en servicios externos.

## Observaciones

- `POST /bug-report` acepta una sesión cuando existe, registra el rol efectivo y aplica límite de frecuencia por cliente.
- Cada reporte se guarda como JSON en `logs/BugReport.log`, con rotación de cinco archivos de 5 MB.
- Las capturas opcionales se guardan en `logs/bugreport_screenshots/`; el log sólo contiene su ruta y metadatos.
- El reporte puede incluir lo visible en pantalla. Antes de enviarlo deben ocultarse datos sensibles.
- `GET /admin/services/metrics/bug-reports` permite a un administrador consultar cantidades por día desde el log local.

## Errores y/u outputs

Una respuesta satisfactoria tiene la forma:

```json
{"status": "ok", "id": "br-<timestamp>"}
```

Un exceso de solicitudes devuelve `429`. Una falla de persistencia devuelve una respuesta de error sin exponer rutas internas ni contenido sensible.

## Objetivo

Conservar evidencia suficiente para reproducir un problema sin convertir los reportes, capturas o datos de sesión en un canal de salida hacia Internet.

## Propuesta de código o pasos

1. Abrir el botón **Reportar** y describir el resultado esperado, el observado y los pasos para reproducirlo.
2. Adjuntar una captura sólo cuando aporte evidencia y no muestre secretos ni datos personales innecesarios.
3. Correlacionar el identificador devuelto con `logs/BugReport.log` y los logs estructurados de la API.
4. Si el incidente requiere seguimiento documental, crear o actualizar manualmente una nota curada en el espacio privado de SiYuan. No copiar cookies, tokens, contraseñas, encabezados de autorización ni capturas sin depurar.
5. Aplicar la retención con `scripts/cleanup_logs.py --dry-run` antes de autorizar cualquier eliminación efectiva.

## Criterios de aceptación

- Un usuario puede generar un reporte y recibe un identificador correlacionable; si hay sesión, el rol queda registrado.
- Ningún usuario puede enumerar reportes mediante la API.
- Las capturas no se embeben en el archivo de log.
- La documentación privada de seguimiento reside en SiYuan y su actualización es explícita y curada.
- Se documentan los cambios y se actualiza cualquier información desactualizada.
