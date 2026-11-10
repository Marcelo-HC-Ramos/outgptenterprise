"""Cursos gerados a partir dos conteúdos da empresa: lições, perguntas de verificação e progresso por usuário.

- Cada categoria de conteúdo vira um curso (categorias grandes são divididas em partes de até 12 lições).
- Cada lição é um conteúdo; quando ele tem pergunta e resposta de exemplo, vira uma pergunta de múltipla escolha
  cujas alternativas erradas vêm das respostas de outros conteúdos da mesma empresa.
- O usuário só vê lições de conteúdos que sua visibilidade permite (colaborador externo: apenas "todos").
"""
import json
import math
import random
import re
import secrets

from auth import visibilidades_do

PARTE_MAX = 12
LICAO_MAX_CHARS = 6000        # documentos maiores (manuais, PDFs) ficam só na busca do assistente, não viram lição
PALAVRAS_POR_MIN = 180


def _marcas(vis):
    return ",".join("?" * len(vis))


def _minutos(texto):
    return max(1, math.ceil(len(re.findall(r"\w+", texto)) / PALAVRAS_POR_MIN))


# ---------- Geração automática ----------
def sincronizar(con, empresa_id):
    """Cria um curso por categoria e anexa conteúdos novos aos cursos existentes. Devolve (criados, anexados)."""
    criados = anexados = 0
    por_categoria = {}
    for r in con.execute("SELECT id, categoria FROM conteudos WHERE empresa_id=? AND LENGTH(texto) <= ? ORDER BY id", (empresa_id, LICAO_MAX_CHARS)):   # ordem de cadastro
        por_categoria.setdefault(r["categoria"], []).append(r["id"])
    ordem = (con.execute("SELECT COALESCE(MAX(ordem),0) FROM cursos WHERE empresa_id=?", (empresa_id,)).fetchone()[0])
    for categoria, ids in por_categoria.items():
        existentes = con.execute("SELECT id FROM cursos WHERE empresa_id=? AND categoria=? ORDER BY ordem, id", (empresa_id, categoria)).fetchall()
        ligados = set()
        if existentes:
            ligados = {r[0] for r in con.execute(
                f"SELECT conteudo_id FROM curso_itens WHERE curso_id IN ({_marcas(existentes)})", [e["id"] for e in existentes])}
        faltam = [i for i in ids if i not in ligados]
        if not faltam:
            continue
        if existentes:                                        # anexa ao último curso da categoria
            cid = existentes[-1]["id"]
            pos = con.execute("SELECT COALESCE(MAX(ordem),0) FROM curso_itens WHERE curso_id=?", (cid,)).fetchone()[0]
            con.executemany("INSERT OR IGNORE INTO curso_itens (curso_id, conteudo_id, ordem) VALUES (?,?,?)",
                            [(cid, i, pos + n + 1) for n, i in enumerate(faltam)])
            anexados += len(faltam)
            continue
        partes = math.ceil(len(faltam) / PARTE_MAX)
        tam = math.ceil(len(faltam) / partes)
        for p in range(partes):
            fatia = faltam[p * tam:(p + 1) * tam]
            titulo = categoria if partes == 1 else f"{categoria} · Parte {p + 1} de {partes}"
            ordem += 1
            cur = con.execute("INSERT INTO cursos (empresa_id,titulo,descricao,categoria,nivel,ordem) VALUES (?,?,?,?,?,?)",
                              (empresa_id, titulo, f"Procedimentos e regras de {categoria} da sua empresa.", categoria,
                               "Iniciante" if p == 0 else "Intermediário", ordem))
            con.executemany("INSERT INTO curso_itens (curso_id, conteudo_id, ordem) VALUES (?,?,?)",
                            [(cur.lastrowid, i, n + 1) for n, i in enumerate(fatia)])
            criados += 1
    # cursos automáticos que ficaram sem lições (conteúdos excluídos)
    con.execute("DELETE FROM cursos WHERE empresa_id=? AND categoria IS NOT NULL AND id NOT IN (SELECT curso_id FROM curso_itens)", (empresa_id,))
    con.commit()
    return criados, anexados


