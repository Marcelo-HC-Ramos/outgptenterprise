"""Verificação rápida de um OutGPT publicado (ou rodando localmente), sem precisar de login.

Uso:  python tests/verificar_publicacao.py https://seu-site.exemplo.com
      OUTGPT_SETUP_TOKEN=... python tests/verificar_publicacao.py http://127.0.0.1:8000 --criar-master

--criar-master: SÓ para servidor novo/de teste. Usa o token de primeiro acesso para criar um master de teste com senha aleatória,
confere o login e o cookie de sessão. Não use em produção (deixaria um master extra).
Sai com código 1 se alguma verificação falhar.
"""
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

base = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8000").rstrip("/")
ok = fail = 0


def req(metodo, caminho, dados=None, cookie=None):
    h = {"Content-Type": "application/json"}
    if cookie:
        h["Cookie"] = cookie
    rq = urllib.request.Request(base + caminho, data=None if dados is None else json.dumps(dados).encode(), method=metodo, headers=h)
    try:
        r = urllib.request.urlopen(rq, timeout=30)
    except urllib.error.HTTPError as e:
        r = e
    corpo = r.read()
    try:
        corpo = json.loads(corpo)
    except ValueError:
        pass
    return r.status, corpo, r.headers


def chk(nome, cond, extra=""):
    global ok, fail
    ok += bool(cond)
    fail += not cond
    print(("PASS " if cond else "FAIL ") + nome + ("" if cond and not extra else f" | {str(extra)[:160]}"))


s, b, h = req("GET", "/saude")
chk("/saude responde ok", s == 200 and b == b"ok", (s, b))
s, b, h = req("GET", "/")
chk("página inicial é servida", s == 200 and b"OutGPT" in (b if isinstance(b, bytes) else b""), s)
chk("cabeçalhos de segurança presentes", h.get("X-Content-Type-Options") == "nosniff" and h.get("X-Frame-Options") == "DENY" and "default-src" in (h.get("Content-Security-Policy") or ""))
s, st, _ = req("GET", "/api/status")
chk("/api/status responde", s == 200 and "precisa_configurar" in st, st)
chk("rotas protegidas exigem login (401)", req("GET", "/api/conteudos")[0] == 401 and req("GET", "/api/cursos")[0] == 401)
chk("arquivos internos não são servidos", req("GET", "/server.py")[0] == 404 and req("GET", "/outgpt.db")[0] == 404 and req("GET", "/.env")[0] == 404)
chk("pesquisa pública carrega as perguntas", req("GET", "/api/perguntas")[0] == 200)

if "--criar-master" in sys.argv:
    token, senha = os.environ.get("OUTGPT_SETUP_TOKEN", ""), "Vp-" + secrets.token_urlsafe(12) + "9"
    chk("servidor está pronto para o primeiro acesso", st.get("precisa_configurar") is True, st)
    s, b, _ = req("POST", "/api/configuracao-inicial", {"token": token, "nome": "Verificacao", "email": "verificacao@teste.com", "senha": senha})
    chk("primeiro acesso cria o master", s == 200, (s, b))
    s, b, h = req("POST", "/api/login", {"email": "verificacao@teste.com", "senha": senha})
    cookie = (h.get("Set-Cookie") or "")
    chk("login do master funciona", s == 200 and b.get("tipo") == "master", (s, b))
    chk("cookie de sessão é HttpOnly e SameSite=Strict", "HttpOnly" in cookie and "SameSite=Strict" in cookie, cookie)
    c = cookie.split(";")[0]
    chk("sessão vale nas rotas protegidas", req("GET", "/api/eu", cookie=c)[0] == 200 and req("GET", "/api/empresas", cookie=c)[0] == 200)
    chk("primeiro acesso some depois do master", req("GET", "/api/status")[1] == {"precisa_configurar": False})

print(f"\n{ok} ok, {fail} falhas")
sys.exit(1 if fail else 0)