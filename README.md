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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# crear base de datos growen en PostgreSQL
alembic upgrade head
uvicorn services.api:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Visita `http://localhost:5173` para el chat.

## Instalación con Docker

```bash
docker compose up --build
```
Levanta PostgreSQL, API en `:8000` y frontend en `:5173`.

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
