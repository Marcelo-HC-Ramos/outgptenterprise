"""Servidor do OutGPT Enterprise (somente biblioteca padrão + SDK da LLM).

Uso:  python server.py   ->  http://localhost:8000

Perfis: master (dono do sistema) > admin (da empresa) > funcionario / colaborador_interno > colaborador_externo.
Toda rota (exceto login, pesquisa pública e arquivos estáticos) exige sessão válida (cookie HttpOnly).
"""
import json
import os
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import auth
import db
import llm
import pesquisa
import rag

BASE = Path(__file__).parent
FRONT = BASE.parent / "docs"
COOKIE = "outgpt_sessao"
MAX_CORPO = 2_000_000
LIMIAR_SIMILARIDADE = float(os.environ.get("OUTGPT_LIMIAR", "0.50"))   # abaixo disso o assistente recusa
CSP_APP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"
CSP_PESQUISA = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
SITE = {  # lista fixa: nenhum outro arquivo é exposto
    "/": ("index.html", "text/html; charset=utf-8", CSP_APP),
    "/index.html": ("index.html", "text/html; charset=utf-8", CSP_APP),
    "/styles.css": ("styles.css", "text/css; charset=utf-8", CSP_APP),
    "/app.js": ("app.js", "text/javascript; charset=utf-8", CSP_APP),
    "/dados.js": ("dados.js", "text/javascript; charset=utf-8", CSP_APP),
    "/pesquisa.html": ("pesquisa.html", "text/html; charset=utf-8", CSP_PESQUISA),
}
SITE["/pesquisa"] = SITE["/pesquisa.html"]

_limites = {}            # chave -> [timestamps]
_limites_lock = threading.Lock()


class Erro(Exception):
    def __init__(self, codigo, mensagem):
        self.codigo, self.mensagem = codigo, mensagem


class Binario:
    def __init__(self, dados, ctype, headers=None):
        self.dados, self.ctype, self.headers = dados, ctype, headers or {}


def limitar(chave, maximo, janela_s, registrar=True):
    """Limita eventos por janela de tempo. Com registrar=False só verifica (sem contar este evento)."""
    agora = time.time()
    with _limites_lock:
        lst = [t for t in _limites.get(chave, []) if agora - t < janela_s]
        if len(lst) >= maximo:
            _limites[chave] = lst
            raise Erro(429, "Muitas requisições. Aguarde um pouco e tente novamente.")
        if registrar:
            lst.append(agora)
        _limites[chave] = lst


# ---------- Rotas ----------
ROTAS = []   # (metodo, regex, função, acesso)  acesso: None = público | "auth" | tupla de tipos


def rota(metodo, caminho, acesso="auth"):
    def deco(f):
        ROTAS.append((metodo, re.compile("^" + caminho + "$"), f, acesso))
        return f
    return deco


class Ctx:
    def __init__(self, con, usuario, corpo, args, query, ip):
        self.con, self.usuario, self.corpo, self.args, self.query, self.ip = con, usuario, corpo, args, query, ip


def texto(valor, campo, maximo, obrigatorio=True):
    v = str(valor or "").strip()
    if obrigatorio and not v:
        raise Erro(400, f"Preencha: {campo}.")
    if len(v) > maximo:
        raise Erro(400, f"{campo} excede {maximo} caracteres.")
    return v


def empresa_alvo(ctx, fonte, obrigatoria=True):
    """Empresa em que a operação vale: a do usuário; o master escolhe via empresa_id."""
    u = ctx.usuario
    if u["tipo"] != "master":
        return u["empresa_id"]
    eid = (fonte or {}).get("empresa_id")
    if eid in (None, ""):
        if obrigatoria:
            raise Erro(400, "Escolha a empresa.")
        return None
    try:
        eid = int(eid)
    except (TypeError, ValueError):
        raise Erro(400, "Empresa inválida.")
    if not ctx.con.execute("SELECT 1 FROM empresas WHERE id=?", (eid,)).fetchone():
        raise Erro(404, "Empresa não encontrada.")
    return eid


def dados_usuario(con, u):
    emp = con.execute("SELECT nome FROM empresas WHERE id=?", (u["empresa_id"],)).fetchone() if u["empresa_id"] else None
    return {"id": u["id"], "nome": u["nome"], "email": u["email"], "tipo": u["tipo"], "empresa_id": u["empresa_id"],
            "empresa": emp["nome"] if emp else None, "llm": llm.disponivel(), "modelo": llm.MODELO if llm.disponivel() else None}


