"""Dados de demonstração para a apresentação (opcional): departamentos, colaboradores e um histórico de estudo simulado.

Por que existe: o relatório de Engajamento e as trilhas por departamento só mostram algo com várias pessoas estudando, e numa
apresentação de poucos minutos não dá para gerar esse histórico de verdade. Este script cria os dados em segundos e remove tudo depois.

Uso:
    python demo_apresentacao.py criar [--empresa "Minha Empresa"]
    python demo_apresentacao.py remover [--empresa "Minha Empresa"]

O que cria (na empresa escolhida; por padrão a primeira):
  - departamentos RH, TI e Operações (se ainda não existirem);
  - 9 colaboradores @demo.outgpt (3 por departamento) SEM senha utilizável (ninguém consegue entrar com eles) e com estudo simulado
    nas 5 primeiras lições de um curso: uma lição tranquila, uma difícil, uma de atenção, uma com poucos dados e uma sem estudo;
  - 1 "Colaborador Demo" com login real (a senha aparece uma única vez) para mostrar a visão do colaborador ao vivo.
Tudo que é criado aqui tem e-mail @demo.outgpt; o comando `remover` apaga esses usuários (e o progresso deles) e os departamentos
criados por este script que ficarem vazios. NÃO deixe os dados de demonstração no ar depois da apresentação.
"""
import argparse
import re
import secrets
import sys
from datetime import datetime, timedelta

import auth
import db

DOMINIO = "demo.outgpt"
MARCA = "[demo]"                       # descrição dos departamentos criados por este script
DEPARTAMENTOS = ("RH", "TI", "Operações")
NOMES = ["Ana Souza", "Bruno Lima", "Carla Dias", "Diego Alves", "Elisa Rocha", "Fábio Nunes", "Gabriela Melo", "Henrique Costa", "Isabela Prado"]
LOGIN_DEMO = f"colaborador@{DOMINIO}"


def _empresa(con, nome):
    r = con.execute("SELECT id, nome FROM empresas WHERE nome=?", (nome,)).fetchone() if nome else con.execute("SELECT id, nome FROM empresas ORDER BY id LIMIT 1").fetchone()
    if not r:
        sys.exit("Empresa não encontrada. Crie a empresa primeiro (ou informe o nome com --empresa).")
    return r["id"], r["nome"]


def _senha_demo():
    senha = f"Demo-{secrets.token_hex(6)}-Out7"
    assert auth.validar_senha_nova(senha) is None
    return senha


