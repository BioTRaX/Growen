"""
Módulo MCP para el registro de ventas de forma conversacional.

Este módulo actúa como un traductor entre el lenguaje natural del usuario y la
API RESTful de ventas de Growen. No accede directamente a la base de datos.
"""
import httpx
import os
from typing import Any, Dict, List, Optional
from enum import Enum
from rapidfuzz import process, fuzz

# --- Configuración de la API ---
# Se recomienda obtener la URL base de una variable de entorno.
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
# El token debería ser gestionado de forma segura, por ejemplo, inyectado en el contexto de la petición.
AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "token_de_prueba")
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
}

# --- Lógica de la Herramienta Conversacional ---

async def _buscar_producto(nombre_producto: str) -> List[Dict[str, Any]]:
    """
    Busca productos en el catálogo. Primero usa la API para una búsqueda amplia
    y luego usa rapidfuzz para reordenar los resultados y encontrar la mejor coincidencia.
    """
    params = {"q": nombre_producto}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/sales/catalog/search",
                params=params,
                headers=HEADERS,
                timeout=10.0
            )
            response.raise_for_status()
            productos_candidatos = response.json()

            if not productos_candidatos:
                return []

            # Extraer solo los nombres para el procesamiento con fuzzy matching
            nombres_candidatos = [p.get("name", "") for p in productos_candidatos]
            
            # Usar rapidfuzz para encontrar las mejores coincidencias
            # extract() devuelve una lista de tuplas: (nombre, score, indice_original)
            mejores_coincidencias = process.extract(nombre_producto, nombres_candidatos, scorer=fuzz.WRatio, limit=5)

            # Mapear los resultados ordenados de vuelta a los objetos de producto originales
            productos_ordenados = []
            for nombre, score, indice in mejores_coincidencias:
                if score > 75: # Umbral de confianza para evitar malas coincidencias
                    producto_original = productos_candidatos[indice]
                    producto_original['match_score'] = score # Opcional: añadir el score al objeto
                    productos_ordenados.append(producto_original)
            
            return productos_ordenados

    except httpx.RequestError as e:
        print(f"Error en la petición a la API para buscar producto: {e}")
        return []
    except httpx.HTTPStatusError as e:
        print(f"Error de estado HTTP al buscar producto: {e.response.status_code}")
        return []

def _formatear_info_producto(producto: Dict[str, Any], user_role: str) -> str:
    """Formatea la información de un producto en un string legible para el usuario, respetando su rol."""
    # Roles con acceso a información sensible como el stock
    ROLES_CON_ACCESO_AVANZADO = {"admin", "colaborador"}

    nombre = producto.get('name', 'Nombre no disponible')
    precio = producto.get('price', 0.0)
    descripcion = producto.get('description')
    categoria = producto.get('category')
    stock = producto.get('stock')

    info = f"-- Producto: {nombre} --\n"
    info += f"Precio: ${precio:.2f}\n"
    if descripcion:
        info += f"Descripción: {descripcion}\n"
    if categoria:
        info += f"Categoría: {categoria}\n"
    
    if user_role in ROLES_CON_ACCESO_AVANZADO:
        if stock is not None:
            info += f"Stock disponible: {stock} unidades\n"
        else:
            info += "Stock: No disponible\n"
            
    return info

async def consultar_producto(nombre_producto: str, user_role: str) -> str:
    """
    Consulta la información de un producto y la devuelve formateada según el rol del usuario.
    """
    productos_encontrados = await _buscar_producto(nombre_producto)

    if not productos_encontrados:
        return f"No pude encontrar el producto '{nombre_producto}'."

    if len(productos_encontrados) == 1:
        producto = productos_encontrados[0]
        return _formatear_info_producto(producto, user_role)

    # Si hay múltiples resultados, los listamos con información básica.
    respuesta = f"Encontré varios productos que coinciden con '{nombre_producto}':\n"
    for producto in productos_encontrados:
        nombre = producto.get('name', 'Nombre no disponible')
        precio = producto.get('price', 0.0)
        respuesta += f"- {nombre} (Precio: ${precio:.2f})\n"
    respuesta += "\nPor favor, sé más específico para obtener más detalles."
    
    return respuesta

