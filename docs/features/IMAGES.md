<!-- NG-HEADER: Nombre de archivo: IMAGES.md -->
<!-- NG-HEADER: Ubicación: docs/features/IMAGES.md -->
<!-- NG-HEADER: Descripción: Suite integral de imágenes, sincronización con Google Drive, edición interactiva y procesamiento masivo. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Gestión y Edición Integral de Imágenes de Productos

Este documento describe la arquitectura, flujos operativos, soporte de formatos y herramientas de edición de imágenes de productos en Growen.

---

## 1. Módulos y Rutas en Frontend (Vue 3)

La operativa de imágenes se encuentra organizada de forma modular:

1. **/imagenes-productos** (`src/modules/images/views/ProductImagesView.vue`):
   - **Pestaña 1: Sincronización con Drive**: Selector de carpeta de Google Drive (ID por defecto: `13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7` "Galeria x SKU"), contraste en memoria y base de datos contra el SKU canónico (`/admin/drive-sync/preview`), y sincronización en tiempo real vía WebSocket.
   - **Pestaña 2: Catálogo y Procesamiento Masivo**: Búsqueda de productos, tabla con selección múltiple con casillas de verificación, aplicación en lote de Logo Institucional Global (PNG), generación de WebP y marcas de agua, y acceso directo a la galería de cada producto.
   - **Pestaña 3: Cola de Revisión**: Moderación de imágenes encontradas automáticamente por crawlers (aprobación o rechazo con motivo).
   - **Cabecera de Marca**: Visualizador del logo institucional actual (dimensiones en px) y subida de archivos PNG con transparencia.

2. **/productos/:id/imagenes** (`src/modules/images/views/ProductImagesGalleryView.vue`):
   - Suite de edición individual para la galería de un producto:
     - Recorte interactivo con coordenadas porcentuales (`vue-advanced-cropper`).
     - Recorte automático cuadrado con margen porcentual slider (`crop-square`).
     - Rotación rápida (↺ -90° / ↻ +90°).
     - Asignación de portada / imagen principal.
     - Procesamiento individual: generación de WebP, marca de agua, eliminación de fondo y aplicación de logo institucional.
     - Descarga directa con nombre canónico (`SKU.webp` o `SKU.jpg`).

3. **/admin/imagenes-operacion** (`src/modules/admin/views/ImageOperationsView.vue`):
   - Consola técnica exclusiva para administradores: configuración del crawler de imágenes, observabilidad, prueba de scraping, inspección de snapshots y descarga de logs en streaming SSE.

---

## 2. Formatos Admitidos y Tratamiento de HEIC

El sistema soporta transparentemente los siguientes formatos:
- **PNG** (`image/png`)
- **JPEG / JPG** (`image/jpeg`)
- **WebP** (`image/webp`)
- **HEIC / HEIF** (`image/heic`, `image/heif`, `application/octet-stream`)

### Particularidades de archivos HEIC:
- Los navegadores web estándar no admiten la reproducción nativa del formato HEIC generado habitualmente por dispositivos móviles iOS.
- Growen integra la biblioteca `pillow_heif` para registrar el codec HEIF en Pillow.
- Durante la ingesta o sincronización de un archivo `.heic`, se preserva el archivo original raw en almacenamiento (`data/media/`), pero el backend genera automáticamente las derivadas cuadradas WebP y asigna una URL amigable para los navegadores en `display_url` y `url`. De este modo, la interfaz gráfica siempre visualiza la imagen sin errores.

---

## 3. Sincronización con Google Drive y Contraste de SKU

La sincronización desde Google Drive (`workers/drive_sync.py` y `services/routers/drive_sync.py`) implementa:

1. **Selector de Carpeta**:
   - ID predeterminado: `13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7` ("Galeria x SKU").
   - Es configurable desde la interfaz en `/imagenes-productos`.

2. **Detección de SKU Canónico y Fotos Adicionales**:
   - `parse_image_filename` detecta el patrón canónico `XXX_####_YYY`.
   - **Imagen Principal**: nombres directos o con sufijo `1` (ej: `FER_0001_ORG.jpg`, `ABC_1234_XYZ 1.png`). Se asigna como portada (`is_primary=True`) si el producto no tiene una portada previa.
   - **Imágenes Adicionales**: nombres con sufijos numéricos o textuales (ej: `FER_0001_ORG - 2.jpg`, `FER_0001_ORG Dorso.png`, `FER_0001_ORG_2.png`, `FER_0001_ORG (2).heic`). Se guardan como fotos secundarias en la misma galería del producto, con su correspondiente etiqueta descriptiva (`additional_label`) y orden de visualización (`sort_order`).

3. **Prevención de Re-descargas (Idempotencia)**:
   - Antes de iniciar la descarga de bytes desde Google Drive, el sistema consulta la base de datos verificando si existe un registro de imagen activo para ese producto asociado al `file_id` de Drive (`drive://{file_id}`) o si ya existe un archivo físico idéntico en disco.
   - Si la imagen ya fue descargada, se omite de forma idempotente, ahorrando ancho de banda y tiempo de procesamiento.

4. **Previsualización y Diagnóstico**:
   - El endpoint `GET /admin/drive-sync/preview` contrasta los archivos de la carpeta contra el catálogo antes de iniciar cualquier descarga, clasificando cada archivo en:
     - `matched`: Match correcto para imagen principal o adicional.
     - `already_downloaded`: Ya presente en la galería del producto.
     - `product_not_found`: SKU canónico válido pero inexistente en el catálogo.
     - `no_sku`: Nombre sin formato canónico.

---

## 4. Edición Masiva e Individual

- **Logo Institucional**: Se carga un archivo PNG con transparencia en la cabecera del gestor. La aplicación masiva o individual superpone el logo en la esquina inferior derecha con escalado proporcional y opacidad configurable.
- **Generación WebP**: Convierte y comprime la imagen original a formato WebP optimizado con versiones thumbnail (`256px`), medium (`800px`) y large (`1600px`).
- **Recorte Interactivo y Cuadrado**: Permite a los operadores corregir encuadres mediante el cropper interactivo o forzar relación de aspecto 1:1 con slider de margen porcentual para centrado de producto.
