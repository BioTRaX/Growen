# Pruebas manuales E2E de mutaciones

## Crear proveedor
1. Iniciar el backend y el frontend.
2. Iniciar sesión con un usuario válido.
3. Abrir el modal de proveedores y completar **Nombre** y **Slug**.
4. Enviar el formulario y verificar en las herramientas de desarrollador que la solicitud `POST /suppliers` incluye el encabezado `X-CSRF-Token`.
5. Confirmar que la respuesta es `201` y que el nuevo proveedor aparece en la lista.

## Actualizar stock de producto
1. Buscar un producto existente en el buscador.
2. Modificar el campo de stock y guardar.
3. Revisar en las herramientas de desarrollador que la solicitud `PATCH /products/{id}/stock` contenga el encabezado `X-CSRF-Token`.
4. Comprobar que la respuesta es `200` y que el valor de stock se actualiza en pantalla.
