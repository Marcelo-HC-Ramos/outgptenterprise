"""Liga a IA do assistente: pede a chave da API, testa com uma chamada real e a guarda em backend/.env.

Uso:  python configurar_llm.py
(Também dá para fazer isso pelo site: menu Administração > Inteligência artificial, logado como master.)
A chave é digitada sem aparecer na tela e nunca é impressa nem versionada no Git.
"""
import getpass
import sys

import llm


def main():
    print(f"Modelo configurado: {llm.MODELO}  (mude com OUTGPT_MODELO no .env)")
    print("Crie a chave em https://console.anthropic.com (menu API Keys).")
    chave = getpass.getpass("Cole a chave (sk-ant-...): ")
    ok, msg = llm.salvar_chave(chave)
    print(("OK: " if ok else "ERRO: ") + msg)
    if ok:
        print("Chave salva em backend/.env. Reinicie o servidor se ele já estiver rodando.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())