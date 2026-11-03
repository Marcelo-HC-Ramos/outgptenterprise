"""Dataset de SOPs: carga no SQLite + indexação no ChromaDB + busca semântica (RAG) + anonimização de PII.

Uso:  python rag.py                       # lê data/sops_corporativos.csv
      python rag.py caminho/do/arquivo.csv
Colunas esperadas: id, categoria, procedimento_titulo, contexto_documental,
                   pergunta_utilizador, resposta_esperada, contem_pii
"""
import csv
import os
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "outgpt.db"
CSV_PADRAO = BASE / "data" / "sops_corporativos.csv"
CHROMA_DIR = BASE / "data" / "chroma_db"
COLECAO = "sops_corporativos"
COLUNAS = ["id", "categoria", "procedimento_titulo", "contexto_documental",
           "pergunta_utilizador", "resposta_esperada", "contem_pii"]

_colecao = None
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"   # multilíngue (o padrão do Chroma é só inglês)
_modelo = None


def _embedder():
    import chromadb
    from fastembed import TextEmbedding

    class FastEmbedMultilingue(chromadb.EmbeddingFunction):
        def __init__(self):
            pass

        def __call__(self, input):
            global _modelo
            if _modelo is None:
                _modelo = TextEmbedding(MODELO)
            return [list(map(float, v)) for v in _modelo.embed(list(input))]

        @staticmethod
        def name():
            return "fastembed_multilingue"

        def get_config(self):
            return {}

        @staticmethod
        def build_from_config(config):
            return FastEmbedMultilingue()

    return FastEmbedMultilingue()


def _bool(v):
    return 1 if str(v).strip().lower() in ("1", "true", "sim", "s", "yes", "y", "verdadeiro") else 0


def ler_csv(caminho):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
        if faltando:
            raise SystemExit(f"CSV sem as colunas: {', '.join(faltando)}. Encontradas: {leitor.fieldnames}")
        linhas = []
        for r in leitor:
            linhas.append(tuple((r[c] or "").strip() for c in COLUNAS))
    ids = [l[0] for l in linhas]
    if len(set(ids)) != len(ids):
        raise SystemExit("CSV com ids duplicados.")
    return linhas


def carregar_sqlite(linhas):
    con = sqlite3.connect(DB)
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))
    with con:
        con.execute("DELETE FROM sops")
        con.executemany(
            "INSERT INTO sops (id,categoria,procedimento_titulo,contexto_documental,pergunta_utilizador,resposta_esperada,contem_pii) "
            "VALUES (?,?,?,?,?,?,?)",
            [(*l[:6], _bool(l[6])) for l in linhas])
    con.close()


def colecao():
    global _colecao
    if _colecao is None:
        import chromadb
        _colecao = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
            COLECAO, embedding_function=_embedder(), metadata={"hnsw:space": "cosine"})
    return _colecao


def indexar(linhas):
    """Recria a coleção no ChromaDB (vetores de conteúdo e de pergunta-exemplo de cada SOP)."""
    global _colecao
    import chromadb
    cli = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        cli.delete_collection(COLECAO)
    except Exception:
        pass
    _colecao = cli.create_collection(COLECAO, embedding_function=_embedder(), metadata={"hnsw:space": "cosine"})
    # Dois vetores por SOP (o modelo trunca textos longos): a pergunta de exemplo e o conteúdo do procedimento.
    ids, docs, metas = [], [], []
    for l in linhas:
        meta = {"sop_id": l[0], "categoria": l[1], "titulo": l[2]}
        ids += [f"{l[0]}#conteudo", f"{l[0]}#pergunta"]
        docs += [f"{l[2]}. {l[3]}", l[4] or l[2]]
        metas += [{**meta, "parte": "conteudo"}, {**meta, "parte": "pergunta"}]
    for i in range(0, len(ids), 100):
        _colecao.add(ids=ids[i:i + 100], documents=docs[i:i + 100], metadatas=metas[i:i + 100])


# ---------- Anonimização (LGPD) ----------
PADROES = [
    ("E-mail", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    ("CNPJ", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ]"),
    ("Telefone", re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[TELEFONE]"),
]


def anonimizar(texto):
    """Devolve (texto mascarado, lista de tipos de PII encontrados). Não devolve os valores originais."""
    tipos = []
    for nome, rx, mascara in PADROES:
        if rx.search(texto):
            tipos.append(nome)
            texto = rx.sub(mascara, texto)
    return texto, tipos


# ---------- Consulta ----------
def buscar(pergunta, k=3):
    col = colecao()
    if col.count() == 0:
        return []
    r = col.query(query_texts=[pergunta], n_results=min(k * 2 + 2, col.count()))
    melhor = {}   # sop_id -> menor distância entre seus vetores
    for meta, dist in zip(r["metadatas"][0], r["distances"][0]):
        melhor[meta["sop_id"]] = min(dist, melhor.get(meta["sop_id"], 9))
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    out = []
    for sop_id, dist in sorted(melhor.items(), key=lambda x: x[1])[:k]:
        row = con.execute("SELECT * FROM sops WHERE id=?", (sop_id,)).fetchone()
        if row:
            out.append({**dict(row), "similaridade": round(1 - dist, 3)})
    con.close()
    return out


def main():
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_PADRAO
    if not caminho.exists():
        raise SystemExit(f"Arquivo não encontrado: {caminho}\nColoque o CSV em backend/data/sops_corporativos.csv ou passe o caminho.")
    linhas = ler_csv(caminho)
    carregar_sqlite(linhas)
    indexar(linhas)
    print(f"{len(linhas)} SOPs carregadas no SQLite e indexadas no ChromaDB ({CHROMA_DIR}).")


if __name__ == "__main__":
    main()

