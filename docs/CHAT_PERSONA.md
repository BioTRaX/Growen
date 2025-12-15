# NG-HEADER: Nombre de archivo: CHAT_PERSONA.md
# NG-HEADER: Ubicación: docs/CHAT_PERSONA.md
# NG-HEADER: Descripción: Documentación del sistema de personas dinámicas del chatbot
# NG-HEADER: Lineamientos: Ver AGENTS.md

# Sistema de Personas Dinámicas del Chatbot

## Resumen

El chatbot Growen utiliza un sistema de **personas dinámicas** que adapta su tono, estilo y nivel de detalle según el rol del usuario y la intención de la consulta. Esto permite ofrecer una experiencia personalizada y apropiada para cada contexto.

## Personas Disponibles

### 1. ASISTENTE (Admin/Colaborador)

**Cuándo se activa:**
- Usuario con rol `admin` o `colaborador`
- Consultas de productos, precios, stock

**Características:**
- Tono directo, eficiente y técnico
- Muestra SKU canónico (formato `XXX_####_YYY`) siempre que esté disponible
- Muestra stock exacto: "Stock: X unidades"
- Incluye ubicación en depósito si está disponible
- Respuestas concisas, sin relleno comercial
- Prioridad: velocidad y precisión de datos

**Ejemplo de respuesta:**
```
Producto: Top Crop Veg 1L
SKU: FER_1234_VEG
Stock: 15 unidades
Precio: $2,500
```

### 2. VENDEDOR (Cliente/Guest)

**Cuándo se activa:**
- Usuario con rol `cliente` o `guest`
- Consultas de productos, precios, stock

**Características:**
- Tono amigable, asesor y orientado a la conversión
- **NUNCA muestra SKUs técnicos** a clientes
- Enfocado en beneficios y características relevantes
- Crea urgencia si hay poco stock (1-3 unidades): "¡Quedan pocas unidades!"
- Tranquiliza si hay buen stock: "Tenemos stock disponible"
- Ofrece alternativas si no hay stock
- Prioridad: satisfacción y conversión

**Ejemplo de respuesta:**
```
¡Perfecto! Tenemos Top Crop Veg 1L disponible. 
Es un fertilizante orgánico ideal para la etapa de crecimiento vegetativo.
Precio: $2,500. ¡Quedan 3 unidades disponibles!
```

### 3. CULTIVADOR (Diagnóstico)

**Cuándo se activa:**
- Cualquier usuario cuando la consulta es diagnóstica
- Detectado automáticamente por palabras clave como:
  - "hojas amarillas", "plaga", "carencia", "problema"
  - "enfermedad", "hongos", "diagnóstico"
  - "no crece", "se muere", "qué le pasa"

**Características:**
- Tono educativo, paciente y empático
- **PRIMERO diagnostica** usando contexto RAG (Knowledge Base) si está disponible
- NO recomienda productos inmediatamente
- Hace preguntas de seguimiento si necesita más información
- Explica qué puede estar causando el problema
- Una vez diagnosticado, recomienda productos específicos con explicación
- Incluye consejos de uso y prevención
- Prioridad: resolver el problema del cultivador

**Ejemplo de respuesta:**
```
Las hojas amarillas pueden indicar varias cosas. Según nuestra documentación, 
puede ser carencia de nitrógeno, exceso de riego, o estrés por temperatura.

¿En qué etapa está la planta? ¿Hace cuánto apareció el problema?

Una vez que tengamos más información, te recomendaré el producto adecuado.
```

## Detección de Persona

La selección de persona se realiza en `ai/persona.py` mediante la función `get_persona_prompt()`:

```python
persona_mode, system_prompt = get_persona_prompt(
    user_role="admin",      # Rol del usuario
    intent="product_lookup", # Intención detectada
    user_text="hojas amarillas" # Texto del usuario
)
```

**Lógica de selección:**
1. Si el texto contiene palabras clave diagnósticas → **CULTIVADOR** (independiente del rol)
2. Si el rol es `admin` o `colaborador` → **ASISTENTE**
3. Si el rol es `cliente` o `guest` → **VENDEDOR**

## Integración con Tags de Productos

Los productos pueden tener **tags** asociados (ej: `#Organico`, `#Mineral`, `#Floracion`) que se incluyen en las respuestas de las tools:

- `find_products_by_name`: Incluye `tags` en cada producto de la lista
- `get_product_info`: Incluye `tags` en la información detallada

**Uso por el LLM:**
- El bot puede usar tags para identificar características sin adivinar por el nombre
- Si el usuario pide "algo orgánico", el bot ve el tag `#Organico` y puede recomendar productos con ese tag
- Los tags se incluyen en el contexto del LLM para mejorar la precisión de recomendaciones

**Ejemplo de respuesta con tags:**
```json
{
  "product_id": 123,
  "name": "Top Crop Veg 1L",
  "sku": "FER_1234_VEG",
  "stock": 15,
  "price": 2500,
  "tags": ["#Organico", "#Vegetativo"]
}
```

## Implementación Técnica

### Archivos Clave

- **`ai/persona.py`**: Define los prompts de cada persona y la función `get_persona_prompt()`
- **`ai/router.py`**: Usa `get_persona_prompt()` para determinar el system prompt antes de llamar al provider
- **`services/routers/chat.py`**: Pasa el contexto del usuario (rol, intent) al router
- **`services/routers/catalog.py`**: Incluye tags en las respuestas de productos (`_build_product_response`, `/catalog/search`)
- **`mcp_servers/products_server/tools.py`**: Propaga tags desde la API hacia las tools del LLM

### Flujo de Ejecución

1. Usuario envía mensaje → `chat.py` recibe request
2. Se detecta rol del usuario desde `session_data.role`
3. Se clasifica intención con `classify_intent()`
4. `AIRouter.run_async()` llama a `get_persona_prompt()` con:
   - `user_role`: Rol del usuario
   - `intent`: Intención detectada
   - `user_text`: Texto del usuario (para detectar diagnósticos)
5. Se obtiene el `system_prompt` apropiado
6. El provider (OpenAI) recibe el system prompt y genera la respuesta

## Testing

Para probar cada persona:

### ASISTENTE
```
Usuario: admin
Mensaje: "¿Cuánto cuesta Top Crop Veg?"
Esperado: Respuesta con SKU, stock exacto, precio
```

### VENDEDOR
```
Usuario: cliente
Mensaje: "¿Tienes fertilizante orgánico?"
Esperado: Respuesta amigable, sin SKU técnico, con urgencia si hay poco stock
```

### CULTIVADOR
```
Usuario: cliente
Mensaje: "Mis hojas están amarillas, ¿qué puede ser?"
Esperado: Diagnóstico primero, preguntas de seguimiento, luego recomendación
```

## Mejoras Futuras

- [ ] Agregar más palabras clave para detección de diagnósticos
- [ ] Permitir que el usuario cambie manualmente de persona (ej: "actúa como técnico")
- [ ] Personalizar urgencia de stock según historial de compras del cliente
- [ ] Agregar más tags de productos (ej: `#Premium`, `#Económico`)
- [ ] Usar tags para filtrar búsquedas directamente en la API

## Referencias

- `ai/persona.py`: Definición de personas y lógica de selección
- `ai/router.py`: Integración con AIRouter
- `services/routers/chat.py`: Endpoint principal de chat
- `docs/RAG.md`: Sistema de Knowledge Base usado por CULTIVADOR
