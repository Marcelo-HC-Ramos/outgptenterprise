"""RAG multiempresa: conteúdos no SQLite + vetores no ChromaDB + anonimização de PII.

Como funciona
  1. Ingestão: o conteúdo (digitado, importado de CSV ou extraído de TXT/MD/PDF/DOCX) é dividido em trechos de
     ~600 caracteres com sobreposição, para caber no limite do modelo de embeddings e preservar o contexto.
  2. Indexação: cada trecho (e a pergunta de exemplo, se houver) vira um vetor no ChromaDB, com `empresa_id` e
     `visibilidade` nos metadados.
  3. Busca: a pergunta vira vetor; a busca SEMPRE filtra por empresa e visibilidade e devolve os trechos mais
     parecidos, agrupados por conteúdo, para a LLM responder com base neles.

Uso (linha de comando):
  python rag.py reindexar                                   # recria todo o índice a partir do SQLite
  python rag.py importar "Minha Empresa" data/sops_corporativos.csv [todos|internos]
CSV: id, categoria, procedimento_titulo, contexto_documental, pergunta_utilizador, resposta_esperada, contem_pii
"""
import csv
import io
import os
import re
import sys
from pathlib import Path

import db

BASE = Path(__file__).parent
CSV_PADRAO = BASE / "data" / "sops_corporativos.csv"
CHROMA_DIR = Path(os.environ.get("OUTGPT_CHROMA") or BASE / "data" / "chroma_db")
COLECAO = "conteudos"
FORMATO_INDICE = 4                      # muda quando o formato dos vetores muda (força reindexação automática)
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"   # multilíngue (o padrão do Chroma é só inglês)
COLUNAS_CSV = ["id", "categoria", "procedimento_titulo", "contexto_documental", "pergunta_utilizador", "resposta_esperada", "contem_pii"]
TRECHO_ALVO = 600                       # caracteres por trecho
TRECHO_SOBREPOSICAO = 80
LIMITE_TEXTO_ARQUIVO = 400_000

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
            COLECAO, embedding_function=_embedder(), metadata={"hnsw:space": "cosine", "formato": FORMATO_INDICE})
    return _colecao


# ---------- Divisão em trechos (chunking) ----------
def dividir_em_trechos(texto, alvo=TRECHO_ALVO, sobreposicao=TRECHO_SOBREPOSICAO):
    """Divide o texto em trechos de até ~`alvo` caracteres, respeitando parágrafos e frases.
    Textos curtos (até 1,5x o alvo) viram um único trecho. Trechos consecutivos compartilham `sobreposicao` caracteres."""
    texto = re.sub(r"[ \t]+", " ", texto.replace("\r", "")).strip()
    if len(texto) <= alvo * 1.5:
        return [texto] if texto else []
    unidades = []                                   # frases/parágrafos, nunca maiores que `alvo`
    for par in re.split(r"\n\s*\n|\n(?=[-•*\d]+[.)]?\s)", texto):
        par = par.strip()
        if not par:
            continue
        for frase in re.split(r"(?<=[.!?;:])\s+", par):
            while len(frase) > alvo:                # frase gigante: corta em espaço
                corte = frase.rfind(" ", 0, alvo)
                corte = corte if corte > alvo // 2 else alvo
                unidades.append(frase[:corte].strip())
                frase = frase[corte:].strip()
            if frase:
                unidades.append(frase)
    trechos, atual = [], ""
    for u in unidades:
        if atual and len(atual) + 1 + len(u) > alvo:
            trechos.append(atual)
            cauda = atual[-sobreposicao:]
            cauda = cauda[cauda.find(" ") + 1:] if " " in cauda else ""      # começa em palavra inteira
            atual = (cauda + " " + u).strip()
        else:
            atual = (atual + " " + u).strip()
    if atual:
        trechos.append(atual)
    return trechos


