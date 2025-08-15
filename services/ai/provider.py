import httpx
import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


async def ai_reply(prompt: str) -> str:
    """Solicita una respuesta a Ollama y limpia prefijos no deseados."""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt},
        )
        r.raise_for_status()
        data = r.json()
    text = (data.get("response") or "").strip()
    if text.lower().startswith("ollama:"):
        text = text.split(":", 1)[1].strip()
    return text
