# OutGPT Enterprise

Plataforma de onboarding e retenção do conhecimento operacional com IA generativa (RAG híbrido + LLM).
Projeto de Processamento de Linguagem Natural - Fatec Cotia, Ciência de Dados.

**Equipe:** Marcelo Henrique do Carmo Ramos, Victor Henrique Duarte Cardoso

## O que a plataforma faz
- Cada **empresa** cadastra seus conteúdos (procedimentos, manuais, FAQs; digitados, em CSV ou enviados como TXT/MD/PDF/DOCX) e seus usuários.
- **Cursos automáticos:** cada categoria de conteúdo vira um curso, com lições, perguntas de verificação e progresso por usuário.
- **Assistente com IA (Claude):** responde dúvidas só com base nos conteúdos da empresa, em linguagem clara (resposta direta, passos numerados, prazos em destaque) e cita a fonte. Lembra da conversa para perguntas de continuação. Se não há base, recusa em vez de inventar.
- **RAG híbrido:** os textos são divididos em trechos e buscados por significado (vetores, ChromaDB) e por palavras-chave (BM25, SQLite FTS5).
- **Privacidade:** e-mail, CPF, CNPJ e telefone são mascarados antes de qualquer consulta; os dados de cada empresa são isolados.

## Perfis de acesso
| Perfil | O que pode |
|---|---|
| `master` (dono do sistema) | Tudo: empresas, usuários, conteúdos, configuração da IA e resultados da pesquisa |
| `admin` (da empresa) | Gerencia conteúdos, cursos e usuários da própria empresa |
| `funcionario` / `colaborador_interno` | Faz os cursos, usa o assistente e lê a biblioteca da empresa |
| `colaborador_externo` | Usa o assistente e os cursos, mas só enxerga conteúdos marcados como "Todos" |

## Instalar e rodar (Windows/PowerShell)
```
cd backend
pip install -r requirements.txt
python init_db.py                  # cria ou atualiza o banco
python criar_master.py             # cria o SEU login de dono (a senha é digitada no terminal)
python server.py                   # http://localhost:8000
```
Depois, no site: entre com o login master e abra **Administração > Inteligência artificial** para colar a chave da API
(ou rode `python configurar_llm.py`). A chave é testada, guardada só em `backend/.env` e nunca mais aparece na tela.
Sem a chave tudo funciona, mas o assistente devolve o trecho encontrado em vez de uma resposta escrita pela IA.

Para começar a usar: **Empresas** (criar) > **Biblioteca** (importar o CSV `backend/data/sops_corporativos.csv`, enviar arquivos ou cadastrar conteúdos) > **Usuários** (criar o admin, funcionários e colaboradores).
No primeiro uso, o índice de busca é criado sozinho (na primeira vez baixa o modelo de embeddings, ~220 MB).

## Pesquisa com especialistas
Arquivo separado e autônomo: `docs/pesquisa.html` (`http://localhost:8000/pesquisa.html`), com as abas **Responder** (pública) e **Resultados** (somente master, com exportação CSV).

## Demo online (GitHub Pages)
Publicando a pasta `docs/` (Settings > Pages > Branch `main`, pasta `/docs`) o site roda em **modo demonstração**: sem login e sem IA
(o GitHub Pages não executa Python). Os cursos, as perguntas de verificação e a busca usam o conteúdo de exemplo `docs/demo_conteudos.js`.

## Estrutura
```
docs/      Site (HTML/CSS/JS) + pesquisa.html. Publicado no GitHub Pages
backend/   Servidor Python, banco SQLite, RAG, cursos e integração com a LLM
```

## Banco de dados (SQLite, `backend/outgpt.db`)
`empresas`, `usuarios`, `sessoes`, `conteudos`, `trechos_fts`, `cursos`, `curso_itens`, `progresso_licoes`, `historico_duvidas`,
`especialistas`, `perguntas`, `opcoes`, `respostas`. Esquema em `backend/schema.sql`.
Senhas com scrypt; sessões por cookie HttpOnly; login bloqueado por 15 min após 5 falhas.

## Configuração da LLM (opcional, em `backend/.env`)
```
ANTHROPIC_API_KEY=sk-ant-...      # ou pela tela de Administração
OUTGPT_MODELO=claude-opus-5-5     # padrão; para gastar menos: claude-haiku-5-5
OUTGPT_ESFORCO=low                # low | medium | high
```

## Comandos úteis
```
python rag.py importar "Nome da Empresa" data/sops_corporativos.csv internos   # importa CSV pela linha de comando
python rag.py reindexar                                                         # refaz o índice de busca
python export_static.py                                                         # atualiza os dados do site publicado
```

## Desenvolvimento
`seed_faker.py` gera respostas de TESTE da pesquisa para desenvolver as telas (`--limpar` remove). Nunca publique esses dados como resultado de pesquisa.

## Segurança e privacidade
- Nunca coloque a chave da API no código ou no GitHub: ela fica só em `backend/.env` (ignorado pelo Git).
- `backend/outgpt.db` contém usuários e respostas reais e também não é versionado.
- As perguntas ao assistente são gravadas já anonimizadas.
- O servidor escuta apenas em `127.0.0.1`. Para uso por outras pessoas, hospede-o atrás de HTTPS e defina `OUTGPT_COOKIE_SECURE=1`.
