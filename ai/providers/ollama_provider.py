# NG-HEADER: Nombre de archivo: ollama_provider.py
# NG-HEADER: Ubicación: ai/providers/ollama_provider.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Proveedor local Ollama real (HTTP API).

Integra con el daemon de Ollama (por defecto en http://127.0.0.1:11434)
para generar texto usando modelos Llama u otros compatibles.

Variables de entorno relevantes:
  OLLAMA_HOST         Host/base URL (por defecto http://127.0.0.1:11434)
  OLLAMA_MODEL        Nombre de modelo (por defecto llama3.1)
  OLLAMA_TIMEOUT      Timeout (seg) para la petición completa (defecto 120)
  OLLAMA_STREAM       "1" para streaming token a token (defecto 0 en este provider)

Notas:
 - El endpoint usado es /api/generate (streaming= true/false según config).
 - Si streaming está activo se irán rindiendo fragmentos conforme arriban.
 - Ante errores HTTP se levanta RuntimeError para que el router pueda degradar.
"""
from __future__ import annotations

import json
import os
import time
from typing import Iterable, Generator

import requests

from ..provider_base import ILLMProvider
from ..types import Task


class OllamaProvider(ILLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        # Modelos comunes: llama3.1, llama3, codellama, qwen2, mistral, etc.
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))
        self.stream = os.getenv("OLLAMA_STREAM", "0").lower() in {"1", "true", "yes"}
        self.default_opts = {
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
            "num_predict": int(os.getenv("OLLAMA_MAX_TOKENS", "512")),
        }

    def supports(self, task: str) -> bool:  # simple routing filter
        return task in {Task.NLU_PARSE.value, Task.NLU_INTENT.value, Task.SHORT_ANSWER.value,
                        Task.CONTENT.value, Task.SEO.value, Task.REASONING.value}

    # --- Internal helpers -------------------------------------------------
    def _request_payload(self, prompt: str) -> dict:
        return {
            "model": self.model,
            "prompt": prompt,
            "stream": self.stream,
            "options": self.default_opts,
        }

    def _iter_stream(self, resp: requests.Response) -> Generator[str, None, None]:
        for raw in resp.iter_lines():
            if not raw:
                continue
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if "response" in data:
                yield data["response"]
            if data.get("done"):
                break

    # --- Public API -------------------------------------------------------
    def generate(self, prompt: str) -> Iterable[str]:
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = self._request_payload(prompt)
        started = time.time()
        try:
            if self.stream:
                resp = requests.post(url, json=payload, timeout=self.timeout, stream=True)
                resp.raise_for_status()
                for chunk in self._iter_stream(resp):
                    yield chunk
            else:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                text = data.get("response", "").strip()
                if text:
                    yield text
        except requests.RequestException as e:
            raise RuntimeError(f"Fallo al invocar Ollama: {e}") from e
        finally:
            elapsed = time.time() - started
            # Logging ligero (evitar dependencia de logger global aquí)
            if os.getenv("OLLAMA_DEBUG", "0") in {"1", "true", "yes"}:
                print(f"[ollama] model={self.model} stream={self.stream} elapsed={elapsed:.2f}s")
