@echo off
rem Wrapper para compatibilidad: delega a scripts\fix_deps.bat
call "%~dp0scripts\fix_deps.bat" %*
exit /b %ERRORLEVEL%
