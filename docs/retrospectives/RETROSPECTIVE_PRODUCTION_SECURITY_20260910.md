<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_PRODUCTION_SECURITY_20260910.md -->
<!-- NG-HEADER: Ubicación: docs/retrospectives/RETROSPECTIVE_PRODUCTION_SECURITY_20260910.md -->
<!-- NG-HEADER: Descripción: Retrospectiva del endurecimiento y preparación productiva LAN -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva de seguridad y preparación productiva — 2026-09-10

## Contexto

La sesión preparó la primera producción de Growen en un Swarm de un nodo,
accesible sólo desde la LAN en `192.168.100.100`. El alcance incluyó cierre de
exposiciones HTTP, separación de media privada, configuración fail-closed,
secretos externos, SSRF, autenticación, infraestructura reproducible y retiro
completo del runtime de Notion en favor de SiYuan.

## Observaciones

- Las descargas privadas requieren sesión y rol sin revelar existencia de
  recursos ajenos.
- La configuración productiva exige TLS, autenticación, hosts, proxies, Redis,
  orígenes exactos y secretos por archivo.
- La documentación se reorganizó por arquitectura, desarrollo, features,
  operaciones y retrospectivas; SiYuan es el destino documental privado.
- El despliegue separa `Preflight`, `Bootstrap` y `Application`, con topología
  `SingleNode` explícita e imágenes inmutables por digest.
- La IP del servidor quedó configurada manualmente en `192.168.100.100/24`.

## Errores y/u outputs

- La primera PKI persistente tenía IP SAN pero no Authority Key Identifier; los
  clientes TLS estrictos no podían construir su cadena. Se generó la versión
  `2026091002` con AKI enlazado a la CA y se preservó la versión anterior sin
  habilitarla para despliegue.
- Windows denegó la creación del firewall desde una consola no elevada.
- La importación de la CA requiere confirmación interactiva o elevación. Hasta
  completarla y reiniciar Docker Desktop, `docker login`, push y pull siguen
  bloqueados por confianza del daemon.
- La reserva o exclusión DHCP de `.100` depende del router y continúa pendiente.
- El gate Ruff acotado queda en cero; el barrido global conserva 798 incidencias
  legacy documentadas como deuda separada.
- La migración de media, el despliegue y el smoke desde otro dispositivo no se
  ejecutaron.

## Objetivo alcanzado y límites

El código y los manifiestos de endurecimiento quedaron preparados para revisión.
La PKI `2026091002`, los secretos Swarm versionados y el registro privado existen
como estado operativo persistente fuera de Git. El registro está saludable y su
HTTPS autenticado fue validado con la CA explícita: `401` anónimo y `200`
autenticado. Esto no equivale a una puesta en producción: faltan confianza de CA,
firewall, reserva DHCP, publicación de imágenes, migración, despliegue y smoke.

## Evolución agéntica

La skill de cierre ahora exige inventariar contenedores, volúmenes, certificados,
secretos versionados y servicios externos, diferenciándolos del estado de Git.
El auditor contractual valida esta obligación para evitar cierres que confundan
una suite verde con infraestructura realmente operativa.

## Propuesta de código o pasos pendientes

1. Reservar o excluir `192.168.100.100` en DHCP para la MAC documentada.
2. Crear reglas de firewall LAN para `80`, `443` y `5000` desde PowerShell elevado.
3. Importar la CA `2026091002` en `LocalMachine\\Root` y reiniciar Docker Desktop.
4. Validar login, push y pull con una imagen sonda.
5. Construir desde el SHA integrado, ejecutar Trivy y generar SBOM y digests.
6. Ejecutar media en dry-run y solicitar autorización independiente antes de
   cualquier migración o despliegue.
7. Completar Bootstrap, Application y smoke autenticado desde otro dispositivo.

## Criterios de aceptación

- Las pruebas, auditorías, builds y validaciones de manifiestos terminan en cero
  sobre el árbol integrado.
- No se versionan secretos, archivos locales ni credenciales.
- El estado Git, el estado operativo y los pasos manuales pendientes quedan
  diferenciados y verificables.
- Se documentan todos los cambios y se actualiza cualquier información
  desactualizada.