# ---------- Extração de texto de arquivos ----------
def extrair_texto(nome, dados):
    """Texto de um arquivo enviado (.txt, .md, .pdf, .docx). Levanta ValueError com mensagem amigável."""
    ext = Path(nome).suffix.lower()
    if ext in (".txt", ".md", ".csv"):
        for enc in ("utf-8-sig", "cp1252"):
            try:
                texto = dados.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Não foi possível ler o texto do arquivo (codificação desconhecida).")
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
            leitor = PdfReader(io.BytesIO(dados))
            if leitor.is_encrypted:
                raise ValueError("O PDF está protegido por senha.")
            texto = "\n\n".join((p.extract_text() or "") for p in leitor.pages)
        except ValueError:
            raise
        except ImportError:
            raise ValueError("Suporte a PDF não instalado no servidor (pip install pypdf).")
        except Exception:
            raise ValueError("Não foi possível ler o PDF (arquivo corrompido?).")
    elif ext == ".docx":
        try:
            import docx
            d = docx.Document(io.BytesIO(dados))
            partes = [p.text for p in d.paragraphs]
            for tabela in d.tables:
                for linha in tabela.rows:
                    partes.append(" | ".join(c.text.strip() for c in linha.cells))
            texto = "\n\n".join(partes)
        except ImportError:
            raise ValueError("Suporte a DOCX não instalado no servidor (pip install python-docx).")
        except Exception:
            raise ValueError("Não foi possível ler o DOCX (arquivo corrompido?).")
    else:
        raise ValueError("Formato não suportado. Envie .txt, .md, .pdf ou .docx.")
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if len(texto) < 20:
        raise ValueError("Não encontrei texto no arquivo (PDF escaneado como imagem? Use um PDF com texto selecionável).")
    return texto[:LIMITE_TEXTO_ARQUIVO]


# ---------- Índice ----------
def _trechos_do_conteudo(c):
    return [(i, f"{c['titulo']}. {t}") for i, t in enumerate(dividir_em_trechos(c["texto"]))]


def _vetores(c):
    """(ids, documentos, metadados) de um conteúdo (sqlite3.Row ou dict)."""
    base = {"conteudo_id": int(c["id"]), "empresa_id": int(c["empresa_id"]), "visibilidade": c["visibilidade"]}
    ids, docs, metas = [], [], []
    for i, doc in _trechos_do_conteudo(c):
        ids.append(f"c{c['id']}#t{i}")
        docs.append(doc)
        metas.append({**base, "parte": "trecho", "ordem": i})
    if c["pergunta_exemplo"]:
        ids.append(f"c{c['id']}#pergunta")
        docs.append(c["pergunta_exemplo"])
        metas.append({**base, "parte": "pergunta", "ordem": 0})
    return ids, docs, metas


def _fts_gravar(con, c):
    con.execute("DELETE FROM trechos_fts WHERE conteudo_id = ?", (int(c["id"]),))
    con.executemany("INSERT INTO trechos_fts (texto, conteudo_id, empresa_id, visibilidade, ordem) VALUES (?,?,?,?,?)",
                    [(doc, int(c["id"]), int(c["empresa_id"]), c["visibilidade"], i) for i, doc in _trechos_do_conteudo(c)])


def indexar_conteudo(c, con=None):
    """Indexa (ou reindexa) um conteúdo. Passe a conexão do chamador para não disputar o lock do SQLite."""
    col = colecao()
    col.delete(where={"conteudo_id": int(c["id"])})          # substitui os vetores antigos deste conteúdo
    ids, docs, metas = _vetores(c)
    for k in range(0, len(ids), 100):                         # lotes (arquivos grandes geram centenas de trechos)
        col.add(ids=ids[k:k + 100], documents=docs[k:k + 100], metadatas=metas[k:k + 100])
    if con is not None:
        _fts_gravar(con, c)
        con.commit()
    else:
        with db.conectar() as nova:
            _fts_gravar(nova, c)


def remover_conteudo(conteudo_id, con=None):
    colecao().delete(where={"conteudo_id": int(conteudo_id)})
    if con is not None:
        con.execute("DELETE FROM trechos_fts WHERE conteudo_id = ?", (int(conteudo_id),))
        con.commit()
    else:
        with db.conectar() as nova:
            nova.execute("DELETE FROM trechos_fts WHERE conteudo_id = ?", (int(conteudo_id),))


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
    ids, docs, metas, n = [], [], [], 0
    with db.conectar() as con:
        con.execute("DELETE FROM trechos_fts")
        for c in con.execute("SELECT * FROM conteudos").fetchall():
            i, d, m = _vetores(c)
            ids += i; docs += d; metas += m; n += 1
            _fts_gravar(con, c)
    for k in range(0, len(ids), 100):
        col.add(ids=ids[k:k + 100], documents=docs[k:k + 100], metadatas=metas[k:k + 100])
    return n


