# Growen

Agente para gestión de catálogo y stock de Nice Grow con interfaz de chat web e IA híbrida.

## Arquitectura

- **Backend**: FastAPI + WebSocket.
- **Base de datos**: PostgreSQL 15 (Alembic para migraciones).
- **IA**: ruteo automático entre Ollama (local) y OpenAI.
- **Frontend**: React + Vite con listas virtualizadas mediante `react-window`.
- **Adapters**: stubs de Tiendanube.

## Requisitos

- Python 3.11+
- Node.js LTS
- PostgreSQL 15
- Opcional: Docker y Docker Compose
- El backend usa httpx para llamadas a proveedores (Ollama / APIs); ya viene incluido.

## Instalación local

Antes de instalar dependencias, `pyproject.toml` debe listar los paquetes o usar un directorio `src/`.
Este repositorio mantiene sus módulos en la raíz, así que es necesario declararlos explícitamente:

```toml
[tool.setuptools.packages.find]
include = ["agent_core", "ai", "cli", "adapters", "services", "db"]
```bash
# Crear una nueva revisión a partir de los modelos
alembic -c ./alembic.ini revision -m "descripcion" --autogenerate

# Aplicar las migraciones pendientes
alembic -c ./alembic.ini upgrade head

# Revertir la última migración
alembic -c ./alembic.ini downgrade -1
```

Si se prefiere un layout `src/`, trasladá las carpetas anteriores a `src/` y añadí `where = ["src"]` en la misma sección.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# reemplazar SECRET_KEY, ADMIN_USER y ADMIN_PASS antes de continuar
# las variables de entorno se cargan automáticamente desde .env
# crear base de datos growen en PostgreSQL
alembic -c ./alembic.ini upgrade head
uvicorn services.api:app --reload
```

## Migraciones automáticas

`start.sh`, `start.bat` y `scripts/run_api.cmd` ejecutan `alembic upgrade head` con el intérprete del entorno virtual antes de iniciar el servidor.
Si la migración falla, el proceso se detiene para evitar correr con un esquema desactualizado.
De esta forma la base siempre está en el esquema más reciente sin comandos manuales.

### Permisos mínimos en esquema

Para evitar errores como `permiso denegado al esquema public`, el usuario de la base de datos debe contar con permisos sobre el esquema `public`:

```sql
ALTER DATABASE growen OWNER TO growen;
GRANT USAGE, CREATE ON SCHEMA public TO growen;
```

## Migraciones idempotentes

Cuando existen tablas creadas manualmente o por otras ramas, las migraciones detectan el esquema real y agregan columnas, claves foráneas e índices faltantes en lugar de fallar con errores como `DuplicateTable` o `UndefinedColumn`. Esto vuelve a las migraciones seguras e idempotentes.

La revisión inicial `init_schema` usa `sa.inspect` para crear tablas solo cuando faltan y eliminarlas únicamente si existen, evitando fallas en upgrades o downgrades.

Comandos útiles en `psql` para verificar el estado de una tabla:

```sql
\d supplier_price_history
SELECT column_name FROM information_schema.columns
  WHERE table_name='supplier_price_history'
  ORDER BY ordinal_position;
```

## Instalación Frontend

```bash
cd frontend
npm install
npm run dev
```

En desarrollo, Vite proxya `/ws`, `/chat` y `/actions` hacia `http://localhost:8000`, evitando errores de CORS. Durante el arranque pueden mostrarse errores de proxy WebSocket si la API aún no está disponible; una vez arriba, la conexión se restablece sola. El chat abre un WebSocket en `/ws` y, si no está disponible, utiliza `POST /chat`, que admite la variante con o sin barra final para evitar redirecciones 307. El servidor envía un ping cada 30 s y corta la sesión tras 60 s sin recibir datos; el frontend ignora esos pings, cierra limpiamente y reintenta con backoff exponencial si la conexión se pierde. Para modificar las URLs se puede crear `frontend/.env.development` con `VITE_WS_URL` y `VITE_API_BASE`.

## Subir listas de precios desde el chat

