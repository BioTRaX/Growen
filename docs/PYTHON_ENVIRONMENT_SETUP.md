<!-- NG-HEADER: Nombre de archivo: PYTHON_ENVIRONMENT_SETUP.md -->
<!-- NG-HEADER: Ubicación: docs/PYTHON_ENVIRONMENT_SETUP.md -->
<!-- NG-HEADER: Descripción: Guía para evitar errores comunes de entorno Python -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Gestión de Entorno Python - Mejores Prácticas

Este documento explica cómo evitar el **error más común** en desarrollo Python: instalar dependencias en el Python global en lugar del entorno virtual del proyecto.

---

## ⚠️ Problema Común: Instalación en Python Global

### Síntoma
```bash
# Comando ejecutado sin .venv activado
pip install some-package

# Resultado: paquete instalado en Python global
# C:\Users\<user>\AppData\Local\Programs\Python\Python311\Lib\site-packages
```

### Consecuencias
1. ❌ **Conflictos de versiones**: El proyecto requiere `package==1.2.3` pero global tiene `package==2.0.0`
2. ❌ **Tests fallan**: pytest usa paquetes del global en lugar de los del proyecto
3. ❌ **Imports erróneos**: Código importa versiones incorrectas
4. ❌ **Deploy fallido**: Producción no tiene las dependencias globales de tu máquina
5. ❌ **Difícil de reproducir**: Otros desarrolladores no pueden replicar tu entorno

### Cómo Detectarlo
```bash
# Ver qué Python estás usando
python -c "import sys; print(sys.executable)"

# ❌ MAL (Python global):
# C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe

# ✅ BIEN (Entorno virtual):
# C:\Proyectos\NiceGrow\Growen\.venv\Scripts\python.exe
```

---

## ✅ Solución: SIEMPRE Usar Entorno Virtual

### Paso 1: Crear Entorno Virtual (solo primera vez)

```bash
# PowerShell
cd C:\Proyectos\NiceGrow\Growen
python -m venv .venv
```

### Paso 2: Activar ANTES de Cualquier Comando

```bash
# PowerShell
.\.venv\Scripts\Activate.ps1

# Bash (Git Bash, WSL, Linux, Mac)
source .venv/bin/activate

# Verificar que esté activado
# Debe aparecer (.venv) al inicio del prompt:
(.venv) PS C:\Proyectos\NiceGrow\Growen>
```

### Paso 3: Instalar Dependencias en .venv

```bash
# SIEMPRE con .venv activado
pip install -r requirements.txt

# O instalar paquete individual
pip install pytest

# Verificar instalación en .venv
pip list
```

---

## 🔧 Comandos Correctos por Tarea

### Instalar Dependencias del Proyecto

```bash
# ✅ CORRECTO
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# ❌ INCORRECTO (sin activar .venv)
pip install -r requirements.txt
```

### Ejecutar Tests

```bash
# ✅ CORRECTO
.\.venv\Scripts\Activate.ps1
pytest tests/ -v

# ❌ INCORRECTO
pytest tests/ -v  # usa pytest del global
```

### Ejecutar Scripts

```bash
# ✅ CORRECTO
.\.venv\Scripts\Activate.ps1
python scripts/mi_script.py

# ❌ INCORRECTO
python scripts/mi_script.py  # usa Python global
```

### Ejecutar Alembic

```bash
# ✅ CORRECTO
.\.venv\Scripts\Activate.ps1
alembic upgrade head

# ❌ INCORRECTO
alembic upgrade head  # usa alembic del global
```

### Ejecutar Backend

```bash
# ✅ CORRECTO
.\.venv\Scripts\Activate.ps1
uvicorn services.api:app --reload

# ❌ INCORRECTO
uvicorn services.api:app --reload
```

---

## 🚨 Cómo Recuperarse de Instalación Global Incorrecta

Si ya instalaste paquetes en el Python global por error:

### Paso 1: Verificar Estado Actual

```bash
# Ver dónde está instalado un paquete
pip show pytest

# Si la ruta es:
# Location: C:\Users\...\AppData\Local\Programs\Python\...
# ❌ Está en global
```

### Paso 2: Limpiar .venv Corrupto (Opcional)

