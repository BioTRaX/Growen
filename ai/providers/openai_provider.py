# NG-HEADER: Nombre de archivo: openai_provider.py
# NG-HEADER: Ubicación: ai/providers/openai_provider.py
# NG-HEADER: Descripción: Proveedor IA basado en OpenAI.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Proveedor remoto OpenAI.

Implementación real usando la librería oficial ``openai`` (>=1.x). Si falta
``OPENAI_API_KEY`` o ocurre un error de red, se degrada a eco con prefijo
``openai:`` para no romper los tests existentes.

Formato de ``prompt`` recibido: el router actualmente concatena el
``SYSTEM_PROMPT`` + dos saltos de línea + el prompt del usuario.
Separaremos ambos para enviarlos como roles `system` y `user`, lo cual asegura
que el tono/persona se aplique correctamente.
"""
from __future__ import annotations

import os
from typing import Iterable, List, Dict, Any
import json
import httpx
import logging

from ..provider_base import ILLMProvider
from ..types import Task

try:  # Import perezoso para no forzar dependencia si no se usa
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - si la lib no está
    OpenAI = None  # type: ignore


class OpenAIProvider(ILLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY") or ""
        self.model = os.getenv("OPENAI_MODEL", os.getenv("IMPORT_AI_MODEL", "gpt-4.1-mini"))
        # Timeout (segundos) opcional (cae a 60s si no seteado)
        self.timeout = float(os.getenv("AI_TIMEOUT_OPENAI", os.getenv("AI_TIMEOUT_OPENAI_MS", "60000")))
        if self.timeout > 300:  # si viene en ms convertir aproximado
            # heurística: si es >300 asumimos ms
            self.timeout = self.timeout / 1000.0

    def supports(self, task: str) -> bool:  # pragma: no cover - simple set membership
        # Ampliamos soporte para SHORT_ANSWER para que el chat WebSocket pueda
        # forzar OpenAI cuando Ollama está deshabilitado y la política aún
        # mapea la tarea a "ollama". Esto evita un fallback forzado a un
        # proveedor inexistente y permite respuestas consistentes.
        return task in {
            Task.CONTENT.value,
            Task.SEO.value,
            Task.REASONING.value,
            Task.SHORT_ANSWER.value,
        }

    def _split_prompt(self, prompt: str) -> tuple[str, str]:
        """Divide el prompt concatenado en (system, user).

        Busca el primer doble salto de línea. Si no lo encuentra, todo va como
        user y se genera un system mínimo.
        """
        parts = prompt.split("\n\n", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1]
        return "Eres un asistente útil.", prompt

    def generate(self, prompt: str) -> Iterable[str]:
        # Fallback inmediato si falta API key o lib
        if not self.api_key or OpenAI is None:
            yield f"openai:{prompt}"
            return
        system_prompt, user_prompt = self._split_prompt(prompt)
        try:
            client = OpenAI(api_key=self.api_key)
            # Usamos la API de chat no streaming (por simplicidad). Si se
            # necesita streaming, habría que adaptar a `client.chat.completions.create(stream=True, ...)`.
            # Si el prompt exige JSON estricto (como iAVaL), pedimos formato JSON
            wants_json = "Esquema de salida EXACTO:" in user_prompt or "Esquema de salida esperado:" in user_prompt
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
                response_format=(
                    {"type": "json_object"} if wants_json else {"type": "text"}
                ),
            )
            text = resp.choices[0].message.content if resp.choices else ""
            yield f"openai:{text.strip()}"
        except Exception as e:  # pragma: no cover - red/timeout variable
            # Degradar a eco para no romper funcionalidad general
            yield f"openai:{user_prompt}"

    # ------------------------------------------------------------------
    # Tool Calling (MCP Products) --------------------------------------
    # ------------------------------------------------------------------
    def _build_tools_schema(self, user_role: str) -> List[Dict[str, Any]]:
        base_tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "get_product_info",
                    "description": "Obtiene información básica de un producto por SKU interno (name, sale_price, stock, sku).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sku": {"type": "string", "description": "SKU interno exacto del producto"},
                        },
                        "required": ["sku"],
                    },
                },
            }
        ]
        if user_role in {"admin", "colaborador"}:
            base_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "get_product_full_info",
                        "description": "Obtiene información extendida del producto (en el MVP igual a básica) por SKU interno.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "sku": {"type": "string", "description": "SKU interno exacto del producto"},
                            },
                            "required": ["sku"],
                        },
                    },
                }
            )
        return base_tools

    async def chat_with_tools(self, *, prompt: str, user_role: str) -> str:
        """Ejecuta un ciclo de tool-calling con OpenAI y el servidor MCP.

        Flujo:
        1. Primera llamada al modelo con las tools disponibles.
        2. Si responde con `tool_calls`, se invoca el MCP (`http://mcp_products:8001/invoke_tool`).
        3. Se añade el resultado como mensaje de role `tool` y se hace segunda llamada.
        4. Devuelve texto final prefijado `openai:`.

        En caso de errores de red o falta de API key, responde eco prefijado.
        """
        if not self.api_key or OpenAI is None:
            return f"openai:{prompt}"

        system_prompt, user_prompt = self._split_prompt(prompt)
        client = OpenAI(api_key=self.api_key)
        tools = self._build_tools_schema(user_role)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            first = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
        except Exception:
            return f"openai:{user_prompt}"

        choice = first.choices[0] if first.choices else None
        tool_calls = getattr(choice.message, "tool_calls", None) if choice else None
        if not tool_calls:
            content = choice.message.content if choice and choice.message.content else ""
            return f"openai:{content.strip()}"

        # Solo procesamos la primera tool call para este MVP.
        call = tool_calls[0]
        fn_name = call.function.name
        try:
            fn_args = json.loads(call.function.arguments or "{}")
        except Exception:
            fn_args = {}
        # Aseguramos sku presente
        if "sku" not in fn_args or not isinstance(fn_args["sku"], str):
            return f"openai:No pude determinar el SKU solicitado."

        # Invocar MCP
        mcp_payload = {"tool_name": fn_name, "parameters": {"sku": fn_args["sku"], "user_role": user_role}}
        try:
            async with httpx.AsyncClient(timeout=8.0) as http_client:
                mcp_resp = await http_client.post(
                    os.getenv("MCP_PRODUCTS_URL", "http://mcp_products:8001/invoke_tool"), json=mcp_payload
                )
                if mcp_resp.status_code != 200:
                    tool_result = {"error": f"MCP status {mcp_resp.status_code}", "detail": mcp_resp.text[:200]}
                else:
                    tool_result = mcp_resp.json().get("result", {})
        except Exception as e:  # noqa: BLE001
            logging.exception("Error invocando MCP tool=%s", fn_name)
            tool_result = {"error": f"fallo_red_mcp: {e}"}

        # Añadir respuesta de la tool como mensaje role=tool
        messages.append(
            {
                "role": "tool",
                "tool_call_id": getattr(call, "id", "call_0"),
                "name": fn_name,
                "content": json.dumps(tool_result, ensure_ascii=False),
            }
        )

        try:
            second = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
            final_choice = second.choices[0] if second.choices else None
            answer = final_choice.message.content if final_choice and final_choice.message.content else ""
            return f"openai:{answer.strip()}"
        except Exception:
            return f"openai:{json.dumps(tool_result, ensure_ascii=False)}"

    def generate_stream(self, prompt: str) -> Iterable[str]:  # pragma: no cover - dependiente de red
        """Versión streaming: emite deltas (solo texto nuevo).

        Si falta API key o librería, se degrada al comportamiento no streaming
        devolviendo un único chunk (eco prefijado).
        """
        if not self.api_key or OpenAI is None:
            yield f"openai:{prompt}"
            return
        system_prompt, user_prompt = self._split_prompt(prompt)
        try:
            client = OpenAI(api_key=self.api_key)
            stream = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
                stream=True,
            )
            for event in stream:
                try:
                    # API 1.x: event.choices[0].delta.content (puede ser None)
                    delta = event.choices[0].delta.content if event.choices else None
                except Exception:  # estructura inesperada
                    delta = None
                if not delta:
                    continue
                yield f"openai:{delta}"
        except Exception:
            # degradar: entregar el prompt del usuario como eco
            yield f"openai:{user_prompt}"
