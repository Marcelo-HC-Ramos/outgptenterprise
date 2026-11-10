"""Popula a PESQUISA em outgpt.db com respostas fictícias geradas pelo Faker (pt_BR).

Uso:  python seed_faker.py              # adiciona dados fictícios (padrão: 40 especialistas)
      python seed_faker.py -n 100       # quantidade de especialistas
      python seed_faker.py --limpar     # remove somente os dados gerados por este script

Os registros fictícios são identificados pelo domínio de e-mail @faker.example.
Seed fixa (--seed) torna a geração reproduzível.
"""
import argparse
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


def limpar(con):
    ids = [r[0] for r in con.execute("SELECT id FROM especialistas WHERE email LIKE ?", (f"%@{DOMINIO}",))]
    con.executemany("DELETE FROM especialistas WHERE id=?", [(i,) for i in ids])   # respostas caem em cascata
    print(f"Removidos: {len(ids)} especialistas fictícios.")

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
        for t in ("especialistas", "respostas"):
            print(f"{t:18} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()