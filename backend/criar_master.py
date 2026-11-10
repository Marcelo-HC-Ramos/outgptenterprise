"""Cria o usuário MASTER (dono do sistema). A senha é digitada no terminal e nunca fica em arquivo.

Uso:  python criar_master.py
"""
import getpass
import re
import sqlite3
import sys

import auth
import db


def main():
    if not db.DB.exists():
        raise SystemExit("Banco não encontrado. Rode antes: python init_db.py")
    con = db.conectar()
    existentes = con.execute("SELECT nome, email FROM usuarios WHERE tipo='master'").fetchall()
    if existentes:
        print("Já existe master:", ", ".join(f"{r['nome']} <{r['email']}>" for r in existentes))
        if input("Criar mais um? (s/N) ").strip().lower() != "s":
            return
    nome = input("Nome do master: ").strip()
    email = input("E-mail (será o login): ").strip().lower()
    if not nome or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Nome ou e-mail inválido.")
    senha = getpass.getpass(f"Senha (mín. {auth.SENHA_MIN} caracteres, com letras e números): ")
    erro = auth.validar_senha_nova(senha)
    if erro:
        raise SystemExit(erro)
    if getpass.getpass("Repita a senha: ") != senha:
        raise SystemExit("As senhas não conferem.")
    try:
        con.execute("INSERT INTO usuarios (empresa_id, nome, email, senha_hash, tipo) VALUES (NULL,?,?,?, 'master')",
                    (nome, email, auth.hash_senha(senha)))
        con.commit()
    except sqlite3.IntegrityError:
        raise SystemExit("Já existe um usuário com esse e-mail.")
    print(f"Master criado: {email}. Agora rode: python server.py")


if __name__ == "__main__":
    sys.exit(main())
