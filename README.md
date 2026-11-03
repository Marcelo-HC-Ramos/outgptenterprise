# OutGPT Enterprise

Plataforma de onboarding e retencao do conhecimento operacional com IA generativa (RAG).
Projeto de Processamento de Linguagem Natural - Fatec Cotia, Ciencia de Dados.

**Equipe:** Marcelo Henrique do Carmo Ramos, Victor Henrique Duarte Cardoso

## Demo online
O site fica publicado pelo GitHub Pages (Settings > Pages > Branch `main`, pasta `/docs`) em:
`https://marcelo-hc-ramos.github.io/outgptenterprise/`

Online ele roda em **modo demonstracao**: a pesquisa usa dados ficticios (Faker) e as novas respostas ficam apenas
no navegador de quem responde. O GitHub Pages nao executa Python, por isso o banco SQLite so funciona localmente.

## Estrutura
```
docs/      Front-end (HTML/CSS/JS) - publicado no GitHub Pages
backend/   Banco SQLite, servidor Python, gerador de dados Faker
```

## Rodar localmente com o banco SQLite
```
cd backend
pip install -r requirements.txt
python init_db.py            # cria outgpt.db (12 tabelas)
python seed_faker.py         # dados ficticios (opcional)
python server.py             # http://localhost:8000
```
Rotas: site em `/`, API `/api/perguntas`, `/api/enviar`, `/api/resultados`, `/api/exportar.csv`.

## Banco de dados
- Plataforma: usuarios, documentos, chunks, trilhas, modulos, questoes, progresso, historico_duvidas
- Pesquisa: especialistas, perguntas, opcoes, respostas
Esquema completo em `backend/schema.sql`.

## Atualizar a demo online
```
cd backend
python export_static.py      # regenera docs/dados.js (somente dados ficticios, anonimizados)
```

## Aviso sobre dados
Os dados de `seed_faker.py` sao ficticios e servem so para demonstracao; nao sao resultados reais de pesquisa.
Respostas reais ficam em `backend/outgpt.db`, que nao e versionado (.gitignore) por conter dados pessoais.

## Dataset de SOPs + RAG (ChromaDB)
```
pip install -r backend/requirements.txt
# o CSV ja esta em backend/data/sops_corporativos.csv
# colunas: id, categoria, procedimento_titulo, contexto_documental, pergunta_utilizador, resposta_esperada, contem_pii
python backend/rag.py            # carrega no SQLite (tabela sops) e indexa no ChromaDB
python backend/server.py
```
- `GET /api/documentos`: catalogo das SOPs (tambem aparece em "Documentos" no site)
- `POST /api/chat {"pergunta": "..."}`: busca semantica; mascara e-mail, CPF, CNPJ e telefone antes de buscar; recusa quando a similaridade fica abaixo do limiar (`OUTGPT_LIMIAR`, padrao 0.50)
- Embeddings: modelo multilingue paraphrase-multilingual-MiniLM-L12-v2 via fastembed (baixado na primeira execucao, ~220 MB). Cada SOP gera dois vetores (conteudo e pergunta de exemplo).
- Teste com 12 perguntas reescritas: acerto na 1a posicao 10/12 e nas 3 primeiras 12/12. O limiar de recusa (0.50) separou as perguntas fora do assunto nesse teste; recalibre com mais exemplos.


