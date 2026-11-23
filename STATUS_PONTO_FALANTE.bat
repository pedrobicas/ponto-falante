@echo off
rem Mostra o estado de cada servico e faz um teste de ponta a ponta pelo site publicado.
title Ponto Falante - status
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ponto_falante\status.ps1" -Testar
echo.
pause
