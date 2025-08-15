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

En desarrollo, Vite proxya `/ws`, `/chat` y `/actions` hacia `http://localhost:8000`, evitando errores de CORS. El backend solo acepta orígenes `http://localhost:5173` y `http://127.0.0.1:5173`, por lo que la UI debe abrirse en esa dirección. El chat abre un WebSocket en `/ws` y, si no está disponible, utiliza `POST /chat`, que admite la variante con o sin barra final para evitar redirecciones 307. Para modificar las URLs se puede crear `frontend/.env.development` con `VITE_WS_URL` y `VITE_API_BASE`.

## Inicio rápido (1‑clic)

Levanta API y frontend al mismo tiempo.

### Windows

- **CMD**: doble clic en `start.bat`.
- **PowerShell**: `./start.ps1` (si `ExecutionPolicy` lo bloquea: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`).

`start.bat` ejecuta primero `stop.bat` para liberar los puertos `8000` y `5173`,
valida que sigan libres y luego inicia backend y frontend en ventanas
separadas con `cmd /k`. Toda la salida se muestra en consola y se agrega a
`logs/server.log` con marca temporal. Tras unos segundos se realiza una
petición con `curl` para confirmar que respondan.

Las versiones recientes de `start.bat` soportan rutas con espacios porque las
envuelven en comillas simples al invocar PowerShell. Si aun así aparecen
problemas, prueba con `start.ps1` o mueve el repositorio a una ruta sin
espacios. El script utiliza PowerShell y un mal escape de comillas puede
impedir el arranque.

- **Backend**: `http://localhost:8000/docs`
- **Frontend**: `http://localhost:5173/`

En consola se muestran mensajes `[OK]` o `[ERROR]` según el estado y las
ventanas permanecen abiertas incluso si ocurre un fallo. El resultado de cada
inicio queda registrado en `logs/server.log` con entradas como
`[YYYY-MM-DD HH:MM:SS] START backend: OK`.

Para detener los servicios usar `stop.bat` (CMD) o `stop.ps1` (PowerShell);
ambos cierran los procesos en `8000` y `5173` y registran la acción en el
mismo archivo de log.

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
