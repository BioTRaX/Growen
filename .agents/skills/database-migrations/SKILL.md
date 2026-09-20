---
name: database-migrations
description: Usar al cambiar db/models.py, crear o revisar una revisión Alembic, o investigar drift del esquema PostgreSQL.
---

# Gestionar migraciones

1. Leer `docs/MIGRATIONS_NOTES.md`, `db/models.py`, `alembic.ini` y las revisiones relacionadas en `db/migrations/versions/`.
2. Ante un `IntegrityError` o un HTTP 409 genérico, identificar primero la restricción exacta mediante logs de PostgreSQL y consultas de esquema de solo lectura. No inferir la causa únicamente desde el mensaje del frontend.
3. Diagnosticar heads, revisión aplicada y paridad del objeto afectado con `.\.venv\Scripts\python.exe scripts\debug_migrations.py`, `scripts\check_schema.py`, `-m alembic heads` y una consulta focal de nulabilidad, índices o constraints.
4. Generar con `.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "descripción_en_español"`, tratándolo como una propuesta y no como una migración aceptada.
5. Revisar todo el diff autogenerado. Si incluye deriva histórica ajena al incidente, eliminar esas operaciones y conservar una revisión mínima y focal; no intentar corregir deriva no relacionada dentro de la misma migración.
6. Revisar `upgrade()` y `downgrade()`: idempotencia cuando corresponda, defaults no nulos, locks, índices, datos y operaciones destructivas. Un downgrade debe rechazar explícitamente una reversión que perdería datos.
7. Ejecutar `alembic check` y clasificar su salida. Si existe drift histórico, separar explícitamente: operaciones sobre objetos creados o modificados por la revisión actual, y operaciones ajenas ya conocidas. Un reporte global ruidoso no invalida por sí solo una revisión focal, pero tampoco debe presentarse como limpio.
8. Aplicar primero sobre desarrollo o una base temporal y ejecutar `scripts\audit_schema.py` con la venv. Verificar además `current == head` y el atributo concreto modificado en PostgreSQL.
9. Agregar tests de cadena limpia y upgrade incremental. El test fresh debe afirmar el head esperado y los objetos concretos de la revisión —columnas, índices o constraints—, no limitarse a comprobar que `upgrade head` termina. Si la prueba PostgreSQL completa es opt-in, registrar claramente que quedó omitida y qué variable la habilita.
10. Después de corregir una migración o su test, repetir la selección consolidada afectada; una rerun focal del caso antes fallido debe informarse como tal.
11. Documentar revisión, impacto, rollback, prerequisitos y drift residual en `docs/MIGRATIONS_NOTES.md`, `Roadmap.md` y documentos afectados.

Los scripts de diagnóstico deben ocultar contraseñas y tokens al imprimir URLs de conexión o configuración.

No ejecutar downgrade destructivo ni modificar una base productiva sin autorización explícita.
