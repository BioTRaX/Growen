# Growen

Agente modular para cultivo y e-commerce.

## Configuración de Base de Datos con PostgreSQL

1. Crea un archivo `.env` basado en `.env.example` y ajusta `DB_URL` con las credenciales de tu servidor PostgreSQL. El formato esperado es:
   ```env
   DB_URL=postgresql+psycopg://usuario:clave@localhost:5432/growen
   ```
2. Si no tienes PostgreSQL instalado, puedes levantarlo rápidamente con Docker:
   ```bash
   docker run -d --name growen-db -p 5432:5432 \
     -e POSTGRES_USER=usuario -e POSTGRES_PASSWORD=clave \
     -e POSTGRES_DB=growen postgres:15
   ```
3. Antes del primer uso asegúrate de que exista la base `growen`. Puedes crearla manualmente con `CREATE DATABASE growen;` o dejar que Alembic la cree si el usuario tiene permisos.
4. Instala las dependencias del proyecto:
   ```bash
   pip install -e .[dev]
   ```
5. Ejecuta las migraciones para crear las tablas en PostgreSQL:
   ```bash
   python -m cli.ng db init
   ```
6. Verifica la cantidad de registros:
   ```bash
   python -m cli.ng db info
   ```
7. Exporta el catálogo a CSV:
   ```bash
   python -m cli.ng catalog export --out catalogo.csv
   ```
8. Corre los tests (se usa una base SQLite en memoria):
   ```bash
   pytest
   ```

## Variables de entorno

- `ENV`: entorno de ejecución (`dev` o `prod`). Con `ENV=prod` se deshabilitan operaciones peligrosas como el borrado de tablas.
- `DB_URL`: URL de conexión a PostgreSQL en formato `postgresql+psycopg://usuario:clave@host:5432/base`.
- `TN_CLIENT_ID`, `TN_CLIENT_SECRET`, `TN_ACCESS_TOKEN`, `TN_SHOP_ID`: credenciales de la API de Tiendanube.
- `AI_MODE`: modo de IA (`auto`, `openai` u `ollama`).
- `OLLAMA_HOST`, `OLLAMA_MODEL`: configuración del modelo local.
- `OPENAI_API_KEY`, `OPENAI_MODEL`: configuración para OpenAI.
- `AI_ALLOW_EXTERNAL`: si es `false`, obliga a usar solo el modelo local.

## Ejecución del servicio API

### Desarrollo

```bash
uvicorn services.api:app --reload
```

### Producción

```bash
ENV=prod uvicorn services.api:app --host 0.0.0.0 --port 8000
```
Se recomienda ejecutarlo sin `--reload` y detrás de un proxy web.

Revisa la salud del servicio visitando `http://localhost:8000/health`.

## Integración con Tiendanube

El agente está diseñado para sincronizar el catálogo con una tienda de Tiendanube utilizando las credenciales `TN_*`.

Comandos disponibles:

- `/sync pull --dry-run`: obtener el catálogo sin aplicar cambios.
- `/sync pull --apply`: importar productos y actualizarlos localmente.
- `/sync push --dry-run`: simular el envío de cambios locales.
- `/sync push --apply`: aplicar en Tiendanube los cambios de la base local.
- `/stock adjust --sku=<SKU> --qty=<N>`: ajustar stock localmente para luego sincronizarlo.

Estas acciones se exponen vía API en `/actions` y pueden ejecutarse desde la interfaz de chat o vía HTTP.

## Población inicial de datos

Tras correr las migraciones, la base de datos queda vacía. Puedes:

- Ejecutar `/sync pull --apply` (cuando esté implementado) para importar el catálogo de Tiendanube.
- Insertar registros de prueba manualmente para explorar los endpoints.

## Objetivos del proyecto

- **E-commerce**: almacenar el catálogo de productos y sincronizarlo con la tienda.
- **IA**: combinar Ollama y OpenAI para interpretar comandos y generar contenido.
- **Cultivo**: la arquitectura es modular para integrar sensores y tareas agrícolas en el futuro.

## Uso con Docker (opcional)

### Construcción de la imagen

```bash
docker build -t growen:latest .
```

### Ejecución del contenedor

```bash
docker run --env-file .env -p 8000:8000 growen:latest
```

### Docker Compose (desarrollo)

```bash
docker-compose up --build
```
Inicia la API en `localhost:8000` y PostgreSQL en el puerto `5432`.

## Modo de IA híbrido

El proyecto integra dos proveedores de lenguaje:

- **Ollama** (local) para NLU y respuestas cortas.
- **OpenAI** para generación de contenido largo y tareas de SEO.

### Instalación de Ollama

1. [Descarga Ollama](https://ollama.com/download) para tu plataforma (Debian o Windows).
2. Inicia el servicio y descarga el modelo requerido:
   ```bash
   ollama pull llama3.1:8b-instruct
   ```

### Clave de OpenAI

Si deseas usar el proveedor externo, define `OPENAI_API_KEY` con tu clave.

### Ejemplos de uso

- **Interpretar comando ambiguo** (usa Ollama):
  ```json
  {"message": "¿qué hace /sync?"}
  ```
- **Generar descripción SEO** (usa OpenAI):
  ```json
  {"message": "redactá descripción detallada para SKU X con tono Nice Grow"}
  ```

Si `AI_ALLOW_EXTERNAL=false`, todas las peticiones se procesan con Ollama.
