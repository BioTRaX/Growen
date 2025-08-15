@echo off
setlocal
chcp 65001 >NUL
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] No existe .venv\Scripts\activate.bat
  echo Cree el entorno: python -m venv .venv
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

python "scripts\generate_requirements.py"
if errorlevel 1 (
  color 0C
  echo [ERROR] No se pudo generar requirements.txt
  color 07
  pause
  exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
  color 0C
  echo [ERROR] Falló la instalación de dependencias
  color 07
  pause
  exit /b 1
)

color 0A
echo [OK] Dependencias instaladas correctamente
color 07
pause
exit /b 0
