# OutGPT Enterprise

Plataforma de onboarding e retenção do conhecimento operacional com IA generativa (RAG híbrido + LLM).
Projeto de Processamento de Linguagem Natural - Fatec Cotia, Ciência de Dados.

**Equipe:** Marcelo Henrique do Carmo Ramos, Victor Henrique Duarte Cardoso

## Como usar (Windows) — dois cliques
1. Dê dois cliques em **`INICIAR.bat`** (na pasta do projeto).
2. Na primeira vez, a janela preta faz poucas perguntas: seu **login** (e-mail e senha), a **chave da IA** (pode pular e colar depois no site) e o nome da sua **empresa** (já carrega os 100 procedimentos do dataset do projeto).
3. O navegador abre em **http://localhost:8000**. Entre com o login que você criou. Pronto.

Nas próximas vezes o `INICIAR.bat` não pergunta mais nada: só liga o sistema e abre o navegador. Para encerrar, feche a janela "OutGPT - servidor".
Requisito: Python 3.10+ instalado ("Add python.exe to PATH"). O `INICIAR.bat` instala as bibliotecas sozinho na primeira vez (a primeira indexação baixa o modelo de busca, ~250 MB).

**Ligar a IA:** em *Administração > Inteligência artificial* cole a chave da API (criada em console.anthropic.com). Ela é testada na hora e guardada só em `backend/.env`.
Sem a chave o assistente funciona, mas mostra o trecho do manual em vez de uma resposta escrita pela IA.

