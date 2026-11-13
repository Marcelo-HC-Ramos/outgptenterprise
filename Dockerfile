# OutGPT Enterprise - imagem para publicar na internet (veja DEPLOY.md)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    OUTGPT_HOST=0.0.0.0 \
    OUTGPT_DB=/data/outgpt.db \
    OUTGPT_CHROMA=/data/chroma_db \
    OUTGPT_ENV_ARQ=/data/.env \
    OUTGPT_COOKIE_SECURE=1 \
    OUTGPT_CONFIAR_PROXY=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Baixa o modelo de busca (~250 MB) na construção da imagem: a primeira pergunta não precisa baixar nada.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY backend backend
COPY docs docs

# /data é o volume persistente (banco SQLite, índice de busca e a chave da API salva pela tela de administração)
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN useradd --create-home app && mkdir -p /data && chown -R app:app /data /app && chmod +x /app/docker-entrypoint.sh
VOLUME /data
WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/saude' % (os.environ.get('PORT') or '8000'))" || exit 1

# O entrypoint ajusta a permissão de /data, cria/atualiza o banco e inicia o servidor como usuário comum.
# A porta vem da variável PORT (a hospedagem define) ou 8000.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
