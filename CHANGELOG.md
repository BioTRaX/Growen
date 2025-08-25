# Changelog

## [Unreleased]
- feat: drag & drop, tema oscuro en buscador y modal de subida más robusto
- Add: upload UI (+), dry-run viewer, commit
- Add: productos canónicos y tabla de equivalencias
- Add: middleware de logging, endpoints `/healthz` y `/debug/*`, SQLAlchemy con `echo` opcional.
- Add: endpoints `GET/PATCH /canonical-products/{id}`, listado y borrado de `/equivalences`
- Add: comparador de precios `GET /canonical-products/{id}/offers` con mejor precio marcado
- Add: modo oscuro básico en el frontend
- Add: plantilla Excel por proveedor `GET /suppliers/{id}/price-list/template`
- Add: plantilla Excel genérica `GET /suppliers/price-list/template`
- fix: restaurar migración `20241105_auth_roles_sessions` renombrando archivo y `revision` para mantener la cadena de dependencias
- fix: evitar errores creando o borrando tablas ya existentes en `init_schema` mediante `sa.inspect`
- Add: componentes `CanonicalForm` y `EquivalenceLinker` integrados en `ImportViewer` y `ProductsDrawer`
- dev: valores por defecto inseguros para SECRET_KEY y ADMIN_PASS en `ENV=dev` (evita fallos en pruebas)
- deps: incluir `aiosqlite` para motor SQLite asíncrono
- dev: en ausencia de sesión y con `ENV=dev` se asume rol `admin` para facilitar pruebas
- fix: corregir comillas en `scripts/start.bat` y `start.bat` para rutas con espacios
- fix: soporte de `psycopg` asíncrono en Windows usando `WindowsSelectorEventLoopPolicy`
- fix: migración idempotente que agrega `users.identifier` si falta y actualiza el modelo
- fix: formulario de login centrado y autenticación/guest integrados con `AuthContext`
