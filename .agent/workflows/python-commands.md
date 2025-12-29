---
description: Ejecutar comandos Python en el proyecto Growen
---

# Comandos Python en Growen

Este proyecto usa un virtual environment (venv) ubicado en `.venv/`.

## Reglas

// turbo-all

1. **Python directo**: Usar `.\.venv\Scripts\python.exe` en lugar de `python`
2. **Pytest**: Usar `.\.venv\Scripts\python.exe -m pytest`
3. **Scripts**: Usar `.\.venv\Scripts\python.exe script.py`

## Ejemplos

### Ejecutar tests
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_example.py -v
```

### Ejecutar un script
```powershell
.\.venv\Scripts\python.exe scripts/mi_script.py
```

### Verificar imports
```powershell
.\.venv\Scripts\python.exe -c "from services.chat.cultivator import parse_npk_from_tags; print('OK')"
```

### Instalar dependencias
```powershell
.\.venv\Scripts\pip.exe install -r requirements.txt
```
