"""Relatório de engajamento para o RH: quais materiais são mais difíceis de assimilar.

Os dados são AGREGADOS por lição e por curso: o relatório não traz nomes nem e-mails. Para cada lição mede quantas pessoas começaram e
concluíram, o tempo de estudo (mediana), o acerto na 1ª tentativa e o abandono, e resume tudo em um índice de dificuldade (0 a 100).

Índice de dificuldade = média ponderada (só dos sinais que existem para a lição):
    erro na 1ª tentativa da pergunta de verificação  (peso 0,5)
    tempo acima do esperado (mediana / tempo estimado de leitura; 2x o esperado = 100%)  (peso 0,3)
    abandono (começaram e não concluíram)  (peso 0,2)
"""
import csv
import io
import statistics
from datetime import datetime, timedelta

import cursos
from auth import conteudo_visivel

MIN_AMOSTRA = 3                    # abaixo disso a lição aparece, mas marcada como "amostra pequena" (não classifica)
PESOS = {"erro": 0.5, "ritmo": 0.3, "abandono": 0.2}
LIMIAR_DIFICIL, LIMIAR_ATENCAO = 60, 35
TIPOS_ALUNOS = ("funcionario", "colaborador_interno", "colaborador_externo")      # admins e master não entram na métrica
JANELA_ATIVOS_DIAS = 30
_FMT = "%Y-%m-%d %H:%M:%S"


def indice_dificuldade(erro, ritmo, abandono):
    """0 a 100, ou None se nenhum sinal está disponível. `erro` e `abandono` são frações (0 a 1); `ritmo` = tempo real / esperado."""
    sinais = {}
    if erro is not None:
        sinais["erro"] = min(1.0, max(0.0, erro))
    if ritmo is not None:
        sinais["ritmo"] = min(1.0, max(0.0, ritmo - 1.0))
    if abandono is not None:
        sinais["abandono"] = min(1.0, max(0.0, abandono))
    if not sinais:
        return None
    return round(100 * sum(PESOS[k] * v for k, v in sinais.items()) / sum(PESOS[k] for k in sinais))


def classificar(indice, amostra):
    if indice is None or amostra < MIN_AMOSTRA:
        return "amostra"
    return "dificil" if indice >= LIMIAR_DIFICIL else "atencao" if indice >= LIMIAR_ATENCAO else "tranquila"


def _pct(parte, total):
    return round(100 * parte / total) if total else None


