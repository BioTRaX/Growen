<!-- NG-HEADER: Nombre de archivo: GOOGLE_DRIVE_SYNC.md -->
<!-- NG-HEADER: Ubicación: docs/GOOGLE_DRIVE_SYNC.md -->
<!-- NG-HEADER: Descripción: Documentación de sincronización de imágenes desde Google Drive. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Sincronización de Imágenes desde Google Drive

Este documento describe la funcionalidad de sincronización automática de imágenes de productos desde Google Drive, accesible desde el Panel de Administración.

## Resumen

La sincronización permite:
- Detectar automáticamente imágenes subidas a una carpeta específica en Google Drive
- Validar que los nombres de archivo correspondan a SKUs canónicos
- Procesar y asociar las imágenes a los productos correspondientes
- Mover archivos a carpetas organizadas según el resultado del procesamiento
- Monitorear el progreso en tiempo real mediante WebSocket

## Configuración

### Variables de Entorno

Agregar las siguientes variables al archivo `.env`:

```env
# Google Drive Integration
GOOGLE_APPLICATION_CREDENTIALS=./certs/service_account.json
DRIVE_SOURCE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j
DRIVE_PROCESSED_FOLDER_NAME=Procesados
DRIVE_SIN_SKU_FOLDER_NAME=SIN_SKU
DRIVE_ERRORS_FOLDER_NAME=Errores_SKU
```

**Descripción de variables:**

- `GOOGLE_APPLICATION_CREDENTIALS`: Ruta al archivo JSON de Service Account de Google Cloud
- `DRIVE_SOURCE_FOLDER_ID`: ID de la carpeta principal donde se suben las imágenes
- `DRIVE_PROCESSED_FOLDER_NAME`: Nombre de la subcarpeta para imágenes procesadas exitosamente (default: `Procesados`)
- `DRIVE_SIN_SKU_FOLDER_NAME`: Nombre de la subcarpeta para archivos sin formato SKU válido (default: `SIN_SKU`)
- `DRIVE_ERRORS_FOLDER_NAME`: Nombre de la subcarpeta para archivos con errores de procesamiento (default: `Errores_SKU`)

### Configuración de Google Cloud

Ver `docs/GOOGLE_DRIVE_SETUP.md` para instrucciones detalladas sobre:
- Crear proyecto en Google Cloud Console
- Habilitar Google Drive API
- Crear Service Account
- Descargar credenciales JSON
- Compartir carpeta con Service Account

## Formato de Nombres de Archivo

### Requisitos

1. **Formato**: `SKU #` (SKU seguido de espacio y número)
   - Ejemplo: `ABC_1234_XYZ 1.jpg`
   - El número después del espacio es opcional pero recomendado para múltiples imágenes del mismo SKU

2. **SKU Canónico**: El SKU extraído debe cumplir el formato canónico:
   - Formato: `XXX_####_YYY`
   - `XXX`: 3 letras mayúsculas (A-Z)
   - `####`: 4 dígitos (0-9)
   - `YYY`: 3 caracteres alfanuméricos (A-Z0-9)
   - Ejemplos válidos: `ABC_1234_XYZ`, `ROS_0123_RED`, `SUP_0007_A1B`

### Ejemplos

**Válidos:**
- `ABC_1234_XYZ 1.jpg` → SKU: `ABC_1234_XYZ`
- `ROS_0123_RED 2.png` → SKU: `ROS_0123_RED`
- `SUP_0007_A1B 3.webp` → SKU: `SUP_0007_A1B`

**Inválidos:**
- `abc_1234_xyz 1.jpg` → Minúsculas (no canónico)
- `ABC_12_XYZ 1.jpg` → Faltan dígitos (no canónico)
- `ABC_1234_XYZ.jpg` → Falta espacio y número
- `imagen.jpg` → No tiene formato SKU

## Flujo de Procesamiento

### 1. Inicio de Sincronización

- Se accede desde el Panel de Administración → "Drive Sync"
- El endpoint `/admin/drive-sync/start` requiere permisos de administrador
- Solo puede ejecutarse una sincronización a la vez

### 2. Listado de Archivos

- Se listan todos los archivos de imagen en la carpeta origen (`DRIVE_SOURCE_FOLDER_ID`)
- **Solo se procesan archivos directamente en la carpeta raíz** (no en subcarpetas)
- Se excluyen automáticamente archivos en carpetas como "Procesados", "Errores_SKU", "SIN_SKU"

### 3. Validación y Procesamiento

Para cada archivo:

1. **Extracción de SKU**: Se extrae el SKU del nombre del archivo
2. **Validación de formato**: Se verifica que el SKU sea canónico usando `db.sku_utils.is_canonical_sku()`
3. **Búsqueda de producto**: Se busca en la tabla `Product` por `canonical_sku`
4. **Procesamiento**:
   - Si el producto existe:
     - Descarga la imagen
     - Valida checksum SHA256 (evita duplicados)
     - Guarda imagen original
     - Genera derivados (thumb, card, full)
     - Mueve archivo a `DRIVE_PROCESSED_FOLDER_NAME`
   - Si el producto NO existe:
     - Mueve archivo a `DRIVE_ERRORS_FOLDER_NAME`
     - Si `DEBUG=true`, guarda log de error en Drive