def garantir_indice():
    """Reindexa sozinho se o índice estiver vazio ou no formato antigo (ex.: primeiro uso depois de clonar o projeto)."""
    with db.conectar() as con:
        if not con.execute("SELECT 1 FROM conteudos LIMIT 1").fetchone():
            return False
        fts_vazio = not con.execute("SELECT 1 FROM trechos_fts LIMIT 1").fetchone()
    col = colecao()
    if fts_vazio or col.count() == 0 or (col.metadata or {}).get("formato") != FORMATO_INDICE:
        reindexar_tudo()
        return True
    return False

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
    """Insere/atualiza os conteúdos de uma empresa a partir do CSV, reindexa e sincroniza os cursos. Devolve a quantidade."""
    if visibilidade not in ("todos", "internos"):
        raise ValueError("Visibilidade inválida.")
    linhas = linhas_do_csv(texto)
    for l in linhas:
        con.execute(
            "INSERT INTO conteudos (empresa_id,codigo,titulo,categoria,texto,pergunta_exemplo,resposta_exemplo,contem_pii,visibilidade,criado_por) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(empresa_id,codigo) DO UPDATE SET titulo=excluded.titulo, "
            "categoria=excluded.categoria, texto=excluded.texto, pergunta_exemplo=excluded.pergunta_exemplo, "
            "resposta_exemplo=excluded.resposta_exemplo, contem_pii=excluded.contem_pii, atualizado_em=datetime('now','localtime')",
            (empresa_id, l["id"], l["procedimento_titulo"], l["categoria"] or "Geral", l["contexto_documental"],
             l["pergunta_utilizador"], l["resposta_esperada"] or None, _bool(l["contem_pii"]), visibilidade, criado_por))
    con.commit()
    for c in con.execute("SELECT * FROM conteudos WHERE empresa_id=? AND codigo IN (%s)" % ",".join("?" * len(linhas)),
                         [empresa_id] + [l["id"] for l in linhas]).fetchall():
        indexar_conteudo(c, con)
    import cursos
    cursos.sincronizar(con, empresa_id)
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


# ---------- Consulta (busca híbrida) ----------
STOPWORDS = set("""a o as os um uma uns umas de da do das dos em no na nos nas ao aos à às para por pra com sem sobre entre ate até que
qual quais quanto quantos quantas como quando onde quem porque por que e ou se mas ser sao são foi era tem ter tenho posso preciso
precisa devo deve fazer faco faço fazem minha meu meus minhas seu sua seus suas isso esse essa esses essas este esta estes estas
ha há ja já mais muito muita existe existem vou vai pode podem""".split())
RRF_K = 60


def _termos(pergunta):
    """Palavras úteis da pergunta, sem acentos e sem stopwords (para a busca por palavras-chave)."""
    import unicodedata
    norm = unicodedata.normalize("NFKD", pergunta.lower())
    norm = "".join(ch for ch in norm if not unicodedata.combining(ch))
    return [t for t in re.findall(r"[a-z0-9]+", norm) if len(t) >= 3 and t not in STOPWORDS]


def _consulta_fts(termos):
    """Prefixos simples fazem as vezes de radical: 'devolvo' casa com 'devolver'/'devolução'."""
    partes = []
    for t in dict.fromkeys(termos):
        partes.append(f'"{t[:max(4, len(t) - 2)]}"*' if len(t) >= 5 else f'"{t}"')
    return " OR ".join(partes)


def _normalizar(texto):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(ch))


def _busca_lexical(pergunta, empresa_id, visibilidades, limite=20):
    """Trechos com palavras da pergunta (BM25). Devolve lista de (conteudo_id, ordem, texto, forca) do melhor para o pior."""
    termos = _termos(pergunta)
    if not termos:
        return []
    marcas = ",".join("?" * len(visibilidades))
    with db.conectar() as con:
        try:
            linhas = con.execute(
                f"SELECT conteudo_id, ordem, texto FROM trechos_fts WHERE trechos_fts MATCH ? AND empresa_id = ? "
                f"AND visibilidade IN ({marcas}) ORDER BY bm25(trechos_fts) LIMIT ?",
                [_consulta_fts(termos), int(empresa_id), *visibilidades, limite]).fetchall()
        except Exception:
            return []
    out = []
    for r in linhas:
        norm = _normalizar(r["texto"])
        casados = sum(1 for t in set(termos) if t[:max(4, len(t) - 2)] in norm)
        out.append((r["conteudo_id"], r["ordem"], r["texto"], casados / len(set(termos)), casados))
    return out


