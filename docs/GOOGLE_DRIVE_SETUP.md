<!-- NG-HEADER: Nombre de archivo: GOOGLE_DRIVE_SETUP.md -->
<!-- NG-HEADER: Ubicación: docs/GOOGLE_DRIVE_SETUP.md -->
<!-- NG-HEADER: Descripción: Guía de configuración para integración con Google Drive. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Configuración de Google Drive para Sincronización de Imágenes

Esta guía explica paso a paso cómo configurar la integración con Google Drive para automatizar la carga de imágenes de productos.

## Requisitos Previos

- Cuenta de Google con acceso a Google Cloud Console
- Acceso a Google Drive con permisos para crear carpetas y compartir
- Proyecto Growen configurado y funcionando

## Paso 1: Crear Proyecto en Google Cloud Console

1. Accede a [Google Cloud Console](https://console.cloud.google.com/)
2. Si no tienes un proyecto, haz clic en el selector de proyectos (arriba a la izquierda)
3. Haz clic en **"Nuevo Proyecto"**
4. Ingresa un nombre para el proyecto (ej: "Growen Drive Integration")
5. Opcionalmente, selecciona una organización
6. Haz clic en **"Crear"**
7. Espera a que el proyecto se cree y selecciónalo

## Paso 2: Habilitar Google Drive API

1. En el menú lateral, ve a **"APIs y servicios"** > **"Biblioteca"**
2. En el buscador, escribe **"Google Drive API"**
3. Haz clic en el resultado **"Google Drive API"**
4. Haz clic en el botón **"HABILITAR"**
5. Espera a que se habilite (puede tardar unos segundos)

## Paso 3: Crear Service Account

1. En el menú lateral, ve a **"APIs y servicios"** > **"Credenciales"**
2. Haz clic en **"+ CREAR CREDENCIALES"** (arriba)
3. Selecciona **"Cuenta de servicio"**
4. Completa el formulario:
   - **Nombre**: `growen-drive-sync` (o el que prefieras)
   - **ID de cuenta de servicio**: Se genera automáticamente
   - **Descripción**: `Service account para sincronización de imágenes desde Drive`
5. Haz clic en **"Crear y continuar"**
6. En **"Otorgar a esta cuenta de servicio acceso al proyecto"**:
   - **Rol**: Selecciona **"Editor"** (o un rol más restrictivo si lo prefieres)
   - Haz clic en **"Continuar"**
7. Opcional: Agrega usuarios que puedan usar esta cuenta de servicio
8. Haz clic en **"Listo"**

## Paso 4: Descargar JSON de Credenciales

1. En la lista de cuentas de servicio, busca la que acabas de crear
2. Haz clic en el email de la cuenta de servicio (ej: `growen-drive-sync@...`)
3. Ve a la pestaña **"Claves"**
4. Haz clic en **"Agregar clave"** > **"Crear nueva clave"**
5. Selecciona **"JSON"**
6. Haz clic en **"Crear"**
7. El archivo JSON se descargará automáticamente
8. **IMPORTANTE**: Guarda este archivo en un lugar seguro. Contiene credenciales sensibles.

## Paso 5: Preparar Carpeta en Google Drive

1. Abre [Google Drive](https://drive.google.com/)
2. Crea una carpeta nueva o selecciona una existente donde subirás las imágenes
3. **Obtener el ID de la carpeta**:
   - Abre la carpeta
   - Mira la URL en el navegador. Debería verse así:
     ```
     https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j
     ```
   - El ID es la parte después de `/folders/`: `1a2b3c4d5e6f7g8h9i0j`
   - **Copia este ID**, lo necesitarás para la configuración

## Paso 6: Compartir Carpeta con Service Account

1. En Google Drive, haz clic derecho en la carpeta que creaste/seleccionaste
2. Selecciona **"Compartir"**
3. En el campo de búsqueda, pega el **email de la Service Account**
   - El email tiene el formato: `growen-drive-sync@PROJECT-ID.iam.gserviceaccount.com`
   - Puedes encontrarlo en Google Cloud Console > Credenciales > tu Service Account
4. Asigna el rol **"Editor"** (necesita permisos para leer, mover y crear carpetas)
5. **Desmarca** la opción "Notificar a las personas" (no es necesario)
6. Haz clic en **"Compartir"**

## Paso 7: Configurar Variables de Entorno

1. Coloca el archivo JSON de credenciales en el proyecto:
   - Crea una carpeta `certs/` en la raíz del proyecto (si no existe)
   - Mueve el archivo JSON allí
   - Renómbralo a `service_account.json` (o el nombre que prefieras)

2. Agrega las siguientes variables a tu archivo `.env`:

```env
# Google Drive Integration
GOOGLE_APPLICATION_CREDENTIALS=./certs/service_account.json
DRIVE_SOURCE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j
DRIVE_PROCESSED_FOLDER_NAME=Procesados
DRIVE_ERRORS_FOLDER_NAME=Errores_SKU
```

**Reemplaza:**
- `1a2b3c4d5e6f7g8h9i0j` con el ID de tu carpeta (obtenido en el Paso 5)
- La ruta del JSON si lo colocaste en otra ubicación

## Paso 8: Verificar .gitignore

Asegúrate de que el archivo `.gitignore` incluya:

```
# Credenciales y llaves
*.pem
*.key
*.crt
*.pfx
*.json
!frontend/package.json
!frontend/package-lock.json
!frontend/tsconfig.json
!frontend/.env.development

# Carpeta de certificados
certs/
```

Esto evitará que las credenciales se suban al repositorio.

## Paso 9: Instalar Dependencias

Si aún no has instalado las dependencias de Google:

```bash
pip install -r requirements.txt
```

O específicamente:

```bash
pip install google-api-python-client>=2.0.0 google-auth>=2.0.0
```

## Paso 10: Probar la Configuración

1. Sube una imagen de prueba a la carpeta de Drive con el formato: `SKU 1.jpg`
   - Ejemplo: Si tienes un producto con `canonical_sku = "ABC123"`, sube `ABC123 1.jpg`

2. Ejecuta el script de sincronización:

```bash
python scripts/sync_drive_images.py
```

3. Verifica los logs:
   - Deberías ver mensajes indicando que se encontró el archivo
   - Si el SKU existe en la base de datos, la imagen se procesará
   - El archivo se moverá a la subcarpeta "Procesados"

4. Verifica en la base de datos:
   - Debería haberse creado un registro en la tabla `images`
   - Deberían existir registros en `image_versions` (original, thumb, card, full)

## Formato de Nombres de Archivo

El sistema espera que los archivos sigan este formato:

```
SKU número.extensión
```

**Ejemplos:**
- `ABC123 1.jpg` → SKU: `ABC123`
- `XYZ-789 2.png` → SKU: `XYZ-789`
- `PROD_001 3.webp` → SKU: `PROD_001`

**Reglas:**
- El SKU debe coincidir con el campo `canonical_sku` del producto
- El número después del espacio es opcional (para múltiples imágenes del mismo SKU)
- Extensiones soportadas: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`

## Flujo de Procesamiento

1. **Listado**: El script lista todos los archivos de imagen en la carpeta origen
2. **Extracción**: Extrae el SKU del nombre de archivo
3. **Búsqueda**: Busca el producto por `canonical_sku`
4. **Procesamiento**:
   - Si el producto existe:
     - Descarga la imagen
     - Valida checksum (evita duplicados)
     - Guarda imagen original
     - Genera derivados (thumb, card, full)
     - Mueve archivo a "Procesados"
   - Si el producto NO existe:
     - Mueve archivo a "Errores_SKU"
     - Registra warning en logs

## Troubleshooting

### Error: "Archivo de credenciales no encontrado"
- Verifica que `GOOGLE_APPLICATION_CREDENTIALS` apunte a la ruta correcta
- Asegúrate de que el archivo existe y tiene permisos de lectura

### Error: "Error de autenticación"
- Verifica que el archivo JSON sea válido
- Asegúrate de que la Service Account tenga permisos en el proyecto
- Verifica que la API de Google Drive esté habilitada

### Error: "Error al listar archivos"
- Verifica que la carpeta esté compartida con la Service Account
- El rol debe ser "Editor" (no solo "Lector")
- Verifica que el `DRIVE_SOURCE_FOLDER_ID` sea correcto

### Error: "Producto no encontrado"
- Verifica que el SKU extraído del nombre coincida exactamente con `canonical_sku`
- El SKU es case-sensitive
- Revisa los logs para ver qué SKU se extrajo

### Las imágenes no se mueven
- Verifica que la Service Account tenga rol "Editor" en la carpeta
- Verifica que no haya errores en los logs antes del movimiento
- Si falla el procesamiento, el archivo NO se mueve (por diseño)

## Automatización (Opcional)

Para ejecutar el script periódicamente, puedes usar:

- **Cron (Linux/Mac)**:
  ```bash
  # Ejecutar cada hora
  0 * * * * cd /ruta/al/proyecto && python scripts/sync_drive_images.py >> logs/drive_sync.log 2>&1
  ```

- **Task Scheduler (Windows)**:
  - Crea una tarea programada que ejecute el script
  - Configura la frecuencia deseada

- **Docker/Container**: Si usas Docker, puedes agregar el script como un cron job dentro del contenedor

## Seguridad

- **NUNCA** subas el archivo JSON de credenciales al repositorio
- **NUNCA** compartas el archivo JSON públicamente
- Si las credenciales se comprometen, elimínalas en Google Cloud Console y crea nuevas
- Considera usar secretos gestionados (AWS Secrets Manager, Azure Key Vault, etc.) en producción

## Referencias

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [Service Accounts Guide](https://cloud.google.com/iam/docs/service-accounts)
- [Google Cloud Console](https://console.cloud.google.com/)

