<!-- NG-HEADER: Nombre de archivo: siyuan-mcp-mutations.md -->
<!-- NG-HEADER: Ubicación: .agents/skills/create-service/references/siyuan-mcp-mutations.md -->
<!-- NG-HEADER: Descripción: Contrato de implementación y aceptación para mutaciones SiYuan por MCP. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Mutaciones SiYuan por MCP

Usar este contrato cuando una tool cree o modifique documentos, bloques o
Attribute Views de SiYuan. El MCP ejecuta la mutación; el navegador sólo aporta
la comprobación visual.

## Contrato de implementación

1. Resolver notebook, documento y ruta desde el servidor. No aceptar rol, raíz
   autorizada ni política de escritura como argumentos del modelo.
2. Validar la autoridad de la ruta por segmentos completos y volver a validarla
   inmediatamente antes de escribir.
3. Crear historial antes de mutar. Si el historial falla, abortar sin escribir.
4. Distinguir reemplazo Markdown de mutación estructurada. Una tabla de base de
   datos requiere APIs de Attribute View; no se representa como tabla Markdown.
5. Ejecutar cada escritura una sola vez. Ante timeout o respuesta ambigua,
   devolver estado incierto y exigir una lectura nueva antes de continuar.
6. Diseñar la reejecución para reconciliar artefactos conocidos sin duplicar
   contenido. En SiYuan 3.8.1 una Attribute View puede incorporar una columna
   vacía `Select`; eliminarla sólo si la tool demuestra que es el valor generado
   por defecto y no contiene datos.
7. Auditar actor seudonimizado, tool, raíz, identificador hasheado, resultado y
   revisiones; nunca contenido, ruta privada completa ni token.

## Contrato de aceptación

Validar en este orden:

1. Pruebas unitarias de autorización, historial, no reintento, conflicto,
   idempotencia/reconciliación y sanitización de errores.
2. Invocación por MCP real en el transporte soportado; una llamada directa a la
   función Python no prueba descubrimiento, catálogo ni despacho MCP.
3. Verificación por API semántica del árbol, Attribute View, campos, tipos y
   valores persistidos.
4. Verificación visual en Chrome después de la comprobación semántica, usando un
   workspace desechable o un documento autorizado explícitamente.

Registrar la versión de SiYuan usada en el smoke cuando el comportamiento
depende de normalizaciones o columnas generadas por el producto.
