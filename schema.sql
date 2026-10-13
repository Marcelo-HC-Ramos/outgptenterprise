-- OutGPT Enterprise - esquema SQLite
PRAGMA foreign_keys = ON;

-- ===== Núcleo da plataforma =====
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  perfil TEXT NOT NULL CHECK (perfil IN ('colaborador','gestor')),
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS documentos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome_arquivo TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('PDF','TXT','DOCX')),
  status TEXT NOT NULL DEFAULT 'Processando' CHECK (status IN ('Processando','Indexado','Erro')),
  enviado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  enviado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
  ordem INTEGER NOT NULL,
  pagina INTEGER,
  texto TEXT NOT NULL,
  UNIQUE (documento_id, ordem)
);

CREATE TABLE IF NOT EXISTS trilhas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  nivel TEXT NOT NULL CHECK (nivel IN ('Iniciante','Intermediário','Avançado'))
);

CREATE TABLE IF NOT EXISTS modulos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trilha_id INTEGER NOT NULL REFERENCES trilhas(id) ON DELETE CASCADE,
  ordem INTEGER NOT NULL,
  titulo TEXT NOT NULL,
  conteudo TEXT NOT NULL,
  documento_id INTEGER REFERENCES documentos(id) ON DELETE SET NULL,
  fonte TEXT,
  UNIQUE (trilha_id, ordem)
);

CREATE TABLE IF NOT EXISTS questoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trilha_id INTEGER NOT NULL REFERENCES trilhas(id) ON DELETE CASCADE,
  enunciado TEXT NOT NULL,
  alternativas TEXT NOT NULL,            -- JSON: ["a","b","c","d"]
  indice_correto INTEGER NOT NULL,
  explicacao TEXT
);

CREATE TABLE IF NOT EXISTS progresso (
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  trilha_id INTEGER NOT NULL REFERENCES trilhas(id) ON DELETE CASCADE,
  percentual INTEGER NOT NULL DEFAULT 0 CHECK (percentual BETWEEN 0 AND 100),
  PRIMARY KEY (usuario_id, trilha_id)
);

CREATE TABLE IF NOT EXISTS historico_duvidas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  pergunta TEXT NOT NULL,
  resposta TEXT NOT NULL,
  fontes TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
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
