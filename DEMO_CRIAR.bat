@echo off
setlocal
title OutGPT - dados de demonstracao
cd /d "%~dp0backend"
python --version >nul 2>nul
if errorlevel 1 (
  echo Python nao foi encontrado neste computador.
  pause
  exit /b 1
)
echo.
echo ===== Criar dados de demonstracao para a apresentacao =====
echo Cria departamentos, colaboradores simulados e um historico de estudo na primeira empresa.
echo.
python init_db.py >nul
python demo_apresentacao.py criar
echo.
echo ANOTE a senha do Colaborador Demo acima (ela so aparece agora).
echo Depois da apresentacao, de dois cliques em DEMO_REMOVER.bat.
echo.
pause
