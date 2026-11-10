"""Gera os arquivos de dados do site publicado (GitHub Pages / modo demonstração).

  docs/dados.js            perguntas da pesquisa (e, com --com-respostas, as respostas reais, de forma anônima)
  docs/demo_conteudos.js   conteúdo de exemplo (backend/data/sops_corporativos.csv) usado pelos cursos e pelo assistente da demo

Uso:  python export_static.py [--com-respostas]
As respostas da pesquisa só são publicadas com --com-respostas, sem nome, e-mail, cargo ou organização.
Revise os comentários livres antes de publicar: eles podem conter dados pessoais.
"""
import csv
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "outgpt.db"
CSV_SOPS = BASE / "data" / "sops_corporativos.csv"
SAIDA = BASE.parent / "docs"


def pesquisa(com_respostas):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    perguntas = []
    for p in con.execute("SELECT * FROM perguntas ORDER BY ordem"):
        ops = [dict(o) for o in con.execute("SELECT id, texto FROM opcoes WHERE pergunta_id=? ORDER BY ordem", (p["id"],))]
        perguntas.append({"id": p["id"], "ordem": p["ordem"], "texto": p["texto"], "tipo": p["tipo"],
                          "obrigatoria": bool(p["obrigatoria"]), "opcoes": ops})
    participantes = []
    if com_respostas:
        tipos = {p["id"]: p["tipo"] for p in perguntas}
        for e in con.execute("SELECT id, tipo_organizacao FROM especialistas ORDER BY id"):
            resp = {}
            for r in con.execute("SELECT pergunta_id, opcao_id, valor_escala, texto_livre FROM respostas WHERE especialista_id=?", (e["id"],)):
                t, k = tipos[r["pergunta_id"]], str(r["pergunta_id"])
                if t == "escala":
                    resp[k] = r["valor_escala"]
                elif t == "unica":
                    resp[k] = r["opcao_id"]
                elif t == "multipla":
                    resp.setdefault(k, []).append(r["opcao_id"])
                else:
                    resp[k] = r["texto_livre"]
            participantes.append({"tipo_organizacao": e["tipo_organizacao"], "respostas": resp})
    (SAIDA / "dados.js").write_text("window.DADOS_PESQUISA = " + json.dumps({"perguntas": perguntas, "participantes": participantes}, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"docs/dados.js: {len(perguntas)} perguntas, {len(participantes)} respostas")


def conteudos():
    if not CSV_SOPS.exists():
        print("CSV de conteúdo de exemplo não encontrado; demo_conteudos.js não gerado.")
        return
    with open(CSV_SOPS, encoding="utf-8-sig", newline="") as f:
        itens = [{"codigo": r["id"], "titulo": r["procedimento_titulo"], "categoria": r["categoria"], "texto": r["contexto_documental"],
                  "pergunta": r["pergunta_utilizador"], "resposta": r["resposta_esperada"]} for r in csv.DictReader(f)]
    (SAIDA / "demo_conteudos.js").write_text("window.DEMO_CONTEUDOS = " + json.dumps(itens, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"docs/demo_conteudos.js: {len(itens)} conteúdos")


if __name__ == "__main__":
    pesquisa("--com-respostas" in sys.argv)
    conteudos()
