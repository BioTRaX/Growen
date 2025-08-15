"""Proveedor local Ollama."""
from __future__ import annotations

from typing import Iterable

from ..provider_base import ILLMProvider
from ..types import Task


class OllamaProvider(ILLMProvider):
    """Implementa un proveedor que consulta a Ollama.

    Para simplificar los tests se usa un *stub* que antepone ``"ollama:"`` al
    texto, por lo que aquí se limpia dicho prefijo antes de devolver el
    contenido al ruteador de IA.
    """

    name = "ollama"

    def supports(self, task: str) -> bool:
        return task in {Task.NLU_PARSE.value, Task.NLU_INTENT.value, Task.SHORT_ANSWER.value}

    def _call_ollama(self, prompt: str) -> str:
        """Devuelve la respuesta cruda del servicio Ollama.

        En un entorno real debería realizar una petición HTTP al servidor
        configurado. Para los propósitos del repositorio se devuelve un texto
        prefijado que simula la respuesta.
        """

        return f"ollama:{prompt}"

    def generate(self, prompt: str) -> Iterable[str]:
        """Genera texto a partir del ``prompt``.

        Se quita cualquier prefijo ``"ollama:"`` para que el resto de la
        aplicación reciba únicamente el contenido generado.
        """

        text = self._call_ollama(prompt)
        if text.startswith("ollama:"):
            text = text[len("ollama:") :]
        yield text.strip()
