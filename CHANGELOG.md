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
- fix: restaurar migración `20241105_auth_roles_sessions` renombrando archivo y `revision` para mantener la cadena de dependencias
