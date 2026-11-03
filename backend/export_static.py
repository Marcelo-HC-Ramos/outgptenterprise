"""Gera docs/dados.js: dados da pesquisa para o modo demonstração (GitHub Pages).

Exporta as perguntas e as respostas de forma anônima (sem nome, e-mail, cargo ou organização).
Por padrão inclui apenas os dados fictícios do Faker (e-mails @faker.example), para nunca
publicar respostas reais por engano. Use --todos para incluir também as reais (revise os comentários antes!).
"""
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "outgpt.db"
SAIDA = BASE.parent / "docs" / "dados.js"


def main():
    todos = "--todos" in sys.argv
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    perguntas = []
    for p in con.execute("SELECT * FROM perguntas ORDER BY ordem"):
        ops = [dict(o) for o in con.execute("SELECT id, texto FROM opcoes WHERE pergunta_id=? ORDER BY ordem", (p["id"],))]
        perguntas.append({"id": p["id"], "ordem": p["ordem"], "texto": p["texto"], "tipo": p["tipo"],
                          "obrigatoria": bool(p["obrigatoria"]), "opcoes": ops})
    tipos = {p["id"]: p["tipo"] for p in perguntas}

    filtro = "" if todos else "WHERE email LIKE '%@faker.example'"
    participantes = []
    for e in con.execute(f"SELECT id, tipo_organizacao FROM especialistas {filtro} ORDER BY id"):
        resp = {}
        for r in con.execute("SELECT pergunta_id, opcao_id, valor_escala, texto_livre FROM respostas WHERE especialista_id=?", (e["id"],)):
            t = tipos[r["pergunta_id"]]
            if t == "escala":
                resp[str(r["pergunta_id"])] = r["valor_escala"]
            elif t == "unica":
                resp[str(r["pergunta_id"])] = r["opcao_id"]
            elif t == "multipla":
                resp.setdefault(str(r["pergunta_id"]), []).append(r["opcao_id"])
            else:
                resp[str(r["pergunta_id"])] = r["texto_livre"]
        participantes.append({"tipo_organizacao": e["tipo_organizacao"], "respostas": resp})

    SAIDA.write_text("window.DADOS_PESQUISA = " + json.dumps({"perguntas": perguntas, "participantes": participantes}, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"{SAIDA}: {len(perguntas)} perguntas, {len(participantes)} participantes ({'todos' if todos else 'apenas fictícios'})")


if __name__ == "__main__":
    main()
