# OutGPT Enterprise

Plataforma de onboarding e retencao do conhecimento operacional com IA generativa (RAG + LLM).
Projeto de Processamento de Linguagem Natural - Fatec Cotia, Ciencia de Dados.

**Equipe:** Marcelo Henrique do Carmo Ramos, Victor Henrique Duarte Cardoso

## O que a plataforma faz
- Cada **empresa** cadastra seus conteudos (procedimentos, manuais, FAQs) e seus usuarios.
- O **assistente** responde duvidas usando uma **LLM (Claude)** somente com base nesses conteudos, citando a fonte.
  Se nao ha base suficiente, ele recusa em vez de inventar. Dados pessoais (e-mail, CPF, CNPJ, telefone) sao mascarados antes da consulta.
- Os dados de cada empresa sao **isolados**: um usuario nunca ve conteudo de outra empresa.

## Perfis de acesso
| Perfil | O que pode |
|---|---|
| `master` (dono do sistema) | Tudo: empresas, usuarios e conteudos de todas as empresas, resultados da pesquisa |
| `admin` (da empresa) | Gerencia conteudos e usuarios da propria empresa |
| `funcionario` / `colaborador_interno` | Usa o assistente e le os conteudos da empresa |
| `colaborador_externo` | Usa o assistente, mas so enxerga conteudos marcados como "Todos" |

## Instalar e rodar (Windows/PowerShell)
```
cd backend
pip install -r requirements.txt
python init_db.py                  # cria o banco (use --reset para recriar do zero)
python criar_master.py             # cria o SEU login de dono (a senha e digitada no terminal)
copy .env.example .env             # depois edite o .env e coloque sua ANTHROPIC_API_KEY
python server.py                   # http://localhost:8000
```
1. Entre com o login master, abra **Empresas** e crie a primeira empresa.
2. Em **Conteudos**, cadastre manualmente ou use **Importar CSV** (`backend/data/sops_corporativos.csv` e um exemplo com 100 SOPs).
3. Em **Usuarios**, crie o admin da empresa, funcionarios e colaboradores.

Sem a chave da API, tudo funciona, mas o assistente devolve o trecho encontrado em vez de uma resposta gerada pela LLM.

## Pesquisa com especialistas
Arquivo separado e autonomo: `docs/pesquisa.html` (abre em `http://localhost:8000/pesquisa.html`).
Tem duas abas: **Responder** (publica) e **Resultados** (somente master, com exportacao CSV).

## Demo online (GitHub Pages)
Publicando a pasta `docs/` (Settings > Pages > Branch `main`, pasta `/docs`), o site roda em **modo demonstracao**:
sem login, com dados ficticios e sem LLM real (o GitHub Pages nao executa Python). A pesquisa tambem funciona em demo.

## Estrutura
```
docs/      Site (HTML/CSS/JS) + pesquisa.html. Publicado no GitHub Pages
backend/   Servidor Python, banco SQLite, RAG (ChromaDB), integracao com a LLM
```

## Banco de dados (SQLite, `backend/outgpt.db`)
- Plataforma: `empresas`, `usuarios`, `sessoes`, `conteudos`, `historico_duvidas`, `trilhas`, `modulos`, `questoes`, `progresso`
- Pesquisa: `especialistas`, `perguntas`, `opcoes`, `respostas`
Esquema em `backend/schema.sql`. Senhas guardadas com scrypt; sessoes por cookie HttpOnly; login bloqueado por 15 min apos 5 falhas.

## Outros comandos
```
python rag.py importar "Nome da Empresa" data/sops_corporativos.csv internos   # importa CSV pela linha de comando
python rag.py reindexar                                                         # refaz o indice vetorial
python seed_faker.py                                                            # respostas ficticias da pesquisa
python export_static.py                                                         # atualiza docs/dados.js (demo da pesquisa)
```

## Atualizando de uma versao anterior
Rode `python init_db.py` uma vez: as tabelas de demonstracao antigas sao substituidas pelo modelo multiempresa e a pesquisa e preservada.
Depois crie o master (`python criar_master.py`) e reimporte o CSV.

## Seguranca e privacidade
- Nunca coloque a chave da API no codigo ou no GitHub: ela fica so em `backend/.env` (ignorado pelo Git).
- `backend/outgpt.db` contem usuarios e respostas reais e tambem nao e versionado.
- As perguntas ao assistente sao gravadas ja anonimizadas.
- O servidor escuta apenas em `127.0.0.1`. Para uso por outras pessoas, hospede-o atras de HTTPS e defina `OUTGPT_COOKIE_SECURE=1`.