# NG-HEADER: Nombre de archivo: provider.py
# NG-HEADER: Ubicación: services/ai/provider.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Cliente de IA que se conecta a Ollama.

La URL del servicio se lee desde la variable de entorno ``OLLAMA_URL``,
permitiendo apuntar a instancias remotas sin tocar el código.
"""

import json
import os
import logging
import time

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
logger = logging.getLogger(__name__)

try:  # inicializar logging dedicado si habilitado
    from ai.logging_setup import setup_ai_logger
    setup_ai_logger()
except Exception:  # pragma: no cover
    pass


async def ai_reply(prompt: str) -> str:
    """Obtiene una respuesta de Ollama.

    La función primero intenta un request tradicional (`stream=False`).
    Si la API devuelve un error o un cuerpo inválido, cae a modo
    *streaming* acumulando las partes JSONL. En ambos casos se eliminan
    prefijos como ``"ollama:"`` y espacios sobrantes.
    """

    started = time.perf_counter()
    mode = "single"
    text = ""
    prompt_chars = len(prompt)
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            data = r.json()
            text = (data.get("response") or "").strip()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            mode = "stream"
            text_parts = []
            stream_started = time.perf_counter()
            try:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            text_parts.append(obj.get("response") or "")
                        except json.JSONDecodeError:
                            logger.warning("Línea JSON inválida ignorada: %s", line)
            except Exception as stream_exc:  # pragma: no cover defensivo
                logger.error(
                    "ai_reply stream error", extra={
                        "error": str(stream_exc),
                        "mode": mode,
                        "prompt_chars": prompt_chars,
                        "model": OLLAMA_MODEL,
                    }
                )
                raise
            else:
                text = "".join(text_parts).strip()
                logger.info(
                    "ai_reply stream fallback ok",
                    extra={
                        "mode": mode,
                        "prompt_chars": prompt_chars,
                        "stream_duration_ms": int((time.perf_counter() - stream_started) * 1000),
                        "parts": len(text_parts),
                    },
                )
        finally:
            pass

    if text.lower().startswith("ollama:"):
        text = text.split(":", 1)[1].strip()
    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "ai_reply done",
        extra={
            "mode": mode,
            "prompt_chars": prompt_chars,
            "reply_chars": len(text),
            "duration_ms": duration_ms,
            "model": OLLAMA_MODEL,
        },
    )
    return text
