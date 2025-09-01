<!-- NG-HEADER: Nombre de archivo: AGENTS.md -->
<!-- NG-HEADER: Ubicación: AGENTS.md -->
<!-- NG-HEADER: Descripción: Lineamientos para agentes de desarrollo -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Lineamientos para agentes de desarrollo

Este documento orienta a herramientas de asistencia de código (Copilot, Codex, Gemini, etc.) sobre cómo interactuar con este repositorio. No aplica a agentes internos de la aplicación.

## Estructura de prompt obligatoria
1. **Contexto**
2. **Observaciones**
3. **Errores y/u outputs**
4. **Objetivo**
5. **Propuesta de código o pasos**
6. **Criterios de aceptación** (siempre exigir "documentar los cambios y actualizar si algo está desactualizado")

## Estándares de entrega
- Código listo para revisión, con pruebas cuando apliquen.
- Mensajes de commit claros y en español.
- Documentar cambios de esquema o infraestructura.
- No introducir dependencias sin documentarlas y agregarlas a los requirements/README.

## Encabezado obligatorio (NG-HEADER)
Agregar al inicio de cada archivo de código y documentación `.md` (excepto `README.md`). Excepciones: `*.json`, `destinatarios.json`, binarios, imágenes, PDFs y otros archivos de datos.

Formato por lenguaje:

### Python
```py
#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```

### TypeScript/JavaScript
```ts
// NG-HEADER: Nombre de archivo: <basename>
// NG-HEADER: Ubicación: <ruta/desde/la/raiz>
// NG-HEADER: Descripción: <breve descripción>
// NG-HEADER: Lineamientos: Ver AGENTS.md
```

### Bash
```bash
#!/usr/bin/env bash
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```

### YAML / Dockerfile
```yaml
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```
```dockerfile
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```

### HTML / CSS
```html
<!-- NG-HEADER: Nombre de archivo: <basename> -->
<!-- NG-HEADER: Ubicación: <ruta/desde/la/raiz> -->
<!-- NG-HEADER: Descripción: <breve descripción> -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
```
```css
/* NG-HEADER: Nombre de archivo: <basename> */
/* NG-HEADER: Ubicación: <ruta/desde/la/raiz> */
/* NG-HEADER: Descripción: <breve descripción> */
/* NG-HEADER: Lineamientos: Ver AGENTS.md */
```

### Markdown de documentación
```md
<!-- NG-HEADER: Nombre de archivo: <basename> -->
<!-- NG-HEADER: Ubicación: <ruta/desde/la/raiz> -->
<!-- NG-HEADER: Descripción: <breve descripción> -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
```

## Buenas prácticas para agentes
- Confirmar impacto de cambios (migraciones, variables de entorno, dependencias nativas).
- Dejar notas de migración cuando corresponda.
- Adjuntar ejemplos mínimos de uso y pruebas cuando sea razonable.

## Checklist para cada PR generado por un agente
- [ ] Se agregó/actualizó encabezado NG-HEADER cuando corresponde.
- [ ] Se actualizaron docs afectadas.
- [ ] Se listaron dependencias nuevas y prerequisitos.
- [ ] Se agregaron o actualizaron tests si aplica.

