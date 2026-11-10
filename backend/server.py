"""Servidor do OutGPT Enterprise (somente biblioteca padrão + SDK da LLM).

Uso:  python server.py   ->  http://localhost:8000

Perfis: master (dono do sistema) > admin (da empresa) > funcionario / colaborador_interno > colaborador_externo.
Toda rota (exceto login, pesquisa pública e arquivos estáticos) exige sessão válida (cookie HttpOnly).
"""
import base64
import binascii
import hmac
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
import cursos
import db
import llm
import pesquisa
import rag

BASE = Path(__file__).parent
FRONT = BASE.parent / "docs"
COOKIE = "outgpt_sessao"
MAX_CORPO = 2_000_000
MAX_ARQUIVO = 8_000_000            # tamanho máximo de um arquivo enviado (bytes)
PISO_VETOR = float(os.environ["OUTGPT_LIMIAR"]) if os.environ.get("OUTGPT_LIMIAR") else None   # piso de similaridade (padrão: 0,45 com LLM / 0,50 sem)
CSP_APP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"
CSP_PESQUISA = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
SITE = {  # lista fixa: nenhum outro arquivo é exposto
    "/": ("index.html", "text/html; charset=utf-8", CSP_APP),
    "/index.html": ("index.html", "text/html; charset=utf-8", CSP_APP),
    "/styles.css": ("styles.css", "text/css; charset=utf-8", CSP_APP),
    "/app.js": ("app.js", "text/javascript; charset=utf-8", CSP_APP),
    "/dados.js": ("dados.js", "text/javascript; charset=utf-8", CSP_APP),
    "/pesquisa.html": ("pesquisa.html", "text/html; charset=utf-8", CSP_PESQUISA),
    "/verificar.html": ("verificar.html", "text/html; charset=utf-8", CSP_PESQUISA),
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


def rota(metodo, caminho, acesso="auth", limite=MAX_CORPO):
    def deco(f):
        ROTAS.append((metodo, re.compile("^" + caminho + "$"), f, acesso, limite))
        return f
    return deco


CONFIAR_PROXY = os.environ.get("OUTGPT_CONFIAR_PROXY") == "1"   # atrás de um proxy/balanceador confiável (Render, Fly, nginx...)


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


# ----- publicação: saúde do serviço e primeiro acesso -----
@rota("GET", "/saude", None)
def h_saude(c):
    c.con.execute("SELECT 1")
    return Binario(b"ok", "text/plain; charset=utf-8")


def _precisa_configurar(con):
    return bool(os.environ.get("OUTGPT_SETUP_TOKEN")) and not con.execute("SELECT 1 FROM usuarios WHERE tipo='master'").fetchone()


@rota("GET", "/api/status", None)
def h_status(c):
    return {"precisa_configurar": _precisa_configurar(c.con)}


@rota("POST", "/api/configuracao-inicial", None)
def h_configuracao_inicial(c):
    """Cria o primeiro usuário master num servidor novo. Só funciona enquanto não existe master e com o token secreto
    definido por quem hospeda (variável OUTGPT_SETUP_TOKEN). Depois do primeiro master, a rota deixa de funcionar."""
    limitar("setup:" + c.ip, 5, 600)
    if not _precisa_configurar(c.con):
        raise Erro(403, "A configuração inicial não está disponível.")
    if not hmac.compare_digest(str(c.corpo.get("token") or "").encode(), os.environ["OUTGPT_SETUP_TOKEN"].encode()):
        raise Erro(403, "Token de configuração incorreto.")
    nome = texto(c.corpo.get("nome"), "nome", 120)
    email = texto(c.corpo.get("email"), "e-mail", 160).lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise Erro(400, "E-mail inválido.")
    erro = auth.validar_senha_nova(c.corpo.get("senha"))
    if erro:
        raise Erro(400, erro)
    try:
        c.con.execute("INSERT INTO usuarios (empresa_id, nome, email, senha_hash, tipo) VALUES (NULL,?,?,?, 'master')", (nome, email, auth.hash_senha(c.corpo["senha"])))
    except sqlite3.IntegrityError:
        raise Erro(409, "Já existe um usuário com esse e-mail.")
    c.con.commit()
    return {"ok": True}

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
SEM_RESPOSTA = ("Não encontrei essa informação nos conteúdos disponíveis para você. "
                "Para evitar respostas inventadas, consulte seu gestor ou abra um chamado.")
MARCADORES_PII = re.compile(r"\[(?:EMAIL|CPF|CNPJ|TELEFONE)\]")


class Fluxo:
    """Resposta em streaming (Server-Sent Events): `gerador` produz tuplas (evento, dados)."""
    def __init__(self, gerador):
        self.gerador = gerador


def _resposta_de_busca(achados):
    top = achados[0]
    return f"Com base em «{top['titulo']}» ({top['codigo']}):\n\n" + "\n\n".join(top["trechos"])


def _historico_recebido(corpo):
    """Últimas trocas da conversa enviadas pelo navegador (perguntas anonimizadas; tudo tratado como dado não confiável)."""
    out = []
    for h in (corpo.get("historico") or [])[-llm.MAX_HISTORICO:]:
        if isinstance(h, dict) and isinstance(h.get("pergunta"), str) and isinstance(h.get("resposta"), str):
            out.append({"pergunta": rag.anonimizar(h["pergunta"][:1000])[0], "resposta": h["resposta"][:1500]})
    return out


def _preparar_chat(c):
    """Valida, anonimiza e recupera os trechos relevantes (comum à resposta completa e ao streaming)."""
    limitar(f"chat:{c.usuario['id']}", 20, 60)
    pergunta = texto(c.corpo.get("pergunta"), "pergunta", 1000)
    eid = empresa_alvo(c, c.corpo)
    historico = _historico_recebido(c.corpo)
    limpa, pii = rag.anonimizar(pergunta)
    consulta = MARCADORES_PII.sub(" ", limpa).strip() or limpa
    if historico and len(consulta.split()) < 6:        # pergunta curta de continuação: junta a pergunta anterior na busca
        consulta = MARCADORES_PII.sub(" ", historico[-1]["pergunta"]).strip() + " " + consulta
    try:
        achados = rag.buscar(consulta, eid, auth.visibilidades_do(c.usuario["tipo"]), k=3)
    except Exception as e:
        raise Erro(503, f"Base vetorial indisponível ({type(e).__name__}). Rode: python rag.py reindexar")
    com_llm = llm.disponivel()
    achados = [a for a in achados if rag.relevante(a, com_llm, PISO_VETOR)]
    if achados:   # mantém só os trechos próximos do melhor (evita citar fontes pouco relevantes)
        topo = max(a["similaridade"] for a in achados)
        achados = [a for a in achados if a["similaridade"] >= topo - 0.15 or a["lexical"]]
    return {"eid": eid, "historico": historico, "limpa": limpa, "achados": achados,
            "base": {"pii_mascaradas": pii, "pergunta_anonimizada": limpa}}


def _sem_base(p):
    return {**p["base"], "encontrado": False, "gerado_por_ia": False, "fontes": [], "resposta": SEM_RESPOSTA}


def _fontes(achados):
    return [{"conteudo_id": a["id"], "codigo": a["codigo"], "titulo": a["titulo"], "categoria": a["categoria"],
             "similaridade": a["similaridade"]} for a in achados]


def _resposta_da_llm(p, g):
    if g["texto"].strip().upper().startswith("SEM_BASE"):      # a LLM concluiu que os documentos não respondem
        return _sem_base(p)
    return {**p["base"], "encontrado": True, "gerado_por_ia": True, "resposta": g["texto"], "fontes": _fontes(p["achados"])}


def _resposta_sem_llm(p, motivo):
    return {**p["base"], "encontrado": True, "gerado_por_ia": False, "resposta": _resposta_de_busca(p["achados"]),
            "fontes": _fontes(p["achados"]), "aviso": motivo}


def _registrar_chat(c, p, resp, g=None):
    """Grava a pergunta (já anonimizada) no histórico e devolve o id do registro."""
    g = g or {}
    cur = c.con.execute(
        "INSERT INTO historico_duvidas (usuario_id,empresa_id,pergunta,resposta,fontes,gerado_por_ia,modelo,tokens_entrada,tokens_saida,encontrado) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (c.usuario["id"], p["eid"], p["limpa"], resp["resposta"],
         json.dumps([{"codigo": f["codigo"], "titulo": f["titulo"]} for f in resp["fontes"]], ensure_ascii=False),
         int(resp["gerado_por_ia"]), g.get("modelo"), g.get("tokens_entrada"), g.get("tokens_saida"), int(resp["encontrado"])))
    c.con.commit()
    return cur.lastrowid


