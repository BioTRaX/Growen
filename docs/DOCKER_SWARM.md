<!-- NG-HEADER: Nombre de archivo: DOCKER_SWARM.md -->
<!-- NG-HEADER: Ubicación: docs/DOCKER_SWARM.md -->
<!-- NG-HEADER: Descripción: Preparación y despliegue altamente disponible de Growen en Docker Swarm. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Docker Swarm

`docker-stack.yml` describe el stack productivo completo: PostgreSQL/Redis stateful, API, frontend, Dramatiq, workers Mercado/Enrich/Conocimiento, MCP y el dominio MeLi. Swarm no construye imágenes; todas las variables `GROWEN_*_IMAGE` deben apuntar a tags inmutables ya publicados.

## Preflight

1. Inicializar o unir nodos al Swarm fuera de este script.
2. Etiquetar exactamente un nodo persistente: `docker node update --label-add growen_stateful=true <nodo>`.
3. Crear los secretos externos listados en `docker-stack.yml` mediante stdin o archivos externos. No pasar su valor como argumento. Ejemplo: `Get-Content -Raw <archivo> | docker secret create meli_app_id -`.
4. Definir las imágenes y `MELI_REDIRECT_URI=https://<host>/integrations/meli/oauth/callback` en el entorno del operador.
5. Ejecutar `./scripts/deploy-swarm.ps1 -WhatIf`; luego repetir sin `-WhatIf` para desplegar.

El preflight exige Swarm activo, secretos, imágenes, HTTPS, label stateful y una configuración renderizable antes de `docker stack deploy --prune`.

## Alta disponibilidad y redes

API, frontend, MCP, gateway MeLi, worker MeLi y `cloudflared` usan réplicas. Los tres componentes MeLi aplican `max_replicas_per_node: 1`; se requieren al menos dos nodos elegibles para tolerar la caída de uno. PostgreSQL y Redis tienen una réplica con volumen local: la HA real de datos exige almacenamiento/replicación externos y no se presume por este stack.

`backend` y `meli_ingress` son overlays internas. Sólo frontend publica un puerto del routing mesh. `cloudflared` no participa de `backend`; el gateway es el único puente entre `meli_ingress`, base de datos y egress. Ningún servicio MeLi publica puertos.

## Actualización y rollback

Los servicios stateless usan actualización `start-first`, una tarea por vez y rollback automático ante fallo. Antes de actualizar, aplicar migraciones compatibles hacia adelante y atrás desde una tarea administrativa controlada. Verificar con `docker stack services growen`, `docker service ps growen_meli_webhook_gateway` y los health checks. No eliminar volúmenes para resolver un rollout fallido.
