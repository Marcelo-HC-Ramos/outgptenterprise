#!/usr/bin/env python3
"""Instala (ou atualiza) o OutGPT Enterprise em um servidor Ubuntu/Debian que fica ligado 24 horas.

Uso, como administrador:   sudo sh servidor/instalar.sh      (baixa o projeto e chama este programa; veja SERVIDOR.md)

O que faz, em ordem:
  1. instala o Docker (se faltar) e cria memória de troca (swap) em servidores com pouca RAM;
  2. pergunta o endereço, as credenciais do túnel Cloudflare (arquivo .json) e a chave da IA; gera a senha do primeiro acesso;
  3. grava .env e cloudflared/ na pasta do projeto (ficam fora do GitHub; só o administrador lê);
  4. sobe o sistema + o túnel (docker compose), espera responder e agenda o backup diário.
Rodar de novo atualiza o sistema sem perder o banco nem as respostas já dadas (ele reaproveita o .env).

Opções para testes/automação: --gerar-apenas (só grava os arquivos), --sem-perguntas, --dominio, --pasta, --sem-exemplos, --trocar-tunel.
Sem terminal interativo, as credenciais vêm da variável OUTGPT_INSTALAR_CREDENCIAIS e a chave da IA de ANTHROPIC_API_KEY.
"""
import argparse
import base64
import getpass
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
DOMINIO_PADRAO = "outgpt.ramosys.com.br"
MODELO_PADRAO = "claude-opus-5-5"
COMPOSE_CREDENCIAIS = "docker-compose.servidor.yml"      # túnel criado sem cartão (arquivo .json de credenciais)
COMPOSE_TOKEN = "docker-compose.yml"                      # túnel criado no painel Zero Trust (token)
UA = "Mozilla/5.0 (compatible; OutGPT-instalador/1.0)"    # o Cloudflare bloqueia o User-Agent padrão do Python (erro 1010)
DONO_CLOUDFLARED = 65532                                   # usuário "nonroot" da imagem cloudflare/cloudflared
INTERATIVO = sys.stdin.isatty()                            # --sem-perguntas desliga (automação e testes)


# ---------- Funções puras (testadas em backend/tests/teste_servidor.py) ----------
def validar_dominio(texto):
    d = (texto or "").strip().lower().replace("https://", "").replace("http://", "").strip("/ ")
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", d):
        raise ValueError(f"Endereço inválido: {texto!r}. Exemplo: outgpt.ramosys.com.br")
    return d


def ler_credenciais(texto):
    """Conteúdo do arquivo <id-do-túnel>.json criado pelo cloudflared. Levanta ValueError se não for isso."""
    try:
        d = json.loads((texto or "").strip())
    except ValueError:
        raise ValueError("Isso não parece o conteúdo do arquivo .json do túnel.")
    if not isinstance(d, dict) or not all(isinstance(d.get(k), str) and d[k] for k in ("AccountTag", "TunnelSecret", "TunnelID")):
        raise ValueError("Faltam campos no arquivo do túnel (AccountTag, TunnelSecret e TunnelID).")
    if not re.fullmatch(UUID, d["TunnelID"]):
        raise ValueError("O TunnelID do arquivo não é válido.")
    return d


def extrair_token(texto):
    """Token do túnel criado no painel Zero Trust (aceita o token puro ou o comando inteiro copiado do painel)."""
    for cand in re.findall(r"[A-Za-z0-9+/_=-]{80,}", texto or ""):
        try:
            d = json.loads(base64.b64decode(cand + "=" * (-len(cand) % 4)))
            if isinstance(d, dict) and {"a", "t", "s"} <= set(d):
                return cand
        except Exception:
            continue
    return None


def config_cloudflared(tunel_id, dominio):
    return (f"tunnel: {tunel_id}\ncredentials-file: /etc/cloudflared/credenciais.json\ningress:\n"
            f"  - hostname: {dominio}\n    service: http://outgpt:8000\n  - service: http_status:404\n")


