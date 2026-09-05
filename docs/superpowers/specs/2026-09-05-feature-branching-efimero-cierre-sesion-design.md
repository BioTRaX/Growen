<!-- NG-HEADER: Nombre de archivo: 2026-09-05-feature-branching-efimero-cierre-sesion-design.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/specs/2026-09-05-feature-branching-efimero-cierre-sesion-design.md -->
<!-- NG-HEADER: Descripción: Diseño del branching efímero y cierre secuencial de sesiones agénticas. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Feature Branching Efímero y cierre secuencial de sesión

## Contexto

Growen reemplazará el trabajo directo sobre `dev` y las ramas intermedias
estáticas por una rama efímera por sesión o tarea. La rama se crea desde el
estado actual de `dev`, concentra el trabajo autorizado y se integra de forma
secuencial durante el cierre explícito de la sesión.

El árbol existente puede contener cambios sin confirmar al comenzar. El agente
debe inventariarlos antes de crear la rama, conservar su atribución y no afirmar
que son propios sin evidencia.

## Observaciones

- `dev` es la rama estable de integración y no admite commits directos.
- `develop` deja de formar parte del flujo vigente.
- `.agents/skills/` es la única fuente canónica de skills; `.agent/skills/`
  conserva exclusivamente adaptadores legacy existentes.
- Toda operación Git se ejecuta por terminal.
- La automatización no elimina los controles de secretos, alcance, pruebas,
  documentación, remoto ni riesgo.

## Errores y/u outputs que el cambio debe prevenir

- Cambios simultáneos confirmados directamente en `dev`.
- Ramas estáticas reutilizadas por varias sesiones.
- Cierres parciales que publican antes de completar la retrospectiva o la
  documentación.
- Conflictos abandonados aun cuando su resolución sea verificable.
- Inclusión accidental de cambios ajenos mediante staging indiscriminado.
- Evoluciones agénticas de riesgo muy alto aplicadas sin confirmación.
- Documentación que siga presentando `develop` o el commit directo a `dev` como
  prácticas vigentes.

## Objetivo

Definir un contrato único, obligatorio y comprobable para iniciar trabajo,
cerrar sesiones, evolucionar el entorno agéntico, resolver conflictos e integrar
cambios en `dev`. Reducir además el contexto duplicado entre las skills
canónicas de Growen y Superpowers: el pack externo define metodología general y
las skills del proyecto conservan únicamente restricciones, comandos y contratos
propios de Growen.

## Propuesta de código o pasos

### Inicio obligatorio

1. Leer la gobernanza y la documentación del dominio.
2. Ejecutar `git status --short --branch`, identificar la rama y registrar los
   cambios preexistentes.
3. Estando en `dev`, crear una rama nueva con un nombre descriptivo y efímero,
   por ejemplo `feat/<nombre-tarea>`, `fix/<nombre-tarea>` o
   `docs/<nombre-tarea>`.
4. Si el trabajo comenzó accidentalmente en `dev` sin commits nuevos, crear la
   rama antes de continuar y preservar el worktree. Si ya existe un commit
   directo nuevo en `dev`, detener la publicación y reparar la topología sin
   reescribir historia remota sin autorización.
5. Mantener un inventario lógico de archivos preexistentes, propios y ajenos.

### Activación del cierre

Los únicos triggers directos son `Cerrar sesión` y `Cerremos sesión`, sin
distinguir mayúsculas ni puntuación final. Variantes como “terminamos”, “final
del chat”, nombrar la skill o pedir una retrospectiva no activan por sí solas el
auto-merge.

Si uno de los triggers aparece mientras existe una instrucción abierta que hace
ambiguo si debe completarse o descartarse, el agente solicita una confirmación
breve antes de iniciar el cierre. La confirmación sólo despeja la ambigüedad; no
reemplaza ninguno de los dos triggers.

### Flujo secuencial de cierre

1. **Análisis retrospectivo:** delimitar la sesión, contrastar tareas con
   evidencia y documentar dificultades, errores, causas, soluciones,
   implementaciones, validaciones y riesgos residuales.
2. **Evolución agéntica:** derivar mejoras preventivas o aceleradores a partir
   de evidencia concreta. Preferir corregir una fuente canónica o automatizar
   una regla verificable antes de crear duplicados.
3. **Compuerta de riesgo:** clasificar cada evolución:
   - bajo: documentación, aclaraciones o validaciones locales reversibles;
   - medio: cambios acotados en skills, scripts o contratos con pruebas y
     reversión local clara;
   - muy alto: reescritura de historia, force-push, eliminación amplia,
     exposición o rotación de secretos, mutaciones externas irreversibles,
     migraciones destructivas o decisiones de conflicto cuya intención no
     pueda demostrarse.
4. Implementar evoluciones de riesgo bajo o medio y validarlas. Ante riesgo muy
   alto, informar estado y propuesta, preguntar si se avanza y detener todo el
   flujo hasta recibir respuesta explícita.
5. **Documentación:** actualizar `README.md`, `Roadmap.md`, los documentos de
   dominio y todo contenido verificablemente desactualizado encontrado durante
   el cierre.
6. **Gate previo:** comprobar alcance, NG-HEADER, pruebas, documentación,
   secretos, diff, remoto y pertenencia de todos los cambios que serían
   incluidos.
7. **Commit de trabajo:** confirmar que la rama actual es la efímera, agregar
   sólo las rutas atribuidas a la sesión y crear commits atómicos en español.
