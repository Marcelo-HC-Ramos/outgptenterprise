"""Testes rápidos (sem servidor) da leitura do IP real e do domínio aceito atrás de proxy/Cloudflare."""
import os
import sys
from pathlib import Path

os.environ.update({"OUTGPT_CONFIAR_PROXY": "1", "OUTGPT_DOMINIO": "https://outgpt.exemplo.com.br/, www.exemplo.com.br"})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402


class Falso:
    def __init__(self, headers, ip="127.0.0.1"):
        self.headers, self.client_address = headers, (ip, 1234)
    _ip = server.Handler._ip
    _origem_permitida = server.Handler._origem_permitida


ok = fail = 0
def chk(nome, cond):
    global ok, fail
    ok += bool(cond); fail += not cond
    print(("PASS " if cond else "FAIL ") + nome)

chk("Cloudflare: usa CF-Connecting-IP", Falso({"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "1.1.1.1, 2.2.2.2"})._ip() == "203.0.113.7")
chk("sem Cloudflare: usa o último X-Forwarded-For", Falso({"X-Forwarded-For": "1.1.1.1, 2.2.2.2"})._ip() == "2.2.2.2")
chk("sem cabeçalhos: usa o IP da conexão", Falso({}, "10.0.0.5")._ip() == "10.0.0.5")
chk("domínio configurado é aceito no Origin (com https:// e barra removidos)", Falso({"Host": "localhost:8000"})._origem_permitida("https://outgpt.exemplo.com.br"))
chk("segundo domínio da lista também é aceito", Falso({"Host": "localhost:8000"})._origem_permitida("https://www.exemplo.com.br"))
chk("domínio diferente é recusado", not Falso({"Host": "localhost:8000"})._origem_permitida("https://site-malicioso.com"))
chk("Origin igual ao Host continua aceito", Falso({"Host": "meu.site"})._origem_permitida("https://meu.site"))
print(f"\n{ok} ok, {fail} falhas")
sys.exit(1 if fail else 0)