# ---------- Perguntas de verificação ----------
def _quiz(con, k, vis):
    """Questão de múltipla escolha de um conteúdo (dict com pergunta, opcoes, indice) ou None. Determinística."""
    if not k["pergunta_exemplo"] or not k["resposta_exemplo"]:
        g = con.execute("SELECT pergunta, correta, erradas FROM quiz_gerados WHERE conteudo_id=?", (k["id"],)).fetchone()
        if not g:
            return None
        rnd = random.Random(f"quiz:{k['id']}")
        opcoes = json.loads(g["erradas"]) + [g["correta"]]
        rnd.shuffle(opcoes)
        return {"pergunta": g["pergunta"], "opcoes": opcoes, "indice": opcoes.index(g["correta"]), "ia": True}
    correta = k["resposta_exemplo"].strip()
    outros = con.execute(
        f"SELECT categoria, resposta_exemplo FROM conteudos WHERE empresa_id=? AND id<>? AND resposta_exemplo IS NOT NULL "
        f"AND visibilidade IN ({_marcas(vis)}) ORDER BY id", [k["empresa_id"], k["id"], *vis]).fetchall()
    mesma, resto, vistos = [], [], {correta}
    for o in outros:
        t = o["resposta_exemplo"].strip()
        if t in vistos:
            continue
        vistos.add(t)
        (mesma if o["categoria"] == k["categoria"] else resto).append(t)
    rnd = random.Random(f"quiz:{k['id']}")
    rnd.shuffle(mesma); rnd.shuffle(resto)
    erradas = (mesma + resto)[:3]
    if len(erradas) < 2:
        return None
    opcoes = erradas + [correta]
    rnd.shuffle(opcoes)
    return {"pergunta": k["pergunta_exemplo"], "opcoes": opcoes, "indice": opcoes.index(correta)}


# ---------- Consultas ----------
def _linhas(con, usuario, empresa_id, curso_id=None):
    vis = visibilidades_do(usuario["tipo"])
    sql = (f"SELECT c.id AS curso_id, c.titulo AS curso, c.descricao, c.categoria AS curso_categoria, c.nivel, k.*, i.ordem AS posicao, "
           "p.concluida_em, p.acertou FROM cursos c JOIN curso_itens i ON i.curso_id=c.id JOIN conteudos k ON k.id=i.conteudo_id "
           "LEFT JOIN progresso_licoes p ON p.curso_id=c.id AND p.conteudo_id=k.id AND p.usuario_id=? "
           f"WHERE c.empresa_id=? AND k.visibilidade IN ({_marcas(vis)})")
    params = [usuario["id"], empresa_id, *vis]
    if curso_id:
        sql += " AND c.id=?"
        params.append(curso_id)
    return con.execute(sql + " ORDER BY c.ordem, c.id, i.ordem", params).fetchall()


def listar(con, usuario, empresa_id):
    cursos = {}
    for r in _linhas(con, usuario, empresa_id):
        c = cursos.setdefault(r["curso_id"], {
            "id": r["curso_id"], "titulo": r["curso"], "descricao": r["descricao"], "categoria": r["curso_categoria"], "nivel": r["nivel"], "personalizado": r["curso_categoria"] is None,
            "licoes": 0, "concluidas": 0, "respondidas": 0, "acertos": 0, "minutos": 0, "ultima": None, "proxima": None})
        c["licoes"] += 1
        c["minutos"] += _minutos(r["texto"])
        if r["concluida_em"]:
            c["concluidas"] += 1
            c["ultima"] = max(c["ultima"] or "", r["concluida_em"])
            if r["acertou"] is not None:
                c["respondidas"] += 1
                c["acertos"] += r["acertou"]
        elif c["proxima"] is None:
            c["proxima"] = {"conteudo_id": r["id"], "titulo": r["titulo"]}
    out = list(cursos.values())
    for c in out:
        c["percentual"] = round(100 * c["concluidas"] / c["licoes"])
    return out


