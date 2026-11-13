@echo off
setlocal
title OutGPT Enterprise
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

python aguardar.py --rapido >nul 2>nul
if not errorlevel 1 (
  echo O OutGPT ja esta em execucao. Abrindo o navegador...
  start "" http://localhost:8000
  exit /b 0
)

echo.
echo ===== OutGPT Enterprise =====
echo.
echo [1/4] Verificando as bibliotecas (a primeira vez pode demorar alguns minutos)...
python -c "import chromadb, fastembed, anthropic, pypdf, docx" >nul 2>nul
if errorlevel 1 (
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Falha ao instalar as bibliotecas. Confira a conexao com a internet.
    pause
    exit /b 1
  )
)

echo [2/4] Preparando o banco de dados...
python init_db.py >nul
if errorlevel 1 (
  echo Falha ao preparar o banco de dados.
  pause
  exit /b 1
)

echo [3/4] Configuracao inicial...
python preparar.py
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo [4/4] Iniciando o servidor...
start "OutGPT - servidor (nao feche esta janela)" python server.py
python aguardar.py
if errorlevel 1 (
  echo O servidor nao respondeu. Veja a janela "OutGPT - servidor" para ler o erro.
  pause
  exit /b 1
)
start "" http://localhost:8000

echo.
echo OutGPT no ar em http://localhost:8000
echo Para encerrar, feche a janela "OutGPT - servidor".
timeout /t 6 >nul