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
# ----- modo sem cartão (túnel criado pelo cloudflared) -----
lista = json.dumps([{"id": "aaaaaaaa-1111-2222-3333-444444444444", "name": "outro", "deleted_at": "0001-01-01T00:00:00Z"},
                    {"id": "bbbbbbbb-1111-2222-3333-444444444444", "name": "outgpt", "deleted_at": "0001-01-01T00:00:00Z"},   # formato real: túnel ativo
                    {"id": "cccccccc-1111-2222-3333-444444444444", "name": "outgpt", "deleted_at": "2026-01-01T00:00:00Z"}])
chk("lista de túneis: acha o túnel ativo pelo nome (deleted_at zerado = ativo)", publicar.id_do_tunel(lista, "outgpt") == "bbbbbbbb-1111-2222-3333-444444444444")
chk("lista de túneis: ignora túneis apagados e outros nomes", publicar.id_do_tunel(lista, "inexistente") is None and publicar.id_do_tunel(json.dumps([{"id": "y", "name": "outgpt", "deleted_at": None}]), "outgpt") == "y" and publicar.id_do_tunel(json.dumps([{"id": "x", "name": "outgpt", "deleted_at": "2026-01-01"}]), "outgpt") is None)
chk("lista de túneis: saída inválida ou vazia", publicar.id_do_tunel("erro qualquer", "outgpt") is None and publicar.id_do_tunel("null", "outgpt") is None)
aviso = "2026-11-17T19:08:15Z WRN Your version 2026.11.0 is outdated. We recommend upgrading it to 2026.11.1\n"
chk("lista de túneis: aviso de versão misturado à saída não impede a leitura", publicar.id_do_tunel(aviso + lista + "\n" + aviso, "outgpt") == "bbbbbbbb-1111-2222-3333-444444444444")
chk("lista de túneis: colchetes soltos num aviso são ignorados", publicar.id_do_tunel("WRN [1] aviso\n" + lista, "outgpt") == "bbbbbbbb-1111-2222-3333-444444444444")
import tempfile, pathlib
with tempfile.TemporaryDirectory() as _d:
    chk("credenciais: sem arquivo, sem túnel", publicar.id_pelas_credenciais(_d) is None)
    (pathlib.Path(_d) / "cert.pem").write_text("x"); (pathlib.Path(_d) / "4a110a74-9040-45e7-90c8-b6c8de879b5f.json").write_text("{}")
    chk("credenciais: um único <id>.json é o túnel (cert.pem é ignorado)", publicar.id_pelas_credenciais(_d) == "4a110a74-9040-45e7-90c8-b6c8de879b5f")
    (pathlib.Path(_d) / "5a110a74-9040-45e7-90c8-b6c8de879b5f.json").write_text("{}")
    chk("credenciais: dois arquivos = ambíguo, não adivinha", publicar.id_pelas_credenciais(_d) is None)
saida_create = "Tunnel credentials written to C:\\Users\\X\\.cloudflared\\0a1b2c3d-1111-2222-3333-444455556666.json. cloudflared chose this file...\nCreated tunnel outgpt with id 0a1b2c3d-1111-2222-3333-444455556666"
import re
chk("saída do 'tunnel create': extrai o ID do túnel", re.search(publicar.UUID, saida_create).group(0) == "0a1b2c3d-1111-2222-3333-444455556666")
cfg = publicar.config_yaml("0a1b2c3d-1111-2222-3333-444455556666", r"C:\Users\X\.cloudflared\0a1b2c3d-1111-2222-3333-444455556666.json", "outgpt.exemplo.com.br", 8000)
chk("config do túnel: hostname, serviço local e 404 padrão", "tunnel: 0a1b2c3d-1111-2222-3333-444455556666" in cfg and "hostname: outgpt.exemplo.com.br" in cfg and "service: http://localhost:8000" in cfg and cfg.rstrip().endswith("service: http_status:404"))
chk("config do túnel: caminho do Windows entre aspas simples", "credentials-file: 'C:\\Users\\X\\.cloudflared\\" in cfg)
print(f"\n{ok} ok, {fail} falhas")
sys.exit(1 if fail else 0)