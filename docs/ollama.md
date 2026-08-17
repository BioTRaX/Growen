<!-- NG-HEADER: Nombre de archivo: ollama.md -->
<!-- NG-HEADER: Ubicación: docs/ollama.md -->
<!-- NG-HEADER: Descripción: Operación de Ollama local para Chat y RAG. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Ollama local

Growen no envía Chat/RAG a proveedores externos. Producción fija `AI_MODE=ollama`, `AI_ALLOW_EXTERNAL=false`, `OLLAMA_MODEL=llama3.1:8b`, `RAG_EMBEDDING_MODEL=qwen3-embedding:4b` y `RAG_EMBEDDING_DIMENSIONS=1536`.

`OllamaProvider` usa `httpx.AsyncClient` contra `/api/generate`; el servicio de embeddings usa `/api/embed` con `dimensions: 1536`. Daemon ausente, modelo ausente, HTTP inválido, respuesta vacía o dimensión incorrecta fallan cerrado. Nunca se devuelve el prompt como eco.

## Perfil canónico: VRAM prioritaria

En un equipo con GPU NVIDIA dedicada no se exige tener 16 GiB de RAM **libre**.
Ollama intenta cargar el modelo completo en VRAM y `ollama ps` debe informar
`100% GPU`. El perfil de Growen limita el contexto y la concurrencia para evitar
offload a RAM:

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_CONTEXT_LENGTH', '4096', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS', '1', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL', '1', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_KEEP_ALIVE', '30s', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_MAX_QUEUE', '32', 'User')
[Environment]::SetEnvironmentVariable('OLLAMA_NO_CLOUD', '1', 'User')
```

Cerrar Ollama desde el icono de la bandeja y abrirlo nuevamente después de
cambiar variables. `OLLAMA_MAX_LOADED_MODELS=1` hace que generación y embeddings
se alternen; reduce memoria a costa de latencia de carga.

El SSD/pagefile sólo aporta memoria virtual de emergencia. No reemplaza VRAM y
si el modelo se ejecuta desde pagefile la latencia se degrada fuertemente. En
Windows se recomienda pagefile administrado por el sistema o, si es fijo, al
menos 16 GiB iniciales y 32 GiB máximos, seguido de reinicio.

## Preflight obligatorio

Antes de descargar o activar:

- 8 GiB de VRAM libre y verificación posterior `100% GPU`;
- 1,5 GiB de RAM física libre para overhead;
- pagefile automático o fijo de al menos 16 GiB;
- 15 GiB de disco libre;
- puerto 11434 accesible sólo desde host/red Docker;
- modelos exactos presentes, sin sustitución automática;
- health separado de generación y embeddings.

La API expone `GET /health/ollama/generation` y
`GET /health/ollama/embeddings`. Ambos devuelven estado, modelo y latencia; el
segundo también informa la dimensión esperada. Ninguno ejecuta ni registra un
prompt.

El diagnóstico del 2026-08-17 aprobó una RTX 5070 con 12.227 MiB de VRAM,
pagefile de 18 GB, ambos modelos instalados y `llama3.1:8b` cargado `100% GPU`
con contexto 4096. El embedding real devolvió 1536 dimensiones.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\ollama-preflight.ps1
```

Agregar `-RequireModels` después de descargarlos.

## Instalación, descarga y limpieza

Ollama ya está instalado en este host. Iniciarlo desde el menú Inicio y luego:

```powershell
ollama list
ollama pull llama3.1:8b
ollama pull qwen3-embedding:4b
ollama run llama3.1:8b "Respondé solamente OK"
ollama ps
ollama stop llama3.1:8b
```

Para borrar modelos existentes, listar primero y remover nombres exactos. No
borrar manualmente `.ollama/models`, porque los blobs pueden estar compartidos:

```powershell
ollama list
ollama stop NOMBRE_EXACTO
ollama rm NOMBRE_EXACTO
```

La descarga de ambos modelos ocupa cerca de 7,4 GB. Compose usa
`OLLAMA_HOST_DOCKER=http://host.docker.internal:11434`; la API local conserva
`OLLAMA_HOST=http://localhost:11434`.

## Variables

| Variable | Valor productivo |
|---|---|
| `OLLAMA_HOST` | `http://host.docker.internal:11434` desde contenedores |
| `OLLAMA_MODEL` | `llama3.1:8b` |
| `OLLAMA_TIMEOUT` | `120` |
| `OLLAMA_CONTEXT_LENGTH` | `4096` |
| `RAG_EMBEDDING_PROVIDER` | `ollama` |
| `RAG_EMBEDDING_MODEL` | `qwen3-embedding:4b` |
| `RAG_EMBEDDING_DIMENSIONS` | `1536` |

## Validación

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ollama_local.py -q
```

No registrar prompts, respuestas ni URLs con credenciales en health o logs.
