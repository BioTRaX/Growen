<!-- NG-HEADER: Nombre de archivo: CONTRIBUTING.md -->
<!-- NG-HEADER: Ubicación: CONTRIBUTING.md -->
<!-- NG-HEADER: Descripción: Guía para contribuciones -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Guía de contribuciones

## Estilo de código
- Seguir PEP8 para Python y las guías estándar de cada lenguaje.
- Incluir siempre el encabezado `NG-HEADER` al crear nuevos archivos.

## Testing
- Ejecutar `pytest` antes de enviar un PR.
- Incluir tests para nuevas funcionalidades cuando sea posible.

## Commits
- Mensajes en español y en modo imperativo.
- Un commit por funcionalidad o corrección clara.
- Crear una rama efímera desde el estado actual de `dev` antes de modificar archivos.
- No hacer commits directos a `dev`; integrarla únicamente durante el cierre validado de la sesión.
- Ejecutar Git por terminal y resolver conflictos verificables antes del merge final.

## Prompts a agentes
- Estructurar solicitudes según `AGENTS.md`.
- Asegurar que la documentación se mantenga actualizada.

