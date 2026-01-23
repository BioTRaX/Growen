---
name: skill-scaffolder
description: Genera la estructura de carpetas y plantillas para nuevas skills de Antigravity, asegurando que cumplan con los estándares de documentación y configuración.
---

# Skill Scaffolder

Esta skill guía al agente paso a paso para crear **nuevas skills** de manera estandarizada, cumpliendo con las mejores prácticas del ecosistema Antigravity.

## When to use this skill

Usa esta skill cuando:

- El usuario diga **"crea una skill para X"** o **"necesitamos estandarizar el proceso Y"**.
- Se necesite generar una nueva skill desde cero con estructura completa.
- Se requiera asegurar que una skill cumpla con los estándares de Antigravity.

## How to use it

Sigue estos pasos en orden para crear una nueva skill:

---

### Paso 1: Análisis de Requisitos

Antes de crear cualquier archivo, **pregunta al usuario** lo siguiente:

1. **Nombre deseado para la skill:**
   - Debe seguir el formato `kebab-case` (ej: `my-skill`, `code-review`, `deploy-checker`).
   - Evitar nombres genéricos como `helper` o `utils`.

2. **Propósito específico de la skill:**
   - Solicita una descripción clara para redactar el campo `description` del frontmatter.
   - La descripción debe estar en **tercera persona** e incluir palabras clave que ayuden al mecanismo de discovery.
   - Ejemplo: *"Automatiza el respaldo de bases de datos PostgreSQL siguiendo las convenciones del equipo."*

3. **¿Requiere scripts ejecutables o solo instrucciones de texto?**
   - Si la skill necesita scripts (Python, Bash, PowerShell, etc.), se creará una subcarpeta `scripts/`.
   - Si solo necesita instrucciones markdown, basta con el `SKILL.md`.

---

### Paso 2: Generación de Estructura

Una vez recopilada la información, crea la estructura de carpetas:

```
.agent/skills/<nombre-skill>/
├── SKILL.md           # Archivo principal (obligatorio)
├── scripts/           # Solo si se requieren scripts
├── examples/          # Opcional: implementaciones de referencia
└── resources/         # Opcional: plantillas y otros assets
```

**Acciones a ejecutar:**

1. Crear el directorio principal:
   ```
   .agent/skills/<nombre-skill>/
   ```

2. Si el usuario indicó que necesita scripts:
   ```
   .agent/skills/<nombre-skill>/scripts/
   ```

---

### Paso 3: Creación del SKILL.md

Genera el archivo `SKILL.md` con la siguiente plantilla base:

```markdown
---
name: <nombre-skill>
description: <descripción-en-tercera-persona-con-keywords>
---

# <Título de la Skill>

<Breve párrafo introductorio explicando qué hace esta skill.>

## When to use this skill

Usa esta skill cuando:

- <Condición o trigger 1>
- <Condición o trigger 2>
- <Condición o trigger 3>

## How to use it

### Paso 1: <Nombre del paso>

<!-- TODO: Agregar instrucciones detalladas -->

### Paso 2: <Nombre del paso>

<!-- TODO: Agregar instrucciones detalladas -->

## Recursos adicionales

<!-- Opcional: listar scripts, ejemplos o recursos incluidos -->
```

**Reglas para el contenido:**

- El `name` debe coincidir con el nombre de la carpeta.
- La `description` debe ser concisa pero incluir palabras clave relevantes.
- Los encabezados `When to use this skill` y `How to use it` son **obligatorios**.
- Usa marcadores `<!-- TODO: ... -->` donde falten instrucciones específicas.

---

### Paso 4: Validación

Antes de finalizar, verifica los siguientes puntos:

| Criterio | Verificación |
|----------|--------------|
| **Nombre válido** | El nombre usa `kebab-case` sin caracteres especiales |
| **Descripción clara** | La descripción explica qué hace y cuándo usarla |
| **Frontmatter completo** | Contiene `name` y `description` |
| **Secciones obligatorias** | Tiene `When to use this skill` y `How to use it` |
| **Estructura correcta** | Los archivos están en `.agent/skills/<nombre>/` |

> [!TIP]  
> Una buena descripción es clave para que Antigravity detecte automáticamente cuándo usar la skill. Incluye verbos de acción y el contexto de uso.

---

## Plantilla de ejemplo completo

Para referencia, aquí hay un ejemplo de una skill simple pero bien estructurada:

```markdown
---
name: test-generator
description: Genera tests unitarios para código Python usando pytest y las convenciones del proyecto.
---

# Test Generator

Skill para generar tests unitarios automatizados siguiendo las mejores prácticas de pytest.

## When to use this skill

Usa esta skill cuando:

- El usuario pida "genera tests para esta función".
- Se necesite asegurar cobertura de código.
- Se esté haciendo refactoring y se quieran validar los cambios.

## How to use it

### Paso 1: Identificar el código objetivo

Localiza la función o clase que necesita tests.

### Paso 2: Generar tests

Crea un archivo de test siguiendo el patrón:
- `test_<nombre_modulo>.py`
- Una función de test por cada caso de uso

### Paso 3: Ejecutar y validar

Corre `pytest` para asegurar que los tests pasen.
```
