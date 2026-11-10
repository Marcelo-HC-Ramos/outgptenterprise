"""Conexão com o SQLite e leitura do arquivo .env (sem dependências externas)."""
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
ENV_ARQ = Path(os.environ.get("OUTGPT_ENV_ARQ") or BASE / ".env")


def carregar_env():
    """Lê backend/.env (CHAVE=valor) sem sobrescrever variáveis que já existem no ambiente."""
    if not ENV_ARQ.exists():
        return
    for linha in ENV_ARQ.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


carregar_env()
DB = Path(os.environ.get("OUTGPT_DB") or BASE / "outgpt.db")


def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
