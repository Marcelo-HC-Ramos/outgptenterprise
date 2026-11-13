"""Espera o servidor do OutGPT responder (usado pelo INICIAR.bat). Sai com código 0 se respondeu, 1 se não.

Uso:  python aguardar.py            # espera até 3 minutos (o primeiro início carrega o modelo de busca)
      python aguardar.py --rapido   # só verifica se já está no ar (3 segundos)
"""
import os
import sys
import time
import urllib.request

porta = int(os.environ.get("OUTGPT_PORTA") or os.environ.get("PORT") or 8000)
limite = 3 if "--rapido" in sys.argv else 180
fim = time.time() + limite
while time.time() < fim:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{porta}/saude", timeout=2).read()
        sys.exit(0)
    except Exception:
        time.sleep(1)
sys.exit(1)