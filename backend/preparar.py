"""Configuração inicial guiada. Roda a cada INICIAR.bat e só pergunta o que ainda falta:
  1. seu login de dono do sistema (master);
  2. a chave da IA (opcional: dá para ligar depois, em Administração > Inteligência artificial);
  3. sua empresa e, se quiser, os procedimentos do dataset do projeto, já indexados e organizados em cursos.
As senhas e a chave são digitadas sem aparecer na tela e nunca ficam em arquivo (a chave vai só para backend/.env).
"""
import getpass
import os
import re
import sys

import auth
import db
import llm
import rag


def ler(msg, secreto=False, padrao=""):
    try:
        v = getpass.getpass(msg) if secreto and sys.stdin.isatty() else input(msg)
    except EOFError:                       # sem teclado (execução automática): usa o padrão
        v = ""
    v = v.lstrip("\ufeff")
    return v if secreto else (v.strip() or padrao)


def garantir_master(con):
    if con.execute("SELECT 1 FROM usuarios WHERE tipo='master'").fetchone():
        return
    print("\n=== 1. Seu login (dono do sistema) ===")
    nome = ""
    while not nome:
        nome = ler("Seu nome: ")
    email = ""
    while not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        email = ler("E-mail (será o seu login): ").lower()
    for _ in range(5):
        senha = ler(f"Senha (mínimo {auth.SENHA_MIN} caracteres, com letras e números): ", secreto=True)
        erro = auth.validar_senha_nova(senha)
        if erro:
            print("  " + erro)
        elif ler("Repita a senha: ", secreto=True) != senha:
            print("  As senhas não conferem.")
        else:
            con.execute("INSERT INTO usuarios (empresa_id, nome, email, senha_hash, tipo) VALUES (NULL,?,?,?, 'master')", (nome, email, auth.hash_senha(senha)))
            con.commit()
            print(f"  Login criado: {email}")
            return
    raise SystemExit("Não foi possível criar o login. Rode o INICIAR.bat de novo.")


def garantir_ia():
    if llm.disponivel() or os.environ.get("OUTGPT_IA_PULADA") == "1":
        return
    print("\n=== 2. Inteligência artificial ===")
    print("Com a chave da API, o assistente escreve respostas claras e completas. Sem ela, mostra só o trecho do manual.")
    print("Crie a chave em https://console.anthropic.com (menu API Keys), copie e cole aqui.")
    print("Aperte Enter para pular (você pode ligar depois em Administração > Inteligência artificial).")
    for _ in range(3):
        chave = ler("Chave da API (sk-ant-...): ", secreto=True).strip()
        if not chave:
            print("  Pulado: o assistente vai mostrar só o trecho do manual por enquanto (não vou perguntar de novo).")
            with open(db.ENV_ARQ, "a", encoding="utf-8") as f:       # lembra a escolha para não perguntar a cada início
                f.write("OUTGPT_IA_PULADA=1\n")
            return
        ok, msg = llm.salvar_chave(chave)
        print(("  IA ligada! " if ok else "  Não deu certo: ") + msg)
        if ok:
            return


def garantir_empresa(con):
    if con.execute("SELECT 1 FROM empresas").fetchone():
        return
    print("\n=== 3. Sua empresa ===")
    nome = ler("Nome da empresa [Minha Empresa]: ", padrao="Minha Empresa")
    con.execute("INSERT INTO empresas (nome) VALUES (?)", (nome,))
    con.commit()
    eid = con.execute("SELECT id FROM empresas WHERE nome=?", (nome,)).fetchone()["id"]
    if rag.CSV_PADRAO.exists() and ler("Carregar os 100 procedimentos do dataset do projeto (RH, TI, segurança, operações...)? [S/n]: ", padrao="s").lower().startswith("s"):
        print("  Indexando os procedimentos (na primeira vez baixa o modelo de busca, ~250 MB; pode levar alguns minutos)...")
        n = rag.importar_csv(con, eid, rag.CSV_PADRAO.read_text(encoding="utf-8-sig"), "internos")
        print(f"  {n} procedimentos carregados e organizados em cursos.")


def main():
    con = db.conectar()
    antes = (con.execute("SELECT COUNT(*) FROM usuarios WHERE tipo='master'").fetchone()[0], llm.disponivel(), con.execute("SELECT COUNT(*) FROM empresas").fetchone()[0])
    garantir_master(con)
    garantir_ia()
    garantir_empresa(con)
    depois = (con.execute("SELECT COUNT(*) FROM usuarios WHERE tipo='master'").fetchone()[0], llm.disponivel(), con.execute("SELECT COUNT(*) FROM empresas").fetchone()[0])
    print("\nTudo pronto." if antes == depois else "\nConfiguração concluída.")
    if not llm.disponivel():
        print("(A IA está desligada: ligue em Administração > Inteligência artificial quando tiver a chave.)")


if __name__ == "__main__":
    main()