- Arrastrá y soltá un archivo `.xlsx` o `.csv` sobre la zona punteada encima del chat para abrir el modal de carga.
- También podés usar el botón **Adjuntar Excel**.
- El modal muestra nombre y tamaño del archivo y habilita **Subir** solo cuando hay proveedor seleccionado.
- Se validan formato y tamaño antes de enviar. El límite se define con `VITE_MAX_UPLOAD_MB`.
- Solo los roles `proveedor`, `colaborador` y `admin` ven la opción de adjuntar. Si el usuario es `proveedor`, su `supplier_id` queda preseleccionado.

## Autenticación y roles

La API implementa sesiones mediante la cookie `growen_session` y un token CSRF almacenado en `csrf_token`. Cada vez que se inicia o cierra sesión se generan nuevos valores para ambas cookies, evitando la fijación de sesiones. Todas las mutaciones deben enviar el encabezado `X-CSRF-Token` coincidiendo con dicha cookie. Las rutas que modifican datos añaden dependencias `require_roles` para comprobar que el usuario posea el rol autorizado.

El login acepta **identificador** o email junto con la contraseña. Al ejecutar las migraciones se crea, si no existe, un usuario administrador usando `ADMIN_USER` y `ADMIN_PASS` definidos en `.env` (ver `.env.example`). El servidor se niega a iniciar si `ADMIN_PASS` queda en `changeme`.

### Endpoints principales

- `POST /auth/login` valida credenciales por identificador o email y genera una sesión nueva.
- `POST /auth/guest` crea una sesión con rol `guest` sin usuario, regenerando el token.
- `POST /auth/logout` cierra la sesión, crea una nueva sesión de invitado y regenera el token (requiere CSRF).
- `GET /auth/me` informa el estado actual.
- `GET /auth/users` lista usuarios (solo admin).
- `POST /auth/users` crea usuarios (solo admin, requiere CSRF).
- `PATCH /auth/users/{id}` actualiza usuarios (solo admin, requiere CSRF).
- `POST /auth/users/{id}/reset-password` regenera la contraseña (solo admin, requiere CSRF).

### Roles y permisos

| Rol         | Permisos principales |
|-------------|---------------------|
| invitado    | Solo lectura |
| cliente     | Solo lectura |
| proveedor   | Subir Excel de su proveedor asignado |
| colaborador | Subir Excel y aplicar importaciones de cualquier proveedor |
| admin       | Todos los permisos, incluyendo registrar usuarios |

La lista completa de rutas y roles se encuentra en [docs/roles-endpoints.md](docs/roles-endpoints.md).

### Variables de entorno relevantes

```env
SECRET_KEY=changeme
# ADMIN_USER y ADMIN_PASS se definen en .env (ver .env.example)
SESSION_EXPIRE_MINUTES=1440 # duración de la sesión en minutos (1 día recomendado)
AUTH_ENABLED=true
# se ignora en producción; allí siempre es true
COOKIE_SECURE=false
COOKIE_DOMAIN=
```

`SECRET_KEY` y las credenciales iniciales (`ADMIN_USER` y `ADMIN_PASS`, definidas en `.env`) deben reemplazarse por valores robustos antes de
iniciar la aplicación; ésta abortará el arranque si `ADMIN_PASS` permanece en
`changeme`. Mantener estas claves fuera del control de versiones y rotarlas
periódicamente.

`SESSION_EXPIRE_MINUTES` define cuánto tiempo permanece válida una sesión.
El valor recomendado de `1440` mantiene la sesión durante un día. Al expirar,
el usuario debe volver a autenticarse. Valores más altos reducen la frecuencia
de inicio de sesión pero incrementan el riesgo ante robo de cookies; valores
más bajos obligan a reautenticarse con mayor frecuencia y elevan la seguridad.

## Botonera

La interfaz presenta una botonera fija sobre el chat con accesos rápidos:

- **Adjuntar Excel** abre el modal de carga de listas de precios.
- **Proveedores** muestra la gestión básica de proveedores (listar y crear).
- **Productos** abre un panel para buscar en la base, ajustar stock y gestionar canónicos: permite editar fichas canónicas y vincular equivalencias manualmente. Los resultados se cargan bajo demanda al desplazarse gracias a `react-window`.

