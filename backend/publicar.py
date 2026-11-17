"""Publica o OutGPT no seu domínio pelo Cloudflare Tunnel (o servidor roda neste computador; o Cloudflare entrega o HTTPS).

Uso: PUBLICAR.bat (ou: python publicar.py)

Antes (uma vez, no painel do Cloudflare): criar um túnel, ligar o domínio a ele (Public Hostname -> http://localhost:8000) e copiar o token.
Veja o passo a passo em CLOUDFLARE.md. O token é guardado só em backend/.env (ignorado pelo Git).
"""
import base64
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

import db

DOMINIO_PADRAO = "outgpt.ramosys.com.br"
PORTA = int(os.environ.get("OUTGPT_PORTA") or os.environ.get("PORT") or 8000)


def ler(msg, secreto=False, padrao=""):
    try:
        v = getpass.getpass(msg) if secreto and sys.stdin.isatty() else input(msg)
    except EOFError:
        v = ""
    v = v.lstrip("\ufeff")
    return v if secreto else (v.strip() or padrao)


def extrair_token(texto):
    """Aceita o token puro ou o comando inteiro copiado do painel (ex.: 'cloudflared.exe service install eyJ...')."""
    for cand in re.findall(r"[A-Za-z0-9+/_=-]{80,}", texto or ""):
        try:
            d = json.loads(base64.b64decode(cand + "=" * (-len(cand) % 4)))
            if isinstance(d, dict) and {"a", "t", "s"} <= set(d):
                return cand
        except Exception:
            continue
    return None


def gravar_env(chave, valor):
    linhas = db.ENV_ARQ.read_text(encoding="utf-8").splitlines() if db.ENV_ARQ.exists() else []
    linhas = [l for l in linhas if not l.strip().startswith(chave + "=")]
    linhas.append(f"{chave}={valor}")
    db.ENV_ARQ.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.environ[chave] = valor


def achar_cloudflared():
    caminho = shutil.which("cloudflared")
    if caminho:
        return caminho
    candidatos = [r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe",
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WinGet\Links\cloudflared.exe")]
    return next((c for c in candidatos if c and os.path.exists(c)), None)


def garantir_cloudflared():
    exe = achar_cloudflared()
    if exe:
        return exe
    print("\nO programa 'cloudflared' (o túnel oficial do Cloudflare) não está instalado.")
    if not shutil.which("winget"):
        raise SystemExit("Instale o cloudflared em https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ e rode de novo.")
    if ler("Instalar agora pelo winget (pacote oficial Cloudflare.cloudflared)? [S/n]: ", padrao="s").lower().startswith("n"):
        raise SystemExit("Sem o cloudflared não dá para publicar. Instale e rode de novo.")
    subprocess.run(["winget", "install", "--id", "Cloudflare.cloudflared", "-e", "--accept-source-agreements", "--accept-package-agreements"])
    exe = achar_cloudflared()
    if not exe:
        raise SystemExit("Instalação concluída, mas o cloudflared ainda não foi encontrado. Feche esta janela, abra o PUBLICAR.bat de novo.")
    return exe


def no_ar(url, tempo=3):
    try:
        return urllib.request.urlopen(url, timeout=tempo).read() == b"ok"
    except Exception:
        return False


def garantir_servidor(dominio):
    if no_ar(f"http://127.0.0.1:{PORTA}/saude"):
        print("O servidor já está em execução. (Se ele foi aberto pelo INICIAR.bat, feche a janela dele e rode o PUBLICAR.bat de novo para ativar as proteções do modo público.)")
        return
    print("Iniciando o servidor em modo público...")
    env = {**os.environ, "OUTGPT_COOKIE_SECURE": "1", "OUTGPT_CONFIAR_PROXY": "1", "OUTGPT_DOMINIO": dominio}
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([sys.executable, "server.py"], cwd=str(db.BASE), env=env, creationflags=flags)
    for _ in range(180):
        if no_ar(f"http://127.0.0.1:{PORTA}/saude"):
            return
        time.sleep(1)
    raise SystemExit("O servidor não respondeu. Veja a janela 'server.py' para ler o erro.")


def vigiar_dominio(dominio):
    """Depois que o túnel conecta, confere se o endereço público responde e avisa o que fazer se não."""
    time.sleep(10)
    for i in range(24):
        if no_ar(f"https://{dominio}/saude", tempo=8):
            print(f"\n>>> NO AR: https://{dominio}\n>>> Para encerrar, feche esta janela (e a janela do servidor).\n")
            return
        time.sleep(5)
    print(f"\nO endereço https://{dominio} ainda não respondeu. Confira no painel do Cloudflare (Zero Trust > Networks > Tunnels):\n"
          f"  - o túnel está 'Healthy'?\n  - existe um Public Hostname {dominio} apontando para http://localhost:{PORTA}?\n")


def main():
    print("=== Publicar o OutGPT no seu domínio (Cloudflare Tunnel) ===")
    dominio = os.environ.get("OUTGPT_DOMINIO") or ler(f"Endereço público [{DOMINIO_PADRAO}]: ", padrao=DOMINIO_PADRAO)
    dominio = dominio.replace("https://", "").replace("http://", "").strip("/ ")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", dominio):
        raise SystemExit(f"Endereço inválido: {dominio}")
    gravar_env("OUTGPT_DOMINIO", dominio)

    token = extrair_token(os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", ""))
    if not token:
        print("\nCole o token do túnel (painel do Cloudflare > Zero Trust > Networks > Tunnels > seu túnel).")
        print("Pode colar o comando inteiro que o painel mostra: eu extraio o token.")
        for _ in range(3):
            token = extrair_token(ler("Token do túnel: ", secreto=True))
            if token:
                break
            print("  Não encontrei um token válido nesse texto. Copie de novo, inteiro.")
        if not token:
            raise SystemExit("Sem o token não dá para ligar o túnel. Veja CLOUDFLARE.md.")
        gravar_env("CLOUDFLARE_TUNNEL_TOKEN", token)
        print("  Token guardado em backend/.env (não vai para o GitHub).")

    exe = garantir_cloudflared()
    garantir_servidor(dominio)
    print(f"\nLigando o túnel para https://{dominio} ...")
    threading.Thread(target=vigiar_dominio, args=(dominio,), daemon=True).start()
    try:
        subprocess.run([exe, "tunnel", "--no-autoupdate", "run"], env={**os.environ, "TUNNEL_TOKEN": token})   # o token vai por variável, não pela linha de comando
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()