def cookie_sessao(token, max_age):
    seguro = "; Secure" if os.environ.get("OUTGPT_COOKIE_SECURE") == "1" else ""
    return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}{seguro}"


# ----- autenticação -----
@rota("POST", "/api/login", None)
def h_login(c):
    limitar("login:" + c.ip, 20, 300, registrar=False)       # 20 tentativas FALHAS por IP a cada 5 min
    u, erro = auth.autenticar(c.con, c.corpo.get("email"), c.corpo.get("senha"))
    if erro:
        limitar("login:" + c.ip, 10**9, 300)                  # registra a falha
        raise Erro(401, erro)
    token = auth.criar_sessao(c.con, u["id"])
    return dados_usuario(c.con, u), {"Set-Cookie": cookie_sessao(token, int(auth.DURACAO_SESSAO.total_seconds()))}


@rota("POST", "/api/logout", None)
def h_logout(c):
    return {"ok": True}, {"Set-Cookie": cookie_sessao("", 0)}


@rota("GET", "/api/eu")
def h_eu(c):
    return dados_usuario(c.con, c.usuario)


@rota("POST", "/api/senha")
def h_senha(c):
    u = c.usuario
    if not auth.verificar_senha(str(c.corpo.get("atual") or ""), u["senha_hash"]):
        raise Erro(400, "Senha atual incorreta.")
    erro = auth.validar_senha_nova(c.corpo.get("nova"))
    if erro:
        raise Erro(400, erro)
    c.con.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (auth.hash_senha(c.corpo["nova"]), u["id"]))
    auth.encerrar_sessoes_do_usuario(c.con, u["id"])
    token = auth.criar_sessao(c.con, u["id"])
    c.con.commit()
    return {"ok": True}, {"Set-Cookie": cookie_sessao(token, int(auth.DURACAO_SESSAO.total_seconds()))}


# ----- assistente (RAG + LLM) -----
def _resposta_de_busca(achados):
    top = achados[0]
    return f"Com base em «{top['titulo']}» ({top['codigo']}): {top['texto']}"


@rota("POST", "/api/chat")
def h_chat(c):
    limitar(f"chat:{c.usuario['id']}", 20, 60)
    pergunta = texto(c.corpo.get("pergunta"), "pergunta", 1000)
    eid = empresa_alvo(c, c.corpo)
    limpa, pii = rag.anonimizar(pergunta)
    consulta = re.sub(r"\[(?:EMAIL|CPF|CNPJ|TELEFONE)\]", " ", limpa).strip() or limpa
    try:
        achados = rag.buscar(consulta, eid, auth.visibilidades_do(c.usuario["tipo"]), k=3)
    except Exception as e:
        raise Erro(503, f"Base vetorial indisponível ({type(e).__name__}). Rode: python rag.py reindexar")
    achados = [a for a in achados if a["similaridade"] >= LIMIAR_SIMILARIDADE]
    if achados:   # mantém só os trechos próximos do melhor (evita citar fontes pouco relevantes)
        achados = [a for a in achados if a["similaridade"] >= achados[0]["similaridade"] - 0.12]
    base = {"pii_mascaradas": pii, "pergunta_anonimizada": limpa}
    meta_llm = {"modelo": None, "tokens_entrada": None, "tokens_saida": None}
    if not achados:
        resp = {**base, "encontrado": False, "gerado_por_ia": False, "fontes": [],
                "resposta": "Não encontrei essa informação nos conteúdos disponíveis para você. "
                            "Para evitar respostas inventadas, consulte seu gestor ou abra um chamado."}
    else:
        fontes = [{"codigo": a["codigo"], "titulo": a["titulo"], "categoria": a["categoria"],
                   "similaridade": a["similaridade"]} for a in achados]
        try:
            g = llm.gerar_resposta(limpa, achados)
            meta_llm = {k: g[k] for k in meta_llm}
            resp = {**base, "encontrado": True, "gerado_por_ia": True, "resposta": g["texto"], "fontes": fontes}
        except llm.LLMIndisponivel as e:
            resp = {**base, "encontrado": True, "gerado_por_ia": False, "resposta": _resposta_de_busca(achados),
                    "fontes": fontes, "aviso": str(e)}
    c.con.execute(
        "INSERT INTO historico_duvidas (usuario_id,empresa_id,pergunta,resposta,fontes,gerado_por_ia,modelo,tokens_entrada,tokens_saida) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (c.usuario["id"], eid, limpa, resp["resposta"], json.dumps([{"codigo": f["codigo"], "titulo": f["titulo"]} for f in resp["fontes"]], ensure_ascii=False),
         int(resp["gerado_por_ia"]), meta_llm["modelo"], meta_llm["tokens_entrada"], meta_llm["tokens_saida"]))
    c.con.commit()
    return resp


