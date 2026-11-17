"""Testes rápidos (sem Docker, sem rede) do instalador de servidor: credenciais do túnel, .env, config do cloudflared, swap."""
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location("instalar", RAIZ / "servidor" / "instalar.py")
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)

ok = fail = 0
def chk(nome, cond, detalhe=""):
    global ok, fail
    ok += bool(cond); fail += not cond
    print(("PASS " if cond else "FAIL ") + nome + ("" if cond else f" | {detalhe}"))

TID = "4a110a74-9040-45e7-90c8-b6c8de879b5f"
CRED = {"AccountTag": "0123456789abcdef0123456789abcdef", "TunnelSecret": "c2VjcmV0by1kZS10ZXN0ZQ==", "TunnelID": TID}
token = base64.b64encode(json.dumps({"a": "0123456789abcdef0123456789abcdef", "t": TID, "s": "c2VjcmV0by1kZS10ZXN0ZS1jb20tYmFzdGFudGUtdGFtYW5obw=="}).encode()).decode()

# ---- endereço ----
chk("endereço: aceita https://, maiúsculas e barra final", inst.validar_dominio(" HTTPS://OutGPT.Ramosys.com.br/ ") == "outgpt.ramosys.com.br")
for ruim in ("", "semponto", "a b.com", "-x.com", "x.com/caminho", "x..com", "https://"):
    try:
        inst.validar_dominio(ruim); chk(f"endereço inválido recusado: {ruim!r}", False)
    except ValueError:
        chk(f"endereço inválido recusado: {ruim!r}", True)

# ---- credenciais do túnel ----
chk("credenciais: arquivo .json do cloudflared é aceito", inst.ler_credenciais(json.dumps(CRED))["TunnelID"] == TID)
chk("credenciais: aceita o campo extra Endpoint e espaços em volta", inst.ler_credenciais("  " + json.dumps({**CRED, "Endpoint": ""}) + "\n")["TunnelID"] == TID)
for nome, texto in (("vazio", ""), ("texto qualquer", "olá"), ("JSON de outro tipo", "[1,2]"), ("falta TunnelSecret", json.dumps({k: v for k, v in CRED.items() if k != "TunnelSecret"})),
                    ("TunnelID inválido", json.dumps({**CRED, "TunnelID": "nao-e-uuid"})), ("campo vazio", json.dumps({**CRED, "AccountTag": ""}))):
    try:
        inst.ler_credenciais(texto); chk(f"credenciais inválidas recusadas: {nome}", False)
    except ValueError:
        chk(f"credenciais inválidas recusadas: {nome}", True)
chk("token: puro e dentro do comando do painel", inst.extrair_token(token) == token and inst.extrair_token(f"cloudflared.exe service install {token}") == token)
chk("token: texto qualquer ou o .json não viram token", inst.extrair_token("x" * 200) is None and inst.extrair_token(json.dumps(CRED)) is None and inst.extrair_token("") is None)

# ---- config do cloudflared ----
cfg = inst.config_cloudflared(TID, "outgpt.ramosys.com.br")
chk("config do túnel: id, credenciais, domínio e serviço do contêiner", f"tunnel: {TID}" in cfg and "credentials-file: /etc/cloudflared/credenciais.json" in cfg
    and "hostname: outgpt.ramosys.com.br" in cfg and "service: http://outgpt:8000" in cfg and cfg.rstrip().endswith("service: http_status:404"), cfg)

