# Growen

Agente para gestión de catálogo y stock de Nice Grow con interfaz de chat web e IA híbrida.

## Arquitectura

- **Backend**: FastAPI + WebSocket.
- **Base de datos**: PostgreSQL 15 (Alembic para migraciones).
- **IA**: ruteo automático entre Ollama (local) y OpenAI.
- **Frontend**: React + Vite.
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
# las variables de entorno se cargan automáticamente desde .env
# crear base de datos growen en PostgreSQL
alembic -c ./alembic.ini upgrade head
uvicorn services.api:app --reload
```

### Permisos mínimos en esquema

Para evitar errores como `permiso denegado al esquema public`, el usuario de la base de datos debe contar con permisos sobre el esquema `public`:

```sql
ALTER DATABASE growen OWNER TO growen;
GRANT USAGE, CREATE ON SCHEMA public TO growen;
```

## Instalación Frontend

```bash
cd frontend
npm install
npm run dev
```

En desarrollo, Vite proxya `/ws`, `/chat` y `/actions` hacia `http://localhost:8000`, evitando errores de CORS. Durante el arranque pueden mostrarse errores de proxy WebSocket si la API aún no está disponible; una vez arriba, la conexión se restablece sola. El chat abre un WebSocket en `/ws` y, si no está disponible, utiliza `POST /chat`, que admite la variante con o sin barra final para evitar redirecciones 307. Para modificar las URLs se puede crear `frontend/.env.development` con `VITE_WS_URL` y `VITE_API_BASE`.

## Botonera

La interfaz presenta una botonera fija sobre el chat con accesos rápidos:

- **Adjuntar Excel** abre el modal de carga de listas de precios.
- **Proveedores** muestra la gestión básica de proveedores (listar y crear).
- **Productos** despliega un panel de consulta aún en construcción.

La barra queda visible al hacer scroll y usa un estilo mínimo con sombreado suave.

## Contrato del Chat (DEV)

- **HTTP**: `POST /chat` con cuerpo `{ "text": "hola" }` → responde `{ "role": "assistant", "text": "..." }`.
- **WebSocket**: se envía texto plano y cada mensaje recibido es un JSON `{ "role": "assistant", "text": "..." }`.
- **Proveedor**: Ollama es el motor por defecto (`OLLAMA_MODEL=llama3.1`). El backend intenta primero con `stream=False` y, si la API falla, cae a modo *streaming* acumulando las partes. En ambos casos normaliza la respuesta y remueve prefijos como `ollama:` antes de reenviarla.

La interfaz muestra las respuestas del asistente con la etiqueta visual **Growen**.

## Importación de listas de precios

La API permite subir archivos de proveedores en formatos `.xlsx` o `.csv` para revisar y aplicar nuevas listas de precios.

1. `POST /suppliers/{supplier_id}/price-list/upload` recibe el archivo del proveedor y un parámetro `dry_run` (por defecto `true`). Es obligatorio que el proveedor exista y tenga un *parser* registrado.
2. `GET /imports/{job_id}?limit=N` muestra las primeras `N` filas analizadas y los errores detectados (`N` por defecto es `50`).
3. `POST /imports/{job_id}/commit` aplica los cambios, creando categorías, productos y relaciones en `supplier_products`.

Cada proveedor tiene su propio formato de planilla. Los *parsers* disponibles se registran en `SUPPLIER_PARSERS`.

| Proveedor | Campos requeridos | Campos normalizados |
|-----------|------------------|---------------------|
| `santaplanta` | ID, Producto, Agrupamiento, Familia, SubFamilia, Compra Minima, PrecioDeCompra, PrecioDeVenta | codigo, nombre, categoria_path, compra_minima, precio_compra, precio_venta |

En modo *dry-run* se puede revisar el contenido antes de confirmar los cambios definitivos.

### Adjuntar Excel desde el chat

La interfaz de chat incluye un botón **+** y la opción de la botonera **Adjuntar Excel** para subir listas de precios sin pasar por la IA.

1. Hacer clic en **Adjuntar Excel** o arrastrar un archivo `.xlsx`/`.csv` sobre la ventana.
2. El modal exige elegir un proveedor; si no existen proveedores se muestra un estado vacío con el botón **Crear proveedor**.
3. Tras seleccionar proveedor y archivo, el frontend llama a `POST /suppliers/{supplier_id}/price-list/upload?dry_run=true`.
4. Growen envía un mensaje de sistema con el `job_id` y abre un visor para revisar el *dry-run*.
5. Desde el visor se puede explorar la previsualización y los errores paginados y luego ejecutar `POST /imports/{job_id}/commit`.