def criar(nome_empresa=None):
    agora = datetime.now()
    marca_t = lambda dias: (agora - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    with db.conectar() as con:
        eid, enome = _empresa(con, nome_empresa)
        dep = {}
        for nome in DEPARTAMENTOS:
            r = con.execute("SELECT id FROM departamentos WHERE empresa_id=? AND nome=?", (eid, nome)).fetchone()
            dep[nome] = r["id"] if r else con.execute("INSERT INTO departamentos (empresa_id,nome,descricao) VALUES (?,?,?)", (eid, nome, MARCA)).lastrowid
        usuarios = []
        for i, nome in enumerate(NOMES):
            email = f"{re.sub(r'[^a-z]', '', nome.split()[0].lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('â', 'a'))}.{i + 1}@{DOMINIO}"
            r = con.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()
            usuarios.append(r["id"] if r else con.execute(
                "INSERT INTO usuarios (empresa_id,nome,email,senha_hash,tipo,departamento_id) VALUES (?,?,?,?,?,?)",
                (eid, nome, email, auth.hash_senha(secrets.token_urlsafe(24)), "funcionario", dep[DEPARTAMENTOS[i % 3]])).lastrowid)
        senha = None
        if not con.execute("SELECT 1 FROM usuarios WHERE email=?", (LOGIN_DEMO,)).fetchone():
            senha = _senha_demo()
            con.execute("INSERT INTO usuarios (empresa_id,nome,email,senha_hash,tipo,departamento_id) VALUES (?,?,?,?,?,?)",
                        (eid, "Colaborador Demo", LOGIN_DEMO, auth.hash_senha(senha), "funcionario", dep["TI"]))
        curso = con.execute("SELECT c.id, c.titulo FROM cursos c WHERE c.empresa_id=? AND (SELECT COUNT(*) FROM curso_itens i WHERE i.curso_id=c.id) >= 5 "
                            "ORDER BY c.ordem, c.id LIMIT 1", (eid,)).fetchone()
        if not curso:
            con.commit()
            sys.exit("Nenhum curso com pelo menos 5 lições nesta empresa: carregue os conteúdos antes (Biblioteca > Importar CSV).")
        licoes = [r[0] for r in con.execute("SELECT conteudo_id FROM curso_itens WHERE curso_id=? ORDER BY ordem LIMIT 5", (curso["id"],))]

        def prog(i, k, acertou, tentativas):
            con.execute("INSERT OR REPLACE INTO progresso_licoes (usuario_id,curso_id,conteudo_id,concluida_em,acertou,tentativas) VALUES (?,?,?,?,?,?)",
                        (usuarios[i], curso["id"], licoes[k], marca_t(i % 5), acertou, tentativas))

        def tempo(i, k, segundos):
            con.execute("INSERT OR REPLACE INTO licao_tempo (usuario_id,curso_id,conteudo_id,segundos,primeira_em,ultima_em) VALUES (?,?,?,?,?,?)",
                        (usuarios[i], curso["id"], licoes[k], segundos, marca_t(i % 5), marca_t(i % 5)))

        for i, s in enumerate((45, 60, 55, 70, 50, 65, 58, 62, 52)):                       # lição 1: tranquila (todos acertam, tempo esperado)
            prog(i, 0, 1, 1); tempo(i, 0, s)
        for i, s in enumerate((320, 280, 350, 300, 260, 310, 290, 330)):                    # lição 2: difícil (erros, tempo ~5x, abandono)
            tempo(i, 1, s)
            if i < 6:
                prog(i, 1, (0, 0, 0, 0, 1, 0)[i], (3, 2, 2, 3, 1, 2)[i])
        for i, s in enumerate((150, 120, 170, 140, 160, 130, 145)):                         # lição 3: atenção (tempo ~2,4x)
            prog(i, 2, (1, 1, 0, 1, 0, 1, 1)[i], 1); tempo(i, 2, s)
        tempo(0, 3, 90); tempo(1, 3, 80)                                                    # lição 4: poucos dados (amostra pequena)
        con.commit()
    print(f"Dados de demonstração criados na empresa '{enome}' (curso '{curso['titulo']}').")
    print(f"  Departamentos: {', '.join(DEPARTAMENTOS)} | colaboradores simulados: {len(NOMES)} (sem senha utilizável)")
    if senha:
        print(f"Login do colaborador de demonstração: {LOGIN_DEMO} / {senha}   (anote: a senha só aparece agora)")
    else:
        print(f"O colaborador de demonstração ({LOGIN_DEMO}) já existia; para gerar outra senha rode 'remover' e 'criar'.")
    print("Depois da apresentação rode:  python demo_apresentacao.py remover")


def remover(nome_empresa=None):
    with db.conectar() as con:
        eid, enome = _empresa(con, nome_empresa)
        n = con.execute("DELETE FROM usuarios WHERE empresa_id=? AND email LIKE ?", (eid, f"%@{DOMINIO}")).rowcount
        d = 0
        for r in con.execute("SELECT id FROM departamentos WHERE empresa_id=? AND descricao=?", (eid, MARCA)).fetchall():
            usa = con.execute("SELECT (SELECT COUNT(*) FROM usuarios WHERE departamento_id=?) + (SELECT COUNT(*) FROM conteudo_departamentos WHERE departamento_id=?)", (r["id"], r["id"])).fetchone()[0]
            if not usa:
                con.execute("DELETE FROM departamentos WHERE id=?", (r["id"],)); d += 1
        con.commit()
    print(f"Empresa '{enome}': {n} usuário(s) de demonstração e {d} departamento(s) removidos.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Dados de demonstração para a apresentação.")
    ap.add_argument("acao", choices=("criar", "remover"))
    ap.add_argument("--empresa", help="nome da empresa (padrão: a primeira)")
    a = ap.parse_args()
    (criar if a.acao == "criar" else remover)(a.empresa)