# ---- .env ----
env = inst.montar_env({}, "outgpt.ramosys.com.br", "credenciais", chave_ia="sk-ant-teste_123-abc")
chk("env: modo credenciais usa o compose do servidor, sem token do túnel", env["COMPOSE_FILE"] == "docker-compose.servidor.yml" and "CLOUDFLARE_TUNNEL_TOKEN" not in env)
chk("env: gera senha de primeiro acesso longa e aleatória", len(env["OUTGPT_SETUP_TOKEN"]) >= 30 and env["OUTGPT_SETUP_TOKEN"] != inst.montar_env({}, "a.com", "credenciais")["OUTGPT_SETUP_TOKEN"])
chk("env: modelo padrão e chave da IA", env["OUTGPT_MODELO"] == "claude-opus-5-5" and env["ANTHROPIC_API_KEY"] == "sk-ant-teste_123-abc")
de_novo = inst.montar_env(env, "novo.ramosys.com.br", "credenciais")
chk("env: rodar de novo preserva a senha do primeiro acesso e a chave, e troca o endereço",
    de_novo["OUTGPT_SETUP_TOKEN"] == env["OUTGPT_SETUP_TOKEN"] and de_novo["ANTHROPIC_API_KEY"] == env["ANTHROPIC_API_KEY"] and de_novo["OUTGPT_DOMINIO"] == "novo.ramosys.com.br")
chk("env: modelo escolhido vale e é lembrado", inst.montar_env(env, "a.com", "credenciais", modelo="claude-haiku-5-5")["OUTGPT_MODELO"] == "claude-haiku-5-5"
    and inst.montar_env({"OUTGPT_MODELO": "claude-haiku-5-5"}, "a.com", "credenciais")["OUTGPT_MODELO"] == "claude-haiku-5-5")
env_tok = inst.montar_env({}, "a.com", "token", token_tunel=token)
chk("env: modo token usa o docker-compose.yml e guarda o token", env_tok["COMPOSE_FILE"] == "docker-compose.yml" and env_tok["CLOUDFLARE_TUNNEL_TOKEN"] == token)
chk("env: trocar de token para credenciais remove o token antigo", "CLOUDFLARE_TUNNEL_TOKEN" not in inst.montar_env(env_tok, "a.com", "credenciais"))
for ruim in ("com espaco", "com\nquebra", 'aspas"', "x#y"):
    try:
        inst.montar_env({}, "a.com", "credenciais", chave_ia=ruim); chk(f"env: valor perigoso recusado: {ruim!r}", False)
    except ValueError:
        chk(f"env: valor perigoso recusado: {ruim!r}", True)
tmp = Path(tempfile.mkdtemp())
(tmp / ".env").write_text(inst.texto_env(env), encoding="utf-8")
chk("env: texto gravado é lido de volta igual", inst.ler_env(tmp / ".env") == env and inst.ler_env(tmp / "nao-existe") == {})
chk("env: comentários e linhas soltas são ignorados", inst.ler_env(tmp / ".env").get("# Gerado por servidor/instalar.py. NÃO vai para o GitHub. Contém segredos: não compartilhe.") is None)

# ---- swap ----
chk("swap: servidor de 1 GB sem swap precisa", inst.precisa_swap("MemTotal:  980000 kB\nSwapTotal:  0 kB\n"))
chk("swap: servidor de 2 GB sem swap também (a instalação usa bastante memória)", inst.precisa_swap("MemTotal: 1950000 kB\nSwapTotal: 0 kB\n"))
chk("swap: já tem swap ou RAM grande, não precisa", not inst.precisa_swap("MemTotal: 980000 kB\nSwapTotal: 2097148 kB\n") and not inst.precisa_swap("MemTotal: 8000000 kB\nSwapTotal: 0 kB\n"))
chk("swap: leitura vazia não cria swap", not inst.precisa_swap("") and not inst.precisa_swap(None))

