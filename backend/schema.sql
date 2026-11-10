-- OutGPT Enterprise - esquema SQLite (versão 2: multiempresa, com autenticação)
PRAGMA foreign_keys = ON;

-- ===== Empresas (clientes da plataforma) =====
CREATE TABLE IF NOT EXISTS empresas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL UNIQUE,
  ativa INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0,1)),
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ===== Usuários =====
-- tipo: master            dono do sistema (sem empresa; vê e administra tudo)
--       admin             administrador de uma empresa (gerencia conteúdos e usuários dela)
--       funcionario       funcionário da empresa
--       colaborador_interno  colaborador com vínculo interno (ex.: estagiário, temporário)
--       colaborador_externo  prestador/consultor externo (só vê conteúdos marcados como 'todos')
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE,
  nome TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  senha_hash TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('master','admin','funcionario','colaborador_interno','colaborador_externo')),
  ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
  tentativas_falhas INTEGER NOT NULL DEFAULT 0,
  bloqueado_ate TEXT,
  ultimo_login TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  CHECK ((tipo = 'master' AND empresa_id IS NULL) OR (tipo <> 'master' AND empresa_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_usuarios_empresa ON usuarios(empresa_id);

-- Sessões de login (guarda só o hash do token; o token vai no cookie)
CREATE TABLE IF NOT EXISTS sessoes (
  token_hash TEXT PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  criada_em TEXT NOT NULL DEFAULT (datetime('now')),
  expira_em TEXT NOT NULL
);

-- ===== Conteúdos das empresas (base de conhecimento do RAG) =====
-- visibilidade: 'todos'    = qualquer usuário da empresa, inclusive colaboradores externos
--               'internos' = somente admin, funcionários e colaboradores internos
CREATE TABLE IF NOT EXISTS conteudos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  codigo TEXT NOT NULL,
  titulo TEXT NOT NULL,
  categoria TEXT NOT NULL,
  texto TEXT NOT NULL,
  pergunta_exemplo TEXT,
  resposta_exemplo TEXT,                -- resposta aprovada (usada nos questionários dos cursos)
  arquivo_nome TEXT,                   -- preenchido quando o conteúdo veio de um arquivo enviado
  contem_pii INTEGER NOT NULL DEFAULT 0 CHECK (contem_pii IN (0,1)),
  visibilidade TEXT NOT NULL DEFAULT 'internos' CHECK (visibilidade IN ('todos','internos')),
  criado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (empresa_id, codigo)
);
CREATE INDEX IF NOT EXISTS idx_conteudos_empresa ON conteudos(empresa_id);

-- ===== Índice de palavras-chave (busca híbrida: complementa os vetores do ChromaDB) =====
CREATE VIRTUAL TABLE IF NOT EXISTS trechos_fts USING fts5(
  texto, conteudo_id UNINDEXED, empresa_id UNINDEXED, visibilidade UNINDEXED, ordem UNINDEXED,
  tokenize = 'unicode61 remove_diacritics 2'
);
-- ===== Histórico de perguntas ao assistente (a pergunta é gravada já anonimizada) =====
CREATE TABLE IF NOT EXISTS historico_duvidas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE,
  pergunta TEXT NOT NULL,
  resposta TEXT NOT NULL,
  fontes TEXT,                          -- JSON: [{"codigo","titulo"}]
  gerado_por_ia INTEGER NOT NULL DEFAULT 0,
  modelo TEXT,
  tokens_entrada INTEGER,
  tokens_saida INTEGER,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_historico_empresa ON historico_duvidas(empresa_id, criado_em);

-- ===== Cursos (gerados a partir dos conteúdos da empresa) =====
CREATE TABLE IF NOT EXISTS cursos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  titulo TEXT NOT NULL,
  descricao TEXT,
  categoria TEXT,                       -- categoria de origem (cursos automáticos)
  nivel TEXT NOT NULL DEFAULT 'Iniciante' CHECK (nivel IN ('Iniciante','Intermediário','Avançado')),
  ordem INTEGER NOT NULL DEFAULT 0,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_cursos_empresa ON cursos(empresa_id);

CREATE TABLE IF NOT EXISTS curso_itens (   -- lições de um curso, na ordem
  curso_id INTEGER NOT NULL REFERENCES cursos(id) ON DELETE CASCADE,
  conteudo_id INTEGER NOT NULL REFERENCES conteudos(id) ON DELETE CASCADE,
  ordem INTEGER NOT NULL,
  PRIMARY KEY (curso_id, conteudo_id)
);

CREATE TABLE IF NOT EXISTS progresso_licoes (
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  curso_id INTEGER NOT NULL REFERENCES cursos(id) ON DELETE CASCADE,
  conteudo_id INTEGER NOT NULL REFERENCES conteudos(id) ON DELETE CASCADE,
  concluida_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  acertou INTEGER,                      -- resultado da pergunta de verificação (NULL = não respondida)
  PRIMARY KEY (usuario_id, curso_id, conteudo_id)
);
-- ===== Pesquisa com especialistas =====
CREATE TABLE IF NOT EXISTS especialistas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  email TEXT,
  cargo TEXT NOT NULL,
  organizacao TEXT NOT NULL,
  tipo_organizacao TEXT NOT NULL CHECK (tipo_organizacao IN ('Empresa','Instituição de ensino','Consultoria / outro')),
  anos_experiencia INTEGER CHECK (anos_experiencia BETWEEN 0 AND 60),
  consentimento INTEGER NOT NULL DEFAULT 1 CHECK (consentimento IN (0,1)),
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS perguntas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ordem INTEGER NOT NULL UNIQUE,
  texto TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('escala','unica','multipla','aberta')),
  obrigatoria INTEGER NOT NULL DEFAULT 1 CHECK (obrigatoria IN (0,1))
);

CREATE TABLE IF NOT EXISTS opcoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pergunta_id INTEGER NOT NULL REFERENCES perguntas(id) ON DELETE CASCADE,
  ordem INTEGER NOT NULL,
  texto TEXT NOT NULL,
  UNIQUE (pergunta_id, ordem)
);

CREATE TABLE IF NOT EXISTS respostas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  especialista_id INTEGER NOT NULL REFERENCES especialistas(id) ON DELETE CASCADE,
  pergunta_id INTEGER NOT NULL REFERENCES perguntas(id) ON DELETE CASCADE,
  opcao_id INTEGER REFERENCES opcoes(id) ON DELETE CASCADE,   -- unica / multipla
  valor_escala INTEGER CHECK (valor_escala BETWEEN 1 AND 5),   -- escala
  texto_livre TEXT,                                            -- aberta
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_respostas_pergunta ON respostas(pergunta_id);
CREATE INDEX IF NOT EXISTS idx_respostas_especialista ON respostas(especialista_id);