@rota("GET", "/api/historico")
def h_historico(c):
    u = c.usuario
    sql = ("SELECT h.id,h.pergunta,h.resposta,h.fontes,h.gerado_por_ia,h.criado_em,us.nome AS usuario "
           "FROM historico_duvidas h LEFT JOIN usuarios us ON us.id=h.usuario_id WHERE ")
    if u["tipo"] in ("master", "admin"):
        eid = empresa_alvo(c, {"empresa_id": (c.query.get("empresa_id") or [None])[0]}, obrigatoria=False)
        rows = c.con.execute(sql + ("h.empresa_id=?" if eid else "1=1") + " ORDER BY h.id DESC LIMIT 200", (eid,) if eid else ())
    else:
        rows = c.con.execute(sql + "h.usuario_id=? ORDER BY h.id DESC LIMIT 200", (u["id"],))
    return {"itens": [{**dict(r), "fontes": json.loads(r["fontes"] or "[]")} for r in rows]}


# ----- conteúdos -----
CAMPOS_CONTEUDO = "id,empresa_id,codigo,titulo,categoria,texto,pergunta_exemplo,contem_pii,visibilidade,atualizado_em"


def _conteudo_permitido(c, cid):
    r = c.con.execute("SELECT * FROM conteudos WHERE id=?", (cid,)).fetchone()
    if not r or (c.usuario["tipo"] != "master" and r["empresa_id"] != c.usuario["empresa_id"]):
        raise Erro(404, "Conteúdo não encontrado.")
    return r


def _dados_conteudo(corpo):
    vis = corpo.get("visibilidade", "internos")
    if vis not in ("todos", "internos"):
        raise Erro(400, "Visibilidade inválida.")
    return {"titulo": texto(corpo.get("titulo"), "título", 200), "categoria": texto(corpo.get("categoria") or "Geral", "categoria", 100),
            "texto": texto(corpo.get("texto"), "conteúdo", 20000), "pergunta_exemplo": texto(corpo.get("pergunta_exemplo"), "pergunta de exemplo", 500, False) or None,
            "contem_pii": 1 if corpo.get("contem_pii") else 0, "visibilidade": vis}


@rota("GET", "/api/conteudos")
def h_conteudos(c):
    u = c.usuario
    eid = empresa_alvo(c, {"empresa_id": (c.query.get("empresa_id") or [None])[0]}, obrigatoria=False)
    vis = auth.visibilidades_do(u["tipo"])
    sql = f"SELECT {CAMPOS_CONTEUDO} FROM conteudos WHERE visibilidade IN ({','.join('?' * len(vis))})"
    params = list(vis)
    if eid:
        sql += " AND empresa_id=?"
        params.append(eid)
    rows = [dict(r) for r in c.con.execute(sql + " ORDER BY categoria, codigo", params)]
    return {"total": len(rows), "categorias": sorted({r["categoria"] for r in rows}), "itens": rows,
            "pode_editar": u["tipo"] in ("master", "admin")}


