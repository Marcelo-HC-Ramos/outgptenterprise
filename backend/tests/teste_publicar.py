"""Testes rápidos (sem rede) do assistente de publicação: extração do token do Cloudflare e gravação no .env."""
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["OUTGPT_ENV_ARQ"] = os.path.join(tmp, "x.env")
os.environ.pop("CLOUDFLARE_TUNNEL_TOKEN", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import publicar  # noqa: E402

token = base64.b64encode(json.dumps({"a": "0123456789abcdef0123456789abcdef", "t": "11111111-2222-3333-4444-555555555555", "s": "c2VjcmV0by1kZS10ZXN0ZS1jb20tYmFzdGFudGUtdGFtYW5obw=="}).encode()).decode()
ok = fail = 0
def chk(nome, cond):
    global ok, fail
    ok += bool(cond); fail += not cond
    print(("PASS " if cond else "FAIL ") + nome)

chk("token puro é reconhecido", publicar.extrair_token(token) == token)
chk("comando inteiro do painel: extrai só o token", publicar.extrair_token(f"cloudflared.exe service install {token}") == token)
chk("comando docker run do painel também funciona", publicar.extrair_token(f"docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token {token}") == token)
chk("texto longo qualquer não vira token", publicar.extrair_token("x" * 200) is None)
chk("base64 que não é JSON de túnel é recusado", publicar.extrair_token(base64.b64encode(b"isto nao e um token do cloudflare, so um texto longo " * 3).decode()) is None)
chk("vazio / None", publicar.extrair_token("") is None and publicar.extrair_token(None) is None)
publicar.gravar_env("OUTGPT_DOMINIO", "outgpt.exemplo.com.br")
publicar.gravar_env("CLOUDFLARE_TUNNEL_TOKEN", token)
publicar.gravar_env("OUTGPT_DOMINIO", "novo.exemplo.com.br")
conteudo = open(os.environ["OUTGPT_ENV_ARQ"], encoding="utf-8").read().splitlines()
chk("gravar_env atualiza sem duplicar chaves", conteudo.count("OUTGPT_DOMINIO=novo.exemplo.com.br") == 1 and sum(l.startswith("OUTGPT_DOMINIO=") for l in conteudo) == 1 and f"CLOUDFLARE_TUNNEL_TOKEN={token}" in conteudo)
chk("o token gravado é lido de volta", publicar.extrair_token(os.environ["CLOUDFLARE_TUNNEL_TOKEN"]) == token)
print(f"\n{ok} ok, {fail} falhas")
sys.exit(1 if fail else 0)