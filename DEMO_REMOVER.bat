@echo off
setlocal
title OutGPT - remover dados de demonstracao
cd /d "%~dp0backend"
echo.
echo ===== Remover os dados de demonstracao =====
echo.
python demo_apresentacao.py remover
echo.
pause
