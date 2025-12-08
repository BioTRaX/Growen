<!-- NG-HEADER: Nombre de archivo: GOOGLE_DRIVE_QUICKSTART.md -->
<!-- NG-HEADER: Ubicación: docs/GOOGLE_DRIVE_QUICKSTART.md -->
<!-- NG-HEADER: Descripción: Guía rápida para primera ejecución de sincronización Drive. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Guía Rápida: Primera Ejecución de Sincronización Drive

## Verificación Previa

Antes de ejecutar la sincronización, verifica tu configuración:

```bash
python scripts/verify_drive_config.py
```

Este script verifica:
- ✅ Archivo de credenciales existe y es válido
- ✅ Variables de entorno configuradas
- ✅ Conexión con Google Drive API funciona

## Configuración en .env

Asegúrate de tener estas variables en tu archivo `.env`:

```env
# Google Drive Integration
GOOGLE_APPLICATION_CREDENTIALS=./certs/growen-drive.json
DRIVE_SOURCE_FOLDER_ID=tu_folder_id_aqui
DRIVE_PROCESSED_FOLDER_NAME=Procesados
DRIVE_SIN_SKU_FOLDER_NAME=SIN_SKU
DRIVE_ERRORS_FOLDER_NAME=Errores_SKU
```

**Nota importante sobre rutas:**
- Si usas ruta relativa (`./certs/growen-drive.json`), debe ser relativa al directorio raíz del proyecto
- El servidor FastAPI debe ejecutarse desde el directorio raíz del proyecto

## Primera Ejecución

### Opción 1: Desde el Panel de Administración (Recomendado)

1. Inicia el servidor:
   ```bash
   python -m uvicorn services.api:app --reload --port 8000
   ```

2. Inicia el frontend (en otra terminal):
   ```bash
   cd frontend
   npm run dev
   ```

3. Accede a: `http://localhost:5173/admin/drive-sync`

4. Haz clic en "Iniciar Sincronización"

5. Observa el progreso en tiempo real en la misma página

### Opción 2: Desde el Endpoint API

```bash
curl -X POST http://localhost:8000/admin/drive-sync/start \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: tu_csrf_token" \
  -b "growen_session=tu_session_id"
```

## Verificación de .gitignore

El archivo `.gitignore` ya incluye:
- `certs/` (línea 32) - Protege toda la carpeta de certificados
- `*.json` (línea 83) - Protege archivos JSON (con excepciones para package.json, etc.)

**Tu archivo `certs/growen-drive.json` está protegido y no se subirá al repositorio.**

## Troubleshooting

### Error: "GOOGLE_APPLICATION_CREDENTIALS no está definido"

**Causa:** El servidor no está cargando las variables de entorno.

**Solución:**
1. Verifica que el archivo `.env` esté en el directorio raíz del proyecto
2. Reinicia el servidor después de modificar `.env`
3. Verifica que el servidor se ejecute desde el directorio raíz:
   ```bash
   # Correcto
   cd C:\Proyectos\NiceGrow\Growen
   python -m uvicorn services.api:app --reload
   
   # Incorrecto
   cd C:\Proyectos\NiceGrow\Growen\services
   python -m uvicorn api:app --reload
   ```

### Error: "Archivo de credenciales no encontrado"

**Causa:** La ruta relativa no se resuelve correctamente.

**Solución:**
1. Usa ruta absoluta en `.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=C:\Proyectos\NiceGrow\Growen\certs\growen-drive.json
   ```

2. O verifica que el archivo exista:
   ```bash
   python scripts/verify_drive_config.py
   ```

### Error: "DRIVE_SOURCE_FOLDER_ID no está definido"

**Solución:**
1. Agrega la variable al `.env`:
   ```env
   DRIVE_SOURCE_FOLDER_ID=tu_folder_id
   ```

2. Obtén el Folder ID desde la URL de Google Drive:
   - Abre la carpeta en Drive
   - La URL es: `https://drive.google.com/drive/folders/FOLDER_ID`
   - Copia el `FOLDER_ID` y úsalo en `.env`

### Error: "Error de autenticación" o "Error al listar archivos"

**Causa:** La Service Account no tiene permisos o la carpeta no está compartida.

**Solución:**
1. Verifica que la carpeta esté compartida con el email de la Service Account
2. El email está en `certs/growen-drive.json` → `client_email`
3. El rol debe ser "Editor" (no solo "Lector")
4. Ver guía completa en `docs/GOOGLE_DRIVE_SETUP.md`

## Formato de Archivos

Recuerda que los archivos deben seguir el formato:
- **Nombre:** `SKU #` (ej: `ABC_1234_XYZ 1.jpg`)
- **SKU debe ser canónico:** Formato `XXX_####_YYY` (ej: `ABC_1234_XYZ`)

## Próximos Pasos

Una vez que la sincronización funcione:
1. Sube imágenes a la carpeta de Drive con formato correcto
2. Ejecuta la sincronización desde el panel
3. Verifica que las imágenes se procesen y muevan a "Procesados"
4. Revisa los logs si hay errores

## Referencias

- `docs/GOOGLE_DRIVE_SETUP.md` - Configuración inicial completa
- `docs/GOOGLE_DRIVE_SYNC.md` - Documentación técnica detallada