La barra queda visible al hacer scroll y usa un estilo mínimo con sombreado suave.

## Modo oscuro

El frontend define un esquema de color gris con acentos violeta (`#7C4DFF`) y verde (`#22C55E`).
Un botón en la barra permite alternar el tema y, por defecto, se respeta `prefers-color-scheme` del sistema.

## Contrato del Chat (DEV)

- **HTTP**: `POST /chat` con cuerpo `{ "text": "hola" }` → responde `{ "role": "assistant", "text": "..." }`.
- **WebSocket**: se envía texto plano y cada mensaje recibido es un JSON `{ "role": "assistant", "text": "..." }`. El servidor agrega pings periódicos `{ "role": "ping" }` para mantener viva la conexión y la cierra tras 60 s sin actividad; el cliente los descarta y reintenta con backoff exponencial si se pierde el canal.
- **Sesión**: si la cookie `growen_session` está presente, el backend incluye el nombre y rol del usuario en el prompt para personalizar la respuesta de la IA.
- **Proveedor**: Ollama es el motor por defecto (`OLLAMA_MODEL=llama3.1`). El backend intenta primero con `stream=False` y, si la API falla, cae a modo *streaming* acumulando las partes. En ambos casos normaliza la respuesta y remueve prefijos como `ollama:` antes de reenviarla.

La interfaz muestra las respuestas del asistente con la etiqueta visual **Growen**.

## Importación de listas de precios

Flujo básico: **upload → preview → commit**.

La API permite subir archivos de proveedores en formato `.xlsx` para revisar y aplicar nuevas listas de precios.

1. `POST /suppliers/{supplier_id}/price-list/upload` recibe el archivo del proveedor (campo `file` en `multipart/form-data`) y un parámetro `dry_run` (por defecto `true`). Es obligatorio que el proveedor exista y tenga un *parser* registrado.
2. `GET /imports/{job_id}/preview?status=new,changed&page=1&page_size=50` lista las filas normalizadas filtradas por `status` y paginadas. La respuesta devuelve `{items, summary, total, pages, page}` y permite inspeccionar también `status=error,duplicate_in_file` para los fallos. Durante esta vista previa es posible crear o editar productos canónicos y vincular equivalencias manualmente desde cada fila.
3. `POST /imports/{job_id}/commit` aplica los cambios, creando categorías, productos y relaciones en `supplier_products`.

Cada proveedor define su mapeo en `config/suppliers/*.yml`. Por cada archivo se genera automáticamente un `GenericExcelParser`.
También pueden agregarse parsers especializados instalando paquetes que expongan un `entry_point` en el grupo `growen.suppliers.parsers`.
Para depurar los parsers habilitados se puede llamar a `GET /debug/imports/parsers`, disponible solo para administradores y deshabilitado en producción.

| Proveedor | Configuración |
|-----------|---------------|
| `santa-planta` | `config/suppliers/santa-planta.yml` |

En modo *dry-run* se puede revisar el contenido antes de confirmar los cambios definitivos.

Las tablas `import_jobs` e `import_job_rows` guardan cada archivo cargado y sus filas normalizadas.
`supplier_price_history` registra los cambios de precios para auditoría.
`GET /price-history` permite consultar ese historial filtrando por `supplier_product_id` o `product_id` y admite paginación. Solo está disponible para los roles `cliente`, `proveedor`, `colaborador` y `admin`.

### Plantillas Excel

`GET /suppliers/price-list/template` devuelve una plantilla genérica con la hoja `data` y los encabezados:
`ID`, `Agrupamiento`, `Familia`, `SubFamilia`, `Producto`, `Compra Minima`, `Stock`, `PrecioDeCompra`, `PrecioDeVenta`.
`GET /suppliers/{supplier_id}/price-list/template` genera la misma estructura pero permite personalizar el nombre del archivo según el proveedor.
Ambas rutas requieren un rol válido (`cliente`, `proveedor`, `colaborador` o `admin`).
La celda `A1` incluye una nota con instrucciones y la fila 2 trae un ejemplo. En el modal de carga hay un botón **Descargar plantilla genérica** que llama a `GET /suppliers/price-list/template` y otro **Descargar plantilla** que usa `GET /suppliers/{supplier_id}/price-list/template` para obtener el archivo específico antes de completar los datos.

