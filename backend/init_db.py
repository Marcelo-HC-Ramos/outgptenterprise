"""Cria o banco outgpt.db (esquema v2: multiempresa + autenticação) e carrega as perguntas da pesquisa.

Uso:  python init_db.py          # cria ou atualiza o banco (preserva a pesquisa e dados já existentes da v2)
      python init_db.py --reset  # apaga o arquivo e recria do zero

Depois crie o dono do sistema:  python criar_master.py
"""
import sqlite3
import sys

import db

BASE = db.BASE
VERSAO = 2

PERGUNTAS = [
    (1, "Em uma escala de 1 a 5, qual a importância de reduzir o tempo de onboarding de novos integrantes com apoio de IA generativa?",
     "escala", []),
    (2, "Quais são hoje os principais desafios na transmissão do conhecimento operacional na sua organização? (marque todos que se aplicam)",
     "multipla", ["Dependência de profissionais seniores/professores para explicar o básico",
                  "Perda de conhecimento quando alguém sai ou é transferido",
                  "Manuais e materiais desatualizados ou pouco consultados",
                  "Falta de tempo para treinar novos integrantes",
                  "Falta de padronização das informações"]),
    (3, "Qual o seu nível de confiança em um assistente de IA que responde somente com base nos documentos oficiais da organização e cita a fonte (RAG)? (1 = nenhuma, 5 = total)",
     "escala", []),
    (4, "Em instituições de ensino, qual aplicação da ferramenta teria maior valor?",
     "unica", ["Tutor para dúvidas de alunos sobre conteúdo e regulamentos",
               "Onboarding de novos docentes e servidores",
               "Atendimento de secretaria/FAQ acadêmico",
               "Geração de trilhas e questionários a partir de materiais",
               "Não vejo valor relevante"]),
    (5, "Qual o impacto esperado na redução da sobrecarga de colaboradores seniores e docentes, que hoje respondem a dúvidas repetitivas? (1 = nenhum, 5 = muito alto)",
     "escala", []),
    (6, "Quais são os principais riscos ou barreiras para adotar uma ferramenta como o OutGPT? (marque todos que se aplicam)",
     "multipla", ["Respostas incorretas (alucinações)",
                  "Privacidade e conformidade com a LGPD",
                  "Resistência dos usuários à mudança",
                  "Custo de implantação e manutenção",
                  "Baixa qualidade ou desorganização dos documentos internos"]),
    (7, "Que recomendações, funcionalidades ou comentários finais você tem para o OutGPT?",
     "aberta", []),
]


# tabelas da versão 1 (demonstração) que foram substituídas pelo modelo multiempresa
LEGADO = ["progresso", "historico_duvidas", "questoes", "modulos", "trilhas", "chunks", "documentos", "sops", "usuarios"]


def main():
    if "--reset" in sys.argv and db.DB.exists():
        db.DB.unlink()
    con = sqlite3.connect(db.DB)
    con.execute("PRAGMA foreign_keys = OFF")
    if con.execute("PRAGMA user_version").fetchone()[0] < VERSAO:
        existe = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()
        if existe:   # banco da v1: só havia dados de demonstração nessas tabelas; a pesquisa é preservada
            for t in LEGADO:
                con.execute(f"DROP TABLE IF EXISTS {t}")
            print("Banco da versão anterior atualizado (tabelas de demonstração substituídas; pesquisa preservada).")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))
    con.execute(f"PRAGMA user_version = {VERSAO}")

    if not con.execute("SELECT 1 FROM perguntas LIMIT 1").fetchone():
        for ordem, texto, tipo, opcoes in PERGUNTAS:
            pid = con.execute("INSERT INTO perguntas (ordem, texto, tipo, obrigatoria) VALUES (?,?,?,?)",
                              (ordem, texto, tipo, 0 if tipo == "aberta" else 1)).lastrowid
            con.executemany("INSERT INTO opcoes (pergunta_id, ordem, texto) VALUES (?,?,?)",
                            [(pid, i + 1, o) for i, o in enumerate(opcoes)])
    con.commit()
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    print(f"Banco pronto: {db.DB}\nTabelas: {', '.join(tabelas)}")
    con.close()


if __name__ == "__main__":
    main()
