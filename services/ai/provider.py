"""Cliente de IA que se conecta a Ollama."""

import json
import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


async def ai_reply(prompt: str) -> str:
    """Obtiene una respuesta de Ollama.

    La función primero intenta un request tradicional (`stream=False`).
    Si la API devuelve un error o un cuerpo inválido, cae a modo
    *streaming* acumulando las partes JSONL. En ambos casos se eliminan
    prefijos como ``"ollama:"`` y espacios sobrantes.
    """

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            data = r.json()
            text = (data.get("response") or "").strip()
        except (httpx.HTTPError, json.JSONDecodeError):
            text_parts = []
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
                        # Ignorar líneas que no sean JSON válido.
                        pass
            text = "".join(text_parts).strip()

    if text.lower().startswith("ollama:"):
        text = text.split(":", 1)[1].strip()
    return text
