@echo off
setlocal
title OutGPT Enterprise - Publicar no dominio
cd /d "%~dp0backend"

python --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python nao foi encontrado neste computador.
  echo Instale em https://www.python.org/downloads/ marcando a opcao "Add python.exe to PATH"
  echo e de dois cliques neste arquivo de novo.
  echo.
  pause
  exit /b 1
)

echo.
echo ===== OutGPT Enterprise: publicar no dominio (Cloudflare) =====
echo.
echo [1/3] Verificando as bibliotecas (a primeira vez pode demorar alguns minutos)...
python -c "import chromadb, fastembed, anthropic, pypdf, docx" >nul 2>nul
if errorlevel 1 (
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Falha ao instalar as bibliotecas. Confira a conexao com a internet.
    pause
    exit /b 1
  )
)

echo [2/3] Preparando o banco de dados e a configuracao inicial...
python init_db.py >nul
if errorlevel 1 (
  echo Falha ao preparar o banco de dados.
  pause
  exit /b 1
)
python preparar.py
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo [3/3] Publicando...
python publicar.py
echo.
echo O tunel foi encerrado.
pause