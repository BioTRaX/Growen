@echo off
rem Wrapper para compatibilidad: delega a scripts\stop.bat
call "%~dp0scripts\stop.bat" %*
exit /b %ERRORLEVEL%
