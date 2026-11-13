#!/usr/bin/env bash
# Roda uma vez, quando o Codespace é criado: instala as bibliotecas, prepara o banco e carrega a empresa com os procedimentos.
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ/backend"

echo ">> Instalando as bibliotecas..."
pip install --no-cache-dir -r requirements.txt

echo ">> Preparando o banco de dados..."
python init_db.py

echo ">> Baixando o modelo de busca (~250 MB)..."
python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

echo ">> Criando a empresa e carregando os procedimentos..."
python - <<'PY'
import db, rag
with db.conectar() as con:
    if not con.execute("SELECT 1 FROM empresas").fetchone():
        con.execute("INSERT INTO empresas (nome) VALUES ('Minha Empresa')")
        con.commit()
        eid = con.execute("SELECT id FROM empresas").fetchone()["id"]
        n = rag.importar_csv(con, eid, rag.CSV_PADRAO.read_text(encoding="utf-8-sig"), "internos")
        print(f"{n} procedimentos carregados e organizados em cursos.")
PY

# mostra as instruções de acesso sempre que um terminal é aberto
LINHA="bash \"$RAIZ/.devcontainer/mostrar-acesso.sh\""
grep -qF "mostrar-acesso.sh" ~/.bashrc 2>/dev/null || echo "$LINHA" >> ~/.bashrc
echo ">> Pronto."