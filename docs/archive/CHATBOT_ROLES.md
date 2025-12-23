<!-- NG-HEADER: Nombre de archivo: CHATBOT_ROLES.md -->
<!-- NG-HEADER: Ubicación: docs/CHATBOT_ROLES.md -->
<!-- NG-HEADER: Descripción: Alcances y permisos por rol para el chatbot corporativo -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roles y alcances del chatbot

## Resumen

El chatbot corporativo distinguirá el contexto y las operaciones permitidas según el rol del usuario autenticado. Esta matriz debe revisarse con cada despliegue que añada capacidades o modifique la seguridad.

## Definiciones de rol

- **Admin**: Personal autorizado para operaciones sensibles, soporte de primer nivel y mantenimiento del repositorio. Accede al código completo, métricas internas y puede registrar sugerencias bajo `PR/`.
- **Colaborador**: Equipo operativo (ventas, soporte comercial, onboarding). Acceso a documentación funcional y datos de productos, clientes, proveedores y ventas; sin acceso directo al código ni a `PR/`.
- **Invitado**: Sin autenticación; continúa limitado al chatbot público existente (no participa de este alcance).

## Matriz de permisos

| Recurso / Acción | Admin | Colaborador |
|------------------|:-----:|:-----------:|
| Consultar documentación funcional (`docs/`, guías de uso) | ✅ | ✅ |
| Consultar métricas internas (health checks extendidos, logs recientes) | ✅ | 🚫 |
| Buscar en código fuente (`/chatbot/repo/search`) | ✅ | 🚫 |
| Descargar archivo del repositorio (`/chatbot/repo/file`) | ✅ | 🚫 |
| Generar sugerencias de código (`/chatbot/pr-suggestion`) | ✅ (solo en `PR/`) | 🚫 |
| Consultar auditoría del chatbot | ✅ | 🚫 |
| Consultar información operativa (productos, clientes, proveedores, ventas) | ✅ | ✅ |
| Consultar decisiones de negocio / Roadmap | ✅ | ✅ |
| Acceder a prompts del chatbot o configurar providers IA | ✅ | 🚫 |
| Roles heredados (permisos existentes en API/Frontend) | Se mantiene | Se mantiene |

Notas:
- Toda interacción con el repositorio genera registros en `ChatbotAudit` con hash de archivo y usuario.
- Las respuestas del RAG se filtran por etiquetas `role_scope`, evitando que colaboradores vean contenido restringido.
- Para nuevos roles futuros (p. ej. "Soporte externo"), duplicar esta matriz y documentar pruebas específicas.

## Reglas de auditoría

- Cada request del chatbot debe incluir `user_id`, `role`, `source_ip`, `prompt`, `artifacts` y `duration_ms`.
- Las sugerencias escritas en `PR/` deben incluir diff resumido, hash del contenido base y resultado de validaciones automáticas.
- Configurar retención mínima de 180 días y alertas cuando se detecten accesos inusuales.

## Checklist de cumplimiento

- [ ] Rol admin validado mediante SSO/MFA y tokens OIDC.
- [ ] Colaboradores no pueden acceder a `/chatbot/repo/*` ni a endpoints de auditoría.
- [ ] RAG etiqueta correctamente cada chunk con `role_scope`.
- [ ] Documentación actualizada (`README.md`, `Roadmap.md`, `docs/roles-endpoints.md`).
- [ ] Tests automatizados cubren escenarios de acceso y auditoría.