@rota("POST", "/api/conteudos", ("master", "admin"))
def h_conteudo_criar(c):
    eid = empresa_alvo(c, c.corpo)
    d = _dados_conteudo(c.corpo)
    codigo = texto(c.corpo.get("codigo"), "código", 60, False) or f"DOC_{int(time.time())}"
    try:
        cur = c.con.execute(
            "INSERT INTO conteudos (empresa_id,codigo,titulo,categoria,texto,pergunta_exemplo,contem_pii,visibilidade,criado_por) VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, codigo, d["titulo"], d["categoria"], d["texto"], d["pergunta_exemplo"], d["contem_pii"], d["visibilidade"], c.usuario["id"]))
    except sqlite3.IntegrityError:
        raise Erro(409, "Já existe um conteúdo com esse código nesta empresa.")
    c.con.commit()
    rag.indexar_conteudo(c.con.execute("SELECT * FROM conteudos WHERE id=?", (cur.lastrowid,)).fetchone())
    return {"id": cur.lastrowid}


@rota("PUT", r"/api/conteudos/(\d+)", ("master", "admin"))
def h_conteudo_editar(c):
    cid = int(c.args[0])
    _conteudo_permitido(c, cid)
    d = _dados_conteudo(c.corpo)
    c.con.execute("UPDATE conteudos SET titulo=?,categoria=?,texto=?,pergunta_exemplo=?,contem_pii=?,visibilidade=?,"
                  "atualizado_em=datetime('now','localtime') WHERE id=?",
                  (d["titulo"], d["categoria"], d["texto"], d["pergunta_exemplo"], d["contem_pii"], d["visibilidade"], cid))
    c.con.commit()
    rag.indexar_conteudo(c.con.execute("SELECT * FROM conteudos WHERE id=?", (cid,)).fetchone())
    return {"ok": True}


@rota("DELETE", r"/api/conteudos/(\d+)", ("master", "admin"))
def h_conteudo_excluir(c):
    cid = int(c.args[0])
    _conteudo_permitido(c, cid)
    c.con.execute("DELETE FROM conteudos WHERE id=?", (cid,))
    c.con.commit()
    rag.remover_conteudo(cid)
    return {"ok": True}


@rota("POST", "/api/conteudos/importar", ("master", "admin"))
def h_conteudo_importar(c):
    eid = empresa_alvo(c, c.corpo)
    try:
        n = rag.importar_csv(c.con, eid, str(c.corpo.get("csv") or ""), c.corpo.get("visibilidade", "internos"), c.usuario["id"])
    except ValueError as e:
        raise Erro(400, str(e))
    return {"importados": n}


# ----- usuários -----
def _usuario_gerenciavel(c, uid):
    alvo = c.con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    me = c.usuario
    if not alvo or alvo["tipo"] == "master":
        raise Erro(404, "Usuário não encontrado.")
    if me["tipo"] == "admin" and (alvo["empresa_id"] != me["empresa_id"] or alvo["tipo"] not in auth.GERENCIAVEIS_POR_ADMIN):
        raise Erro(403, "Você não pode gerenciar este usuário.")
    return alvo


def _tipo_permitido(c, tipo):
    permitidos = auth.TIPOS[1:] if c.usuario["tipo"] == "master" else auth.GERENCIAVEIS_POR_ADMIN
    if tipo not in permitidos:
        raise Erro(403 if tipo in auth.TIPOS else 400, "Tipo de usuário não permitido para você.")
    return tipo


@rota("GET", "/api/usuarios", ("master", "admin"))
def h_usuarios(c):
    eid = empresa_alvo(c, {"empresa_id": (c.query.get("empresa_id") or [None])[0]}, obrigatoria=False)
    sql = ("SELECT u.id,u.nome,u.email,u.tipo,u.ativo,u.empresa_id,e.nome AS empresa,u.ultimo_login,u.criado_em "
           "FROM usuarios u LEFT JOIN empresas e ON e.id=u.empresa_id")
    if eid:
        rows = c.con.execute(sql + " WHERE u.empresa_id=? ORDER BY u.nome", (eid,))
    else:
        rows = c.con.execute(sql + " ORDER BY e.nome, u.nome")
    return {"itens": [dict(r) for r in rows]}


@rota("POST", "/api/usuarios", ("master", "admin"))
def h_usuario_criar(c):
    eid = empresa_alvo(c, c.corpo)
    tipo = _tipo_permitido(c, c.corpo.get("tipo"))
    nome = texto(c.corpo.get("nome"), "nome", 120)
    email = texto(c.corpo.get("email"), "e-mail", 160).lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise Erro(400, "E-mail inválido.")
    erro = auth.validar_senha_nova(c.corpo.get("senha"))
    if erro:
        raise Erro(400, erro)
    try:
        cur = c.con.execute("INSERT INTO usuarios (empresa_id,nome,email,senha_hash,tipo) VALUES (?,?,?,?,?)",
                            (eid, nome, email, auth.hash_senha(c.corpo["senha"]), tipo))
    except sqlite3.IntegrityError:
        raise Erro(409, "Já existe um usuário com esse e-mail.")
    c.con.commit()
    return {"id": cur.lastrowid}


@rota("PUT", r"/api/usuarios/(\d+)", ("master", "admin"))
def h_usuario_editar(c):
    alvo = _usuario_gerenciavel(c, int(c.args[0]))
    b = c.corpo
    nome = texto(b.get("nome", alvo["nome"]), "nome", 120)
    tipo = _tipo_permitido(c, b.get("tipo", alvo["tipo"]))
    ativo = 1 if b.get("ativo", bool(alvo["ativo"])) else 0
    if alvo["id"] == c.usuario["id"] and not ativo:
        raise Erro(400, "Você não pode desativar a própria conta.")
    c.con.execute("UPDATE usuarios SET nome=?, tipo=?, ativo=? WHERE id=?", (nome, tipo, ativo, alvo["id"]))
    if b.get("nova_senha"):
        erro = auth.validar_senha_nova(b["nova_senha"])
        if erro:
            raise Erro(400, erro)
        c.con.execute("UPDATE usuarios SET senha_hash=?, tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?",
                      (auth.hash_senha(b["nova_senha"]), alvo["id"]))
    if not ativo or b.get("nova_senha"):
        auth.encerrar_sessoes_do_usuario(c.con, alvo["id"])
    c.con.commit()
    return {"ok": True}


# ----- empresas -----
@rota("GET", "/api/empresas")
def h_empresas(c):
    u = c.usuario
    sql = ("SELECT e.id,e.nome,e.ativa,e.criado_em,(SELECT COUNT(*) FROM usuarios WHERE empresa_id=e.id) AS usuarios,"
           "(SELECT COUNT(*) FROM conteudos WHERE empresa_id=e.id) AS conteudos FROM empresas e")
    rows = c.con.execute(sql + " ORDER BY e.nome") if u["tipo"] == "master" else c.con.execute(sql + " WHERE e.id=?", (u["empresa_id"],))
    return {"itens": [dict(r) for r in rows]}


@rota("POST", "/api/empresas", ("master",))
def h_empresa_criar(c):
    try:
        cur = c.con.execute("INSERT INTO empresas (nome) VALUES (?)", (texto(c.corpo.get("nome"), "nome", 120),))
    except sqlite3.IntegrityError:
        raise Erro(409, "Já existe uma empresa com esse nome.")
    c.con.commit()
    return {"id": cur.lastrowid}


@rota("PUT", r"/api/empresas/(\d+)", ("master",))
def h_empresa_editar(c):
    eid = int(c.args[0])
    atual = c.con.execute("SELECT * FROM empresas WHERE id=?", (eid,)).fetchone()
    if not atual:
        raise Erro(404, "Empresa não encontrada.")
    try:
        c.con.execute("UPDATE empresas SET nome=?, ativa=? WHERE id=?",
                      (texto(c.corpo.get("nome", atual["nome"]), "nome", 120), 1 if c.corpo.get("ativa", bool(atual["ativa"])) else 0, eid))
    except sqlite3.IntegrityError:
        raise Erro(409, "Já existe uma empresa com esse nome.")
    c.con.commit()
    return {"ok": True}


# ----- pesquisa com especialistas -----
@rota("GET", "/api/perguntas", None)
def h_perguntas(c):
    return pesquisa.perguntas()


@rota("POST", "/api/enviar", None)
def h_enviar(c):
    limitar("pesquisa:" + c.ip, 20, 3600)
    ok, msg = pesquisa.salvar(c.corpo)
    if not ok:
        raise Erro(400, msg)
    return {"ok": True, "mensagem": msg}


@rota("GET", "/api/resultados", ("master",))
def h_resultados(c):
    return pesquisa.resultados()


@rota("GET", "/api/exportar.csv", ("master",))
def h_exportar(c):
    return Binario(pesquisa.exportar_csv(), "text/csv; charset=utf-8",
                   {"Content-Disposition": "attachment; filename=respostas_outgpt.csv"})


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    server_version = "OutGPT"
    sys_version = ""

    def _enviar(self, codigo, corpo, ctype, extra=None, csp=None):
        self.send_response(codigo)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if csp:
            self.send_header("Content-Security-Policy", csp)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo, obj, extra=None):
        self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", extra)

    def _token(self):
        for parte in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == COOKIE:
                return v
        return None

    def _tratar(self, metodo):
        url = urlparse(self.path)
        caminho, query = url.path, parse_qs(url.query)
        if metodo == "GET" and caminho in SITE:
            arq, ctype, csp = SITE[caminho]
            try:
                return self._enviar(200, (FRONT / arq).read_bytes(), ctype, csp=csp)
            except FileNotFoundError:
                return self._enviar(404, b"Nao encontrado", "text/plain; charset=utf-8")
        rota_ok = None
        for m, rx, fn, acesso in ROTAS:
            if m == metodo and (mt := rx.match(caminho)):
                rota_ok = (fn, acesso, mt.groups())
                break
        if not rota_ok:
            return self._enviar(404, b"Nao encontrado", "text/plain; charset=utf-8")
        fn, acesso, args = rota_ok
        corpo = {}
        if metodo != "GET":
            origem = self.headers.get("Origin")           # defesa extra contra CSRF (além do SameSite=Strict)
            if origem and urlparse(origem).netloc != self.headers.get("Host"):
                return self._json(403, {"ok": False, "mensagem": "Origem não permitida."})
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return self._json(415, {"ok": False, "mensagem": "Use Content-Type: application/json."})
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                if tam > MAX_CORPO:
                    return self._json(413, {"ok": False, "mensagem": "Requisição grande demais."})
                corpo = json.loads(self.rfile.read(tam) or b"{}")
                if not isinstance(corpo, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"ok": False, "mensagem": "JSON inválido."})
        con = db.conectar()
        try:
            usuario = auth.usuario_da_sessao(con, self._token()) if acesso is not None else None
            if acesso is not None and usuario is None:
                return self._json(401, {"ok": False, "mensagem": "Faça login para continuar."})
            if isinstance(acesso, tuple) and usuario["tipo"] not in acesso:
                return self._json(403, {"ok": False, "mensagem": "Sem permissão para esta ação."})
            res = fn(Ctx(con, usuario, corpo, args, query, self.client_address[0]))
            extra = None
            if isinstance(res, tuple):
                res, extra = res
            if isinstance(res, Binario):
                return self._enviar(200, res.dados, res.ctype, res.headers)
            self._json(200, res, extra)
        except Erro as e:
            self._json(e.codigo, {"ok": False, "mensagem": e.mensagem})
        except Exception as e:                            # não vaza detalhes internos ao cliente
            print(f"[erro] {metodo} {caminho}: {type(e).__name__}: {e}")
            self._json(500, {"ok": False, "mensagem": "Erro interno do servidor."})
        finally:
            con.close()

    def do_GET(self): self._tratar("GET")
    def do_POST(self): self._tratar("POST")
    def do_PUT(self): self._tratar("PUT")
    def do_DELETE(self): self._tratar("DELETE")

    def log_message(self, fmt, *args):
        pass


def _aquecer():
    try:
        rag.colecao().query(query_texts=["aquecimento"], n_results=1)
    except Exception:
        pass


if __name__ == "__main__":
    if not db.DB.exists():
        raise SystemExit("Banco não encontrado. Rode antes: python init_db.py")
    with db.conectar() as con:
        if con.execute("PRAGMA user_version").fetchone()[0] < 2:
            raise SystemExit("Banco desatualizado. Rode: python init_db.py")
        if not con.execute("SELECT 1 FROM usuarios WHERE tipo='master'").fetchone():
            print("Aviso: não há usuário master. Crie o seu com: python criar_master.py")
    print("LLM:", f"ativa ({llm.MODELO})" if llm.disponivel() else "desativada (defina ANTHROPIC_API_KEY em backend/.env para ativar)")
    threading.Thread(target=_aquecer, daemon=True).start()
    porta = int(os.environ.get("OUTGPT_PORTA", "8000"))
    print(f"OutGPT Enterprise:  http://localhost:{porta}\n(Ctrl+C para parar)")
    ThreadingHTTPServer(("127.0.0.1", porta), Handler).serve_forever()