def resumo(cursos):
    """Totais e 'continue de onde parou' a partir da lista de cursos do usuário."""
    licoes = sum(c["licoes"] for c in cursos)
    feitas = sum(c["concluidas"] for c in cursos)
    abertos = [c for c in cursos if c["proxima"]]
    em_andamento = sorted([c for c in abertos if c["concluidas"]], key=lambda c: c["ultima"] or "", reverse=True)
    escolhido = (em_andamento or abertos or [None])[0]
    return {"cursos": len(cursos), "cursos_concluidos": sum(1 for c in cursos if c["percentual"] == 100),
            "licoes": licoes, "concluidas": feitas, "percentual": round(100 * feitas / licoes) if licoes else 0,
            "respondidas": sum(c["respondidas"] for c in cursos), "acertos": sum(c["acertos"] for c in cursos),
            "continuar": ({"curso_id": escolhido["id"], "curso": escolhido["titulo"], "conteudo_id": escolhido["proxima"]["conteudo_id"],
                           "licao": escolhido["proxima"]["titulo"], "percentual": escolhido["percentual"]} if escolhido else None)}


def detalhe(con, usuario, empresa_id, curso_id):
    linhas = _linhas(con, usuario, empresa_id, curso_id)
    if not linhas:
        return None
    vis = visibilidades_do(usuario["tipo"])
    licoes = []
    for r in linhas:
        q = _quiz(con, r, vis)
        licoes.append({"conteudo_id": r["id"], "codigo": r["codigo"], "titulo": r["titulo"], "texto": r["texto"],
                       "minutos": _minutos(r["texto"]), "concluida": bool(r["concluida_em"]),
                       "acertou": None if r["acertou"] is None else bool(r["acertou"]),
                       "quiz": {"pergunta": q["pergunta"], "opcoes": q["opcoes"], "ia": bool(q.get("ia"))} if q else None})
    r0 = linhas[0]
    feitas = sum(1 for l in licoes if l["concluida"])
    return {"id": r0["curso_id"], "titulo": r0["curso"], "descricao": r0["descricao"], "categoria": r0["curso_categoria"], "nivel": r0["nivel"],
            "licoes": licoes, "concluidas": feitas, "percentual": round(100 * feitas / len(licoes))}


def _licao_do_curso(con, usuario, empresa_id, curso_id, conteudo_id):
    for r in _linhas(con, usuario, empresa_id, curso_id):
        if r["id"] == conteudo_id:
            return r
    return None


def concluir(con, usuario, empresa_id, curso_id, conteudo_id):
    if not _licao_do_curso(con, usuario, empresa_id, curso_id, conteudo_id):
        return False
    con.execute("INSERT OR IGNORE INTO progresso_licoes (usuario_id, curso_id, conteudo_id) VALUES (?,?,?)", (usuario["id"], curso_id, conteudo_id))
    con.commit()
    return True


def responder_quiz(con, usuario, empresa_id, curso_id, conteudo_id, opcao):
    """Corrige a pergunta de verificação. Só a primeira tentativa conta para a pontuação; a lição é concluída."""
    lic = _licao_do_curso(con, usuario, empresa_id, curso_id, conteudo_id)
    q = _quiz(con, lic, visibilidades_do(usuario["tipo"])) if lic else None
    if not q:
        return None
    correta = opcao == q["indice"]
    con.execute("INSERT OR IGNORE INTO progresso_licoes (usuario_id, curso_id, conteudo_id) VALUES (?,?,?)", (usuario["id"], curso_id, conteudo_id))
    con.execute("UPDATE progresso_licoes SET acertou=? WHERE usuario_id=? AND curso_id=? AND conteudo_id=? AND acertou IS NULL",
                (1 if correta else 0, usuario["id"], curso_id, conteudo_id))
    con.commit()
    return {"correta": correta, "indice_correto": q["indice"], "resposta_certa": q["opcoes"][q["indice"]]}


# ---------- Cursos personalizados (o admin escolhe e ordena as lições) ----------
NIVEIS = ("Iniciante", "Intermediário", "Avançado")
MAX_LICOES = 60


