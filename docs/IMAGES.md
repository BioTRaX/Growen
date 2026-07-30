<!-- NG-HEADER: Nombre de archivo: IMAGES.md -->
<!-- NG-HEADER: Ubicación: docs/IMAGES.md -->
<!-- NG-HEADER: Descripción: Crawler y gestión de imágenes -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

## Activos de conocimiento

Las imágenes del Centro Conocimiento se almacenan por hash, registran dimensiones/OCR/procedencia y no ingresan automáticamente a la galería comercial. Incorporarlas a la ficha requiere una acción explícita; etiquetas/capacidades no son tags.

# Gestión de imágenes

## Separación de operación y revisión Vue (2026-07-18)

- `/admin/imagenes-operacion`: sólo admin; crawler, configuración, prueba, logs/SSE, snapshots y disparo de jobs. El start/stop de Playwright y workers permanece en Servicios.
- `/imagenes-productos`: colaborador/admin; cola de revisión, selector, portada, WebP, quitar fondo, watermark, logo y procesamiento por selección.
- `/admin/imagenes` y `/admin/imagenes-productos` se conservan como aliases hacia revisión.

El crawler puede operar en dos modos:
- **Stock**: descarga imágenes desde fuentes de stock aprobadas.
- **Base completa**: recorre toda la base de datos para identificar imágenes faltantes.

## Flujo de aprobación
1. Las imágenes descargadas se almacenan en un área temporal.
2. Un revisor aprueba o descarta cada imagen.
3. Las aprobadas pueden pasar por procesos de `watermark` o `rembg` según configuración.

## Logs y estados
Cada ejecución registra acciones y estados de las imágenes para auditoría.