### Adjuntar Excel desde el chat

La interfaz de chat incluye un botón **+** y la opción de la botonera **Adjuntar Excel** para subir listas de precios sin pasar por la IA.

1. Hacer clic en **Adjuntar Excel** o arrastrar un archivo `.xlsx` sobre la ventana.
2. El modal exige elegir un proveedor; si no existen proveedores se muestra un estado vacío con el botón **Crear proveedor**.
3. Tras seleccionar proveedor y archivo, el frontend llama a `POST /suppliers/{supplier_id}/price-list/upload?dry_run=true`.
4. Growen envía un mensaje de sistema con el `job_id` y abre un visor que pagina las filas llamando a `GET /imports/{job_id}/preview`, mostrando el total de filas, la página actual y el número de páginas devueltos por la API.
5. El visor abre la pestaña **Cambios** por defecto para resaltar las variaciones y muestra el recuento en cada pestaña; desde allí se pueden filtrar errores y finalmente ejecutar `POST /imports/{job_id}/commit`.

Errores comunes:

- **400** columnas faltantes.
- **413** tamaño excedido (límite `MAX_UPLOAD_MB`).

## Productos Canónicos y Equivalencias

Para comparar precios entre proveedores se introduce un catálogo propio de productos canónicos. Cada oferta de un proveedor puede
vincularse a uno de estos canónicos mediante *equivalencias*.
El frontend ofrece los componentes **CanonicalForm** y **EquivalenceLinker** para crear o editar canónicos y asociar ofertas directamente desde la interfaz.

- **Crear canónico**: `POST /canonical-products` con `name`, `brand` y `specs_json` opcional. El sistema genera `ng_sku` con el
  formato `NG-000001`.
- **Buscar canónicos**: `GET /canonical-products?q=&page=` permite paginar y filtrar.
- **Detalle/edición**: `GET /canonical-products/{id}` y `PATCH /canonical-products/{id}` devuelven y actualizan un canónico.
- **Vincular oferta**: `POST /equivalences` une un `supplier_product` existente con un `canonical_product`.
- **Listar equivalencias**: `GET /equivalences?supplier_id=&canonical_product_id=` soporta filtros y paginación.
- **Eliminar equivalencia**: `DELETE /equivalences/{id}`.
- **Comparador**: `GET /canonical-products/{id}/offers` ordena las ofertas por precio de venta y marca la mejor con `mejor_precio`.

## Comparativa de precios

El endpoint `GET /canonical-products/{id}/offers` devuelve todas las ofertas vinculadas a un canónico ordenadas por precio, destacando el mejor con el campo `mejor_precio`. Desde la interfaz se accede a esta tabla desde el visor de importación y el panel de productos cuando el artículo tiene una equivalencia canónica.

Variables de entorno relevantes:

```env
AUTO_CREATE_CANONICAL=true
FUZZY_SUGGESTION_THRESHOLD=0.87
SUGGESTION_CANDIDATES=3
```

Estas opciones controlan la creación automática y las sugerencias durante la
importación de listas. Las coincidencias se calculan con `rapidfuzz` y solo se
aceptan si superan el umbral `FUZZY_SUGGESTION_THRESHOLD`.

## Consulta de productos

`GET /products` lista los productos disponibles con filtros, orden y paginación. Requiere los roles `cliente`, `proveedor`, `colaborador` o `admin`.

Parámetros soportados:

- `supplier_id`: filtra por proveedor.
- `category_id`: filtra por categoría interna.
- `q`: búsqueda parcial por nombre del producto o título del proveedor.
- `page` y `page_size`: paginación (por defecto `1` y `20`).
- `sort_by`: `updated_at`, `precio_venta`, `precio_compra` o `name`.
- `order`: `asc` o `desc`.

Si se envían otros valores en `sort_by` u `order`, la API responde `400 Bad Request`.

