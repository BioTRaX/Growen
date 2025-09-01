<!-- NG-HEADER: Nombre de archivo: IMAGES.md -->
<!-- NG-HEADER: Ubicación: docs/IMAGES.md -->
<!-- NG-HEADER: Descripción: Crawler y gestión de imágenes -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Gestión de imágenes

El crawler puede operar en dos modos:
- **Stock**: descarga imágenes desde fuentes de stock aprobadas.
- **Base completa**: recorre toda la base de datos para identificar imágenes faltantes.

## Flujo de aprobación
1. Las imágenes descargadas se almacenan en un área temporal.
2. Un revisor aprueba o descarta cada imagen.
3. Las aprobadas pueden pasar por procesos de `watermark` o `rembg` según configuración.

## Logs y estados
Cada ejecución registra acciones y estados de las imágenes para auditoría.