## Rodar online pelo GitHub (Codespaces)
[![Abrir no GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Marcelo-HC-Ramos/outgptenterprise?quickstart=1)

O GitHub Pages não executa Python, então ele não serve para o sistema real. O que o GitHub oferece para rodar tudo (banco, login e IA) é o **Codespaces**: um computador na nuvem ligado a este repositório, com endereço HTTPS.
1. (Opcional, antes de criar) Em *GitHub > Settings > Codespaces > Secrets*, crie o segredo `ANTHROPIC_API_KEY` com a chave da IA e libere este repositório para ele.
2. Clique no botão acima (ou *Code > Codespaces > Create codespace on main*) e aguarde alguns minutos: ele instala tudo, cria a empresa com os 100 procedimentos e liga o servidor sozinho.
3. No terminal aparece o **endereço do sistema** e o **token de primeiro acesso**. Abra o endereço, preencha "Primeiro acesso" (seu e-mail e senha) e entre.
4. Para qualquer pessoa abrir o link: aba **PORTAS** > botão direito na porta 8000 > *Visibilidade da porta* > **Pública**.

Limites: o Codespace **desliga sozinho** depois de um tempo sem uso (basta abri-lo de novo; o servidor liga junto e os dados continuam lá), usa a cota gratuita mensal da sua conta (confira em github.com/settings/billing) e é apagado após dias parado. Serve bem para apresentações e testes; para uso permanente, veja o `DEPLOY.md`.
O GitHub Actions testa automaticamente o sistema, a imagem Docker e esta configuração a cada envio (aba *Actions*).
## O que a plataforma faz
- Cada **empresa** cadastra seus conteúdos (procedimentos, manuais, FAQs; digitados, em CSV ou enviados como TXT/MD/PDF/DOCX) e seus usuários.
- **Cursos:** cada categoria de conteúdo vira um curso automático (lições, perguntas de verificação e progresso por usuário); o admin também monta **cursos personalizados** escolhendo e ordenando lições, e pode gerar as perguntas de verificação com a IA. Ao concluir um curso, o usuário emite um **certificado** imprimível, com código verificável em `/verificar.html`.
- **Assistente com IA (Claude):** responde dúvidas só com base nos conteúdos da empresa, em linguagem clara (resposta direta, passos numerados, prazos em destaque) e cita a fonte. A resposta aparece em tempo real (streaming), o assistente lembra da conversa e, se não há base, recusa em vez de inventar. Cada resposta pode ser avaliada com 👍/👎.
- **Qualidade (admin):** a tela *Lacunas e feedback* mostra as perguntas que o assistente não soube responder (as mais repetidas primeiro, com atalho para criar o conteúdo) e as respostas que não ajudaram.
- **RAG híbrido:** os textos são divididos em trechos e buscados por significado (vetores, ChromaDB) e por palavras-chave (BM25, SQLite FTS5).
- **Privacidade:** e-mail, CPF, CNPJ e telefone são mascarados antes de qualquer consulta; os dados de cada empresa são isolados.

## Perfis de acesso
| Perfil | O que pode |
|---|---|
| `master` (dono do sistema) | Tudo: empresas, usuários, conteúdos, configuração da IA e resultados da pesquisa |
| `admin` (da empresa) | Gerencia conteúdos, cursos e usuários da própria empresa |
| `funcionario` / `colaborador_interno` | Faz os cursos, usa o assistente e lê a biblioteca da empresa |
| `colaborador_externo` | Usa o assistente e os cursos, mas só enxerga conteúdos marcados como "Todos" |

Depois de entrar como master: **Usuários** (criar o admin, funcionários e colaboradores) e **Biblioteca** (importar CSV, enviar arquivos ou cadastrar conteúdos).

## Pesquisa com especialistas
Arquivo separado e autônomo: `docs/pesquisa.html` (`http://localhost:8000/pesquisa.html`), com as abas **Responder** (pública) e **Resultados** (somente master, com exportação CSV). As respostas vão para o banco de dados do servidor.

## Publicar na internet
O sistema completo precisa do servidor (banco, logins e IA); por isso o GitHub Pages não serve. Veja **[DEPLOY.md](DEPLOY.md)**: Dockerfile, `render.yaml` e `fly.toml` prontos, tela de "Primeiro acesso" por token, HTTPS, backup (`python backup.py`) e cuidados de privacidade.
O modo servidor foi testado localmente; o build Docker e a publicação em si ainda precisam ser executados na hospedagem escolhida.

## Estrutura
```
INICIAR.bat   Liga tudo com dois cliques (Windows)
docs/         Site (HTML/CSS/JS), servido pelo próprio servidor Python
backend/      Servidor Python, banco SQLite, RAG, cursos e integração com a LLM
```

## Instalação manual (sem o INICIAR.bat)
```
cd backend
pip install -r requirements.txt
python init_db.py
python preparar.py        # configuração guiada (login, IA, empresa)
python server.py          # http://localhost:8000
```

## Banco de dados (SQLite, `backend/outgpt.db`)
`empresas`, `usuarios`, `sessoes`, `conteudos`, `trechos_fts`, `cursos`, `curso_itens`, `progresso_licoes`, `quiz_gerados`, `certificados`, `historico_duvidas`,
`especialistas`, `perguntas`, `opcoes`, `respostas`. Esquema em `backend/schema.sql`.
Senhas com scrypt; sessões por cookie HttpOnly; login bloqueado por 15 min após 5 falhas.

## Configuração da LLM (opcional, em `backend/.env`)
```
ANTHROPIC_API_KEY=sk-ant-...      # ou pela tela de Administração
OUTGPT_MODELO=claude-opus-5-5     # padrão; para gastar menos: claude-haiku-5-5
OUTGPT_ESFORCO=low                # low | medium | high
```

## Comandos úteis (pasta `backend`)
```
python rag.py importar "Nome da Empresa" data/sops_corporativos.csv internos   # importa CSV pela linha de comando
python rag.py reindexar                                                         # refaz o índice de busca
python configurar_llm.py                                                        # liga a IA pelo terminal
python backup.py                                                                # cópia de segurança do banco (backend/backups)
```

## Desenvolvimento
`seed_faker.py` gera respostas de TESTE da pesquisa para desenvolver as telas (`--limpar` remove). Nunca use esses dados como resultado de pesquisa.

## Segurança e privacidade
- Nunca coloque a chave da API no código ou no GitHub: ela fica só em `backend/.env` (ignorado pelo Git).
- `backend/outgpt.db` contém usuários e respostas reais e também não é versionado.
- As perguntas ao assistente são gravadas já anonimizadas.
- O servidor escuta apenas em `127.0.0.1`. Para uso por outras pessoas, hospede-o atrás de HTTPS e defina `OUTGPT_COOKIE_SECURE=1`.