```bash
# Eliminar entorno virtual corrupto
Remove-Item -Recurse -Force .venv

# Recrear limpio
python -m venv .venv
```

### Paso 3: Reinstalar Todo en .venv

```bash
# Activar
.\.venv\Scripts\Activate.ps1

# Reinstalar dependencias
pip install -r requirements.txt

# Verificar
pip show pytest
# Location: C:\Proyectos\NiceGrow\Growen\.venv\Lib\site-packages
# ✅ Ahora está en .venv
```

---

## 📋 Checklist Pre-Comando

**Antes de ejecutar CUALQUIER comando Python, verifica:**

- [ ] Terminal muestra `(.venv)` al inicio del prompt
- [ ] `python -c "import sys; print(sys.executable)"` apunta a `.venv\Scripts\python.exe`
- [ ] `pip list` muestra las dependencias del proyecto (no paquetes random del global)

---

## 🛠️ Configuración de VS Code

Para evitar el problema, configura VS Code para usar siempre el .venv:

### 1. Seleccionar Intérprete

1. `Ctrl+Shift+P`
2. Escribir: `Python: Select Interpreter`
3. Elegir: `.venv\Scripts\python.exe`

### 2. Configuración en .vscode/settings.json

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true,
  "python.testing.pytestEnabled": true,
  "python.testing.pytestPath": "${workspaceFolder}/.venv/Scripts/pytest.exe"
}
```

### 3. Verificar Terminal Integrado

Cuando abras una nueva terminal en VS Code, debe aparecer automáticamente:

```powershell
(.venv) PS C:\Proyectos\NiceGrow\Growen>
```

---

## 🐳 Docker y Entornos Virtuales

**IMPORTANTE**: Docker NO usa el .venv del host.

### Durante Desarrollo (Local)
- ✅ USA `.venv` del host
- Comando: `.\.venv\Scripts\Activate.ps1`

### Durante Build de Docker
- ✅ Docker crea su propio entorno en la imagen
- No necesita `.venv` del host
- Dockerfile instala dependencias directamente

### Dockerfile Correcto

```dockerfile
FROM python:3.14.6-slim-bookworm

WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias EN EL CONTENEDOR (no usa .venv del host)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

CMD ["uvicorn", "services.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📊 Comparación Rápida

| Tarea | ❌ Incorrecto | ✅ Correcto |
|-------|--------------|------------|
| Instalar deps | `pip install -r requirements.txt` | `.venv activate` → `pip install -r requirements.txt` |
| Ejecutar tests | `pytest` | `.venv activate` → `pytest` |
| Ejecutar script | `python script.py` | `.venv activate` → `python script.py` |
| Ver dependencias | `pip list` | `.venv activate` → `pip list` |
| Migración BD | `alembic upgrade head` | `.venv activate` → `alembic upgrade head` |

---

## 🔍 Debugging: ¿Por Qué Falla X?

### Pregunta 1: ¿Está activado .venv?
```bash
python -c "import sys; print(sys.executable)"
# Debe incluir ".venv"
```

### Pregunta 2: ¿El paquete está en .venv?
```bash
pip show <paquete>
# Location debe incluir ".venv"
```

### Pregunta 3: ¿VS Code usa el intérprete correcto?
- Mirar barra inferior de VS Code
- Debe decir: `Python 3.14.6+ ('.venv': venv)`

---

## 📚 Referencias

- [Python Virtual Environments](https://docs.python.org/3/tutorial/venv.html)
- [VS Code Python Environments](https://code.visualstudio.com/docs/python/environments)
- [pip User Guide](https://pip.pypa.io/en/stable/user_guide/)

---

## ⚡ TL;DR (Resumen Ejecutivo)

1. **NUNCA** ejecutes comandos Python sin activar `.venv`
2. **SIEMPRE** verifica que el prompt muestre `(.venv)`
3. **SI DUDAS**, ejecuta: `python -c "import sys; print(sys.executable)"`
4. **Si está corrupto**, borra `.venv` y recrea

```bash
# Template universal para CUALQUIER tarea Python
.\.venv\Scripts\Activate.ps1
<tu comando aquí>
```

---

**Última actualización**: 2025-11-12  
**Aplica a**: Python 3.14.6+, Windows PowerShell, VS Code
