@echo off
rem Liga com um clique tudo o que o site publicado do Ponto Falante precisa deste PC:
rem Ollama + modelo, API da GenAI, servico de visao, tuneis da Cloudflare, registro no site e o robo RPA.
rem Opcoes: INICIAR_PONTO_FALANTE.bat -SemNavegador -SemRpa -SemVisao
title Ponto Falante - iniciar
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ponto_falante\iniciar.ps1" %*
echo.
echo Pode fechar esta janela: os servicos continuam rodando em segundo plano.
pause
