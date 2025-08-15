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

## Instalación local

Antes de instalar dependencias, `pyproject.toml` debe listar los paquetes o usar un directorio `src/`.
Este repositorio mantiene sus módulos en la raíz, así que es necesario declararlos explícitamente:

```toml
[tool.setuptools.packages.find]
include = ["agent_core", "ai", "cli", "adapters", "services", "db"]
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

## Instalación Frontend

```bash
cd frontend
npm install
npm run dev
```

El backend se ejecuta en `http://localhost:8000` y el frontend en `http://localhost:5173`.

## Instalación con Docker

```bash
docker compose up --build
```
Levanta PostgreSQL, API en `:8000` y frontend en `:5173`.

## Migraciones (Alembic)

Las migraciones se administran con Alembic usando la carpeta `db/migrations`. La URL `DB_URL` se toma automáticamente de `.env` gracias a `python-dotenv`.

```bash
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
- `OLLAMA_HOST`, `OLLAMA_MODEL`.
- `OPENAI_API_KEY`, `OPENAI_MODEL`.

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
