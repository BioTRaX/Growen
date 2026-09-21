<!-- NG-HEADER: Nombre de archivo: GOOGLE_DRIVE_SYNC.md -->
<!-- NG-HEADER: Ubicación: docs/features/GOOGLE_DRIVE_SYNC.md -->
<!-- NG-HEADER: Descripción: Documentación de sincronización de imágenes desde Google Drive con selector de carpeta, contraste de SKU, prevención de re-descargas y fotos adicionales. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Sincronización de Imágenes desde Google Drive

Este documento describe la funcionalidad de sincronización automática de imágenes de productos desde Google Drive, integrada en `/imagenes-productos` del frontend Vue 3 y en los endpoints administrativos de la API.

---

## 1. Resumen y Capacidades Principales

La sincronización permite:
- **Selector de Carpeta**: Configurable desde la interfaz gráfica `/imagenes-productos`. Carpeta predeterminada: **ID `13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7` ("Galeria x SKU")**.
- **Contraste de SKU Canónico (`/admin/drive-sync/preview`)**: Previsualiza y evalúa todos los archivos de Drive contra la base de datos de Growen antes de iniciar la descarga.
- **Soporte de Formatos**: Admite nativamente **HEIC**, **PNG**, **JPG/JPEG** y **WebP**. Para archivos `.heic`, se realiza una conversión transparente a derivados WebP amigables para navegadores web estándar.
- **Detección de Imágenes Adicionales**: Si el archivo contiene el SKU canónico seguido de un número o identificador (ej: `FER_0001_ORG - 2.jpg`, `FER_0001_ORG Dorso.png`), se descarga como foto adicional (segunda imagen o posterior) en la misma galería del producto, con su correspondiente `additional_label` y `sort_order`.
- **Prevención de Re-descargas (Idempotencia)**: Si la imagen ya fue descargada previamente (comprobado por `source_url = drive://{file_id}` o por path físico en disco), no se vuelve a descargar ni procesar innecesariamente.
- **Monitoreo en Tiempo Real**: WebSocket `/admin/drive-sync/ws` para observar el progreso en vivo (`current / total`), archivo actual y métricas de éxito, omitidas y errores.
- **Organización en Drive**: Tras el procesamiento, los archivos son movidos a subcarpetas organizadas (`Procesados`, `SIN_SKU`, `Errores_SKU`).

---

## 2. Configuración y Variables de Entorno

Variables en `.env`:

```env
# Google Drive Integration
GOOGLE_APPLICATION_CREDENTIALS=./certs/service_account.json
DRIVE_SOURCE_FOLDER_ID=13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7
DRIVE_PROCESSED_FOLDER_NAME=Procesados
DRIVE_SIN_SKU_FOLDER_NAME=SIN_SKU
DRIVE_ERRORS_FOLDER_NAME=Errores_SKU
```

- `DRIVE_SOURCE_FOLDER_ID`: ID de carpeta por defecto. Si el usuario no ingresa otra en `/imagenes-productos`, se utiliza este ID o `13d0sHLN0LrKAuxBV-Aibxrq05jz0n8F7`.
- Si el backend no encuentra `GOOGLE_APPLICATION_CREDENTIALS`, el endpoint de preview reporta un error HTTP 400 descriptivo para alertar al operador.

---

## 3. Formato de Nombres de Archivo

El analizador `parse_image_filename` reconoce el patrón canónico `XXX_####_YYY` y extrae si corresponde a imagen principal o foto secundaria:

### Ejemplos Válidos:
- **Imágenes Principales (Portada)**:
  - `FER_0001_ORG.jpg` → SKU: `FER_0001_ORG`, Principal (`is_additional=False`, `sort_order=0`).
  - `ABC_1234_XYZ 1.png` → SKU: `ABC_1234_XYZ`, Principal (`is_additional=False`, `sort_order=0`).
  - `PAR_0032_PIC.heic` → SKU: `PAR_0032_PIC`, Principal (convertida a WebP para visualización).
- **Imágenes Adicionales (Segunda imagen o posterior en la misma galería)**:
  - `FER_0001_ORG - 2.jpg` → SKU: `FER_0001_ORG`, Adicional (`is_additional=True`, `additional_label="2"`, `sort_order=1`).
  - `FER_0001_ORG Dorso.png` → SKU: `FER_0001_ORG`, Adicional (`is_additional=True`, `additional_label="Dorso"`, `sort_order=1`).
  - `FER_0001_ORG_2.png` → SKU: `FER_0001_ORG`, Adicional (`is_additional=True`, `additional_label="2"`, `sort_order=1`).
  - `FER_0001_ORG (3).heic` → SKU: `FER_0001_ORG`, Adicional (`is_additional=True`, `sort_order=2`).

### Ejemplos no Canónicos (enviados a `SIN_SKU`):
- `foto_producto.jpg` (sin formato canónico).
- `abc_1234_xyz.jpg` (en minúsculas; los SKUs canónicos son estrictamente en mayúsculas).

---

## 4. Endpoints de la API

| Método | Endpoint | Roles | Descripción |
|---|---|---|---|
| `GET` | `/admin/drive-sync/preview` | `colaborador`, `admin` | Previsualiza y contrasta los archivos de la carpeta contra el catálogo de Growen. Retorna conteos de matches principales, adicionales, ya descargadas, no encontrados y sin SKU. |
| `POST` | `/admin/drive-sync/start` | `admin` | Inicia la tarea asíncrona de sincronización en Dramatiq. Acepta query param opcional `source_folder_id`. |
| `GET` | `/admin/drive-sync/status` | `colaborador`, `admin` | Consulta el estado actual de la sincronización activa. |
| `GET` | `/admin/drive-sync/runs` | `colaborador`, `admin` | Lista el historial paginado de ejecuciones de sincronización. |
| `POST` | `/admin/drive-sync/runs/{id}/cancel` | `admin` | Solicita la cancelación cooperativa de una ejecución en curso. |
| `WS` | `/admin/drive-sync/ws` | `admin` | Canal WebSocket para eventos de progreso en tiempo real. |

---

## 5. Idempotencia y Prevención de Duplicados

Antes de descargar bytes de Google Drive:
1. El worker busca en PostgreSQL si existe un registro activo de `Image` para el producto asociado al `file_id` de Drive (`source_url = drive://{file_id}`).
2. Si existe y el archivo físico reside en el volumen (`data/media/`), se omite la descarga e incrementa el contador de `skipped`.
3. Para imágenes nuevas, tras la descarga se calcula el checksum SHA-256 para garantizar la integridad y evitar duplicados de contenido idéntico.