# ---- gravação de arquivos de ponta a ponta (como no servidor, sem Docker) ----
pasta = Path(tempfile.mkdtemp())
e = dict(os.environ, PYTHONIOENCODING="utf-8", OUTGPT_INSTALAR_CREDENCIAIS=json.dumps(CRED))
e.pop("ANTHROPIC_API_KEY", None)
r = subprocess.run([sys.executable, str(RAIZ / "servidor" / "instalar.py"), "--gerar-apenas", "--pasta", str(pasta), "--dominio", "teste.ramosys.com.br", "--sem-exemplos", "--sem-perguntas"],
                   env=e, capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
chk("instalador (--gerar-apenas) termina sem erro", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
chk("gera .env, cloudflared/config.yml e cloudflared/credenciais.json", all((pasta / p).is_file() for p in (".env", "cloudflared/config.yml", "cloudflared/credenciais.json")))
gerado = inst.ler_env(pasta / ".env")
chk("o .env gerado tem domínio, compose e senha do primeiro acesso", gerado.get("OUTGPT_DOMINIO") == "teste.ramosys.com.br" and gerado.get("COMPOSE_FILE") == "docker-compose.servidor.yml" and len(gerado.get("OUTGPT_SETUP_TOKEN", "")) >= 30)
chk("credenciais.json gravado igual ao informado", json.loads((pasta / "cloudflared" / "credenciais.json").read_text(encoding="utf-8")) == CRED)
chk("config.yml aponta o domínio informado", "hostname: teste.ramosys.com.br" in (pasta / "cloudflared" / "config.yml").read_text(encoding="utf-8"))
chk("o instalador não imprime o segredo do túnel", CRED["TunnelSecret"] not in r.stdout + r.stderr and CRED["AccountTag"] not in r.stdout + r.stderr)
if os.name == "posix":
    chk("permissões: .env e credenciais só do dono (600)", oct((pasta / ".env").stat().st_mode & 0o777) == "0o600" and oct((pasta / "cloudflared" / "credenciais.json").stat().st_mode & 0o777) == "0o600")
r2 = subprocess.run([sys.executable, str(RAIZ / "servidor" / "instalar.py"), "--gerar-apenas", "--pasta", str(pasta), "--sem-exemplos", "--sem-perguntas"],
                    env=dict(os.environ, PYTHONIOENCODING="utf-8", OUTGPT_INSTALAR_CREDENCIAIS=""), capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
gerado2 = inst.ler_env(pasta / ".env")
chk("rodar de novo mantém o túnel e a senha do primeiro acesso (sem perguntar nada)", r2.returncode == 0 and gerado2["OUTGPT_SETUP_TOKEN"] == gerado["OUTGPT_SETUP_TOKEN"] and "já configurado" in r2.stdout, r2.stdout[-300:] + r2.stderr[-300:])
r3 = subprocess.run([sys.executable, str(RAIZ / "servidor" / "instalar.py"), "--gerar-apenas", "--pasta", str(tempfile.mkdtemp()), "--dominio", "x.com.br", "--sem-exemplos", "--sem-perguntas"],
                    env=dict(os.environ, PYTHONIOENCODING="utf-8", OUTGPT_INSTALAR_CREDENCIAIS="isto não é o arquivo do túnel"), capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
chk("credenciais inválidas sem terminal: falha com mensagem clara, sem travar", r3.returncode != 0 and "credenciais do túnel" in (r3.stdout + r3.stderr), r3.stdout[-300:] + r3.stderr[-300:])

# ---- arquivos de implantação ----
compose = (RAIZ / "docker-compose.servidor.yml").read_text(encoding="utf-8")
chk("compose do servidor: não publica nenhuma porta na internet", not re.search(r"(?m)^\s*ports:", compose))
chk("compose do servidor: túnel lê ./cloudflared somente leitura e usa o config.yml", "./cloudflared:/etc/cloudflared:ro" in compose and "--config /etc/cloudflared/config.yml" in compose)
chk("compose do servidor: volume persistente de dados e reinício automático", "dados:/data" in compose and compose.count("restart: unless-stopped") == 2)
gi = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
chk("segredos do servidor estão no .gitignore (/.env e /cloudflared/)", "/.env" in gi and "/cloudflared/" in gi)
sh = (RAIZ / "servidor" / "instalar.sh").read_bytes()
chk("instalar.sh: termina em LF (sem CRLF) e chama o instalar.py", b"\r" not in sh and b"servidor/instalar.py" in sh)

print(f"\n{ok} ok, {fail} falhas")
sys.exit(1 if fail else 0)
