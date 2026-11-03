"""Popula outgpt.db com dados fictícios gerados pelo Faker (pt_BR).

Uso:  python seed_faker.py              # adiciona dados fictícios (padrão: 40 especialistas)
      python seed_faker.py -n 100       # quantidade de especialistas
      python seed_faker.py --limpar     # remove somente os dados gerados por este script

Os registros fictícios são identificados pelo domínio de e-mail @faker.example.
Seed fixa (--seed) torna a geração reproduzível.
"""
import argparse
import json
import random
import sqlite3
from pathlib import Path

from faker import Faker

DB = Path(__file__).parent / "outgpt.db"
DOMINIO = "faker.example"

CARGOS_EMP = ["Analista de RH", "Gerente de TI", "Coordenador de Treinamento", "Analista de Suporte", "Gerente de Operações",
              "Líder de Onboarding", "Diretor de Pessoas", "Analista de Processos", "Consultor de Gestão do Conhecimento"]
CARGOS_EDU = ["Professor(a)", "Coordenador(a) de Curso", "Diretor(a) Acadêmico(a)", "Pedagogo(a)", "Secretário(a) Acadêmico(a)",
              "Pesquisador(a)", "Coordenador(a) de EaD"]
CARGOS_CON = ["Consultor(a) de Transformação Digital", "Especialista em IA", "Cientista de Dados", "Analista de Inovação"]
EMPRESAS = ["Tech", "Soluções", "Logística", "Serviços", "Consultoria", "Sistemas", "Indústria", "Digital"]
ESCOLAS = ["Faculdade", "Universidade", "Instituto Federal", "Centro Universitário", "Escola Técnica"]

COMENTARIOS = [
    "A citação da fonte é essencial para gerar confiança nas respostas.",
    "Seria interessante integrar com o Teams/Slack para consultas rápidas.",
    "Recomendo um fluxo de revisão humana para os conteúdos gerados nas trilhas.",
    "Importante garantir que os documentos estejam sempre atualizados na base.",
    "Para escolas, um modo tutor com linguagem adaptada ao aluno seria muito útil.",
    "Cuidado com dados pessoais: aplicar anonimização antes de indexar os documentos.",
    "Métricas de uso e de acertos nos questionários ajudariam a medir o retorno.",
    "A ferramenta pode reduzir bastante o tempo de integração de novos professores.",
    "Sugiro suporte a vídeos e transcrições de reuniões no futuro.",
    "Ótima proposta; o maior desafio será manter a qualidade dos manuais.",
    "Permitir feedback do usuário em cada resposta ajudaria a melhorar o sistema.",
    "Seria valioso ter versão offline para ambientes com restrição de internet.",
]

PERGUNTAS_CHAT = [
    ("Como abro um chamado de prioridade alta?", "Registre título, descrição, impacto e prioridade Alta; o SLA é de 30 minutos.", "SOP_Abertura_de_Chamados.pdf, p. 3"),
    ("Como resolvo erro de conexão na VPN?", "Verifique relógio, 2FA e teste em outra rede antes de abrir chamado.", "Manual_VPN_Corporativa.pdf, p. 12"),
    ("Qual a validade de uma senha temporária?", "Senhas temporárias expiram em 24 horas.", "Politica_Reset_de_Senhas.pdf, p. 2"),
    ("Quando devo escalonar para o nível 2?", "Após 15 minutos sem solução, registrando ações e evidências.", "FAQ_Suporte_Nivel1.txt, seção 2"),
    ("Onde baixo o cliente VPN?", "Somente pelo portal interno de software.", "Manual_VPN_Corporativa.pdf, p. 5"),
]


def limpar(con):
    ids = [r[0] for r in con.execute("SELECT id FROM especialistas WHERE email LIKE ?", (f"%@{DOMINIO}",))]
    con.executemany("DELETE FROM especialistas WHERE id=?", [(i,) for i in ids])   # respostas caem em cascata
    u = [r[0] for r in con.execute("SELECT id FROM usuarios WHERE email LIKE ?", (f"%@{DOMINIO}",))]
    con.executemany("DELETE FROM historico_duvidas WHERE usuario_id=?", [(i,) for i in u])
    con.executemany("DELETE FROM usuarios WHERE id=?", [(i,) for i in u])          # progresso cai em cascata
    d = con.execute("DELETE FROM documentos WHERE nome_arquivo LIKE 'FAKE_%'").rowcount  # chunks em cascata
    print(f"Removidos: {len(ids)} especialistas, {len(u)} usuários, {d} documentos fictícios.")


def nota_enviesada(rnd, centro):
    """Nota 1-5 concentrada em torno de 'centro' (pesquisa tende a ser favorável)."""
    return max(1, min(5, round(rnd.gauss(centro, 0.9))))