Ejemplo de respuesta:

```json
{
  "page": 1,
  "page_size": 20,
  "total": 1,
  "items": [
    {
      "product_id": 1,
      "name": "Carpa Indoor 80x80",
      "supplier": {"id": 1, "slug": "santa-planta", "name": "Santa Planta"},
      "precio_compra": 10000.0,
      "precio_venta": 12500.0,
      "compra_minima": 1,
      "category_path": "Carpas>80x80",
      "stock": 0,
      "updated_at": "2025-08-15T20:33:00Z"
    }
  ]
}
```

Este endpoint se utiliza para consultar el catálogo existente desde el frontend.

Para modificar el stock manualmente existe `PATCH /products/{id}/stock` con cuerpo `{ "stock": <int> }`.

## Historial de precios

`GET /price-history` devuelve el historial de precios ordenado por fecha. Debe recibirse `supplier_product_id` o `product_id` y se puede paginar con `page` y `page_size`. Requiere los roles `cliente`, `proveedor`, `colaborador` o `admin`.

## Inicio rápido (1‑clic)

Levanta API y frontend al mismo tiempo.

### Windows

Ejecutar **desde CMD** con doble clic en `start.bat`. El script realiza estas etapas:

1. Llama a `scripts\stop.bat` y espera hasta 5 s para liberar procesos anteriores.
2. Verifica que los puertos **8000** y **5173** estén libres; si alguno está ocupado aborta con un mensaje.
3. Comprueba que existan `python` y `npm`, luego ejecuta `scripts\fix_deps.bat` para crear la venv, instalar dependencias y preparar el frontend.
4. Abre dos ventanas:
   - Growen API (Uvicorn) en http://127.0.0.1:8000/docs
   - Growen Frontend (Vite) en http://127.0.0.1:5173/

La salida de ambos servicios se guarda en `logs/backend.log` y `logs/frontend.log` para facilitar el diagnóstico. Además, las acciones de los scripts quedan registradas con timestamp en `logs/start.log`, `logs/stop.log` y `logs/fix_deps.log`.

Requisitos previos:

- Python 3.11
- venv creado (`python -m venv .venv`)
- Node.js/npm instalados
- `.env` completado (DB_URL, IA, etc.)
- `frontend/.env` creado a partir de `frontend/.env.example` si se necesita ajustar `VITE_API_URL`.

El script verifica automáticamente que `python` y `npm` estén disponibles antes de iniciar.

Para detener manualmente los servicios, ejecutar `scripts\stop.bat` desde CMD; cierra los procesos de Uvicorn y Vite y escribe su log en `logs/stop.log`.

Rutas con espacios soportadas (los scripts usan `cd /d` y comillas).

PowerShell no requerido (los scripts son CMD puro).

### Debian/Ubuntu

```bash
chmod +x start.sh
./start.sh
```

**Requisitos previos**: entorno virtual creado (`python -m venv .venv`), `pip install -e .`, Node.js instalado y `.env` con `DB_URL` y `OLLAMA_MODEL=llama3.1`. El backend escucha en `http://localhost:8000` y el frontend en `http://localhost:5173`.

En Windows puede aparecer un aviso de firewall; permitir el acceso para ambos puertos. Si alguna de las aplicaciones no inicia, verificar que los puertos 8000 y 5173 estén libres.

