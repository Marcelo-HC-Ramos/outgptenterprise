"""Cria (ou recria) o banco outgpt.db com o esquema e os dados iniciais.

Uso:  python init_db.py          # cria se não existir
      python init_db.py --reset  # apaga e recria
"""
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "outgpt.db"

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

DOCS = [
    ("SOP_Abertura_de_Chamados.pdf", "PDF", "Indexado"),
    ("FAQ_Suporte_Nivel1.txt", "TXT", "Indexado"),
    ("Manual_VPN_Corporativa.pdf", "PDF", "Indexado"),
    ("Politica_Reset_de_Senhas.pdf", "PDF", "Indexado"),
    ("Tutorial_Escalonamento_N2.txt", "TXT", "Processando"),
]


def main():
    if "--reset" in sys.argv and DB.exists():
        DB.unlink()
    novo = not DB.exists()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))

    if novo or not con.execute("SELECT 1 FROM perguntas LIMIT 1").fetchone():
        for ordem, texto, tipo, opcoes in PERGUNTAS:
            pid = con.execute("INSERT INTO perguntas (ordem, texto, tipo, obrigatoria) VALUES (?,?,?,?)",
                              (ordem, texto, tipo, 0 if tipo == "aberta" else 1)).lastrowid
            con.executemany("INSERT INTO opcoes (pergunta_id, ordem, texto) VALUES (?,?,?)",
                            [(pid, i + 1, o) for i, o in enumerate(opcoes)])

    if not con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
        con.executemany("INSERT INTO usuarios (nome, email, perfil) VALUES (?,?,?)", [
            ("Novo Colaborador", "novo.colaborador@empresa.com", "colaborador"),
            ("Gestor Demo", "gestor@empresa.com", "gestor"),
        ])
        con.executemany("INSERT INTO documentos (nome_arquivo, tipo, status, enviado_por) VALUES (?,?,?,2)", DOCS)
        con.execute("INSERT INTO trilhas (titulo, nivel) VALUES ('Fundamentos do Suporte Técnico','Iniciante')")
        con.execute("INSERT INTO modulos (trilha_id, ordem, titulo, conteudo, documento_id, fonte) VALUES "
                    "(1,1,'Como abrir e classificar um chamado',"
                    "'Todo chamado deve ter título objetivo, descrição, impacto e prioridade. Prioridade Alta tem SLA de 30 minutos.',"
                    "1,'SOP_Abertura_de_Chamados.pdf, p. 3')")
        con.execute("INSERT INTO questoes (trilha_id, enunciado, alternativas, indice_correto, explicacao) VALUES (1,?,?,1,?)",
                    ("Qual o SLA de primeira resposta para prioridade Alta?",
                     json.dumps(["10 minutos", "30 minutos", "2 horas", "1 dia"], ensure_ascii=False),
                     "Conforme o SOP de abertura de chamados."))
        con.execute("INSERT INTO progresso (usuario_id, trilha_id, percentual) VALUES (1,1,60)")

    con.commit()
    tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    print(f"Banco pronto: {DB}\nTabelas: {', '.join(tabelas)}")
    con.close()


if __name__ == "__main__":
    main()