@rota("POST", "/api/chat")
def h_chat(c):
    p = _preparar_chat(c)
    g = None
    if not p["achados"]:
        resp = _sem_base(p)
    else:
        try:
            g = llm.gerar_resposta(p["limpa"], p["achados"], p["historico"])
            resp = _resposta_da_llm(p, g)
        except llm.LLMIndisponivel as e:
            resp = _resposta_sem_llm(p, str(e))
    resp["id"] = _registrar_chat(c, p, resp, g)
    return resp


@rota("POST", "/api/chat/stream")
def h_chat_stream(c):
    """Igual a /api/chat, mas devolve a resposta em eventos (SSE): 'delta' (texto) ... 'fim' (resposta completa)."""
    p = _preparar_chat(c)           # erros de validação saem como JSON normal, antes de abrir o fluxo

    def gerar():
        g, resp = None, None
        if not p["achados"]:
            resp = _sem_base(p)
        else:
            buf, decidido = "", False      # segura o início do texto para detectar a resposta SEM_BASE (que não deve aparecer na tela)
            try:
                for ev, dados in llm.gerar_resposta_stream(p["limpa"], p["achados"], p["historico"]):
                    if ev == "fim":
                        g = dados
                        break
                    if decidido:
                        yield "delta", {"texto": dados}
                        continue
                    buf += dados
                    cand = buf.lstrip().upper()
                    if "SEM_BASE".startswith(cand) and len(cand) < 8:
                        continue                                     # ainda indeciso
                    decidido = True
                    if not cand.startswith("SEM_BASE"):
                        yield "delta", {"texto": buf}
                if g is not None:
                    if not decidido and not g["texto"].strip().upper().startswith("SEM_BASE"):
                        yield "delta", {"texto": buf}
                    resp = _resposta_da_llm(p, g)
            except llm.LLMIndisponivel as e:
                resp = _resposta_sem_llm(p, str(e))
        resp["id"] = _registrar_chat(c, p, resp, g)
        yield "fim", resp
    return Fluxo(gerar())


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


