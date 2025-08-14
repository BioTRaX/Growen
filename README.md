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
