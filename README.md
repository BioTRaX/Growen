# Growen

Agente modular para cultivo y e-commerce.

## Configuración de Base de Datos

1. Crea un archivo `.env` basado en `.env.example` y ajusta las credenciales.
2. Instala las dependencias del proyecto:
   ```bash
   pip install -e .[dev]
   ```
3. Ejecuta las migraciones para crear las tablas:
   ```bash
   python -m cli.ng db init
   ```
4. Verifica la cantidad de registros:
   ```bash
   python -m cli.ng db info
   ```
5. Exporta el catálogo a CSV:
   ```bash
   python -m cli.ng catalog export --out catalogo.csv
   ```
6. Corre los tests:
   ```bash
   pytest
   ```

## Ejecución del servicio API

1. Inicia el backend de desarrollo:
   ```bash
   uvicorn services.api:app --reload
   ```
2. Revisa la salud del servicio visitando `http://localhost:8000/health`.

## Modo de IA híbrido

El proyecto integra dos proveedores de lenguaje:

- **Ollama** (local) para NLU y respuestas cortas.
- **OpenAI** para generación de contenido largo y tareas de SEO.

Configura las variables del archivo `.env` siguiendo `.env.example`.

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