@rota("GET", "/api/sugestoes")
def h_sugestoes(c):
    """Perguntas típicas dos conteúdos que o usuário pode ver (atalhos na página inicial e no assistente)."""
    eid = empresa_alvo(c, {"empresa_id": (c.query.get("empresa_id") or [None])[0]}, obrigatoria=False)
    vis = auth.visibilidades_do(c.usuario["tipo"])
    sql = f"SELECT pergunta_exemplo FROM conteudos WHERE pergunta_exemplo IS NOT NULL AND visibilidade IN ({','.join('?' * len(vis))})"
    params = list(vis)
    if eid:
        sql += " AND empresa_id=?"
        params.append(eid)
    return {"itens": [r[0] for r in c.con.execute(sql + " ORDER BY RANDOM() LIMIT 6", params)]}


# ----- conteúdos -----
LIMITE_TEXTO = 400_000
CAMPOS_LISTA = ("id,empresa_id,codigo,titulo,categoria,contem_pii,visibilidade,atualizado_em,arquivo_nome,pergunta_exemplo,"
                "SUBSTR(texto,1,300) AS resumo,LENGTH(texto) AS tamanho")
CAMPOS_COMPLETO = "id,empresa_id,codigo,titulo,categoria,texto,pergunta_exemplo,resposta_exemplo,arquivo_nome,contem_pii,visibilidade,atualizado_em"


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
            "texto": texto(corpo.get("texto"), "conteúdo", LIMITE_TEXTO),
            "pergunta_exemplo": texto(corpo.get("pergunta_exemplo"), "pergunta de exemplo", 500, False) or None,
            "resposta_exemplo": texto(corpo.get("resposta_exemplo"), "resposta de exemplo", 2000, False) or None,
            "contem_pii": 1 if corpo.get("contem_pii") else 0, "visibilidade": vis}


@rota("GET", "/api/conteudos")
def h_conteudos(c):
    u = c.usuario
    eid = empresa_alvo(c, {"empresa_id": (c.query.get("empresa_id") or [None])[0]}, obrigatoria=False)
    vis = auth.visibilidades_do(u["tipo"])
    sql = f"SELECT {CAMPOS_LISTA} FROM conteudos WHERE visibilidade IN ({','.join('?' * len(vis))})"
    params = list(vis)
    if eid:
        sql += " AND empresa_id=?"
        params.append(eid)
    rows = [dict(r) for r in c.con.execute(sql + " ORDER BY categoria, codigo", params)]
    return {"total": len(rows), "categorias": sorted({r["categoria"] for r in rows}), "itens": rows,
            "pode_editar": u["tipo"] in ("master", "admin")}


@rota("GET", r"/api/conteudos/(\d+)")
def h_conteudo(c):
    r = _conteudo_permitido(c, int(c.args[0]))
    if r["visibilidade"] not in auth.visibilidades_do(c.usuario["tipo"]):
        raise Erro(404, "Conteúdo não encontrado.")
    return {k: r[k] for k in CAMPOS_COMPLETO.split(",")}