async def _gestionar_cliente(nombre_cliente: str) -> Optional[Dict[str, Any]]:
    """
    Busca un cliente por nombre a través de la API.

    En esta versión, solo busca y devuelve el primer resultado coincidente.
    La lógica para crear un cliente si no se encuentra se añadirá posteriormente
    en el flujo conversacional.

    Args:
        nombre_cliente: El término de búsqueda para el cliente.

    Returns:
        Un diccionario con los datos del primer cliente encontrado, o None si no hay coincidencias o hay un error.
    """
    params = {"q": nombre_cliente}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/sales/customers/search",
                params=params,
                headers=HEADERS,
                timeout=10.0
            )
            response.raise_for_status()
            resultados = response.json()
            if resultados:  # Si la lista de resultados no está vacía
                return resultados[0]  # Devuelve el primer cliente
            return None
    except httpx.RequestError as e:
        print(f"Error en la petición a la API para buscar cliente: {e}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"Error de estado HTTP al buscar cliente: {e.response.status_code}")
        return None

async def _crear_venta(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envía la solicitud para crear una nueva venta en estado BORRADOR.

    Args:
        payload: Un diccionario con los datos de la venta (customer_id, lines, etc.).

    Returns:
        Un diccionario con la respuesta de la API (la venta creada) o un diccionario vacío en caso de error.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/sales",
                json=payload,
                headers=HEADERS,
                timeout=15.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"Error en la petición a la API para crear la venta: {e}")
        return {}
    except httpx.HTTPStatusError as e:
        print(f"Error de estado HTTP al crear la venta: {e.response.status_code} - {e.response.text}")
        return {}

class EstadoVenta(Enum):
    INICIO = "INICIO"
    NECESITA_CLIENTE = "NECESITA_CLIENTE"
    NECESITA_PRODUCTOS = "NECESITA_PRODUCTOS"
    LISTO_PARA_CONFIRMAR = "LISTO_PARA_CONFIRMAR"
    FINALIZADO = "FINALIZADO"

async def manejar_conversacion_venta(
    entrada_usuario: str,
    estado_actual: Optional[Dict[str, Any]] = None,
    user_role: str = "cliente"  # Default role to avoid breaking if not provided
) -> Dict[str, Any]:
    """
    Gestiona una conversación de varios turnos para registrar una venta.

    Args:
        entrada_usuario: El texto más reciente del usuario.
        estado_actual: Un diccionario que representa el estado de la conversación.
        user_role: El rol del usuario que inicia la conversación.

    Returns:
        Un diccionario con la respuesta para el usuario y el nuevo estado de la conversación.
    """
    if not estado_actual or estado_actual.get("fase") == EstadoVenta.FINALIZADO.value:
        estado_actual = {"fase": EstadoVenta.INICIO.value, "lineas_venta": [], "cliente": None}

    fase_actual = estado_actual["fase"]
    
    # --- FASE DE INICIO: Procesar la primera orden ---
    if fase_actual == EstadoVenta.INICIO.value:
        if not entrada_usuario.strip():
            return {
                "respuesta_para_usuario": "Iniciemos una venta. ¿Qué productos quieres registrar? (ej: 2 productoA y 1 productoB)",
                "nuevo_estado": {**estado_actual, "fase": EstadoVenta.NECESITA_PRODUCTOS.value}
            }

        # NLU simple para la primera orden
        partes = entrada_usuario.lower().split()
        productos_solicitados = []
        cliente_nombre = None
        if "para" in partes:
            indice_para = partes.index("para")
            cliente_nombre = " ".join(partes[indice_para+1:])
            partes_productos = partes[:indice_para]
        else:
            partes_productos = partes

        i = 0
        while i < len(partes_productos):
            if partes_productos[i].isdigit():
                cantidad = int(partes_productos[i])
                nombre_prod = partes_productos[i+1]
                productos_solicitados.append({"nombre": nombre_prod, "cantidad": cantidad})
                i += 2
            else:
                i += 1

        if not productos_solicitados:
            return {
                "respuesta_para_usuario": "No entendí qué productos vender. Por favor, especifica cantidad y nombre.",
                "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}
            }

        # Validar productos
        for item in productos_solicitados:
            productos_encontrados = await _buscar_producto(item['nombre'])
            if not productos_encontrados:
                return {
                    "respuesta_para_usuario": f"No encontré el producto '{item['nombre']}'. Venta cancelada.",
                    "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}
                }
            if len(productos_encontrados) > 1:
                return {
                    "respuesta_para_usuario": f"Encontré múltiples productos para '{item['nombre']}'. Por favor, sé más específico. Venta cancelada.",
                    "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}
                }
            producto = productos_encontrados[0]
            estado_actual["lineas_venta"].append({
                "variant_id": producto.get('id'),
                "quantity": item['cantidad'],
                "unit_price": producto.get('price'),
                "name": producto.get('name')
            })

        # Si hay cliente, buscarlo. Si no, pedirlo.
        if cliente_nombre:
            cliente = await _gestionar_cliente(cliente_nombre)
            if not cliente:
                return {
                    "respuesta_para_usuario": f"No encontré al cliente '{cliente_nombre}'. Venta cancelada.",
                    "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}
                }
            estado_actual["cliente"] = cliente
            estado_actual["fase"] = EstadoVenta.LISTO_PARA_CONFIRMAR.value
            # Llamada recursiva para entrar en la siguiente fase y generar el resumen
            return await manejar_conversacion_venta(entrada_usuario, estado_actual, user_role)
        else:
            return {
                "respuesta_para_usuario": "Productos registrados. ¿Para qué cliente es la venta?",
                "nuevo_estado": {**estado_actual, "fase": EstadoVenta.NECESITA_CLIENTE.value}
            }

    # --- FASE NECESITA_CLIENTE: El usuario ha proporcionado un nombre de cliente ---
    elif fase_actual == EstadoVenta.NECESITA_CLIENTE.value:
        cliente_nombre = entrada_usuario
        cliente = await _gestionar_cliente(cliente_nombre)
        if not cliente:
            return {
                "respuesta_para_usuario": f"Sigo sin encontrar al cliente '{cliente_nombre}'. ¿Quieres intentar con otro nombre?",
                "nuevo_estado": estado_actual # Mantenemos el estado para que pueda reintentar
            }
        estado_actual["cliente"] = cliente
        estado_actual["fase"] = EstadoVenta.LISTO_PARA_CONFIRMAR.value
        # Llamada recursiva para entrar en la siguiente fase y generar el resumen
        return await manejar_conversacion_venta(entrada_usuario, estado_actual, user_role)

    # --- FASE LISTO_PARA_CONFIRMAR: Presentar resumen y esperar confirmación ---
    elif fase_actual == EstadoVenta.LISTO_PARA_CONFIRMAR.value:
        # Si la entrada es la confirmación (ej. "si")
        if entrada_usuario.lower() in ["si", "sí", "ok", "confirmo", "dale"]:
            payload = {
                "customer_id": estado_actual["cliente"]["id"],
                "lines": estado_actual["lineas_venta"],
                "status": "BORRADOR"
            }
            nueva_venta = await _crear_venta(payload)
            if nueva_venta and nueva_venta.get("id"):
                respuesta = f"¡Hecho! Venta #{nueva_venta.get('id')} creada en estado BORRADOR para {estado_actual['cliente'].get('name')}."
            else:
                respuesta = "Hubo un error al crear la venta. La operación ha sido cancelada."
            return {"respuesta_para_usuario": respuesta, "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}}
        
        # Si la entrada es negativa
        if entrada_usuario.lower() in ["no", "cancela"]:
            return {
                "respuesta_para_usuario": "Venta cancelada.",
                "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}
            }

        # Si es la primera vez que llegamos a esta fase, generamos el resumen.
        resumen = "Resumen de la venta:\n"
        resumen += f"- Cliente: {estado_actual['cliente'].get('name')}\n"
        resumen += "- Productos:\n"
        total = 0
        for linea in estado_actual["lineas_venta"]:
            subtotal = linea.get('quantity', 0) * linea.get('unit_price', 0)
            total += subtotal
            resumen += f"  - {linea.get('quantity')}x {linea.get('name')} (@ ${linea.get('unit_price', 0):.2f} c/u) = ${subtotal:.2f}\n"
        resumen += f"TOTAL: ${total:.2f}\n\n¿Confirmas la creación de esta venta? (si/no)"
        return {"respuesta_para_usuario": resumen, "nuevo_estado": estado_actual}

    # --- FASE NECESITA_PRODUCTOS: Esperando la lista de productos ---
    elif fase_actual == EstadoVenta.NECESITA_PRODUCTOS.value:
        # Aquí se podría implementar una lógica similar a la de INICIO para parsear solo los productos
        # y luego pasar a NECESITA_CLIENTE o LISTO_PARA_CONFIRMAR
        return {
            "respuesta_para_usuario": "Fase de añadir productos aún en desarrollo. Por favor, reinicia la conversación.",
            "nuevo_estado": {**estado_actual, "fase": EstadoVenta.FINALIZADO.value}
        }

    return {
        "respuesta_para_usuario": "No sé cómo continuar. Reiniciando conversación.",
        "nuevo_estado": {"fase": EstadoVenta.INICIO.value, "lineas_venta": [], "cliente": None}
    }