def gerar(con, n, seed):
    fake = Faker("pt_BR")
    Faker.seed(seed)
    rnd = random.Random(seed)

    # --- Especialistas e respostas da pesquisa ---
    perguntas = con.execute("SELECT id, ordem, tipo FROM perguntas ORDER BY ordem").fetchall()
    if not perguntas:
        raise SystemExit("Tabela 'perguntas' vazia. Rode antes: python init_db.py")
    opcoes = {p[0]: [r[0] for r in con.execute("SELECT id FROM opcoes WHERE pergunta_id=? ORDER BY ordem", (p[0],))] for p in perguntas}

    for _ in range(n):
        tipo = rnd.choices(["Empresa", "Instituição de ensino", "Consultoria / outro"], weights=[45, 40, 15])[0]
        if tipo == "Empresa":
            cargo, org = rnd.choice(CARGOS_EMP), f"{fake.last_name()} {rnd.choice(EMPRESAS)} {rnd.choice(['Ltda.', 'S.A.', 'EIRELI'])}"
        elif tipo == "Instituição de ensino":
            cargo, org = rnd.choice(CARGOS_EDU), f"{rnd.choice(ESCOLAS)} {fake.city()}"
        else:
            cargo, org = rnd.choice(CARGOS_CON), f"{fake.last_name()} & Associados"
        nome = fake.name()
        email = f"{fake.user_name()}@{DOMINIO}"
        criado = fake.date_time_between(start_date="-30d", end_date="now").strftime("%Y-%m-%d %H:%M:%S")
        eid = con.execute(
            "INSERT INTO especialistas (nome,email,cargo,organizacao,tipo_organizacao,anos_experiencia,consentimento,criado_em) "
            "VALUES (?,?,?,?,?,?,1,?)", (nome, email, cargo, org, tipo, rnd.randint(1, 30), criado)).lastrowid

        linhas = []
        for pid, ordem, ptipo in perguntas:
            if ptipo == "escala":
                centro = {1: 4.3, 3: 3.8, 5: 4.0}.get(ordem, 3.8)
                linhas.append((eid, pid, None, nota_enviesada(rnd, centro), None, criado))
            elif ptipo == "unica":
                pesos = [30, 25, 20, 22, 3][:len(opcoes[pid])]
                linhas.append((eid, pid, rnd.choices(opcoes[pid], weights=pesos)[0], None, None, criado))
            elif ptipo == "multipla":
                escolhidas = rnd.sample(opcoes[pid], rnd.randint(1, min(3, len(opcoes[pid]))))
                linhas += [(eid, pid, o, None, None, criado) for o in escolhidas]
            elif rnd.random() < 0.6:  # aberta (opcional)
                linhas.append((eid, pid, None, None, rnd.choice(COMENTARIOS), criado))
        con.executemany("INSERT INTO respostas (especialista_id,pergunta_id,opcao_id,valor_escala,texto_livre,criado_em) VALUES (?,?,?,?,?,?)", linhas)

    # --- Usuários, documentos, chunks, progresso e histórico ---
    uids = []
    for i in range(max(5, n // 4)):
        uids.append(con.execute("INSERT INTO usuarios (nome,email,perfil) VALUES (?,?,?)",
                                (fake.name(), f"{fake.user_name()}{i}@{DOMINIO}", rnd.choices(["colaborador", "gestor"], weights=[8, 2])[0])).lastrowid)
    trilhas = [r[0] for r in con.execute("SELECT id FROM trilhas")]
    for u in uids:
        for t in rnd.sample(trilhas, rnd.randint(0, len(trilhas))):
            con.execute("INSERT OR IGNORE INTO progresso (usuario_id,trilha_id,percentual) VALUES (?,?,?)", (u, t, rnd.choice([0, 20, 40, 60, 80, 100])))

    for k in range(8):
        ext = rnd.choice(["PDF", "TXT"])
        did = con.execute("INSERT INTO documentos (nome_arquivo,tipo,status,enviado_por) VALUES (?,?,?,?)",
                          (f"FAKE_{fake.word().capitalize()}_{k + 1}.{ext.lower()}", ext, rnd.choices(["Indexado", "Processando", "Erro"], weights=[8, 1, 1])[0], rnd.choice(uids))).lastrowid
        con.executemany("INSERT INTO chunks (documento_id,ordem,pagina,texto) VALUES (?,?,?,?)",
                        [(did, c + 1, c // 3 + 1, fake.paragraph(nb_sentences=4)) for c in range(rnd.randint(5, 15))])

    for _ in range(max(10, n // 2)):
        p, r, f = rnd.choice(PERGUNTAS_CHAT)
        con.execute("INSERT INTO historico_duvidas (usuario_id,pergunta,resposta,fontes,criado_em) VALUES (?,?,?,?,?)",
                    (rnd.choice(uids), p, r, f, fake.date_time_between(start_date="-30d", end_date="now").strftime("%Y-%m-%d %H:%M:%S")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=40, help="quantidade de especialistas (padrão 40)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limpar", action="store_true", help="remove os dados fictícios")
    a = ap.parse_args()
    if not DB.exists():
        raise SystemExit("Banco não encontrado. Rode antes: python init_db.py")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    with con:
        limpar(con)           # sempre limpa antes, evitando duplicar execuções anteriores
        if not a.limpar:
            gerar(con, a.n, a.seed)
    if not a.limpar:
        for t in ("especialistas", "respostas", "usuarios", "documentos", "chunks", "progresso", "historico_duvidas"):
            print(f"{t:18} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