@rota("POST", "/api/conteudos", ("master", "admin"))
def h_conteudo_criar(c):
    eid = empresa_alvo(c, c.corpo)
    d = _dados_conteudo(c.corpo)
    codigo = texto(c.corpo.get("codigo"), "código", 60, False) or f"DOC_{int(time.time())}"
    try:
        cur = c.con.execute(
            "INSERT INTO conteudos (empresa_id,codigo,titulo,categoria,texto,pergunta_exemplo,resposta_exemplo,contem_pii,visibilidade,criado_por) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, codigo, d["titulo"], d["categoria"], d["texto"], d["pergunta_exemplo"], d["resposta_exemplo"], d["contem_pii"], d["visibilidade"], c.usuario["id"]))
    except sqlite3.IntegrityError:
        raise Erro(409, "Já existe um conteúdo com esse código nesta empresa.")
    c.con.commit()
    rag.indexar_conteudo(c.con.execute("SELECT * FROM conteudos WHERE id=?", (cur.lastrowid,)).fetchone(), c.con)
    cursos.sincronizar(c.con, eid)
    return {"id": cur.lastrowid}


@rota("POST", "/api/conteudos/arquivo", ("master", "admin"), limite=12_000_000)
def h_conteudo_arquivo(c):
    """Cria um conteúdo a partir de um arquivo (.txt, .md, .pdf, .docx): extrai o texto, divide em trechos e indexa."""
    eid = empresa_alvo(c, c.corpo)
    nome = Path(texto(c.corpo.get("nome"), "nome do arquivo", 200)).name
    try:
        dados = base64.b64decode(c.corpo.get("dados") or "", validate=True)
    except (binascii.Error, ValueError):
        raise Erro(400, "Arquivo inválido.")
    if len(dados) > MAX_ARQUIVO:
        raise Erro(413, "O arquivo passa de 8 MB.")
    try:
        conteudo = rag.extrair_texto(nome, dados)
    except ValueError as e:
        raise Erro(400, str(e))
    vis = c.corpo.get("visibilidade", "internos")
    if vis not in ("todos", "internos"):
        raise Erro(400, "Visibilidade inválida.")
    titulo = texto(c.corpo.get("titulo") or re.sub(r"[_\-]+", " ", Path(nome).stem).strip() or nome, "título", 200)
    codigo = f"ARQ_{int(time.time() * 1000)}"
    cur = c.con.execute(
        "INSERT INTO conteudos (empresa_id,codigo,titulo,categoria,texto,arquivo_nome,visibilidade,criado_por) VALUES (?,?,?,?,?,?,?,?)",
        (eid, codigo, titulo, texto(c.corpo.get("categoria") or "Documentos", "categoria", 100), conteudo, nome, vis, c.usuario["id"]))
    c.con.commit()
    rag.indexar_conteudo(c.con.execute("SELECT * FROM conteudos WHERE id=?", (cur.lastrowid,)).fetchone(), c.con)
    cursos.sincronizar(c.con, eid)
    return {"id": cur.lastrowid, "caracteres": len(conteudo), "trechos": len(rag.dividir_em_trechos(conteudo))}


@rota("POST", r"/api/conteudos/(\d+)/quiz", ("master", "admin"))
def h_conteudo_quiz(c):
    """Gera (ou refaz) a pergunta de verificação de uma lição com a IA. Uma chamada por lição (o site chama em sequência)."""
    limitar(f"quiz:{c.usuario['id']}", 40, 600)
    cid = int(c.args[0])
    r = _conteudo_permitido(c, cid)
    if r["pergunta_exemplo"] and r["resposta_exemplo"] and not c.corpo.get("forcar"):
        return {"gerado": False, "motivo": "A lição já tem pergunta e resposta de exemplo."}
    try:
        q = llm.gerar_quiz(r["titulo"], r["texto"])
    except llm.LLMIndisponivel as e:
        raise Erro(503, str(e))
    c.con.execute("INSERT OR REPLACE INTO quiz_gerados (conteudo_id, pergunta, correta, erradas, modelo) VALUES (?,?,?,?,?)",
                  (cid, q["pergunta"], q["correta"], json.dumps(q["erradas"], ensure_ascii=False), q["modelo"]))
    c.con.commit()
    return {"gerado": True, "pergunta": q["pergunta"]}

@rota("PUT", r"/api/conteudos/(\d+)", ("master", "admin"))
def h_conteudo_editar(c):
    cid = int(c.args[0])
    atual = _conteudo_permitido(c, cid)
    d = _dados_conteudo(c.corpo)
    if d["texto"] != atual["texto"]:      # o conteúdo mudou: a pergunta gerada antes pode estar desatualizada
        c.con.execute("DELETE FROM quiz_gerados WHERE conteudo_id=?", (cid,))
    c.con.execute("UPDATE conteudos SET titulo=?,categoria=?,texto=?,pergunta_exemplo=?,resposta_exemplo=?,contem_pii=?,visibilidade=?,"
                  "atualizado_em=datetime('now','localtime') WHERE id=?",
                  (d["titulo"], d["categoria"], d["texto"], d["pergunta_exemplo"], d["resposta_exemplo"], d["contem_pii"], d["visibilidade"], cid))
    c.con.commit()
    rag.indexar_conteudo(c.con.execute("SELECT * FROM conteudos WHERE id=?", (cid,)).fetchone(), c.con)
    cursos.sincronizar(c.con, atual["empresa_id"])
    return {"ok": True}


@rota("DELETE", r"/api/conteudos/(\d+)", ("master", "admin"))
def h_conteudo_excluir(c):
    cid = int(c.args[0])
    atual = _conteudo_permitido(c, cid)
    c.con.execute("DELETE FROM conteudos WHERE id=?", (cid,))
    c.con.commit()
    rag.remover_conteudo(cid, c.con)
    cursos.sincronizar(c.con, atual["empresa_id"])
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


# ----- cursos -----
def _eid(c):
    """Empresa da operação: query string (GET) ou corpo (POST/PUT); o master precisa escolher."""
    return empresa_alvo(c, {"empresa_id": (c.query.get("empresa_id") or [c.corpo.get("empresa_id")])[0]})


@rota("GET", "/api/cursos")
def h_cursos(c):
    lista = cursos.listar(c.con, c.usuario, _eid(c))
    return {"itens": lista, "resumo": cursos.resumo(lista), "pode_editar": c.usuario["tipo"] in ("master", "admin")}


@rota("GET", r"/api/cursos/(\d+)")
def h_curso(c):
    d = cursos.detalhe(c.con, c.usuario, _eid(c), int(c.args[0]))
    if not d:
        raise Erro(404, "Curso não encontrado.")
    return d


@rota("POST", r"/api/cursos/(\d+)/licoes/(\d+)/concluir")
def h_licao_concluir(c):
    if not cursos.concluir(c.con, c.usuario, _eid(c), int(c.args[0]), int(c.args[1])):
        raise Erro(404, "Lição não encontrada.")
    return {"ok": True}


@rota("POST", r"/api/cursos/(\d+)/licoes/(\d+)/responder")
def h_licao_responder(c):
    opcao = c.corpo.get("opcao")
    if not isinstance(opcao, int) or isinstance(opcao, bool) or not 0 <= opcao < 10:
        raise Erro(400, "Escolha uma alternativa.")
    r = cursos.responder_quiz(c.con, c.usuario, _eid(c), int(c.args[0]), int(c.args[1]), opcao)
    if r is None:
        raise Erro(404, "Pergunta não encontrada.")
    return r


@rota("POST", "/api/cursos/sincronizar", ("master", "admin"))
def h_cursos_sincronizar(c):
    criados, anexados = cursos.sincronizar(c.con, _eid(c))
    return {"criados": criados, "anexados": anexados}


def _curso_permitido(c, curso_id):
    r = c.con.execute("SELECT * FROM cursos WHERE id=?", (curso_id,)).fetchone()
    if not r or (c.usuario["tipo"] != "master" and r["empresa_id"] != c.usuario["empresa_id"]):
        raise Erro(404, "Curso não encontrado.")
    return r


@rota("POST", "/api/cursos", ("master", "admin"))
def h_curso_criar(c):
    """Curso personalizado: o admin escolhe e ordena as lições (conteúdos) da empresa."""
    eid = _eid(c)
    try:
        cid = cursos.criar_personalizado(c.con, eid, texto(c.corpo.get("titulo"), "título", 200),
                                         texto(c.corpo.get("descricao"), "descrição", 500, False) or None,
                                         c.corpo.get("nivel", "Iniciante"), c.corpo.get("conteudo_ids"))
    except ValueError as e:
        raise Erro(400, str(e))
    return {"id": cid}


@rota("GET", r"/api/cursos/(\d+)/estrutura", ("master", "admin"))
def h_curso_estrutura(c):
    return cursos.estrutura(c.con, _curso_permitido(c, int(c.args[0])))


@rota("PUT", r"/api/cursos/(\d+)", ("master", "admin"))
def h_curso_editar(c):
    curso = _curso_permitido(c, int(c.args[0]))
    titulo = texto(c.corpo.get("titulo"), "título", 200)
    descricao = texto(c.corpo.get("descricao"), "descrição", 500, False) or None
    nivel = c.corpo.get("nivel", curso["nivel"])
    if "conteudo_ids" in c.corpo:                       # troca de lições: só em cursos personalizados
        try:
            cursos.atualizar_personalizado(c.con, curso, titulo, descricao, nivel, c.corpo["conteudo_ids"])
        except ValueError as e:
            raise Erro(400, str(e))
        return {"ok": True}
    if nivel not in cursos.NIVEIS:
        raise Erro(400, "Nível inválido.")
    c.con.execute("UPDATE cursos SET titulo=?, descricao=?, nivel=? WHERE id=?", (titulo, descricao, nivel, curso["id"]))
    c.con.commit()
    return {"ok": True}

@rota("DELETE", r"/api/cursos/(\d+)", ("master", "admin"))
def h_curso_excluir(c):
    _curso_permitido(c, int(c.args[0]))
    c.con.execute("DELETE FROM cursos WHERE id=?", (int(c.args[0]),))
    c.con.commit()
    return {"ok": True}


# ----- certificados -----
@rota("POST", r"/api/cursos/(\d+)/certificado")
def h_certificado_emitir(c):
    try:
        return cursos.emitir_certificado(c.con, c.usuario, _eid(c), int(c.args[0]))
    except ValueError as e:
        raise Erro(400, str(e))


@rota("GET", "/api/certificados")
def h_certificados(c):
    rows = c.con.execute("SELECT * FROM certificados WHERE usuario_id=? ORDER BY emitido_em DESC", (c.usuario["id"],)).fetchall()
    return {"itens": [dict(r) for r in rows]}


@rota("GET", r"/api/verificar/([A-Za-z0-9\-]{6,40})", None)
def h_verificar(c):
    """Verificação pública: qualquer pessoa com o código confere nome, curso e data (sem login)."""
    limitar("verificar:" + c.ip, 30, 60)
    r = cursos.certificado_publico(c.con, c.args[0])
    if not r:
        raise Erro(404, "Certificado não encontrado.")
    return {"valido": True, **r}

# ----- lacunas de conteúdo (perguntas que o assistente não soube responder) -----
def _normalizar_pergunta(p):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", rag._normalizar(p))).strip()


def _lacunas(con, eid):
    """Perguntas sem resposta dos últimos 60 dias, agrupadas por pergunta parecida (mais repetidas primeiro)."""
    grupos = {}
    for r in con.execute(
            "SELECT id, pergunta, usuario_id, criado_em FROM historico_duvidas WHERE empresa_id=? AND encontrado=0 AND resolvida=0 "
            "AND criado_em >= datetime('now','localtime','-60 days') ORDER BY id DESC LIMIT 1000", (eid,)):
        g = grupos.setdefault(_normalizar_pergunta(r["pergunta"]), {"pergunta": r["pergunta"], "ids": [], "usuarios": set(), "ultima": r["criado_em"]})
        g["ids"].append(r["id"]); g["usuarios"].add(r["usuario_id"])
    itens = [{"pergunta": g["pergunta"], "vezes": len(g["ids"]), "usuarios": len(g["usuarios"]), "ultima": g["ultima"], "ids": g["ids"]} for g in grupos.values()]
    itens.sort(key=lambda x: x["ultima"], reverse=True)      # mais recentes primeiro...
    itens.sort(key=lambda x: -x["vezes"])                    # ...e, acima de tudo, as mais repetidas
    return itens


@rota("GET", "/api/lacunas", ("master", "admin"))
def h_lacunas(c):
    return {"itens": _lacunas(c.con, _eid(c))[:50]}

@rota("POST", "/api/lacunas/resolver", ("master", "admin"))
def h_lacunas_resolver(c):
    ids = [i for i in (c.corpo.get("ids") or []) if isinstance(i, int) and not isinstance(i, bool)][:500]
    if not ids:
        raise Erro(400, "Nada para resolver.")
    eid = _eid(c)
    c.con.execute(f"UPDATE historico_duvidas SET resolvida=1 WHERE empresa_id=? AND encontrado=0 AND id IN ({','.join('?' * len(ids))})", [eid, *ids])
    c.con.commit()
    return {"ok": True}

# ----- feedback sobre as respostas do assistente -----
@rota("POST", "/api/avaliar")
def h_avaliar(c):
    """O usuário avalia uma resposta dele: 1 = útil, -1 = não ajudou (com comentário opcional)."""
    hid, nota = c.corpo.get("id"), c.corpo.get("avaliacao")
    if not isinstance(hid, int) or isinstance(hid, bool) or nota not in (1, -1):
        raise Erro(400, "Avaliação inválida.")
    comentario = texto(c.corpo.get("comentario"), "comentário", 500, False) or None
    cur = c.con.execute("UPDATE historico_duvidas SET avaliacao=?, comentario=? WHERE id=? AND usuario_id=?",
                        (nota, comentario, hid, c.usuario["id"]))
    if cur.rowcount == 0:
        raise Erro(404, "Resposta não encontrada.")
    c.con.commit()
    return {"ok": True}


@rota("GET", "/api/feedback", ("master", "admin"))
def h_feedback(c):
    """Resumo das avaliações dos últimos 30 dias e as respostas que não ajudaram (ainda não tratadas)."""
    eid = _eid(c)
    janela = "criado_em >= datetime('now','localtime','-30 days')"
    util = c.con.execute(f"SELECT COUNT(*) FROM historico_duvidas WHERE empresa_id=? AND avaliacao=1 AND {janela}", (eid,)).fetchone()[0]
    ruim = c.con.execute(f"SELECT COUNT(*) FROM historico_duvidas WHERE empresa_id=? AND avaliacao=-1 AND {janela}", (eid,)).fetchone()[0]
    itens = []
    for r in c.con.execute(
            "SELECT h.id,h.pergunta,h.resposta,h.fontes,h.comentario,h.criado_em,u.nome AS usuario FROM historico_duvidas h "
            "LEFT JOIN usuarios u ON u.id=h.usuario_id WHERE h.empresa_id=? AND h.avaliacao=-1 AND h.resolvida=0 ORDER BY h.id DESC LIMIT 50", (eid,)):
        itens.append({**dict(r), "resposta": r["resposta"][:700], "fontes": json.loads(r["fontes"] or "[]")})
    return {"uteis": util, "nao_ajudaram": ruim, "satisfacao": round(100 * util / (util + ruim)) if util + ruim else None, "itens": itens}


@rota("POST", "/api/feedback/resolver", ("master", "admin"))
def h_feedback_resolver(c):
    hid = c.corpo.get("id")
    if not isinstance(hid, int) or isinstance(hid, bool):
        raise Erro(400, "Registro inválido.")
    c.con.execute("UPDATE historico_duvidas SET resolvida=1 WHERE id=? AND empresa_id=? AND avaliacao=-1", (hid, _eid(c)))
    c.con.commit()
    return {"ok": True}

# ----- painel da empresa e administração da IA -----
@rota("GET", "/api/painel", ("master", "admin"))
def h_painel(c):
    eid = _eid(c)
    q = lambda sql, *p: c.con.execute(sql, p).fetchone()[0]
    return {"usuarios": q("SELECT COUNT(*) FROM usuarios WHERE empresa_id=? AND ativo=1", eid),
            "conteudos": q("SELECT COUNT(*) FROM conteudos WHERE empresa_id=?", eid),
            "cursos": q("SELECT COUNT(*) FROM cursos WHERE empresa_id=?", eid),
            "perguntas_7d": q("SELECT COUNT(*) FROM historico_duvidas WHERE empresa_id=? AND criado_em >= datetime('now','localtime','-7 days')", eid),
            "satisfacao": (lambda u, r: round(100 * u / (u + r)) if u + r else None)(
                q("SELECT COUNT(*) FROM historico_duvidas WHERE empresa_id=? AND avaliacao=1 AND criado_em >= datetime('now','localtime','-30 days')", eid),
                q("SELECT COUNT(*) FROM historico_duvidas WHERE empresa_id=? AND avaliacao=-1 AND criado_em >= datetime('now','localtime','-30 days')", eid)),
            "lacunas": len(_lacunas(c.con, eid))}


@rota("GET", "/api/llm", ("master",))
def h_llm(c):
    return {"configurada": llm.disponivel(), "modelo": llm.MODELO, "esforco": llm.ESFORCO}


@rota("POST", "/api/llm/testar", ("master",))
def h_llm_testar(c):
    limitar(f"llm:{c.usuario['id']}", 10, 600)
    ok, msg = llm.testar()
    return {"ok": ok, "mensagem": msg}


@rota("POST", "/api/llm/chave", ("master",), limite=10_000)
def h_llm_chave(c):
    limitar(f"llmchave:{c.usuario['id']}", 5, 600)
    ok, msg = llm.salvar_chave(c.corpo.get("chave"))
    if not ok:
        raise Erro(400, msg)
    return {"ok": True, "mensagem": msg}

# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    server_version = "OutGPT"
    timeout = 60                 # fecha conexões lentas/paradas (protege contra clientes que seguram a conexão aberta)
    sys_version = ""

    def _enviar(self, codigo, corpo, ctype, extra=None, csp=None):
        self.send_response(codigo)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if os.environ.get("OUTGPT_COOKIE_SECURE") == "1":
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        if csp:
            self.send_header("Content-Security-Policy", csp)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _fluxo(self, fluxo):
        self.send_response(200)
        for k, v in (("Content-Type", "text/event-stream; charset=utf-8"), ("Cache-Control", "no-cache, no-transform"), ("X-Accel-Buffering", "no"),
                     ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer")):
            self.send_header(k, v)
        self.end_headers()                                   # HTTP/1.0: o fim do fluxo é o fechamento da conexão

        def enviar(evento, dados):
            self.wfile.write(f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
        try:
            for evento, dados in fluxo.gerador:
                enviar(evento, dados)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass                                              # o navegador fechou a aba no meio da resposta
        except Exception as e:
            print(f"[erro] streaming: {type(e).__name__}: {e}")
            try:
                enviar("erro", {"mensagem": "Erro interno do servidor."})
            except OSError:
                pass
    def _ip(self):
        """IP do cliente. Atrás de um proxy confiável vale o último valor de X-Forwarded-For (o que o proxy anexou)."""
        if CONFIAR_PROXY:
            xff = self.headers.get("X-Forwarded-For", "")
            if xff:
                return xff.split(",")[-1].strip()[:64]
        return self.client_address[0]

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
        for m, rx, fn, acesso, limite in ROTAS:
            if m == metodo and (mt := rx.match(caminho)):
                rota_ok = (fn, acesso, mt.groups(), limite)
                break
        if not rota_ok:
            return self._enviar(404, b"Nao encontrado", "text/plain; charset=utf-8")
        fn, acesso, args, limite = rota_ok
        corpo = {}
        if metodo != "GET":
            origem = self.headers.get("Origin")           # defesa extra contra CSRF (além do SameSite=Strict)
            if origem and urlparse(origem).netloc != self.headers.get("Host"):
                return self._json(403, {"ok": False, "mensagem": "Origem não permitida."})
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return self._json(415, {"ok": False, "mensagem": "Use Content-Type: application/json."})
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                if tam > limite:
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
            res = fn(Ctx(con, usuario, corpo, args, query, self._ip()))
            extra = None
            if isinstance(res, tuple):
                res, extra = res
            if isinstance(res, Fluxo):                       # streaming (SSE)
                return self._fluxo(res)
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
        if rag.garantir_indice():
            print("Índice de busca recriado.")
        rag.colecao().query(query_texts=["aquecimento"], n_results=1)
    except Exception:
        pass


if __name__ == "__main__":
    if not db.DB.exists():
        raise SystemExit("Banco não encontrado. Rode antes: python init_db.py")
    with db.conectar() as con:
        if con.execute("PRAGMA user_version").fetchone()[0] < 4:
            raise SystemExit("Banco desatualizado. Rode: python init_db.py")
        if not con.execute("SELECT 1 FROM usuarios WHERE tipo='master'").fetchone():
            print("Aviso: não há usuário master. Crie o seu com: python criar_master.py")
    print("LLM:", f"ativa ({llm.MODELO})" if llm.disponivel() else "desativada (defina ANTHROPIC_API_KEY em backend/.env para ativar)")
    threading.Thread(target=_aquecer, daemon=True).start()
    porta = int(os.environ.get("OUTGPT_PORTA") or os.environ.get("PORT") or 8000)
    host = os.environ.get("OUTGPT_HOST", "127.0.0.1")            # em servidor: 0.0.0.0 (a imagem Docker já define)
    if host not in ("127.0.0.1", "localhost") and os.environ.get("OUTGPT_COOKIE_SECURE") != "1":
        print("AVISO: servidor exposto na rede sem OUTGPT_COOKIE_SECURE=1. Em produção use HTTPS e defina OUTGPT_COOKIE_SECURE=1.")
    if _precisa_configurar(db.conectar()):
        print("Primeiro acesso: abra o site e crie o master com o token de OUTGPT_SETUP_TOKEN.")
    print(f"OutGPT Enterprise:  http://localhost:{porta}\n(Ctrl+C para parar)")
    ThreadingHTTPServer((host, porta), Handler).serve_forever()