**Modelos Ollama**: instalar [Ollama](https://ollama.com/download) y ejecutar `ollama pull llama3.1`. Si la descarga falla, probar con `ollama pull llama3` u otra variante disponible. La variable `OLLAMA_MODEL` apunta por defecto a `llama3.1`.

## Instalación con Docker

```bash
docker compose up --build
```
Levanta PostgreSQL, API en `:8000` y frontend en `:5173`.

## Migraciones (Alembic)

Las migraciones se administran con Alembic usando la carpeta `db/migrations`. El archivo `env.py` carga automáticamente las
variables definidas en `.env`, por lo que no es necesario configurar la URL en `alembic.ini`.

```bash
cp .env.example .env   # en Windows usar: copy .env.example .env
# Completar DB_URL, SECRET_KEY y las credenciales ADMIN_USER/ADMIN_PASS en .env
alembic -c ./alembic.ini upgrade head

# Crear una nueva revisión a partir de los modelos
alembic -c ./alembic.ini revision -m "descripcion" --autogenerate

# Aplicar las migraciones pendientes
alembic -c ./alembic.ini upgrade head

# Revertir la última migración
alembic -c ./alembic.ini downgrade -1
```

## Variables de entorno

Consulta `.env.example` para la lista completa. Variables destacadas:

- `DB_URL`: URL de PostgreSQL (si la contraseña tiene caracteres reservados, encodéalos, ej.: `=` → `%3D`).
- `AI_MODE`: `auto`, `openai` u `ollama`.
- `AI_ALLOW_EXTERNAL`: si es `false`, solo se usa Ollama.
- `OLLAMA_URL`: URL base de Ollama (por defecto `http://localhost:11434`).
- `OLLAMA_MODEL`: modelo de Ollama (por defecto `llama3.1`).
- `OPENAI_API_KEY`, `OPENAI_MODEL`.
- `SECRET_KEY`: clave usada para firmar sesiones; debe cambiarse del valor
  por defecto `changeme`, rotarse periódicamente y mantenerse fuera del
  control de versiones. El servidor se detiene si no se sobrescribe.
- `SESSION_EXPIRE_MINUTES`: tiempo de expiración de la sesión en minutos (por
  defecto 1440 = 1 día). Incrementarlo prolonga las sesiones pero aumenta el
  riesgo ante robo de cookies; reducirlo fuerza reautenticaciones más frecuentes
  y eleva la seguridad.
- `COOKIE_SECURE`: activa cookies seguras; se ignora en producción donde siempre están habilitadas.
- `ALLOWED_ORIGINS`: orígenes permitidos para CORS, separados por coma. Si se
  incluye `http://localhost` o `http://127.0.0.1` se habilita automáticamente su
  contraparte con el mismo puerto.
- `LOG_LEVEL`: nivel de logging de la aplicación (`DEBUG`, `INFO`, etc.).
- `DEBUG_SQL`: si vale `1`, SQLAlchemy mostrará cada consulta ejecutada.
 - `ADMIN_USER`, `ADMIN_PASS`: credenciales del administrador inicial definidas en `.env` (copiado desde `.env.example`). Si
   `ADMIN_PASS` queda en `changeme`, la aplicación aborta el inicio.
- `MAX_UPLOAD_MB`: tamaño máximo de archivos a subir.
- `AUTH_ENABLED`: si es `true`, requiere sesión autenticada.
- `PRODUCTS_PAGE_MAX`: límite máximo de resultados por página.
- `PRICE_HISTORY_PAGE_SIZE`: tamaño por defecto al paginar el historial de precios.

## Endpoints de diagnóstico

Para verificar el estado del servicio se exponen las siguientes rutas, disponibles únicamente para administradores y omitidas en producción:

- `GET /healthz`: responde `{"status":"ok"}` si la app está viva.
- `GET /debug/db`: ejecuta `SELECT 1` contra la base de datos.
- `GET /debug/config`: muestra `ALLOWED_ORIGINS` y la `DB_URL` sin contraseña.
- `GET /debug/imports/parsers`: enumera los parsers registrados para las importaciones.

## Comandos y chat

En el chat o vía API se pueden usar:

- `/help`
- `/sync pull --dry-run`
- `/sync push --dry-run`
- `/stock adjust --sku=SKU --qty=5`
- `/import last --apply`
- `/search maceta`

La ruta `GET /actions` devuelve acciones rápidas.

## Flujo de chat e intents

El endpoint de chat y el WebSocket analizan cada mensaje para detectar comandos.

1. Si el texto corresponde a un intent conocido, se ejecuta el handler asociado y se retorna una respuesta estructurada.
2. Cuando el intent es desconocido, se invoca `AIRouter.run` con la tarea `Task.SHORT_ANSWER` para generar una contestación libre mediante IA.

El WebSocket utiliza la misma lógica para cada mensaje entrante y, ante una desconexión del cliente (`WebSocketDisconnect`), Starlette cierra el canal automáticamente, por lo que el servidor no invoca `close()` manualmente.

Cuando el proveedor de IA elegido no soporta la tarea solicitada, el ruteador registra una advertencia y cambia a **Ollama** como alternativa.

## Carga de catálogo desde proveedores (ingesta)

Permite subir archivos `.csv` o `.xlsx` de distintos proveedores para poblar el catálogo interno.

- El stock inicial siempre se crea en `0`.
- Los campos se normalizan según mapeos en `config/suppliers/*.yml`.
- Se puede ejecutar desde el chat o por CLI:

```bash
python -m cli.ng ingest file datos.xlsx --supplier default --dry-run
```

Con `--dry-run` se generan reportes en `data/reports/` sin tocar la base. Al aplicar sin ese flag se insertan/actualizan productos y variantes.

Si el archivo no incluye SKU ni GTIN se genera uno interno estable. Las categorías y marcas se crean si no existen y los productos quedan en estado `draft` por defecto.

### Ingesta Santa Planta (mensual)

1. En el chat adjuntá el Excel `ListaPrecios_export_XXXX.xlsx`.
2. Growen detecta automáticamente el proveedor y ejecuta un *dry-run*.
3. Revisá los reportes generados en `data/reports/`.
4. Para aplicar los cambios ejecutá `/import last --apply` en el chat o:

```bash
python -m cli.ng ingest file ListaPrecios_export_XXXX.xlsx --supplier santa-planta --dry-run
python -m cli.ng ingest last --apply
```

### Historial de precios

Cada ingestión registra los precios de compra y venta en la tabla `supplier_price_history` con las variaciones porcentuales respecto del último valor conocido.

### Stock

Los productos tienen la columna `stock` en `products` con valor inicial `0`.
La importación de listas de precios no modifica este valor; se ajusta manualmente desde el buscador o vía API.

## Gestión de proveedores

Desde la botonera puede abrirse un modal que lista los proveedores actuales y permite crear nuevos ingresando **Nombre** y **Slug**. El slug debe ser único y se utiliza para asociar parsers y archivos, por lo que conviene mantenerlo estable.

La API expone endpoints para administrar proveedores externos:

- `GET /suppliers` lista todos los proveedores con la cantidad de archivos cargados. Requiere rol `cliente`, `proveedor`, `colaborador` o `admin`.
- `POST /suppliers` crea un nuevo proveedor validando que el `slug` sea único.
- `PATCH /suppliers/{id}` actualiza el nombre de un proveedor existente.
- `GET /suppliers/{id}/files` muestra los archivos cargados por un proveedor. Requiere rol `cliente`, `proveedor`, `colaborador` o `admin`.

Estos recursos facilitan la organización de las distintas listas de precio y su historial.

## Categorías desde proveedor

Se puede proponer y generar la jerarquía de categorías a partir de un archivo de proveedor:

```bash
POST /categories/generate-from-supplier-file
{
  "file_id": 1,
  "dry_run": true
}
```

Con `dry_run=true` solo se informa qué rutas de categoría se detectarían. Si se envía `dry_run=false`, las categorías faltantes se crean respetando la jerarquía `parent_id`.

Además, `GET /categories` lista las categorías con su ruta completa y `GET /categories/search?q=` permite búsquedas parciales.

## IA híbrida

La política por defecto utiliza:

- **Ollama** para NLU y respuestas cortas.
- **OpenAI** para generación de contenido.

Instala [Ollama](https://ollama.com/download) y descarga el modelo configurado. Para deshabilitar proveedores externos establece `AI_ALLOW_EXTERNAL=false`.

## Pruebas manuales E2E

Para comprobar las mutaciones desde el navegador se documentan pruebas manuales en [tests/manual/e2e-mutations.md](tests/manual/e2e-mutations.md).

## CLI

```bash
python -m cli.ng db-init
```

## Roadmap

- M0: estructura base y stubs (este repositorio)
- M1: sincronización real con Tiendanube
- M2: mejoras de IA y comandos
- M3: despliegue completo

Contribuciones y feedback son bienvenidos.
