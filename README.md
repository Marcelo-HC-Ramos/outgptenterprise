# OutGPT - Base de dados SQLite e formulario de pesquisa

## Como usar
```
python init_db.py     # cria outgpt.db (use --reset para recriar do zero)
python server.py      # http://localhost:8000
```
- Formulario: http://localhost:8000
- Resultados agregados: http://localhost:8000/resultados (com exportacao CSV)

Somente biblioteca padrao do Python 3 (sqlite3, http.server). Sem instalacao.

## Banco (outgpt.db)
- Nucleo da plataforma: usuarios, documentos, chunks, trilhas, modulos, questoes, progresso, historico_duvidas
- Pesquisa: especialistas, perguntas, opcoes, respostas
O formulario e montado a partir das tabelas perguntas/opcoes: alterar uma pergunta no banco altera o formulario.
Tipos de pergunta: escala (1-5), unica, multipla, aberta.

## As 7 perguntas
1. Importancia de reduzir o tempo de onboarding com IA generativa (escala 1-5)
2. Principais desafios na transmissao de conhecimento (multipla)
3. Confianca em assistente de IA com RAG e fonte citada (escala 1-5)
4. Aplicacao de maior valor em instituicoes de ensino (unica)
5. Impacto na reducao da sobrecarga de seniores/docentes (escala 1-5)
6. Principais riscos e barreiras de adocao (multipla)
7. Recomendacoes e comentarios finais (aberta)
Antes das perguntas ha um bloco "Sobre voce" (nome, cargo, organizacao, tipo, experiencia) e consentimento LGPD.

## Para compartilhar com especialistas
O servidor escuta apenas em 127.0.0.1. Para outras pessoas responderem, e preciso hospedar o servidor
(ou usar um tunel temporario) ou aplicar o formulario na sua maquina e exportar os resultados.
