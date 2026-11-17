"""Publica o OutGPT no seu domínio pelo Cloudflare Tunnel (o servidor roda neste computador; o Cloudflare entrega o HTTPS).

Uso: PUBLICAR.bat (ou: python publicar.py)

Dois modos de criar o túnel (veja CLOUDFLARE.md):
  - SEM CARTÃO (padrão): o próprio cloudflared cria o túnel e o registro DNS depois que você autoriza o domínio no navegador
    (cloudflared tunnel login). Não exige ativar o Zero Trust.
  - COM TOKEN: túnel criado no painel Zero Trust (que pede cartão/PayPal para ativar, mesmo no plano gratuito); cole o token aqui.
O token (se houver) é guardado só em backend/.env, ignorado pelo Git.
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
from pathlib import Path

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
    achado = next((c for c in candidatos if c and os.path.exists(c)), None)
    if achado:
        return achado
    pacotes = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"      # onde o winget instala a versão portátil
    return next((str(x) for x in sorted(pacotes.glob("Cloudflare.cloudflared_*/cloudflared.exe"))), None) if pacotes.exists() else None


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


# ---------- Modo sem cartão: túnel criado pelo próprio cloudflared ----------
NOME_TUNEL = "outgpt"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def pasta_cf():
    return Path(os.environ.get("USERPROFILE") or Path.home()) / ".cloudflared"


def rodar(exe, *args):
    r = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def id_do_tunel(saida_json, nome):
    """ID do túnel com esse nome na saída JSON de 'cloudflared tunnel list' (ou None)."""
    try:
        dados = json.loads(saida_json)
    except ValueError:
        return None
    for t in dados or []:
        apagado = (t.get("deleted_at") or "")
        if t.get("name") == nome and (not apagado or apagado.startswith("0001-")):     # túneis ativos vêm com a data "zero" do Go (0001-01-01)
            return t.get("id")
    return None


def config_yaml(tunel_id, credenciais, dominio, porta):
    return (f"tunnel: {tunel_id}\ncredentials-file: '{credenciais}'\ningress:\n"
            f"  - hostname: {dominio}\n    service: http://localhost:{porta}\n  - service: http_status:404\n")


def garantir_login(exe):
    if (pasta_cf() / "cert.pem").exists():
        return
    print("\nVou abrir o login do Cloudflare. No navegador: entre na sua conta, escolha o domínio e clique em AUTORIZAR.")
    print("(Se o navegador não abrir sozinho, copie o endereço que aparecer abaixo e abra nele.)\n")
    subprocess.run([exe, "tunnel", "login"])            # imprime o endereço, espera a autorização e grava cert.pem
    if not (pasta_cf() / "cert.pem").exists():
        raise SystemExit("A autorização não foi concluída. Rode o PUBLICAR.bat de novo.")


def garantir_tunel(exe):
    codigo, saida = rodar(exe, "tunnel", "list", "--output", "json")
    tid = id_do_tunel(saida, NOME_TUNEL) if codigo == 0 else None
    if not tid:
        print(f"Criando o túnel '{NOME_TUNEL}'...")
        codigo, saida = rodar(exe, "tunnel", "create", NOME_TUNEL)
        achado = re.search(UUID, saida)
        if codigo != 0 or not achado:
            raise SystemExit("Não consegui criar o túnel:\n" + saida)
        tid = achado.group(0)
    cred = pasta_cf() / f"{tid}.json"
    if not cred.exists():
        raise SystemExit(f"O túnel '{NOME_TUNEL}' existe, mas o arquivo de credenciais {cred} não está neste computador.\n"
                         f"Apague o túnel com:  cloudflared tunnel delete {NOME_TUNEL}   e rode o PUBLICAR.bat de novo.")
    return tid, cred


def garantir_dns(exe, dominio):
    codigo, saida = rodar(exe, "tunnel", "route", "dns", NOME_TUNEL, dominio)
    if codigo != 0:
        if "already" in saida.lower():
            print(f"Aviso: já existe um registro DNS para {dominio}. Confira no painel (DNS) se é um CNAME para o túnel; se for de outro serviço, apague-o e rode de novo.")
        else:
            raise SystemExit("Não consegui criar o registro DNS do domínio:\n" + saida)
    else:
        print(saida.strip().splitlines()[-1] if saida.strip() else f"Registro DNS de {dominio} criado.")


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
    print(f"\nO endereço https://{dominio} ainda não respondeu. Confira no painel do Cloudflare:\n"
          f"  - DNS: deve existir um CNAME {dominio} apontando para <id-do-túnel>.cfargotunnel.com (com a nuvem laranja);\n"
          f"  - a janela do túnel mostra 'Registered tunnel connection'?\n")


def main():
    print("=== Publicar o OutGPT no seu domínio (Cloudflare Tunnel) ===")
    dominio = os.environ.get("OUTGPT_DOMINIO") or ler(f"Endereço público [{DOMINIO_PADRAO}]: ", padrao=DOMINIO_PADRAO)
    dominio = dominio.replace("https://", "").replace("http://", "").strip("/ ")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", dominio):
        raise SystemExit(f"Endereço inválido: {dominio}")
    gravar_env("OUTGPT_DOMINIO", dominio)

    token = extrair_token(os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", ""))
    if not token and os.environ.get("CLOUDFLARE_MODO") != "cli":
        print("\nModo SEM CARTÃO (recomendado): o túnel é criado por este programa, depois que você autorizar o domínio no navegador.")
        print("Se você já criou um túnel no painel Zero Trust, cole o token (ou o comando inteiro) aqui; senão, aperte Enter.")
        token = extrair_token(ler("Token do túnel (Enter = modo sem cartão): ", secreto=True))
        if token:
            gravar_env("CLOUDFLARE_TUNNEL_TOKEN", token)
            print("  Token guardado em backend/.env (não vai para o GitHub).")

    exe = garantir_cloudflared()
    if token:
        comando, env = [exe, "tunnel", "--no-autoupdate", "run"], {**os.environ, "TUNNEL_TOKEN": token}   # token por variável, não pela linha de comando
    else:
        garantir_login(exe)
        tid, cred = garantir_tunel(exe)
        garantir_dns(exe, dominio)
        cfg = pasta_cf() / "outgpt-config.yml"
        cfg.write_text(config_yaml(tid, cred, dominio, PORTA), encoding="utf-8")
        gravar_env("CLOUDFLARE_MODO", "cli")
        comando, env = [exe, "tunnel", "--no-autoupdate", "--config", str(cfg), "run", NOME_TUNEL], os.environ.copy()

    garantir_servidor(dominio)
    print(f"\nLigando o túnel para https://{dominio} ...")
    threading.Thread(target=vigiar_dominio, args=(dominio,), daemon=True).start()
    try:
        subprocess.run(comando, env=env)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
