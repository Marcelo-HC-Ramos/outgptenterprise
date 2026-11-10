"""Backup do banco de dados (cópia consistente, pode ser feita com o servidor rodando).

Uso:  python backup.py [pasta_destino] [--manter N]
Padrão: pasta backend/backups, mantendo os 14 backups mais recentes.

O que é copiado: o SQLite (usuários, conteúdos, cursos, histórico, pesquisa). O índice de busca (ChromaDB) não precisa de
backup: é refeito sozinho a partir do banco. A chave da API (.env) NÃO entra no backup: guarde-a à parte.

Restaurar: pare o servidor, substitua outgpt.db pelo arquivo do backup e inicie o servidor de novo.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import db


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    manter = 14
    if "--manter" in sys.argv:
        manter = int(sys.argv[sys.argv.index("--manter") + 1])
        args = [a for a in args if a != str(manter)]
    destino = Path(args[0]) if args else db.BASE / "backups"
    destino.mkdir(parents=True, exist_ok=True)
    if not db.DB.exists():
        raise SystemExit(f"Banco não encontrado: {db.DB}")
    arq = destino / f"outgpt-{datetime.now():%Y%m%d-%H%M%S}.db"
    origem, copia = sqlite3.connect(db.DB), sqlite3.connect(arq)
    with copia:
        origem.backup(copia)          # API de backup do SQLite: consistente mesmo durante gravações
    origem.close(); copia.close()
    antigos = sorted(destino.glob("outgpt-*.db"))[:-manter] if manter > 0 else []
    for velho in antigos:
        velho.unlink()
    print(f"Backup criado: {arq} ({arq.stat().st_size / 1024:.0f} KB). Mantidos {min(manter, len(list(destino.glob('outgpt-*.db'))))} backup(s).")


if __name__ == "__main__":
    main()