def _validar_ids(con, empresa_id, ids):
    if not isinstance(ids, list) or not ids:
        raise ValueError("Escolha pelo menos uma lição.")
    if len(ids) > MAX_LICOES:
        raise ValueError(f"Um curso pode ter no máximo {MAX_LICOES} lições.")
    if any(not isinstance(i, int) or isinstance(i, bool) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Lista de lições inválida.")
    n = con.execute(f"SELECT COUNT(*) FROM conteudos WHERE empresa_id=? AND id IN ({_marcas(ids)})", [empresa_id, *ids]).fetchone()[0]
    if n != len(ids):
        raise ValueError("Há lições que não pertencem a esta empresa.")


def _definir_itens(con, curso_id, ids):
    con.execute("DELETE FROM curso_itens WHERE curso_id=?", (curso_id,))   # o progresso das lições que ficam é preservado
    con.executemany("INSERT INTO curso_itens (curso_id, conteudo_id, ordem) VALUES (?,?,?)", [(curso_id, i, n + 1) for n, i in enumerate(ids)])


def criar_personalizado(con, empresa_id, titulo, descricao, nivel, ids):
    if nivel not in NIVEIS:
        raise ValueError("Nível inválido.")
    _validar_ids(con, empresa_id, ids)
    ordem = con.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM cursos WHERE empresa_id=?", (empresa_id,)).fetchone()[0]
    cur = con.execute("INSERT INTO cursos (empresa_id,titulo,descricao,categoria,nivel,ordem) VALUES (?,?,?,NULL,?,?)", (empresa_id, titulo, descricao, nivel, ordem))
    _definir_itens(con, cur.lastrowid, ids)
    con.commit()
    return cur.lastrowid


def atualizar_personalizado(con, curso, titulo, descricao, nivel, ids):
    if curso["categoria"] is not None:
        raise ValueError("Cursos automáticos não permitem trocar as lições (crie um curso personalizado).")
    if nivel not in NIVEIS:
        raise ValueError("Nível inválido.")
    _validar_ids(con, curso["empresa_id"], ids)
    con.execute("UPDATE cursos SET titulo=?, descricao=?, nivel=? WHERE id=?", (titulo, descricao, nivel, curso["id"]))
    _definir_itens(con, curso["id"], ids)
    con.commit()


def estrutura(con, curso):
    """Dados para o editor do admin: lições do curso, na ordem (todas, sem filtrar por visibilidade)."""
    itens = [r[0] for r in con.execute("SELECT conteudo_id FROM curso_itens WHERE curso_id=? ORDER BY ordem", (curso["id"],))]
    return {"id": curso["id"], "titulo": curso["titulo"], "descricao": curso["descricao"], "nivel": curso["nivel"],
            "personalizado": curso["categoria"] is None, "conteudo_ids": itens}


# ---------- Certificados ----------
def _novo_codigo(con):
    while True:
        codigo = "OUT-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
        if not con.execute("SELECT 1 FROM certificados WHERE codigo=?", (codigo,)).fetchone():
            return codigo


def emitir_certificado(con, usuario, empresa_id, curso_id):
    """Emite (ou devolve o já emitido) certificado de um curso concluído por inteiro. Levanta ValueError se não for o caso."""
    curso = next((c for c in listar(con, usuario, empresa_id) if c["id"] == curso_id), None)
    if not curso:
        raise ValueError("Curso não encontrado.")
    if curso["percentual"] < 100:
        raise ValueError("Conclua todas as lições do curso para emitir o certificado.")
    existente = con.execute("SELECT * FROM certificados WHERE usuario_id=? AND curso_id=?", (usuario["id"], curso_id)).fetchone()
    if existente:
        return dict(existente)
    empresa = con.execute("SELECT nome FROM empresas WHERE id=?", (empresa_id,)).fetchone()
    codigo = _novo_codigo(con)
    con.execute("INSERT INTO certificados (codigo,usuario_id,curso_id,nome,curso_titulo,empresa_nome,licoes,acertos,respondidas) VALUES (?,?,?,?,?,?,?,?,?)",
                (codigo, usuario["id"], curso_id, usuario["nome"], curso["titulo"], empresa["nome"] if empresa else None,
                 curso["licoes"], curso["acertos"], curso["respondidas"]))
    con.commit()
    return dict(con.execute("SELECT * FROM certificados WHERE codigo=?", (codigo,)).fetchone())


def certificado_publico(con, codigo):
    """Dados mínimos para a verificação pública de um certificado (ou None)."""
    r = con.execute("SELECT nome, curso_titulo, empresa_nome, licoes, emitido_em FROM certificados WHERE codigo=?", (str(codigo or "").strip().upper(),)).fetchone()
    return dict(r) if r else None