8. **Sincronización de la rama efímera:** confirmar que la rama actual es la
   efímera de la sesión, ejecutar `git fetch` y luego `git merge origin/dev`.
9. **Conflictos:** consultar `git diff --name-only --diff-filter=U`, localizar
   `<<<<<<<`, `=======` y `>>>>>>>`, reconstruir la intención de ambos lados y
   reescribir la versión integrada. Validar cada resolución. Si la intención no
   puede demostrarse o el cambio es de riesgo muy alto, detener el flujo.
10. Después de resolver conflictos, verificar que no queden archivos sin fusionar
   ni marcadores. Ejecutar `git add .` únicamente cuando el inventario confirme
   que todos los cambios del worktree pertenecen al cierre. Crear el commit de
   fusión cuando Git lo requiera.
11. Ejecutar nuevamente el gate aplicable sobre el árbol fusionado.
12. Cambiar a `dev`, comprobar que no recibió commits directos durante el cierre,
    integrar la rama efímera sin reescribir historia y ejecutar `git push
    origin dev`.
13. Verificar que `HEAD`, `dev` y `origin/dev` coincidan. La eliminación de la
    rama efímera local o remota será una operación posterior y recuperable, no
    un requisito para declarar integrado el cierre.

### Conflictos y concurrencia

La resolución autónoma se permite para archivos de texto cuando las pruebas,
contratos y contexto permiten demostrar la combinación correcta. No se elige
automáticamente “ours” o “theirs”, no se eliminan cambios para hacer pasar el
merge y no se resuelven binarios por descarte silencioso.

Si `dev` avanza entre la sincronización y la integración final, el agente vuelve
a la rama efímera, repite `fetch`, merge, resolución y validación. No fuerza la
actualización de `dev`.

### Composición con Superpowers

Las skills canónicas se auditan por responsabilidad, trigger y contenido. Una
skill local puede exigir una sub-skill de Superpowers, pero no debe copiar su
procedimiento. Se aplican estas fronteras:

- `skill-scaffolder` conserva ubicación canónica, frontmatter y validadores de
  Growen; `writing-skills` aporta el método RED–GREEN–REFACTOR.
- `diagnose-local-services` conserva topología y comandos de Growen;
  `systematic-debugging` aporta el método causal general.
- `git-commit-push` conserva autorización, branching efímero, seguridad, remoto
  y cierre hacia `dev`; las skills Git de Superpowers no sustituyen este gate.
- `retrospectiva-tecnica-sesion` conserva triggers, evolución agéntica y cierre
  secuencial; `verification-before-completion` aporta disciplina de evidencia.
- Las skills de dominio (`create-service`, `database-migrations`,
  `git-secret-forensics`, `vue-module-migration`) conservan sólo conocimiento
  específico de Growen y referencian metodología externa cuando corresponda.

La auditoría debe detectar descripciones que resuman procedimientos ya cubiertos,
referencias redundantes o instrucciones locales que reproduzcan íntegramente una
skill externa. Las correcciones se limitan a solapamientos comprobados; no se
reducen controles propios del proyecto.

### Contrato de salida

Tras un cierre exitoso, la respuesta final contiene exclusivamente este
checklist, con cada ítem marcado según evidencia:

- Análisis retrospectivo completado
- Evolución agéntica implementada/propuesta
- Actualización de documentación
- Merge a Dev
- Final de sesión

Si el flujo se detiene por riesgo muy alto, se presenta únicamente el estado de
la propuesta y la pregunta necesaria. El checklist final se reserva para el
cierre completado.

### Archivos alcanzados

- `AGENTS.md`
- `.agents/skills/git-commit-push/SKILL.md`
- `.agent/skills/git-commit-push/SKILL.md`
- `.agents/skills/retrospectiva-tecnica-sesion/SKILL.md`
- `.agents/skills/retrospectiva-tecnica-sesion/agents/openai.yaml`
- `scripts/audit_agentic_environment.py`
- `tests/test_audit_agentic_environment.py`
- `tests/test_retrospective_skill.py`
- `docs/AGENT_SKILLS.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `CONTRIBUTING.md`
- `README.md`
- `Roadmap.md`

## Criterios de aceptación

- Todas las fuentes vigentes prohíben commits directos a `dev`.
- Cada sesión crea una rama efímera desde el estado actual de `dev` antes de
  modificar archivos.
- `develop` no figura como rama activa del flujo.
- Sólo `Cerrar sesión` y `Cerremos sesión` activan el cierre; una ambigüedad de
  trabajo pendiente permite solicitar confirmación.
- El orden retrospectiva, evolución, riesgo, documentación, sincronización,
  resolución, validación, integración y push es inequívoco.
- Las mejoras de riesgo bajo o medio se materializan; las de riesgo muy alto
  detienen el flujo antes de cualquier integración.
- El auto-merge resuelve conflictos verificables y nunca usa force-push.
- Las pruebas ejecutables detectan regresiones de las reglas esenciales.
- Existe una matriz documentada de responsabilidades entre Growen y
  Superpowers, sin procedimientos externos duplicados en las skills canónicas.
- Las descripciones de skills se limitan a condiciones de activación para evitar
  cargar el cuerpo por una coincidencia demasiado amplia.
- Se documentan los cambios y se actualiza toda información verificablemente
  desactualizada encontrada durante la tarea.
