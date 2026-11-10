"""Pesquisa com especialistas: perguntas, gravação das respostas, resultados agregados e exportação CSV."""
import csv
import io

from db import conectar

TIPOS_ORG = ("Empresa", "Instituição de ensino", "Consultoria / outro")


def perguntas():
    with conectar() as con:
        out = []
        for p in con.execute("SELECT * FROM perguntas ORDER BY ordem"):
            ops = [dict(o) for o in con.execute("SELECT id, texto FROM opcoes WHERE pergunta_id=? ORDER BY ordem", (p["id"],))]
            out.append({"id": p["id"], "ordem": p["ordem"], "texto": p["texto"], "tipo": p["tipo"],
                        "obrigatoria": bool(p["obrigatoria"]), "opcoes": ops})
        return out


def salvar(dados):
    """Valida e grava tudo em uma transação. Devolve (ok, mensagem)."""
    esp = dados.get("especialista") or {}
    nome = str(esp.get("nome", "")).strip()[:120]
    cargo = str(esp.get("cargo", "")).strip()[:120]
    org = str(esp.get("organizacao", "")).strip()[:160]
    tipo_org = esp.get("tipo_organizacao")
    email = str(esp.get("email", "")).strip()[:160] or None
    anos = esp.get("anos_experiencia")
    if not (nome and cargo and org) or tipo_org not in TIPOS_ORG:
        return False, "Preencha nome, cargo, organização e tipo de organização."
    try:
        anos = int(anos) if anos not in (None, "") else None
        if anos is not None and not 0 <= anos <= 60:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Anos de experiência inválido."
    if not esp.get("consentimento"):
        return False, "É necessário concordar com o uso dos dados."

    resp = dados.get("respostas") or {}
    with conectar() as con:
        validas = {p["id"]: p for p in perguntas()}
        linhas = []
        for pid, p in validas.items():
            v = resp.get(str(pid))
            if v in (None, "", []):
                if p["obrigatoria"]:
                    return False, f"Responda a pergunta {p['ordem']}."
                continue
            ids_op = {o["id"] for o in p["opcoes"]}
            if p["tipo"] == "escala":
                if not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5):
                    return False, f"Valor inválido na pergunta {p['ordem']}."
                linhas.append((pid, None, v, None))
            elif p["tipo"] == "unica":
                if v not in ids_op:
                    return False, f"Opção inválida na pergunta {p['ordem']}."
                linhas.append((pid, v, None, None))
            elif p["tipo"] == "multipla":
                if not isinstance(v, list) or not set(v) <= ids_op:
                    return False, f"Opção inválida na pergunta {p['ordem']}."
                linhas += [(pid, o, None, None) for o in dict.fromkeys(v)]
            else:
                linhas.append((pid, None, None, str(v).strip()[:2000]))
        eid = con.execute(
            "INSERT INTO especialistas (nome,email,cargo,organizacao,tipo_organizacao,anos_experiencia) VALUES (?,?,?,?,?,?)",
            (nome, email, cargo, org, tipo_org, anos)).lastrowid
        con.executemany("INSERT INTO respostas (especialista_id,pergunta_id,opcao_id,valor_escala,texto_livre) VALUES (?,?,?,?,?)",
                        [(eid, *l) for l in linhas])
    return True, "Resposta registrada. Obrigado!"


def resultados():
    with conectar() as con:
        total = con.execute("SELECT COUNT(*) FROM especialistas").fetchone()[0]
        por_tipo = {r[0]: r[1] for r in con.execute("SELECT tipo_organizacao, COUNT(*) FROM especialistas GROUP BY 1")}
        out = []
        for p in perguntas():
            item = {"ordem": p["ordem"], "texto": p["texto"], "tipo": p["tipo"]}
            if p["tipo"] == "escala":
                r = con.execute("SELECT AVG(valor_escala), COUNT(*) FROM respostas WHERE pergunta_id=?", (p["id"],)).fetchone()
                dist = {i: 0 for i in range(1, 6)}
                for v, c in con.execute("SELECT valor_escala, COUNT(*) FROM respostas WHERE pergunta_id=? GROUP BY 1", (p["id"],)):
                    dist[v] = c
                item.update(media=round(r[0], 2) if r[0] else None, n=r[1], distribuicao=dist)
            elif p["tipo"] in ("unica", "multipla"):
                item["opcoes"] = [{"texto": t, "n": n} for t, n in con.execute(
                    "SELECT o.texto, COUNT(r.id) FROM opcoes o LEFT JOIN respostas r ON r.opcao_id=o.id "
                    "WHERE o.pergunta_id=? GROUP BY o.id ORDER BY o.ordem", (p["id"],))]
            else:
                item["textos"] = [r[0] for r in con.execute(
                    "SELECT texto_livre FROM respostas WHERE pergunta_id=? AND texto_livre IS NOT NULL ORDER BY id DESC", (p["id"],))]
            out.append(item)
        return {"total": total, "por_tipo": por_tipo, "perguntas": out}


def exportar_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["especialista_id", "nome", "cargo", "organizacao", "tipo_organizacao", "anos_experiencia", "pergunta", "resposta", "data"])
    with conectar() as con:
        for r in con.execute(
            "SELECT e.id,e.nome,e.cargo,e.organizacao,e.tipo_organizacao,e.anos_experiencia,p.ordem,"
            "COALESCE(o.texto, CAST(r.valor_escala AS TEXT), r.texto_livre),r.criado_em "
            "FROM respostas r JOIN especialistas e ON e.id=r.especialista_id JOIN perguntas p ON p.id=r.pergunta_id "
            "LEFT JOIN opcoes o ON o.id=r.opcao_id ORDER BY e.id,p.ordem"):
            w.writerow(["" if c is None else (("'" + c) if isinstance(c, str) and c[:1] in "=+-@" else c) for c in r])
    return buf.getvalue().encode("utf-8-sig")