def buscar(pergunta, empresa_id, visibilidades, k=3):
    """Busca híbrida: vetores (significado) + palavras-chave (BM25), combinadas por posição (RRF).
    Cada item traz o conteúdo, a `similaridade` vetorial, `lexical` (casou com palavras da pergunta) e os `trechos`
    que melhor respondem. Sempre restrita à empresa e às visibilidades permitidas."""
    col = colecao()
    if col.count() == 0:
        return []
    filtro = {"$and": [{"empresa_id": {"$eq": int(empresa_id)}}, {"visibilidade": {"$in": list(visibilidades)}}]}
    r = col.query(query_texts=[pergunta], n_results=k * 6 + 6, where=filtro)
    vet = {}      # conteudo_id -> {"dist", "trechos": {ordem: texto}}
    for meta, dist, doc in zip(r["metadatas"][0], r["distances"][0], r["documents"][0]):
        g = vet.setdefault(meta["conteudo_id"], {"dist": 9, "trechos": {}})
        g["dist"] = min(g["dist"], dist)
        if meta["parte"] == "trecho":
            g["trechos"][meta["ordem"]] = doc
    lex = {}      # conteudo_id -> {"pos", "forca", "casados", "trechos": {ordem: texto}}
    for pos, (cid, ordem, doc, forca, casados) in enumerate(_busca_lexical(pergunta, empresa_id, visibilidades)):
        g = lex.setdefault(cid, {"pos": pos, "forca": 0, "casados": 0, "trechos": {}})
        g["forca"] = max(g["forca"], forca); g["casados"] = max(g["casados"], casados)
        if len(g["trechos"]) < 3:
            g["trechos"][ordem] = doc
    n_termos = len(set(_termos(pergunta)))
    for g in lex.values():       # casamento "forte": a maioria das palavras úteis da pergunta aparece no mesmo trecho
        g["forte"] = g["forca"] >= 0.5 and g["casados"] >= min(2, n_termos)
    faltam = [cid for cid in lex if cid not in vet]       # achados só por palavra-chave: mede a similaridade vetorial deles
    if faltam:
        rr = col.query(query_texts=[pergunta], n_results=len(faltam) * 4 + 4, where={"$and": [filtro["$and"][0], {"conteudo_id": {"$in": faltam}}]})
        for meta, dist, doc in zip(rr["metadatas"][0], rr["distances"][0], rr["documents"][0]):
            g = vet.setdefault(meta["conteudo_id"], {"dist": 9, "trechos": {}})
            g["dist"] = min(g["dist"], dist)
    rank_v = {cid: i for i, (cid, _) in enumerate(sorted(vet.items(), key=lambda x: x[1]["dist"]))}
    fortes = sorted((cid for cid, g in lex.items() if g["forte"]), key=lambda cid: lex[cid]["pos"])
    rank_l = {cid: i for i, cid in enumerate(fortes)}      # só o lexical forte entra na fusão (evita palavras genéricas)
    score = {cid: (1 / (RRF_K + rank_v[cid]) if cid in rank_v else 0) + (1 / (RRF_K + rank_l[cid]) if cid in rank_l else 0)
             for cid in set(vet) | set(lex)}
    out = []
    with db.conectar() as con:
        for cid in sorted(score, key=score.get, reverse=True)[:k]:
            row = con.execute("SELECT * FROM conteudos WHERE id=? AND empresa_id=?", (cid, empresa_id)).fetchone()
            if not row or row["visibilidade"] not in visibilidades:
                continue
            prefixo = f"{row['titulo']}. "
            achados = {**vet.get(cid, {}).get("trechos", {}), **lex.get(cid, {}).get("trechos", {})}
            ordenados = sorted(achados.items())[:4]
            trechos = [t[len(prefixo):] if t.startswith(prefixo) else t for _, t in ordenados]
            if not trechos:      # só a pergunta de exemplo casou: usa o início do conteúdo
                trechos = dividir_em_trechos(row["texto"])[:2]
            lexical = bool(lex.get(cid, {}).get("forte"))
            out.append({**dict(row), "similaridade": round(1 - vet[cid]["dist"], 3) if cid in vet else 0.0, "lexical": lexical, "trechos": trechos})
    return out


def relevante(item, com_llm, piso_vetor=None):
    """Filtro de relevância: similaridade vetorial alta, ou palavras-chave casadas com similaridade média.
    Com a LLM disponível o filtro é mais folgado: ela recusa sozinha (SEM_BASE) o que não estiver nos documentos."""
    piso = piso_vetor if piso_vetor is not None else (0.45 if com_llm else 0.50)
    piso_lex = piso - (0.15 if com_llm else 0.10)
    return item["similaridade"] >= piso or (item["lexical"] and item["similaridade"] >= piso_lex)

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
        print(f"{n} conteúdos importados para '{nome}' (visibilidade: {vis}), indexados e com cursos gerados.")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    _cli()