Errores comunes:

- **400** columnas faltantes.
- **413** tamaño excedido (límite `MAX_UPLOAD_MB`).

## Consulta de productos

`GET /products` lista los productos disponibles con filtros, orden y paginación.

Parámetros soportados:

- `supplier_id`: filtra por proveedor.
- `category_id`: filtra por categoría interna.
- `q`: búsqueda parcial por nombre.
- `page` y `page_size`: paginación (por defecto `1` y `20`).
- `sort_by`: `updated_at`, `precio_venta`, `precio_compra` o `name`.
- `order`: `asc` o `desc`.

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
      "supplier": {"id": 1, "slug": "santaplanta", "name": "Santa Planta"},
      "precio_compra": 10000.0,
      "precio_venta": 12500.0,
      "compra_minima": 1,
      "category_path": "Carpas>80x80",
      "updated_at": "2025-08-15T20:33:00Z"
    }
  ]
}
```

Este endpoint se utiliza para consultar el catálogo existente desde el frontend.

## Inicio rápido (1‑clic)

Levanta API y frontend al mismo tiempo.

### Windows

Doble clic en `start.bat` → abre dos ventanas:

`start.bat` ejecuta previamente `fix_deps.bat` para asegurar que las dependencias de `pyproject.toml` estén instaladas en `.venv`.

- Growen API (Uvicorn) en http://127.0.0.1:8000/docs
- Growen Frontend (Vite) en http://127.0.0.1:5173/

Requisitos previos:

- Python 3.11
- venv creado (`python -m venv .venv`)
- Node.js/npm instalados
- `.env` completado (DB_URL, IA, etc.)

Para detener:

- Doble clic en `stop.bat` → libera puertos 8000/5173.

Rutas con espacios soportadas (scripts usan `cd /d` y comillas).

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
# Completar DB_URL en .env
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

- `DB_URL`: URL de PostgreSQL.
- `AI_MODE`: `auto`, `openai` u `ollama`.
- `AI_ALLOW_EXTERNAL`: si es `false`, solo se usa Ollama.
- `OLLAMA_HOST`, `OLLAMA_MODEL` (por defecto `llama3.1`).
- `OPENAI_API_KEY`, `OPENAI_MODEL`.
- `SECRET_KEY`: clave usada para firmar sesiones.
- `SESSION_EXPIRE_MINUTES`: tiempo de expiración de la sesión.
- `COOKIE_SECURE`: activa cookies seguras en producción.
- `ALLOWED_ORIGINS`: orígenes permitidos para CORS, separados por coma. Si se
  incluye `http://localhost` o `http://127.0.0.1` se habilita automáticamente su
  contraparte con el mismo puerto.
- `ADMIN_USER`, `ADMIN_PASS`: credenciales del administrador inicial.
- `MAX_UPLOAD_MB`: tamaño máximo de archivos a subir.
- `AUTH_ENABLED`: si es `true`, requiere sesión autenticada.
- `PRODUCTS_PAGE_MAX`: límite máximo de resultados por página.

## Comandos y chat

En el chat o vía API se pueden usar:

- `/help`
- `/sync pull --dry-run`
- `/sync push --dry-run`
- `/stock adjust --sku=SKU --qty=5`

La ruta `GET /actions` devuelve acciones rápidas.

## Flujo de chat e intents

El endpoint de chat y el WebSocket analizan cada mensaje para detectar comandos.

1. Si el texto corresponde a un intent conocido, se ejecuta el handler asociado y se retorna una respuesta estructurada.
2. Cuando el intent es desconocido, se invoca `AIRouter.run` con la tarea `Task.SHORT_ANSWER` para generar una contestación libre mediante IA.

El WebSocket utiliza la misma lógica para cada mensaje entrante y cierra la conexión de forma limpia ante una desconexión del cliente.

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

El catálogo base ingresa con `stock_qty=0` en `inventory`. La sincronización de stock con proveedores se agregará más adelante.

## Gestión de proveedores

Desde la botonera puede abrirse un modal que lista los proveedores actuales y permite crear nuevos ingresando **Nombre** y **Slug**. El slug debe ser único y se utiliza para asociar parsers y archivos, por lo que conviene mantenerlo estable.

La API expone endpoints para administrar proveedores externos:

- `GET /suppliers` lista todos los proveedores con la cantidad de archivos cargados.
- `POST /suppliers` crea un nuevo proveedor validando que el `slug` sea único.
- `PATCH /suppliers/{id}` actualiza el nombre de un proveedor existente.
- `GET /suppliers/{id}/files` muestra los archivos cargados por un proveedor.

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
