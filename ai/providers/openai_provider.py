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
import logging

from ..provider_base import ILLMProvider
from ..types import Task
from agent_core.mcp_client import mcp_client_manager
from agent_core.tool_security import TOOL_OUTPUT_POLICY

try:  # Import perezoso para no forzar dependencia si no se usa
    from openai import AsyncOpenAI, OpenAI  # type: ignore
except Exception:  # pragma: no cover - si la lib no está
    AsyncOpenAI = None  # type: ignore
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
        # Guardar tool calls para logging
        self._last_tool_calls: List[Dict[str, Any]] = []

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
            Task.DIAGNOSIS_VISION.value,  # NUEVO: Soporte para diagnóstico con visión
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
        """DEPRECATED: Usar generate_async para nuevas implementaciones.
        
        Mantenido por compatibilidad legacy. Este método síncrono no soporta
        tool calling y será removido en futuras versiones.
        """
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
        except Exception:  # pragma: no cover - red/timeout variable
            # Degradar a eco para no romper funcionalidad general
            yield f"openai:{user_prompt}"

    async def generate_async(
        self,
        prompt: str,
        tools_schema: list | None = None,
        user_context: dict | None = None,
        images: list[str] | None = None,  # NUEVO: Lista de imágenes (Base64 data URLs o URLs públicas)
    ) -> str:
        """Genera respuesta asíncrona con soporte unificado de herramientas.

        Este método reemplaza a chat_with_tools y unifica la lógica de generación
        asíncrona con tool calling dinámico.

        Args:
            prompt: Prompt completo (puede incluir system + user concatenados con \n\n).
            tools_schema: Lista de tools en formato OpenAI. Si None, genera sin tools.
            user_context: Dict con contexto del usuario. Claves esperadas:
                - 'role': str (admin, colaborador, cliente, etc.) para control de acceso.
                - Otros campos opcionales para futuras extensiones.

        Returns:
            Respuesta generada sin prefijo técnico (solo el texto limpio).

        Flujo:
            1. Si tools_schema is None: generación simple de una llamada.
            2. Si tools_schema is not None:
                - Primera llamada con tools disponibles (tool_choice="auto").
                - Si el modelo responde con tool_calls, invocar MCP.
                - Inyectar resultados como mensajes role="tool".
                - Segunda llamada para obtener respuesta final.

        Manejo de errores:
            - Si falta API key o librería: devuelve el prompt del usuario como eco.
            - Si falla la red/MCP: devuelve estructura de error serializada para que
              el modelo pueda responder amigablemente al usuario.
        """
        # Validaciones iniciales
        if not self.api_key or AsyncOpenAI is None:
            # Degradar a eco sin prefijo para que el caller maneje
            return prompt.split("\n\n", 1)[-1] if "\n\n" in prompt else prompt

        system_prompt, user_prompt = self._split_prompt(prompt)
        user_role = user_context.get("role", "guest") if user_context else "guest"
        user_channel = user_context.get("channel", "web") if user_context else "web"

        # Construir mensajes iniciales
        # Si hay imágenes, usar formato content array para visión
        if images and len(images) > 0:
            user_content: List[Dict[str, Any]] = [
                {"type": "text", "text": user_prompt}
            ]
            # Agregar cada imagen al contenido
            for img in images:
                if img.startswith("data:image/"):
                    # Base64 data URL
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": img}
                    })
                elif img.startswith("http://") or img.startswith("https://"):
                    # URL pública
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": img}
                    })
            
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            # Usar modelo con visión si hay imágenes
            vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        else:
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            vision_model = None  # Usar modelo por defecto

        client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)

        # Caso 1: Sin tools → generación simple
        if not tools_schema:
            try:
                # Detectar si se requiere JSON estricto
                # NOTA: response_format=json_object no siempre funciona con vision, evitar usarlo
                wants_json = (
                    "Esquema de salida EXACTO:" in user_prompt
                    or "Esquema de salida esperado:" in user_prompt
                    or "Responde SOLO con JSON" in user_prompt
                )
                # Usar modelo con visión si hay imágenes, sino el modelo por defecto
                model_to_use = vision_model or self.model
                
                # Para Vision API, usar más tokens y evitar response_format
                if vision_model:
                    max_tokens = int(os.getenv("OPENAI_VISION_MAX_TOKENS", "2048"))
                    # Vision no siempre soporta response_format bien, omitir
                    resp = await client.chat.completions.create(
                        model=model_to_use,
                        messages=messages,
                        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                        max_tokens=max_tokens,
                    )
                else:
                    resp = await client.chat.completions.create(
                        model=model_to_use,
                        messages=messages,
                        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                        max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
                        response_format=(
                            {"type": "json_object"} if wants_json else {"type": "text"}
                        ),
                    )
                text = resp.choices[0].message.content if resp.choices else ""
                return text.strip()
            except Exception as e:
                # Loguear el error para debugging
                logging.warning("generate_async: Error en Vision API: %s", type(e).__name__)
                # Fallback: devolver prompt del usuario
                return user_prompt

        # Caso 2: Con tools → tool calling
        try:
            # Usar modelo con visión si hay imágenes, sino el modelo por defecto
            model_to_use = vision_model or self.model
            messages.insert(1, {"role": "system", "content": TOOL_OUTPUT_POLICY})
            first = await client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
        except Exception as e:
            logging.warning("generate_async: Error en primera llamada OpenAI: %s", type(e).__name__)
            return user_prompt

        choice = first.choices[0] if first.choices else None
        tool_calls = getattr(choice.message, "tool_calls", None) if choice else None

        # Si no hay tool_calls, devolver respuesta directa
        if not tool_calls:
            content = choice.message.content if choice and choice.message.content else ""
            return content.strip()

        # IMPORTANTE: Agregar el mensaje del assistant con tool_calls antes de procesar las respuestas
        # Esto es requerido por la API de OpenAI para mantener el formato correcto de mensajes
        messages.append(
            {
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        }
                    }
                    for call in tool_calls
                ]
            }
        )

        # Procesar tool_calls (ciclo de invocación MCP)
        used_search_sku: str | None = None
        used_search_product_id: int | None = None
        for idx, call in enumerate(tool_calls[:3]):  # límite de 3 calls por seguridad
            fn_name = call.function.name
            try:
                fn_args = json.loads(call.function.arguments or "{}")
            except Exception:
                fn_args = {}

            # ------------------------------------------------------------------
            # Normalización defensiva de parámetros
            # ------------------------------------------------------------------
            # El LLM puede alucinar nombres de parámetros ligeramente diferentes.
            # Aplicamos aliases comunes para hacer el sistema más resiliente.
            
            if fn_name == "find_products_by_name":
                # Normalización: buscar "query" con aliases comunes
                query = (
                    fn_args.get("query")           # Parámetro correcto (esperado por MCP)
                    or fn_args.get("name")         # Alias: el LLM puede usar "name"
                    or fn_args.get("product_name") # Alias: "product_name"
                    or fn_args.get("search")       # Alias: "search"
                    or fn_args.get("text")         # Alias: "text"
                )
                
                if not query or not isinstance(query, str):
                    # Error: falta parámetro obligatorio
                    tool_result = {
                        "error": "missing_query",
                        "message": "El parámetro 'query' (string) es obligatorio para find_products_by_name"
                    }
                    logging.warning(
                        "Tool call find_products_by_name sin un query válido."
                    )
                else:
                    # Llamada correcta al MCP
                    tool_result = await self.call_mcp_tool(
                        tool_name=fn_name,
                        parameters={"query": query},
                        user_role=user_role,
                        channel=user_channel,
                    )
                    # Auto-extracción de product_id y sku si búsqueda retorna 1 resultado único
                    if isinstance(tool_result, dict) and not tool_result.get("error"):
                        items = tool_result.get("items", [])
                        if isinstance(items, list) and len(items) == 1:
                            if items[0].get("product_id"):
                                used_search_product_id = items[0]["product_id"]
                                logging.debug(
                                    "Auto-extracción de product_id desde búsqueda: %s",
                                    used_search_product_id
                                )
                            if items[0].get("sku"):
                                used_search_sku = items[0]["sku"]
                                logging.debug(
                                    "Auto-extracción de SKU desde búsqueda: %s",
                                    used_search_sku
                                )
            
            elif fn_name == "search_web":
                query = fn_args.get("query") or fn_args.get("search") or fn_args.get("text")
                if not query or not isinstance(query, str):
                    tool_result = {"error": "missing_query"}
                else:
                    max_results = max(1, min(int(fn_args.get("max_results", 5)), 10))
                    tool_result = await mcp_client_manager.call_tool(
                        tool_name=fn_name,
                        arguments={"query": query, "max_results": max_results},
                        role=user_role,
                        server_name="web_search",
                        channel=user_channel,
                    )
            else:
                # Tools basadas en producto: get_product_info, get_product_full_info
                # Prioridad: product_id > sku (product_id es más confiable)
                product_id = (
                    fn_args.get("product_id")      # Parámetro preferido
                    or used_search_product_id      # Fallback: ID extraído de búsqueda previa
                )
                sku = (
                    fn_args.get("sku")             # Parámetro SKU canónico
                    or fn_args.get("product_sku")  # Alias posible
                    or fn_args.get("code")         # Alias posible
                    or used_search_sku             # Fallback: SKU extraído de búsqueda previa
                )
                
                if not product_id and (not sku or not isinstance(sku, str)):
                    # Error: falta parámetro obligatorio
                    tool_result = {
                        "error": "missing_identifier",
                        "message": f"Se requiere 'product_id' o 'sku' para {fn_name}"
                    }
                    logging.warning(
                        "Tool call %s sin identificador válido.",
                        fn_name,
                    )
                else:
                    # Validación de permisos para get_product_full_info
                    if fn_name == "get_product_full_info" and user_role not in {"admin", "colaborador"}:
                        tool_result = {
                            "error": "permission_denied",
                            "message": f"El rol '{user_role}' no tiene permisos para get_product_full_info"
                        }
                        logging.warning(
                            "Intento de usar get_product_full_info con rol '%s' (requiere admin/colaborador)",
                            user_role
                        )
                    else:
                        # Llamada correcta al MCP (preferir product_id sobre sku)
                        params = {}
                        if product_id:
                            params["product_id"] = product_id
                        if sku:
                            params["sku"] = sku
                        tool_result = await self.call_mcp_tool(
                            tool_name=fn_name,
                            parameters=params,
                            user_role=user_role,
                            channel=user_channel,
                        )

            # Guardar tool call para logging
            self._last_tool_calls.append({
                "tool_name": fn_name,
                "parameter_names": sorted(fn_args),
                "success": not isinstance(tool_result, dict) or not tool_result.get("error"),
                "result_summary": {
                    "items_count": len(tool_result.get("items", [])) if isinstance(tool_result, dict) else 0,
                } if isinstance(tool_result, dict) else {},
            })
            
            # DEBUG: Log del resultado de la tool antes de inyectarlo en mensajes
            tool_result_json = json.dumps(tool_result, ensure_ascii=False)
            
            # Verificar si la herramienta devolvió descripción
            if isinstance(tool_result, dict):
                has_description = "description" in tool_result and tool_result["description"]
                logging.info(
                    "Tool %s result: product_id=%s, sku=%s, has_description=%s, desc_length=%d",
                    fn_name,
                    tool_result.get("product_id"),
                    tool_result.get("sku"),
                    has_description,
                    len(tool_result.get("description", "") or "") if has_description else 0,
                )
            
            # Inyectar resultado en mensajes
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(call, "id", f"call_{idx}"),
                    "name": fn_name,
                    "content": tool_result_json,
                }
            )

            # Si búsqueda retornó 1 producto y no hay get_product_info pendiente,
            # forzar llamada sintética para completar información
            if (
                fn_name == "find_products_by_name"
                and (used_search_product_id or used_search_sku)
                and all(c.function.name != "get_product_info" for c in tool_calls)
            ):
                synthetic_params = {}
                if used_search_product_id:
                    synthetic_params["product_id"] = used_search_product_id
                if used_search_sku:
                    synthetic_params["sku"] = used_search_sku
                
                synthetic_result = await self.call_mcp_tool(
                    tool_name="get_product_info",
                    parameters=synthetic_params,
                    user_role=user_role,
                    channel=user_channel,
                )
                
                # IMPORTANTE: Agregar la llamada sintética al assistant message
                # para que OpenAI reconozca el tool_call_id correspondiente
                synthetic_call_id = "call_auto_product"
                synthetic_args = json.dumps(
                    {"product_id": used_search_product_id} if used_search_product_id else {"sku": used_search_sku},
                    ensure_ascii=False,
                )
                
                # Buscar y actualizar el mensaje del assistant con el nuevo tool_call
                for msg in messages:
                    if msg.get("role") == "assistant" and "tool_calls" in msg:
                        msg["tool_calls"].append({
                            "id": synthetic_call_id,
                            "type": "function",
                            "function": {
                                "name": "get_product_info",
                                "arguments": synthetic_args,
                            }
                        })
                        break
                
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": synthetic_call_id,
                        "name": "get_product_info",
                        "content": json.dumps(synthetic_result, ensure_ascii=False),
                    }
                )
                break  # Cerrar ciclo temprano

        # Segunda llamada para obtener respuesta final
        try:
            followup = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
            final_choice = followup.choices[0] if followup.choices else None
            answer = (
                final_choice.message.content
                if final_choice and final_choice.message.content
                else ""
            )
            return answer.strip()
        except Exception as e:
            # Loguear el error para diagnóstico
            logging.warning("generate_async: Error en followup OpenAI: %s", type(e).__name__)
            # Fallback amigable
            return "No pude completar la operación con las herramientas disponibles. Probá nuevamente más tarde."

    # ------------------------------------------------------------------
    # Tool Calling (MCP Products) --------------------------------------
    # ------------------------------------------------------------------
    async def build_tools_schema(
        self, user_role: str, channel: str = "web"
    ) -> List[Dict[str, Any]]:
        """Descubre tools MCP y las convierte al formato de function calling."""
        if channel == "web":
            return await mcp_client_manager.openai_tools(user_role)
        return await mcp_client_manager.openai_tools(user_role, channel)

    async def call_mcp_tool(
        self,
        *,
        tool_name: str,
        parameters: Dict[str, Any],
        user_role: str = "guest",
        channel: str = "web",
    ) -> Dict[str, Any] | str:
        """Compatibilidad interna: invoca Products mediante el cliente MCP real."""
        return await mcp_client_manager.call_tool(
            tool_name=tool_name,
            arguments=parameters,
            role=user_role,
            server_name="products",
            channel=channel,
        )

    async def call_mcp_web_tool(
        self,
        *,
        tool_name: str,
        parameters: Dict[str, Any],
        user_role: str | None = None,
        channel: str = "web",
    ) -> Dict[str, Any] | str:
        """Compatibilidad interna: invoca Web Search mediante MCP real."""
        role = user_role or "guest"
        return await mcp_client_manager.call_tool(
            tool_name=tool_name,
            arguments=parameters,
            role=role,
            server_name="web_search",
            channel=channel,
        )

    async def chat_with_tools(self, *, prompt: str, user_role: str) -> str:
        """Adaptador legacy sobre el flujo asíncrono y el catálogo MCP descubierto."""
        tools = await self.build_tools_schema(user_role)
        result = await self.generate_async(
            prompt=prompt,
            tools_schema=tools,
            user_context={"role": user_role},
        )
        return f"openai:{result}"

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
