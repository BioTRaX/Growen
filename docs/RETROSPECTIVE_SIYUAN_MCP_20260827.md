<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_SIYUAN_MCP_20260827.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_SIYUAN_MCP_20260827.md -->
<!-- NG-HEADER: Descripción: Retrospectiva factual de la integración SiYuan MCP y saneamiento documental. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica: SiYuan MCP y documentación

## Contexto

Sesión dedicada a integrar SiYuan v3.8.1, exponer cuatro tools MCP, publicar documentación y sanear contratos documentales. Se contrastaron código, Compose, scripts, pruebas, logs y estado real de los contenedores.

## Observaciones

- Completado: SiYuan en `127.0.0.1:6806`, MCP HTTP en `127.0.0.1:8104` y Codex STDIO configurado con la venv.
- Completado: smoke real de listar, buscar, leer, crear y releer.
- Completado: publicación create-only; 32 documentos creados y 50 omitidos por colisión.
- Completado: `Roadmap.md` reducido a pendientes/futuro; histórico preservado en `docs/archive/ROADMAP_HISTORY.md`.
- Verificado: auditoría documental sin hallazgos y 33 pruebas focales exitosas.

## Errores y/u outputs

1. PowerShell 5.1 rechazó `utf8NoBOM`; se reemplazó por `System.IO.File.WriteAllText` con `UTF8Encoding($false)`.
2. PowerShell 5.1 tampoco soportó `RandomNumberGenerator.Fill` ni `Convert.ToHexString`; se usó `RNGCryptoServiceProvider` y `BitConverter`.
3. El endurecimiento `cap_drop: ALL` impedía el `chown` inicial de la imagen oficial; se retiró sólo del servicio SiYuan.
4. SiYuan añade frontmatter y título al exportar; el smoke compara el cuerpo escrito, no el envoltorio generado.

## Objetivo

Conservar un patrón reproducible para servicios MCP autenticados, secretos fuera del repositorio, bootstrap idempotente y documentación Git como fuente técnica.

## Propuesta de código o pasos

- Prevención recomendada: mantener pruebas estáticas de compatibilidad PowerShell y ejecutar el smoke real después de cada cambio de Compose.
- Aceleración recomendada: usar `scripts/audit_docs.py` antes de publicar documentación y mantener la publicación create-only hasta definir sincronización incremental segura.
- Pendiente: implementar sincronización Git → SiYuan por hash y actualización explícita.

## Criterios de aceptación

El reporte refleja únicamente evidencia observada, no incluye secretos, documenta los errores y sus soluciones, y deja los pendientes separados de lo completado.