def ler_env(caminho):
    out = {}
    try:
        linhas = Path(caminho).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for linha in linhas:
        if "=" in linha and not linha.lstrip().startswith("#"):
            k, v = linha.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def montar_env(atual, dominio, modo, token_tunel="", chave_ia="", modelo=""):
    """Valores do .env do servidor. Preserva o que já existe (inclusive a senha do primeiro acesso) ao rodar de novo."""
    env = dict(atual)
    env["COMPOSE_FILE"] = COMPOSE_CREDENCIAIS if modo == "credenciais" else COMPOSE_TOKEN
    env["OUTGPT_DOMINIO"] = dominio
    env["OUTGPT_SETUP_TOKEN"] = atual.get("OUTGPT_SETUP_TOKEN") or secrets.token_urlsafe(24)
    env["OUTGPT_MODELO"] = modelo or atual.get("OUTGPT_MODELO") or MODELO_PADRAO
    if chave_ia:
        env["ANTHROPIC_API_KEY"] = chave_ia
    if modo == "token":
        env["CLOUDFLARE_TUNNEL_TOKEN"] = token_tunel or atual.get("CLOUDFLARE_TUNNEL_TOKEN", "")
    else:
        env.pop("CLOUDFLARE_TUNNEL_TOKEN", None)
    for k, v in env.items():
        if not re.fullmatch(r"[A-Za-z0-9_\-.:/+=@]*", v):
            raise ValueError(f"O valor de {k} tem caracteres que não podem ir no .env (espaços, aspas ou quebras de linha).")
    return env


def texto_env(env):
    return "# Gerado por servidor/instalar.py. NÃO vai para o GitHub. Contém segredos: não compartilhe.\n" + \
           "".join(f"{k}={v}\n" for k, v in env.items())


def precisa_swap(meminfo):
    """True se a RAM é pequena (< ~3 GB) e o servidor ainda não tem memória de troca (swap)."""
    kb = {}
    for linha in (meminfo or "").splitlines():
        if ":" in linha:
            k, v = linha.split(":", 1)
            partes = v.split()
            if partes and partes[0].isdigit():
                kb[k.strip()] = int(partes[0])
    if "MemTotal" not in kb:
        return False                      # não deu para ler a memória: não mexe
    return kb.get("MemTotal", 0) < 3_000_000 and kb.get("SwapTotal", 0) == 0


