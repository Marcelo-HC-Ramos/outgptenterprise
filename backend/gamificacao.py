"""Gamificação: pontos, níveis, sequência de estudo e conquistas (badges).

Tudo é calculado a partir do que a pessoa já fez (lições concluídas, perguntas de verificação, certificados, dúvidas ao assistente);
só as conquistas são gravadas, para guardar a data em que foram desbloqueadas. Não há ranking entre pessoas: a ideia é motivar cada um
com o próprio progresso, sem expor ninguém.
"""
from datetime import date, timedelta

import cursos

# (pontos mínimos, nome do nível)
NIVEIS = [(0, "Iniciante"), (100, "Aprendiz"), (300, "Praticante"), (700, "Especialista"), (1500, "Mestre")]
PONTOS = {"licao": 10, "acerto": 5, "curso": 50, "certificado": 30, "conquista": 20}


def _trilha_meta(s):
    return max(2, s["total_cursos"])


def _trilha_valor(s):
    return s["cursos_concluidos"] if s["total_cursos"] >= 2 else 0


# codigo, nome, ícone, descrição, meta (número ou função das estatísticas), valor atual (função das estatísticas)
CATALOGO = [
    ("primeiro_passo", "Primeiro passo", "👣", "Conclua a sua primeira lição.", 1, lambda s: s["licoes"]),
    ("em_ritmo", "Em ritmo", "⚡", "Conclua 10 lições.", 10, lambda s: s["licoes"]),
    ("maratonista", "Maratonista", "🏃", "Conclua 30 lições.", 30, lambda s: s["licoes"]),
    ("curso_concluido", "Curso concluído", "🎓", "Conclua todas as lições de um curso.", 1, lambda s: s["cursos_concluidos"]),
    ("trilha_completa", "Trilha completa", "🧭", "Conclua todos os cursos da sua trilha (a partir de 2 cursos).", _trilha_meta, _trilha_valor),
    ("acerto_de_primeira", "Acerto de primeira", "🎯", "Acerte 5 perguntas de verificação de primeira.", 5, lambda s: s["acertos"]),
    ("gabarito", "Gabarito", "💯", "Conclua um curso acertando todas as perguntas de primeira (mínimo de 3 perguntas).", 1, lambda s: s["gabaritos"]),
    ("certificado", "Certificado em mãos", "🏆", "Emita o seu primeiro certificado.", 1, lambda s: s["certificados"]),
    ("constancia", "Constância", "🔥", "Estude 3 dias seguidos.", 3, lambda s: s["melhor_sequencia"]),
    ("semana_cheia", "Semana cheia", "📅", "Estude 7 dias seguidos.", 7, lambda s: s["melhor_sequencia"]),
    ("curioso", "Curioso", "💬", "Faça 10 perguntas ao assistente.", 10, lambda s: s["perguntas"]),
]
_POR_CODIGO = {c[0]: c for c in CATALOGO}


def _meta(item, s):
    m = item[4]
    return m(s) if callable(m) else m


def _publico(item):
    return {"codigo": item[0], "nome": item[1], "icone": item[2], "descricao": item[3]}


def sequencias(dias, hoje=None):
    """(sequência atual, melhor sequência) de dias consecutivos de estudo. `dias`: datas ISO ('2026-11-22').
    A atual só conta se o último dia de estudo foi hoje ou ontem (ainda dá tempo de manter a sequência)."""
    hoje = hoje or date.today()
    ds = sorted({date.fromisoformat(str(d)[:10]) for d in dias if d})
    melhor = corrente = 0
    anterior = None
    for d in ds:
        corrente = corrente + 1 if anterior is not None and d - anterior == timedelta(days=1) else 1
        melhor = max(melhor, corrente)
        anterior = d
    atual = corrente if anterior is not None and (hoje - anterior) <= timedelta(days=1) else 0
    return atual, melhor


def nivel_de(pontos):
    """(nome, índice) do nível e o próximo nível ({'nome','pontos','faltam'} ou None)."""
    idx = max(i for i, (minimo, _) in enumerate(NIVEIS) if pontos >= minimo)
    prox = NIVEIS[idx + 1] if idx + 1 < len(NIVEIS) else None
    return ({"nome": NIVEIS[idx][1], "indice": idx, "minimo": NIVEIS[idx][0]},
            {"nome": prox[1], "pontos": prox[0], "faltam": prox[0] - pontos} if prox else None)


