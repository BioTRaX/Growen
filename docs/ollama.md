<!-- NG-HEADER: Nombre de archivo: ollama.md -->
<!-- NG-HEADER: Ubicación: docs/ollama.md -->
<!-- NG-HEADER: Descripción: Integración y uso de Ollama como proveedor LLM local -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Ollama – Proveedor LLM Local

Este proyecto puede usar un daemon local de [Ollama](https://ollama.com/) para ejecutar modelos Llama / compatibles sin enviar datos a servicios externos.

## Instalación

Windows / macOS / Linux: seguir instrucciones en https://ollama.com/download

Verificar:
```powershell
ollama --version
```

## Descarga de un modelo
Ejemplos:
```powershell
ollama pull llama3.1
ollama pull llama3
ollama pull codellama
```

Listar modelos instalados:
```powershell
ollama list
```

## Variables de entorno soportadas
| Variable | Descripción | Default |
|----------|-------------|---------|
| OLLAMA_HOST | URL base del daemon | http://127.0.0.1:11434 |
| OLLAMA_MODEL | Nombre del modelo a usar | llama3.1 |
| OLLAMA_TIMEOUT | Timeout segundos de la request | 120 |
| OLLAMA_STREAM | 1 para streaming token a token | 0 |
| OLLAMA_TEMPERATURE | Temperatura generación | 0.7 |
| OLLAMA_MAX_TOKENS | Límite de tokens generados | 512 |
| OLLAMA_DEBUG | 1 para log ligero de latencia | 0 |

## Uso desde el código
El provider `OllamaProvider` realiza POST a `/api/generate`.

Ejemplo rápido (scripting):
```python
import requests
payload = {"model": "llama3.1", "prompt": "Hola, resume esto:", "stream": False}
print(requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=120).json()["response"])
```

Streaming manual:
```python
import requests, json
r = requests.post("http://127.0.0.1:11434/api/generate", json={"model": "llama3.1", "prompt": "Hola", "stream": True}, stream=True)
for line in r.iter_lines():
    if not line: continue
    data = json.loads(line)
    if 'response' in data:
        print(data['response'], end='', flush=True)
    if data.get('done'): break
print()  # newline final
```

## Integración con el router de IA
`ai/router.py` incluye `OllamaProvider` y selecciona proveedor según la política en `policy.py`. Si `AI_ALLOW_EXTERNAL=false`, se forzará Ollama para tareas que de otro modo irían a OpenAI.

## Troubleshooting
- 404 / conexión rechazada: confirmar daemon corriendo (ejecutar `ollama run llama3.1` una vez).
- Latencia alta inicial: primer prompt precalienta el modelo (carga en RAM / VRAM). Repetir para medir latencia real.
- Memoria insuficiente: usar un modelo más pequeño o variante cuantizada (`llama3.1:8b` vs `70b`).
- Token limit alcanzado: ajustar `OLLAMA_MAX_TOKENS`.

## Criterios de aceptación
- Petición simple devuelve texto (no excepción).
- Streaming entrega tokens incrementales si `OLLAMA_STREAM=1`.
- Variables de entorno modifican comportamiento sin reinstrumentar código.
- Documentación actualizada (este archivo referenciado en README o dependencies).
