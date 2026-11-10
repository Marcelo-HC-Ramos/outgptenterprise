"""RAG multiempresa: conteúdos no SQLite + vetores no ChromaDB + anonimização de PII.

Cada conteúdo gera dois vetores (o texto do procedimento e a pergunta de exemplo). Todo vetor leva
`empresa_id` e `visibilidade` nos metadados, e a busca SEMPRE filtra por empresa e visibilidade.

Uso (linha de comando):
  python rag.py reindexar                                   # recria todo o índice a partir do SQLite
  python rag.py importar "Empresa Demo" data/sops_corporativos.csv [todos|internos]
CSV: id, categoria, procedimento_titulo, contexto_documental, pergunta_utilizador, resposta_esperada, contem_pii
"""
import csv
import os
import re
import sys
from pathlib import Path

import db

BASE = Path(__file__).parent
CSV_PADRAO = BASE / "data" / "sops_corporativos.csv"
CHROMA_DIR = Path(os.environ.get("OUTGPT_CHROMA") or BASE / "data" / "chroma_db")
COLECAO = "conteudos"
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"   # multilíngue (o padrão do Chroma é só inglês)
COLUNAS_CSV = ["id", "categoria", "procedimento_titulo", "contexto_documental", "pergunta_utilizador", "resposta_esperada", "contem_pii"]

_colecao = None
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


def colecao():
    global _colecao
    if _colecao is None:
        import chromadb
        _colecao = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
            COLECAO, embedding_function=_embedder(), metadata={"hnsw:space": "cosine"})
    return _colecao


# ---------- Índice ----------
def _vetores(c):
    """Linhas (ids, documentos, metadados) de um conteúdo (sqlite3.Row ou dict)."""
    meta = {"conteudo_id": int(c["id"]), "empresa_id": int(c["empresa_id"]), "visibilidade": c["visibilidade"]}
    return ([f"c{c['id']}#conteudo", f"c{c['id']}#pergunta"],
            [f"{c['titulo']}. {c['texto']}", c["pergunta_exemplo"] or c["titulo"]],
            [{**meta, "parte": "conteudo"}, {**meta, "parte": "pergunta"}])


def indexar_conteudo(c):
    ids, docs, metas = _vetores(c)
    colecao().upsert(ids=ids, documents=docs, metadatas=metas)


def remover_conteudo(conteudo_id):
    colecao().delete(ids=[f"c{conteudo_id}#conteudo", f"c{conteudo_id}#pergunta"])


def reindexar_tudo():
    global _colecao
    import chromadb
    cli = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        cli.delete_collection(COLECAO)
    except Exception:
        pass
    _colecao = None
    col = colecao()
    ids, docs, metas = [], [], []
    with db.conectar() as con:
        for c in con.execute("SELECT * FROM conteudos"):
            i, d, m = _vetores(c)
            ids += i; docs += d; metas += m
    for k in range(0, len(ids), 100):
        col.add(ids=ids[k:k + 100], documents=docs[k:k + 100], metadatas=metas[k:k + 100])
    return len(ids) // 2


# ---------- Importação de CSV ----------
def _bool(v):
    return 1 if str(v).strip().lower() in ("1", "true", "sim", "s", "yes", "y", "verdadeiro") else 0


def linhas_do_csv(texto):
    """Interpreta o texto de um CSV. Levanta ValueError com mensagem amigável se estiver fora do formato."""
    leitor = csv.DictReader(texto.lstrip("﻿").splitlines())
    faltando = [c for c in COLUNAS_CSV if c not in (leitor.fieldnames or [])]
    if faltando:
        raise ValueError("CSV sem as colunas: " + ", ".join(faltando))
    linhas = [{k: (r.get(k) or "").strip() for k in COLUNAS_CSV} for r in leitor]
    codigos = [l["id"] for l in linhas]
    if not linhas:
        raise ValueError("CSV vazio.")
    if any(not l["id"] or not l["procedimento_titulo"] or not l["contexto_documental"] for l in linhas):
        raise ValueError("Há linhas sem id, título ou conteúdo.")
    if len(set(codigos)) != len(codigos):
        raise ValueError("CSV com ids duplicados.")
    return linhas


def importar_csv(con, empresa_id, texto, visibilidade="internos", criado_por=None):
    """Insere/atualiza os conteúdos de uma empresa a partir do CSV e reindexa. Devolve a quantidade."""
    if visibilidade not in ("todos", "internos"):
        raise ValueError("Visibilidade inválida.")
    linhas = linhas_do_csv(texto)
    for l in linhas:
        con.execute(
            "INSERT INTO conteudos (empresa_id,codigo,titulo,categoria,texto,pergunta_exemplo,contem_pii,visibilidade,criado_por) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(empresa_id,codigo) DO UPDATE SET titulo=excluded.titulo, "
            "categoria=excluded.categoria, texto=excluded.texto, pergunta_exemplo=excluded.pergunta_exemplo, "
            "contem_pii=excluded.contem_pii, atualizado_em=datetime('now','localtime')",
            (empresa_id, l["id"], l["procedimento_titulo"], l["categoria"] or "Geral", l["contexto_documental"],
             l["pergunta_utilizador"], _bool(l["contem_pii"]), visibilidade, criado_por))
    con.commit()
    for c in con.execute("SELECT * FROM conteudos WHERE empresa_id=? AND codigo IN (%s)" % ",".join("?" * len(linhas)),
                         [empresa_id] + [l["id"] for l in linhas]):
        indexar_conteudo(c)
    return len(linhas)


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
def buscar(pergunta, empresa_id, visibilidades, k=3):
    """Top-k conteúdos da empresa (e visibilidades permitidas) mais parecidos com a pergunta."""
    col = colecao()
    if col.count() == 0:
        return []
    filtro = {"$and": [{"empresa_id": {"$eq": int(empresa_id)}}, {"visibilidade": {"$in": list(visibilidades)}}]}
    r = col.query(query_texts=[pergunta], n_results=k * 2 + 2, where=filtro)
    melhor = {}   # conteudo_id -> menor distância entre seus vetores
    for meta, dist in zip(r["metadatas"][0], r["distances"][0]):
        cid = meta["conteudo_id"]
        melhor[cid] = min(dist, melhor.get(cid, 9))
    out = []
    with db.conectar() as con:
        for cid, dist in sorted(melhor.items(), key=lambda x: x[1])[:k]:
            row = con.execute("SELECT * FROM conteudos WHERE id=? AND empresa_id=?", (cid, empresa_id)).fetchone()
            if row and row["visibilidade"] in visibilidades:
                out.append({**dict(row), "similaridade": round(1 - dist, 3)})
    return out


def _cli():
    if len(sys.argv) >= 2 and sys.argv[1] == "reindexar":
        print(f"{reindexar_tudo()} conteúdos indexados.")
    elif len(sys.argv) >= 4 and sys.argv[1] == "importar":
        nome, caminho = sys.argv[2], Path(sys.argv[3])
        vis = sys.argv[4] if len(sys.argv) > 4 else "internos"
        with db.conectar() as con:
            emp = con.execute("SELECT id FROM empresas WHERE nome=?", (nome,)).fetchone()
            if not emp:
                con.execute("INSERT INTO empresas (nome) VALUES (?)", (nome,))
                con.commit()
                emp = con.execute("SELECT id FROM empresas WHERE nome=?", (nome,)).fetchone()
            n = importar_csv(con, emp["id"], caminho.read_text(encoding="utf-8-sig"), vis)
        print(f"{n} conteúdos importados para '{nome}' (visibilidade: {vis}) e indexados.")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    _cli()
