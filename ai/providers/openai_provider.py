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
from agent_core.detect_mcp_url import get_mcp_products_url, get_mcp_web_search_url

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
        except Exception as e:  # pragma: no cover - red/timeout variable
            # Degradar a eco para no romper funcionalidad general
            yield f"openai:{user_prompt}"

    async def generate_async(
        self,
        prompt: str,
        tools_schema: list | None = None,
        user_context: dict | None = None,
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
        if not self.api_key or OpenAI is None:
            # Degradar a eco sin prefijo para que el caller maneje
            return prompt.split("\n\n", 1)[-1] if "\n\n" in prompt else prompt

        system_prompt, user_prompt = self._split_prompt(prompt)
        user_role = user_context.get("role", "guest") if user_context else "guest"

        # Construir mensajes iniciales
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        client = OpenAI(api_key=self.api_key)

        # Caso 1: Sin tools → generación simple
        if not tools_schema:
            try:
                # Detectar si se requiere JSON estricto
                wants_json = (
                    "Esquema de salida EXACTO:" in user_prompt
                    or "Esquema de salida esperado:" in user_prompt
                )
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
                    response_format=(
                        {"type": "json_object"} if wants_json else {"type": "text"}
                    ),
                )
                text = resp.choices[0].message.content if resp.choices else ""
                return text.strip()
            except Exception:
                # Fallback: devolver prompt del usuario
                return user_prompt

        # Caso 2: Con tools → tool calling
        try:
            first = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
        except Exception as e:
            logging.warning("generate_async: Error en primera llamada OpenAI: %s: %s", type(e).__name__, e)
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
                        "Tool call find_products_by_name sin 'query' válido. Args recibidos: %s",
                        fn_args
                    )
                else:
                    # Llamada correcta al MCP
                    tool_result = await self.call_mcp_tool(
                        tool_name=fn_name,
                        parameters={"query": query, "user_role": user_role},
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
                        "Tool call %s sin identificador válido. Args: %s, used_product_id: %s, used_sku: %s",
                        fn_name, fn_args, used_search_product_id, used_search_sku
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
                        params = {"user_role": user_role}
                        if product_id:
                            params["product_id"] = product_id
                        if sku:
                            params["sku"] = sku
                        tool_result = await self.call_mcp_tool(
                            tool_name=fn_name,
                            parameters=params,
                        )

            # DEBUG: Log del resultado de la tool antes de inyectarlo en mensajes
            tool_result_json = json.dumps(tool_result, ensure_ascii=False)
            logging.debug(
                "Tool Call Output para LLM (%s): %s",
                fn_name,
                tool_result_json[:1000] + "..." if len(tool_result_json) > 1000 else tool_result_json,
            )
            
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
                synthetic_params = {"user_role": user_role}
                if used_search_product_id:
                    synthetic_params["product_id"] = used_search_product_id
                if used_search_sku:
                    synthetic_params["sku"] = used_search_sku
                
                synthetic_result = await self.call_mcp_tool(
                    tool_name="get_product_info",
                    parameters=synthetic_params,
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
            followup = client.chat.completions.create(
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
            logging.warning("generate_async: Error en followup OpenAI: %s: %s", type(e).__name__, e)
            # Fallback amigable
            return "No pude completar la operación con las herramientas disponibles. Probá nuevamente más tarde."

    # ------------------------------------------------------------------
    # Tool Calling (MCP Products) --------------------------------------
    # ------------------------------------------------------------------
    def _build_tools_schema(self, user_role: str) -> List[Dict[str, Any]]:
        """Construye el schema de tools disponibles según el rol del usuario.
        
        IMPORTANTE: Este schema debe coincidir EXACTAMENTE con la implementación
        en mcp_servers/products_server/tools.py. Cualquier cambio en los parámetros
        o nombres de tools debe sincronizarse en ambos archivos.
        
        Args:
            user_role: Rol del usuario (admin, colaborador, cliente, guest).
                Roles 'admin' y 'colaborador' tienen acceso a get_product_full_info.
        
        Returns:
            Lista de definiciones de functions en formato OpenAI Function Calling.
        """
        base_tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "find_products_by_name",
                    "description": (
                        "Use this tool to search for products when the user provides a partial or complete product name "
                        "(e.g., 'feeding', 'tierra', 'LED lamp', 'fertilizante 1kg'). "
                        "Returns a list of matching products with: product_id, name, sku (canonical format XXX_####_YYY), stock, and price. "
                        "Always use this tool FIRST to find products. "
                        "Use the returned product_id or sku with get_product_info for detailed information. "
                        "IMPORTANT: Only show SKU codes in format XXX_####_YYY to users (canonical SKUs)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": (
                                    "The search text provided by the user. Can be a partial product name, "
                                    "full product name, product category, or size (e.g., 'feeding 125g', 'sustrato', 'maceta 10L')."
                                )
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_product_info",
                    "description": (
                        "Use this tool to get detailed information about a specific product. "
                        "Returns: product name, sale price, stock availability, sku, and product description. "
                        "You can use EITHER product_id (preferred) OR sku to identify the product. "
                        "The product_id or sku must be obtained from find_products_by_name results. "
                        "Do NOT guess or invent IDs or SKU codes."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "integer",
                                "description": (
                                    "The internal product ID. Obtained from find_products_by_name results. "
                                    "Preferred over sku for accuracy."
                                )
                            },
                            "sku": {
                                "type": "string",
                                "description": (
                                    "The canonical SKU code (format XXX_####_YYY, e.g., 'FER_0028_MIN'). "
                                    "Use product_id instead when available."
                                )
                            },
                        },
                        "required": [],
                    },
                },
            }
        ]
        
        # Tool avanzada solo para roles autorizados (coincide con _FULL_INFO_ROLES en MCP)
        if user_role in {"admin", "colaborador"}:
            base_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "get_product_full_info",
                        "description": (
                            "Use this tool to get extended product information including description and technical specs "
                            "(admin/colaborador only). "
                            "Returns all basic info plus: description, technical_specs, usage_instructions. "
                            "You can use EITHER product_id (preferred) OR sku to identify the product."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "product_id": {
                                    "type": "integer",
                                    "description": (
                                        "The internal product ID. Obtained from find_products_by_name results. "
                                        "Preferred over sku for accuracy."
                                    )
                                },
                                "sku": {
                                    "type": "string",
                                    "description": (
                                        "The canonical SKU code (format XXX_####_YYY). "
                                        "Use product_id instead when available."
                                    )
                                },
                            },
                            "required": [],
                        },
                    },
                }
            )
        return base_tools

    async def call_mcp_tool(self, *, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any] | str:
        """Invoca el servidor MCP de productos de forma resiliente.

        Lee URL desde `MCP_PRODUCTS_URL` o detecta automáticamente según contexto
        (Docker vs host local). Maneja errores de red devolviendo un JSON serializado
        que el modelo pueda interpretar para responder al usuario sin exponer detalles técnicos.
        """
        mcp_url = get_mcp_products_url()
        payload = {"tool_name": tool_name, "parameters": parameters}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(mcp_url, json=payload)
                if resp.status_code != 200:
                    logging.warning("MCP respondió status=%s detail=%s", resp.status_code, resp.text[:200])
                    return {"error": "tool_call_failed", "status": resp.status_code}
                return resp.json().get("result", {})
        except httpx.RequestError as e:  # problemas de red, DNS, timeout
            logging.error("Fallo de red MCP tool=%s: %s", tool_name, e)
            return {"error": "tool_network_failure"}
        except Exception as e:  # noqa: BLE001
            logging.exception("Excepción inesperada invocando MCP tool=%s", tool_name)
            return {"error": "tool_internal_failure"}

    async def call_mcp_web_tool(self, *, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any] | str:
        """Invoca el servidor MCP de búsqueda web (MVP) de forma resiliente.

        Lee URL desde `MCP_WEB_SEARCH_URL` o detecta automáticamente según contexto
        (Docker vs host local). Maneja errores de red devolviendo estructura con `error`.
        """
        mcp_url = get_mcp_web_search_url()
        payload = {"tool_name": tool_name, "parameters": parameters}
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(mcp_url, json=payload)
                if resp.status_code != 200:
                    logging.warning("MCP(web) respondió status=%s detail=%s", resp.status_code, resp.text[:200])
                    return {"error": "tool_call_failed", "status": resp.status_code}
                return resp.json().get("result", {})
        except httpx.RequestError as e:
            logging.error("Fallo de red MCP(web) tool=%s: %s", tool_name, e)
            return {"error": "tool_network_failure"}
        except Exception:
            logging.exception("Excepción inesperada invocando MCP(web) tool=%s", tool_name)
            return {"error": "tool_internal_failure"}

    async def chat_with_tools(self, *, prompt: str, user_role: str) -> str:
        """DEPRECATED: Usar generate_async en su lugar.
        
        Este método es mantenido temporalmente por compatibilidad con código
        existente pero será removido en futuras versiones. Migrar a:
        
            result = await provider.generate_async(
                prompt=prompt,
                tools_schema=provider._build_tools_schema(user_role),
                user_context={"role": user_role}
            )
            return f"openai:{result}"  # Si se requiere el prefijo legacy
        
        Flujo original:
        1. Primera llamada al modelo con las tools disponibles.
        2. Si responde con `tool_calls`, se invoca el MCP vía detección automática
           (localhost:8100 en host, mcp_products:8100 en Docker).
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

        # IMPORTANTE: Agregar el mensaje del assistant con tool_calls antes de procesar las respuestas
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

        # Procesar secuencialmente cada tool_call (hasta 2 pasos búsqueda→info)
        tool_results_for_model: List[Dict[str, Any]] = []
        used_search_sku: str | None = None
        for idx, call in enumerate(tool_calls[:3]):  # límite prudente MVP
            fn_name = call.function.name
            try:
                fn_args = json.loads(call.function.arguments or "{}")
            except Exception:
                fn_args = {}
            params: Dict[str, Any] = {"user_role": user_role}
            if fn_name == "find_products_by_name":
                query = fn_args.get("query") or fn_args.get("name") or fn_args.get("product_name")
                if not query or not isinstance(query, str):
                    tool_result = {"error": "missing_query"}
                else:
                    tool_result = await self.call_mcp_tool(tool_name=fn_name, parameters={"query": query, "user_role": user_role})
                    # Si hay un único resultado podemos preparar un segundo paso auto
                    if isinstance(tool_result, dict) and not tool_result.get("error"):
                        items = tool_result.get("items", [])
                        if isinstance(items, list) and len(items) == 1 and items[0].get("sku"):
                            used_search_sku = items[0]["sku"]
            else:
                # Tools basadas en sku
                sku = fn_args.get("sku") or used_search_sku
                if not sku or not isinstance(sku, str):
                    tool_result = {"error": "missing_sku"}
                else:
                    tool_result = await self.call_mcp_tool(tool_name=fn_name, parameters={"sku": sku, "user_role": user_role})
            tool_results_for_model.append({"name": fn_name, "result": tool_result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": getattr(call, "id", f"call_{idx}"),
                    "name": fn_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
            # Si acabamos de hacer búsqueda y obtuvimos 1 SKU, forzamos siguiente llamada get_product_info
            if fn_name == "find_products_by_name" and used_search_sku and all(c.function.name != "get_product_info" for c in tool_calls):
                # Inyectar manualmente una tool call sintética para obtener info
                synthetic_result = await self.call_mcp_tool(tool_name="get_product_info", parameters={"sku": used_search_sku, "user_role": user_role})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"call_auto_sku",
                        "name": "get_product_info",
                        "content": json.dumps(synthetic_result, ensure_ascii=False),
                    }
                )
                tool_results_for_model.append({"name": "get_product_info", "result": synthetic_result})
                break  # cerramos ciclo temprano

        try:
            followup = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
            final_choice = followup.choices[0] if followup.choices else None
            answer = final_choice.message.content if final_choice and final_choice.message.content else ""
            return f"openai:{answer.strip()}"
        except Exception as e:
            # fallback: devolver resumen amigable
            # Loggear el error para debugging
            logging.error(f"Error en chat_with_tools followup: {type(e).__name__}: {str(e)}")
            # No exponemos trazas técnicas al usuario final.
            return "openai:No pude completar la operación con las herramientas disponibles. Probá nuevamente más tarde."

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