def relatorio(con, empresa_id, departamento_id=None, curso_id=None):
    agora = datetime.now()
    corte = (agora - timedelta(days=JANELA_ATIVOS_DIAS)).strftime(_FMT)

    marcas = ",".join("?" * len(TIPOS_ALUNOS))
    pessoas = [dict(r) for r in con.execute(
        f"SELECT id, tipo, departamento_id FROM usuarios WHERE empresa_id=? AND ativo=1 AND tipo IN ({marcas})", (empresa_id, *TIPOS_ALUNOS))]
    if departamento_id is not None:
        pessoas = [p for p in pessoas if p["departamento_id"] == departamento_id]
    ids = {p["id"] for p in pessoas}

    deps_do = {}
    for r in con.execute("SELECT cd.conteudo_id, cd.departamento_id FROM conteudo_departamentos cd JOIN conteudos k ON k.id=cd.conteudo_id WHERE k.empresa_id=?", (empresa_id,)):
        deps_do.setdefault(r[0], set()).add(r[1])

    sql = ("SELECT c.id AS curso_id, c.titulo AS curso, k.id AS cid, k.codigo, k.titulo, k.visibilidade, k.texto FROM cursos c "
           "JOIN curso_itens i ON i.curso_id=c.id JOIN conteudos k ON k.id=i.conteudo_id WHERE c.empresa_id=?")
    params = [empresa_id]
    if curso_id:
        sql += " AND c.id=?"
        params.append(curso_id)
    licoes = con.execute(sql + " ORDER BY c.ordem, c.id, i.ordem", params).fetchall()

    prog = {(r["usuario_id"], r["curso_id"], r["conteudo_id"]): r for r in con.execute(
        "SELECT p.* FROM progresso_licoes p JOIN usuarios u ON u.id=p.usuario_id WHERE u.empresa_id=?", (empresa_id,)) if r["usuario_id"] in ids}
    tempo = {(r["usuario_id"], r["curso_id"], r["conteudo_id"]): r for r in con.execute(
        "SELECT t.* FROM licao_tempo t JOIN usuarios u ON u.id=t.usuario_id WHERE u.empresa_id=?", (empresa_id,)) if r["usuario_id"] in ids}

    visiveis = {}        # (pessoa, curso) -> [conteudo_id das lições que ela pode ver]
    out_licoes = []
    erros_total = respondidas_total = 0
    for L in licoes:
        deps = deps_do.get(L["cid"], set())
        elegiveis = [p for p in pessoas if conteudo_visivel(p["tipo"], p["departamento_id"], L["visibilidade"], deps)]
        if not elegiveis:
            continue
        iniciaram = concluiram = respondidas = erraram = 0
        segundos, tentativas = [], []
        for p in elegiveis:
            visiveis.setdefault((p["id"], L["curso_id"]), []).append(L["cid"])
            pr, tm = prog.get((p["id"], L["curso_id"], L["cid"])), tempo.get((p["id"], L["curso_id"], L["cid"]))
            seg = tm["segundos"] if tm and tm["segundos"] > 0 else 0
            if pr or seg:
                iniciaram += 1
            if seg:
                segundos.append(seg)
            if pr:
                concluiram += 1
                if pr["acertou"] is not None:
                    respondidas += 1
                    erraram += 1 if pr["acertou"] == 0 else 0
                    tentativas.append(max(1, pr["tentativas"] or 1))
        esperado = cursos._minutos(L["texto"]) * 60
        mediana = statistics.median(segundos) if segundos else None
        abandono = (iniciaram - concluiram) / iniciaram if iniciaram else None
        erro = erraram / respondidas if respondidas else None
        ritmo = mediana / esperado if mediana is not None else None
        indice = indice_dificuldade(erro, ritmo, abandono) if iniciaram else None
        erros_total += erraram
        respondidas_total += respondidas
        out_licoes.append({
            "conteudo_id": L["cid"], "codigo": L["codigo"], "titulo": L["titulo"], "curso_id": L["curso_id"], "curso": L["curso"],
            "elegiveis": len(elegiveis), "iniciaram": iniciaram, "concluiram": concluiram,
            "abandono_pct": _pct(iniciaram - concluiram, iniciaram),
            "tempo_mediano_s": round(mediana) if mediana is not None else None,
            "tempo_medio_s": round(sum(segundos) / len(segundos)) if segundos else None,
            "esperado_s": esperado, "ritmo": round(ritmo, 2) if ritmo is not None else None,
            "respondidas": respondidas, "acerto_1a_pct": _pct(respondidas - erraram, respondidas),
            "tentativas_media": round(sum(tentativas) / len(tentativas), 2) if tentativas else None,
            "dificuldade": indice, "nivel": classificar(indice, iniciaram), "amostra": iniciaram,
        })

    # --- por curso ---
    out_cursos = []
    por_curso = {}
    for L in out_licoes:
        por_curso.setdefault(L["curso_id"], {"titulo": L["curso"], "licoes": []})["licoes"].append(L)
    for cid, info in por_curso.items():
        quem = [(pid, lst) for (pid, c), lst in visiveis.items() if c == cid]
        qs = {pid for pid, _ in quem}
        comecou = sum(1 for pid, lst in quem if any((pid, cid, k) in prog or ((pid, cid, k) in tempo and tempo[(pid, cid, k)]["segundos"] > 0) for k in lst))
        terminou = sum(1 for pid, lst in quem if lst and all((pid, cid, k) in prog for k in lst))
        segs = [t["segundos"] for (pid, c, k), t in tempo.items() if c == cid and t["segundos"] > 0 and pid in qs]
        niveis = [l["dificuldade"] for l in info["licoes"] if l["dificuldade"] is not None and l["amostra"] >= MIN_AMOSTRA]
        out_cursos.append({"id": cid, "titulo": info["titulo"], "licoes": len(info["licoes"]), "elegiveis": len(quem),
                           "iniciaram": comecou, "concluiram": terminou, "conclusao_pct": _pct(terminou, len(quem)),
                           "tempo_total_s": sum(segs), "dificuldade_media": round(sum(niveis) / len(niveis)) if niveis else None})

    # --- por pessoa (agregado em departamentos e no resumo; nenhuma pessoa é identificada) ---
    ativos = set()
    for (u, _, _), r in prog.items():
        if r["concluida_em"] >= corte:
            ativos.add(u)
    for (u, _, _), t in tempo.items():
        if t["ultima_em"] >= corte:
            ativos.add(u)
    cursos_da_pessoa = {}
    for (pid, c), lst in visiveis.items():
        cursos_da_pessoa.setdefault(pid, []).append((c, lst))
    fracao = {}
    for p in pessoas:
        total = feitas = 0
        for c, lst in cursos_da_pessoa.get(p["id"], []):
            total += len(lst)
            feitas += sum(1 for k in lst if (p["id"], c, k) in prog)
        fracao[p["id"]] = (feitas / total) if total else None
    nomes = {r["id"]: r["nome"] for r in con.execute("SELECT id, nome FROM departamentos WHERE empresa_id=?", (empresa_id,))}
    por_dep = {}
    for p in pessoas:
        por_dep.setdefault(p["departamento_id"], []).append(p)
    out_deps = []
    for did, grupo in sorted(por_dep.items(), key=lambda kv: (kv[0] is None, nomes.get(kv[0], ""))):
        fr = [fracao[p["id"]] for p in grupo if fracao[p["id"]] is not None]
        out_deps.append({"id": did, "nome": nomes.get(did, "Sem departamento"), "pessoas": len(grupo),
                         "ativas": sum(1 for p in grupo if p["id"] in ativos),
                         "conclusao_media_pct": round(100 * sum(fr) / len(fr)) if fr else None})
    fr_todas = [v for v in fracao.values() if v is not None]
    tempo_total = sum(t["segundos"] for t in tempo.values())
    resumo = {"pessoas": len(pessoas), "ativas": len(ativos), "janela_ativos_dias": JANELA_ATIVOS_DIAS,
              "licoes_concluidas": len(prog), "tempo_total_s": tempo_total,
              "conclusao_media_pct": round(100 * sum(fr_todas) / len(fr_todas)) if fr_todas else None,
              "acerto_1a_pct": _pct(respondidas_total - erros_total, respondidas_total), "min_amostra": MIN_AMOSTRA}
    ordenadas = sorted(out_licoes, key=lambda l: (l["nivel"] == "amostra", -(l["dificuldade"] if l["dificuldade"] is not None else -1)))
    return {"resumo": resumo, "licoes": ordenadas, "cursos": out_cursos, "departamentos": out_deps}


COLUNAS_CSV = ["curso", "licao", "codigo", "pessoas_elegiveis", "iniciaram", "concluiram", "abandono_pct", "tempo_mediano_s", "tempo_esperado_s",
               "acerto_1a_pct", "tentativas_media", "indice_dificuldade", "classificacao"]


def csv_licoes(rel):
    """CSV (UTF-8 com BOM, abre direto no Excel) do relatório por lição. Textos que começam com = + - @ ganham um apóstrofo (injeção de fórmulas)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUNAS_CSV)
    rotulo = {"dificil": "difícil", "atencao": "atenção", "tranquila": "tranquila", "amostra": "amostra pequena"}
    for l in rel["licoes"]:
        linha = [l["curso"], l["titulo"], l["codigo"], l["elegiveis"], l["iniciaram"], l["concluiram"], l["abandono_pct"], l["tempo_mediano_s"],
                 l["esperado_s"], l["acerto_1a_pct"], l["tentativas_media"], l["dificuldade"], rotulo[l["nivel"]]]
        w.writerow(["" if c is None else (("'" + c) if isinstance(c, str) and c[:1] in "=+-@\t\r" else c) for c in linha])
    return buf.getvalue().encode("utf-8-sig")
