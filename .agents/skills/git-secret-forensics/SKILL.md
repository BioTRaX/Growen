---
name: git-secret-forensics
description: Audita y sanea secretos expuestos en el árbol actual y la historia Git de Growen. Usar ante fugas confirmadas, Secret Scanning, git-filter-repo, rotación de credenciales o purga coordinada de referencias remotas.
---

# Saneamiento forense de secretos Git

## Seguridad y autorización

1. Revocar o rotar la credencial antes de modificar Git. Nunca mostrar, copiar a
   un prompt ni pasar el valor literal por la línea de comandos.
2. Separar auditoría de erradicación. La auditoría es de solo lectura; exigir
   autorización explícita antes de reescribir historia, eliminar ramas o hacer
   force-push.
3. Registrar evidencia redactada: proveedor, archivo, commit, fecha, blob y
   huella parcial. No conservar otra copia abierta del secreto.
4. No trabajar sobre cambios sin confirmar. Preservar primero el árbol válido
   en la rama indicada por el usuario y comprobar que el worktree quede limpio.

## Auditoría

1. Revisar `.gitignore`, archivos de entorno rastreados, ramas, tags, stashes,
   reflogs y objetos no alcanzables. Emitir solo cantidades y ubicaciones.
2. Escanear el árbol y los blobs históricos con patrones de alta confianza.
   Clasificar hashes de locks por contexto y no imprimir coincidencias.
3. Documentar commit introductor, commit de remoción, ramas afectadas y estado
   de rotación. No concluir compromiso del host solo por una fuga en Git.

## Reescritura coordinada

1. Crear un espejo temporal fuera del repositorio de trabajo y verificar la URL
   exacta de `origin`. Instalar `git-filter-repo` solo en tooling temporal si no
   está disponible; cualquier Python debe usar el `.venv` 3.14.6 del proyecto.
2. Reemplazar por marcador redactado, nunca interpolar el secreto en comandos o
   logs. Aplicar la transformación a todas las referencias administrables.
3. Comparar hashes de árbol antes y después. Toda diferencia debe limitarse al
   contenido que se autorizó sanear.
4. Hacer `fetch` inmediatamente antes de publicar y usar
   `--force-with-lease=<ref>:<sha-esperado>` por cada rama. Preferir una
   publicación atómica y eliminar solo las ramas afectadas explícitamente.
5. No usar force-push ciego ni intentar escribir `refs/pull/*`.

## Verificación y cierre

1. Clonar nuevamente desde el remoto y repetir el escaneo sobre heads, tags y
   referencias internas de pull requests.
2. Si `refs/pull/*` conserva objetos sensibles, registrar las referencias y
   escalar la purga a GitHub Support: esas referencias no son administrables
   mediante `git push`.
3. Eliminar de forma verificada los espejos temporales que contengan objetos
   sensibles. Invalidar clones, forks, caches y artefactos antiguos; recomendar
   un reclonado limpio.
4. Actualizar `docs/SECURITY.md`, el informe del incidente, `Roadmap.md`,
   `README.md` y `CHANGELOG.md`. Diferenciar controles completados de acciones
   externas pendientes.
5. Verificar SHA remoto, worktree limpio y ausencia de patrones válidos antes
   de cerrar. No declarar erradicación completa mientras exista una referencia
   alcanzable o una rotación pendiente.
