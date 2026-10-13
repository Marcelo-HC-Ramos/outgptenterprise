# OutGPT Enterprise

Plataforma de onboarding e retencao do conhecimento operacional com IA generativa (RAG).
Projeto de Processamento de Linguagem Natural - Fatec Cotia, Ciencia de Dados.

**Equipe:** Marcelo Henrique do Carmo Ramos, Victor Henrique Duarte Cardoso

## Demo online
Apos ativar o GitHub Pages (Settings > Pages > Branch `main`, pasta `/docs`), o site fica em:
`https://SEU-USUARIO.github.io/NOME-DO-REPOSITORIO/`

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