# ---------- Gravação dos arquivos ----------
def gravar_secreto(caminho, texto):
    caminho = Path(caminho)
    fd = os.open(str(caminho), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass


def gravar_tunel(pasta, cred, dominio):
    d = Path(pasta) / "cloudflared"
    d.mkdir(exist_ok=True)
    gravar_secreto(d / "credenciais.json", json.dumps(cred))
    (d / "config.yml").write_text(config_cloudflared(cred["TunnelID"], dominio), encoding="utf-8", newline="\n")
    if hasattr(os, "geteuid") and os.geteuid() == 0:       # o cloudflared roda como "nonroot" dentro do contêiner e precisa ler
        for p in (d, d / "credenciais.json", d / "config.yml"):
            os.chown(p, DONO_CLOUDFLARED, DONO_CLOUDFLARED)
        os.chmod(d / "credenciais.json", 0o600)


# ---------- Perguntas ----------
def perguntar(texto, secreto=False, padrao=""):
    if not INTERATIVO:                      # automação/testes: não pergunta, usa o padrão
        return padrao
    try:
        v = (getpass.getpass(texto) if secreto else input(texto)).strip()
    except EOFError:
        v = ""
    return v or padrao


def pedir_tunel():
    """Devolve ('credenciais', dict) ou ('token', str), lendo do ambiente ou perguntando (3 tentativas)."""
    pre = os.environ.get("OUTGPT_INSTALAR_CREDENCIAIS", "")
    for tentativa in range(3):
        texto = pre or perguntar("\nCole o conteúdo do arquivo .json do túnel (ou o token, se criou o túnel no painel) e tecle Enter:\n> ", secreto=True)
        pre = ""
        if not texto:
            print("  Nada foi colado.")
            continue
        try:
            return "credenciais", ler_credenciais(texto)
        except ValueError as e:
            tok = extrair_token(texto)
            if tok:
                return "token", tok
            print("  " + str(e))
    raise SystemExit("Não consegui ler as credenciais do túnel. Veja o passo 3 do SERVIDOR.md.")


# ---------- Sistema (só roda no servidor) ----------
def exigir_root():
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise SystemExit("Rode como administrador:  sudo sh servidor/instalar.sh")


def sh(cmd, pasta, check=True, **kw):
    print("$ " + " ".join(shlex.quote(c) for c in cmd), flush=True)
    return subprocess.run(cmd, cwd=str(pasta), check=check, **kw)


def garantir_docker(pasta):
    if shutil.which("docker") and subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
        return
    print("Instalando o Docker (script oficial get.docker.com) ...")
    arq = Path("/tmp/get-docker.sh")
    req = urllib.request.Request("https://get.docker.com", headers={"User-Agent": UA})
    arq.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    sh(["sh", str(arq)], pasta)
    sh(["systemctl", "enable", "--now", "docker"], pasta, check=False)
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0:
        raise SystemExit("O Docker não ficou disponível. Veja a mensagem acima.")


def garantir_swap(pasta):
    try:
        info = Path("/proc/meminfo").read_text()
    except OSError:
        return
    if not precisa_swap(info) or Path("/swapfile").exists():
        return
    print("Pouca memória no servidor: criando 2 GB de memória de troca (swap) para a instalação não travar ...")
    if sh(["fallocate", "-l", "2G", "/swapfile"], pasta, check=False).returncode != 0:
        sh(["dd", "if=/dev/zero", "of=/swapfile", "bs=1M", "count=2048"], pasta)
    os.chmod("/swapfile", 0o600)
    sh(["mkswap", "/swapfile"], pasta)
    sh(["swapon", "/swapfile"], pasta)
    with open("/etc/fstab", "a", encoding="utf-8") as f:
        f.write("/swapfile none swap sw 0 0\n")


def esperar(teste, segundos, pausa=3):
    fim = time.time() + segundos
    while time.time() < fim:
        if teste():
            return True
        time.sleep(pausa)
    return False


def agendar_backup(pasta):
    if not Path("/etc/cron.d").is_dir():
        return
    cmd = f"cd {shlex.quote(str(pasta))} && docker compose exec -T -u app outgpt python backup.py /data/backups"
    Path("/etc/cron.d/outgpt-backup").write_text(f"17 3 * * * root {cmd} >> /var/log/outgpt-backup.log 2>&1\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Instala o OutGPT em um servidor sempre ligado.")
    ap.add_argument("--dominio")
    ap.add_argument("--pasta", default=str(RAIZ))
    ap.add_argument("--gerar-apenas", action="store_true", help="só grava .env e cloudflared/ (testes), sem Docker")
    ap.add_argument("--sem-exemplos", action="store_true", help="não oferece os 100 procedimentos de exemplo")
    ap.add_argument("--trocar-tunel", action="store_true", help="pede de novo as credenciais do túnel")
    ap.add_argument("--sem-perguntas", action="store_true", help="nunca pergunta nada (automação e testes)")
    a = ap.parse_args()
    global INTERATIVO
    INTERATIVO = INTERATIVO and not a.sem_perguntas
    pasta = Path(a.pasta).resolve()
    primeira_vez = not (pasta / ".env").exists()

    print("=== Instalar o OutGPT Enterprise neste servidor ===")
    if not a.gerar_apenas:
        exigir_root()
        garantir_docker(pasta)
        garantir_swap(pasta)

    atual = ler_env(pasta / ".env")
    try:
        dominio = validar_dominio(a.dominio or perguntar(f"Endereço público do sistema [{atual.get('OUTGPT_DOMINIO') or DOMINIO_PADRAO}]: ",
                                                         padrao=atual.get("OUTGPT_DOMINIO") or DOMINIO_PADRAO))
    except ValueError as e:
        raise SystemExit(str(e))

    ja_tem_tunel = (pasta / "cloudflared" / "credenciais.json").exists() or atual.get("CLOUDFLARE_TUNNEL_TOKEN")
    if ja_tem_tunel and not a.trocar_tunel:
        print("Túnel Cloudflare já configurado: mantendo (use --trocar-tunel para trocar).")
        modo = "token" if atual.get("CLOUDFLARE_TUNNEL_TOKEN") else "credenciais"
        token = atual.get("CLOUDFLARE_TUNNEL_TOKEN", "")
        if modo == "credenciais":      # o endereço pode ter mudado: refaz só o config.yml
            cred = json.loads((pasta / "cloudflared" / "credenciais.json").read_text(encoding="utf-8"))
            gravar_tunel(pasta, cred, dominio)
    else:
        modo, dado = pedir_tunel()
        token = dado if modo == "token" else ""
        if modo == "credenciais":
            gravar_tunel(pasta, dado, dominio)

    chave = os.environ.get("ANTHROPIC_API_KEY", "")
    if not chave and not atual.get("ANTHROPIC_API_KEY") and INTERATIVO:
        chave = perguntar("Chave da API da Anthropic (sk-ant-...; Enter = colar depois, no site): ", secreto=True)
    try:
        env = montar_env(atual, dominio, modo, token, chave)
    except ValueError as e:
        raise SystemExit(str(e))
    gravar_secreto(pasta / ".env", texto_env(env))
    print(f"Arquivos gravados em {pasta} (.env e cloudflared/).")
    if a.gerar_apenas:
        return

    sh(["docker", "compose", "up", "-d", "--build"], pasta)
    print("Esperando o sistema responder (a primeira vez pode levar alguns minutos) ...")
    pronto = esperar(lambda: subprocess.run(
        ["docker", "compose", "exec", "-T", "outgpt", "python", "-c",
         "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/saude',timeout=3)"],
        cwd=str(pasta), capture_output=True).returncode == 0, 300)
    if not pronto:
        sh(["docker", "compose", "logs", "--tail", "40", "outgpt"], pasta, check=False)
        raise SystemExit("O sistema não respondeu a tempo. Veja o log acima.")

    if primeira_vez and not a.sem_exemplos and INTERATIVO:
        if perguntar("Carregar agora os 100 procedimentos de exemplo, em uma empresa chamada 'Minha Empresa'? [S/n] ", padrao="s").lower().startswith("s"):
            sh(["docker", "compose", "exec", "-T", "-u", "app", "outgpt", "python", "rag.py", "importar", "Minha Empresa",
                "data/sops_corporativos.csv", "internos"], pasta, check=False)

    agendar_backup(pasta)
    tunel_ok = esperar(lambda: "Registered tunnel connection" in (subprocess.run(
        ["docker", "compose", "logs", "--no-color", "cloudflared"], cwd=str(pasta), capture_output=True, text=True).stdout or ""), 90)
    publico = False
    if tunel_ok:
        def ver():
            try:
                req = urllib.request.Request(f"https://{dominio}/saude", headers={"User-Agent": UA})
                return urllib.request.urlopen(req, timeout=10).status == 200
            except Exception:
                return False
        publico = esperar(ver, 60)

    token_setup = env["OUTGPT_SETUP_TOKEN"]
    print("\n" + "=" * 64)
    if publico:
        print(f"NO AR: https://{dominio}")
    else:
        print(f"O sistema está rodando, mas https://{dominio} ainda não respondeu.")
        print("Confira: o túnel 'outgpt' não pode estar ligado em outro computador (feche o PUBLICAR.bat) e o DNS deve apontar para ele.")
        print("Log do túnel:  cd " + str(pasta) + " && docker compose logs --tail 30 cloudflared")
    print("\nPrimeiro acesso: abra o endereço, informe a senha abaixo na tela 'Primeiro acesso' e crie o seu login de dono (master).")
    print(f"Senha do primeiro acesso: {token_setup}   (fica guardada em {pasta}/.env)")
    print("Atualizar o sistema depois:  sudo sh " + str(pasta / "servidor" / "instalar.sh"))
    print("Backup diário às 03:17 em /data/backups (dentro do volume do Docker). COPIE para fora do servidor de vez em quando.")
    print("=" * 64)


if __name__ == "__main__":
    main()
