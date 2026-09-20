# NG-HEADER: Nombre de archivo: ollama_provider.py
# NG-HEADER: Ubicación: ai/providers/ollama_provider.py
# NG-HEADER: Descripción: Proveedor local Ollama asíncrono y fail-closed.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Cliente de generación local para Ollama sin degradación a eco."""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Iterable
from typing import Any

import httpx
import requests

from ..provider_base import ILLMProvider
from ..types import Task


class OllamaUnavailableError(RuntimeError):
    """El daemon o el modelo local no están disponibles."""

    def __init__(self, code: str, *, http_status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = http_status


class OllamaProvider(ILLMProvider):
    name = "ollama"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))
        self.context_length = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "4096"))
        if self.context_length < 512:
            raise ValueError("ollama_context_length_too_small")
        self.stream = os.getenv("OLLAMA_STREAM", "0").lower() in {"1", "true", "yes"}
        self.default_opts = {
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
            "num_predict": int(os.getenv("OLLAMA_MAX_TOKENS", "512")),
            "num_ctx": self.context_length,
        }
        self._client = client

    def supports(self, task: str) -> bool:
        return task in {
            Task.NLU_PARSE.value,
            Task.NLU_INTENT.value,
            Task.SHORT_ANSWER.value,
            Task.CONTENT.value,
            Task.SEO.value,
            Task.REASONING.value,
        }

    def _payload(self, prompt: str, *, stream: bool, images: list[str] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": self.default_opts,
        }
        if images:
            payload["images"] = images
        return payload

    def generate(self, prompt: str) -> Iterable[str]:
        """Compatibilidad síncrona; cualquier fallo local se propaga de forma segura."""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=self._payload(prompt, stream=False),
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = str(response.json().get("response") or "").strip()
            if not text:
                raise OllamaUnavailableError("ollama_empty_response")
            yield text
        except requests.Timeout as exc:
            raise OllamaUnavailableError("timeout") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            raise OllamaUnavailableError("http_error", http_status=status) from exc
        except requests.RequestException as exc:
            raise OllamaUnavailableError("http_error") from exc
        except (ValueError, TypeError) as exc:
            raise OllamaUnavailableError("invalid_json") from exc

    async def generate_async(
        self,
        prompt: str,
        tools_schema: list | None = None,
        user_context: dict | None = None,
        images: list[dict[str, Any]] | list[str] | None = None,
    ) -> str:
        if tools_schema:
            raise OllamaUnavailableError("ollama_tools_not_supported")
        normalized_images = [item for item in (images or []) if isinstance(item, str)]
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=self._payload(prompt, stream=False, images=normalized_images),
            )
            response.raise_for_status()
            text = str(response.json().get("response") or "").strip()
            if not text:
                raise OllamaUnavailableError("ollama_empty_response")
            return text
        except httpx.TimeoutException as exc:
            raise OllamaUnavailableError("timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaUnavailableError("http_error", http_status=exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError("http_error") from exc
        except (ValueError, TypeError) as exc:
            raise OllamaUnavailableError("invalid_json") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def generate_stream_async(self, prompt: str) -> AsyncIterator[str]:
        """Entrega fragmentos NDJSON usando transporte HTTP asíncrono."""
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=self._payload(prompt, stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = str(data.get("response") or "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
        except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise OllamaUnavailableError("ollama_stream_unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def health(self) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=min(self.timeout, 10))
        try:
            response = await client.post(f"{self.base_url}/api/show", json={"model": self.model})
            response.raise_for_status()
            return {"status": "ok", "model": self.model}
        except (httpx.HTTPError, ValueError, TypeError):
            return {"status": "unavailable", "model": self.model, "code": "ollama_generation_unavailable"}
        finally:
            if owns_client:
                await client.aclose()
