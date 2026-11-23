@echo off
rem Desliga tudo o que INICIAR_PONTO_FALANTE.bat ligou.
title Ponto Falante - parar
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ponto_falante\parar.ps1"
echo.
pause
