Contexto:

Estamos trabajando en "Growen", una aplicación de gestión con un backend en FastAPI y un frontend en React/TypeScript. El sistema ya cuenta con un robusto módulo de ventas (/sales) que permite la gestión completa del ciclo de vida de una venta (creación, confirmación, anulación, etc.), manejo de clientes y catálogo de productos.

Toda la lógica de negocio, validaciones de stock y reglas de seguridad (autenticación y roles) ya están implementadas y expuestas a través de endpoints en la API RESTful. La interacción con la base de datos se realiza exclusivamente a través de esta API. Un ejemplo de arquitectura similar ya existe en el microservicio de productos (mcp_servers/products_server/), que consume la API principal mediante requests.

Objetivo:

Crear un nuevo módulo MCP (Procesamiento de Lenguaje Natural para Comandos) que permita a los usuarios con rol Colaborador o Admin registrar ventas utilizando lenguaje natural. Este módulo debe actuar como un "traductor" conversacional que consume los endpoints de la API existentes, sin acceder directamente a la base de datos.

Observaciones y Comentarios:

Arquitectura: El módulo debe ser una nueva herramienta o servicio en Python que no se conecte a la base de datos. Su única interacción con la lógica de la aplicación será a través de llamadas HTTP a los endpoints de la API de FastAPI.

Estado de la Venta: Las ventas creadas a través de este módulo deben registrarse inicialmente en estado BORRADOR.

Endpoints Clave a Utilizar:

Búsqueda de productos: GET /sales/catalog/search.

Búsqueda de clientes: GET /sales/customers/search.

Creación de venta: POST /sales.

Seguridad: El acceso a esta funcionalidad debe estar restringido a usuarios autenticados con los roles apropiados (colaborador, admin), lo cual ya es manejado por la API.

Tareas Sugeridas para llegar al Objetivo:

Crear el Archivo del Módulo: Genera un nuevo archivo Python para la herramienta, por ejemplo, mcp_servers/sales_server/tools.py.

Definir la Herramienta Principal: Crea una función principal, como registrar_venta_conversacional(orden_usuario: str), que sirva como punto de entrada.

Implementar la Lógica de Conversación:

Diseña un manejador de estado para el flujo conversacional (esperando_productos, esperando_cliente, esperando_confirmacion).

Utiliza un modelo de NLU para extraer entidades (productos, cantidades, cliente) del texto del usuario.

Desarrollar Funciones Auxiliares para la API:

Una función para buscar y desambiguar productos (_buscar_producto(nombre: str)). Esta debe llamar a GET /sales/catalog/search y manejar los casos de cero o múltiples coincidencias.

Una función para buscar o crear clientes (_gestionar_cliente(nombre: str)). Debe llamar a GET /sales/customers/search y, si no encuentra resultados, preguntar al usuario si desea crearlo.

Construir y Ejecutar la Venta:

Una vez recopilada toda la información, la herramienta debe formatear un payload JSON compatible con el endpoint POST /sales.

Antes de enviar la solicitud final, debe mostrar un resumen claro al usuario y esperar su confirmación explícita.

Criterios de Aceptación:

Flujo Conversacional Interactivo: El sistema no falla si falta información en la primera orden; en su lugar, la pide. (Ej: Usuario: "Vende 2 producto A" -> Growen: "Ok, ¿para qué cliente?").

Búsqueda Flexible de Productos: La búsqueda de productos maneja ambigüedades. Si se encuentran varios productos, el sistema pide al usuario que aclare cuál desea.

Creación Automática de Clientes: Si se especifica un nombre de cliente que no existe, el sistema ofrece crearlo en el momento.

Confirmación de Seguridad: La venta no se crea hasta que el sistema muestra un resumen completo (cliente, productos, cantidades, total) y el usuario da su aprobación final.

Integración con API: El módulo funciona exclusivamente realizando llamadas HTTP a la API existente y no contiene código de acceso directo a la base de datos.

Resultado Final: Al confirmar el usuario, se crea una nueva venta en la base de datos con estado BORRADOR y se le notifica el ID de la venta creada.