def estatisticas(con, usuario):
    """Números da pessoa que alimentam as conquistas e os pontos (respeitam a trilha: só o que ela pode ver)."""
    lista = cursos.listar(con, usuario, usuario["empresa_id"])
    uid = usuario["id"]
    dias = [r[0] for r in con.execute("SELECT DISTINCT date(concluida_em) FROM progresso_licoes WHERE usuario_id=?", (uid,))]
    atual, melhor = sequencias(dias)
    return {
        "licoes": sum(c["concluidas"] for c in lista),
        "acertos": sum(c["acertos"] for c in lista),
        "respondidas": sum(c["respondidas"] for c in lista),
        "total_cursos": len(lista),
        "cursos_concluidos": sum(1 for c in lista if c["percentual"] == 100),
        "gabaritos": sum(1 for c in lista if c["percentual"] == 100 and c["respondidas"] >= 3 and c["acertos"] == c["respondidas"]),
        "certificados": con.execute("SELECT COUNT(*) FROM certificados WHERE usuario_id=?", (uid,)).fetchone()[0],
        "perguntas": con.execute("SELECT COUNT(*) FROM historico_duvidas WHERE usuario_id=?", (uid,)).fetchone()[0],
        "sequencia_atual": atual, "melhor_sequencia": melhor,
    }


def _grava(con, usuario, codigos):
    novas = []
    for cod in codigos:
        cur = con.execute("INSERT OR IGNORE INTO conquistas (usuario_id, codigo) VALUES (?,?)", (usuario["id"], cod))
        if cur.rowcount:
            novas.append(_publico(_POR_CODIGO[cod]))
    if novas:
        con.commit()
    return novas


def _tem(con, usuario):
    return {r[0] for r in con.execute("SELECT codigo FROM conquistas WHERE usuario_id=?", (usuario["id"],))}


def avaliar(con, usuario):
    """Desbloqueia as conquistas que a pessoa já merece e devolve só as NOVAS (para avisar na tela). O master não participa."""
    if usuario["tipo"] == "master" or not usuario["empresa_id"]:
        return []
    s = estatisticas(con, usuario)
    tem = _tem(con, usuario)
    return _grava(con, usuario, [c[0] for c in CATALOGO if c[0] not in tem and _meta(c, s) > 0 and c[5](s) >= _meta(c, s)])


def avaliar_chat(con, usuario):
    """Versão leve para depois de cada pergunta ao assistente: só a conquista 'Curioso'."""
    if usuario["tipo"] == "master" or not usuario["empresa_id"] or "curioso" in _tem(con, usuario):
        return []
    n = con.execute("SELECT COUNT(*) FROM historico_duvidas WHERE usuario_id=?", (usuario["id"],)).fetchone()[0]
    return _grava(con, usuario, ["curioso"]) if n >= _meta(_POR_CODIGO["curioso"], {}) else []


def perfil(con, usuario):
    """Tela 'Conquistas': pontos, nível, sequência, conquistas (com progresso das que faltam) e números gerais."""
    if usuario["tipo"] == "master" or not usuario["empresa_id"]:
        return {"disponivel": False}
    avaliar(con, usuario)                  # também concede, na primeira visita, o que a pessoa já tinha feito antes da gamificação
    s = estatisticas(con, usuario)
    quando = {r[0]: r[1] for r in con.execute("SELECT codigo, conquistada_em FROM conquistas WHERE usuario_id=?", (usuario["id"],))}
    pontos = (PONTOS["licao"] * s["licoes"] + PONTOS["acerto"] * s["acertos"] + PONTOS["curso"] * s["cursos_concluidos"]
              + PONTOS["certificado"] * s["certificados"] + PONTOS["conquista"] * len(quando))
    nivel, proximo = nivel_de(pontos)
    faixa = (proximo["pontos"] - nivel["minimo"]) if proximo else 0
    conquistas = []
    for item in CATALOGO:
        meta, atual = _meta(item, s), item[5](s)
        conquistas.append({**_publico(item), "conquistada_em": quando.get(item[0]), "atual": min(atual, meta), "meta": meta})
    return {"disponivel": True, "pontos": pontos, "nivel": nivel, "proximo_nivel": proximo,
            "progresso_nivel": round(100 * (pontos - nivel["minimo"]) / faixa) if proximo else 100,
            "sequencia_atual": s["sequencia_atual"], "melhor_sequencia": s["melhor_sequencia"],
            "licoes": s["licoes"], "cursos_concluidos": s["cursos_concluidos"], "total_cursos": s["total_cursos"],
            "certificados": s["certificados"], "acertos": s["acertos"], "respondidas": s["respondidas"],
            "conquistas": conquistas, "desbloqueadas": len(quando), "total_conquistas": len(CATALOGO)}