### 4. Carpetas de Destino

El sistema crea automáticamente las siguientes subcarpetas dentro de `DRIVE_SOURCE_FOLDER_ID`:

- **Procesados** (`DRIVE_PROCESSED_FOLDER_NAME`): Archivos procesados exitosamente
- **SIN_SKU** (`DRIVE_SIN_SKU_FOLDER_NAME`): Archivos que no tienen formato SKU canónico válido
- **Errores_SKU** (`DRIVE_ERRORS_FOLDER_NAME`): Archivos con SKU válido pero que fallaron (producto no encontrado, error de procesamiento, etc.)

## Monitoreo en Tiempo Real

### WebSocket

El sistema emite actualizaciones de progreso en tiempo real mediante WebSocket:

**Endpoint**: `ws://host/admin/drive-sync/ws`

**Mensajes enviados:**

```json
{
  "type": "drive_sync_progress",
  "status": "processing",
  "current": 3,
  "total": 41,
  "sku": "ABC_1234_XYZ",
  "message": "Procesando SKU ABC_1234_XYZ imagen 3/41",
  "error": null
}
```

**Estados posibles:**
- `initializing`: Inicializando sincronización
- `listing`: Listando archivos
- `processing`: Procesando archivos
- `completed`: Sincronización completada
- `error`: Error en sincronización

### Panel de Administración

El componente frontend (`DriveSyncPage.tsx`) muestra:
- Estado actual (Inactivo, Procesando, Completado, Error)
- Barra de progreso (X/Y archivos)
- SKU actual siendo procesado
- Mensajes de estado
- Errores si ocurren

## Logging de Errores (Modo Debug)

Si la variable `DEBUG=true` está configurada, el sistema guarda archivos de log `.txt` en la carpeta de errores para cada archivo que falla:

**Formato del log:**
```
Error al procesar imagen desde Google Drive
Fecha: 2025-01-15T10:30:00Z
Archivo: ABC_1234_XYZ 1.jpg
SKU: ABC_1234_XYZ
Error: Producto no encontrado para SKU 'ABC_1234_XYZ'
```

## Endpoints de API

### POST `/admin/drive-sync/start`

Inicia la sincronización.

**Autenticación**: Requiere rol `admin`

**Respuesta:**
```json
{
  "status": "started",
  "message": "Sincronización iniciada",
  "sync_id": "uuid-del-sync"
}
```

### GET `/admin/drive-sync/status`

Obtiene el estado actual de la sincronización.

**Autenticación**: Requiere rol `admin`

**Respuesta:**
```json
{
  "status": "running",
  "message": "Sincronización en progreso",
  "sync_id": "uuid-del-sync"
}
```

### WebSocket `/admin/drive-sync/ws`

Conexión WebSocket para recibir actualizaciones en tiempo real.

**Mensajes del cliente:**
- `{"type": "ping"}`: Mantener conexión activa

**Mensajes del servidor:**
- `{"type": "drive_sync_progress", ...}`: Actualización de progreso
- `{"type": "drive_sync_status", ...}`: Estado inicial
- `{"type": "ping"}`: Ping para mantener conexión

## Seguridad

- **Autenticación**: Todos los endpoints requieren autenticación de administrador
- **CSRF**: Los endpoints de mutación requieren token CSRF
- **Credenciales**: El archivo JSON de Service Account debe estar en `.gitignore`
- **Permisos**: La Service Account solo necesita acceso a la carpeta específica (rol Editor)

## Troubleshooting

### Error: "Ya hay una sincronización en progreso"

Solo puede ejecutarse una sincronización a la vez. Esperar a que termine o reiniciar el servidor si está bloqueado.

### Error: "GOOGLE_APPLICATION_CREDENTIALS no está definido"

Verificar que la variable de entorno esté configurada en `.env`.

### Error: "DRIVE_SOURCE_FOLDER_ID no está definido"

Verificar que la variable de entorno esté configurada y contenga el ID correcto de la carpeta.

### Los archivos no se procesan

- Verificar que los archivos estén directamente en la carpeta raíz (no en subcarpetas)
- Verificar que los nombres sigan el formato `SKU #`
- Verificar que el SKU sea canónico (formato `XXX_####_YYY`)
- Verificar que el producto exista en la base de datos con ese `canonical_sku`

### Los archivos se mueven a "SIN_SKU"

- El nombre del archivo no sigue el formato `SKU #`
- El SKU extraído no es canónico (no cumple formato `XXX_####_YYY`)

### Los archivos se mueven a "Errores_SKU"

- El SKU es válido pero el producto no existe en la base de datos
- Error al descargar la imagen
- Error al procesar la imagen (corrupta, formato no soportado, etc.)

## Referencias

- `docs/GOOGLE_DRIVE_SETUP.md`: Configuración inicial de Google Cloud y Drive
- `workers/drive_sync.py`: Implementación del worker de sincronización
- `services/routers/drive_sync.py`: Endpoints de API y WebSocket
- `services/integrations/drive.py`: Cliente de Google Drive API
- `db/sku_utils.py`: Utilidades de validación de SKU canónico

