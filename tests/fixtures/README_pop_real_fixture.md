<!-- NG-HEADER: Nombre de archivo: README_pop_real_fixture.md -->
<!-- NG-HEADER: Ubicación: tests/fixtures/README_pop_real_fixture.md -->
<!-- NG-HEADER: Descripción: Instrucciones para agregar fixture real (anonimizado) de POP -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Fixture real de POP (anonimizado)

Para validar el caso real de N≈39 productos, podés agregar un correo real (EML o HTML) de POP, previamente anonimizado.

- Ubicación sugerida (por defecto en los tests):
  - `tests/fixtures/pop_email_real.eml` (preferido), o
  - `tests/fixtures/pop_email_real.html`.

- Alternativamente, seteá la variable de entorno `POP_REAL_FIXTURE` apuntando al archivo a usar en pruebas.

Recomendaciones de anonimización:
- Remover/editar datos personales (emails, teléfonos, direcciones, CUIT).
- Mantener estructura/tablas y títulos de ítems sin alterar demasiado los nombres de producto (para validar las heurísticas de título).
- Dejar el asunto con el patrón “Pedido <número>” si es posible.

Una vez colocado el archivo, ejecutá solo la prueba real:

```powershell
pytest -q tests/test_pop_email_real.py
```
