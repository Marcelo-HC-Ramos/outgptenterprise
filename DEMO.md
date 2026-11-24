# Roteiro de apresentação (5 minutos)

Tudo abaixo foi testado com a IA real (Claude). O roteiro mostra o produto funcionando e fecha com o modelo de negócio para os investidores.

## Antes de começar (faça 10 minutos antes)
1. **Ligue o sistema:** dois cliques em **`INICIAR.bat`** (abre em http://localhost:8000) e entre com o seu login de dono. Se for projetar pelo endereço público, use **`PUBLICAR.bat`**.
2. **Crie os dados de demonstração:** dois cliques em **`DEMO_CRIAR.bat`**. Ele cria departamentos (RH, TI, Operações), 9 colaboradores simulados e o histórico de estudo deles; sem isso o relatório de engajamento fica vazio.
   **Anote a senha do "Colaborador Demo"** (aparece uma única vez). Os outros 9 não têm senha.
3. **Confira a IA:** no **Assistente** deve aparecer o selo verde **"IA ativa · claude-opus-5-5"**. Faça **uma pergunta de aquecimento** (a primeira resposta leva ~8 s; as seguintes, 2 a 5 s).
4. **Deixe abertas 3 abas/janelas:** (a) o sistema logado como dono; (b) uma **janela anônima já logada como Colaborador Demo** (`colaborador@demo.outgpt`); (c) **`/negocio.html`**.
5. Notebook na tomada, suspensão desligada, internet ok. Sem internet o assistente ainda acha os manuais, só não escreve a resposta com a IA.
6. **Depois da apresentação:** dois cliques em **`DEMO_REMOVER.bat`** para apagar tudo que foi criado.

## Roteiro cronometrado
| Tempo | O que mostrar | O que dizer |
|---|---|---|
| **0:00 – 0:30** | Tela inicial | "Empresas perdem tempo e conhecimento no onboarding: o novato interrompe os seniores com dúvidas repetidas. O OutGPT transforma os procedimentos (SOPs) da empresa em um **assistente com IA que cita a fonte** e em **cursos**." |
| **0:30 – 1:50** | **Assistente.** (1) `Como faço para trabalhar de casa e acessar a rede da empresa?` Clique na **fonte** para abrir o trecho oficial. (2) `Meu CPF é 123.456.789-09, como peço reembolso de viagem?` e aponte o aviso **"Dados sensíveis mascarados"**. (3) `Qual é o valor do vale-refeição mensal da empresa?` | (1) "A resposta vem dos documentos e mostra a fonte." (2) "**LGPD:** CPF, e-mail, CNPJ e telefone são mascarados **antes** de a pergunta chegar à IA." (3) "Se não está nos manuais, ele **recusa em vez de inventar**." |
| **1:50 – 2:35** | **Biblioteca > Enviar arquivo:** `backend/data/exemplo_politica_de_viagens.txt`. Pergunte: `Quanto posso gastar por noite de hotel numa viagem e quanto tempo tenho para prestar contas?` | "O conteúdo da empresa entra em segundos. A IA responde **R$ 380 por noite e 5 dias úteis** e ainda **avisa que outro manual traz um prazo diferente**." *(depois exclua o arquivo na Biblioteca)* |
| **2:35 – 3:15** | **Usuários:** painel de departamentos. **Biblioteca:** abra "Novo conteúdo" e mostre **"Quem pode ver (departamentos)"**. | "Cada pessoa tem um **departamento** e vê só as normas e a **trilha da sua área**; isso vale na biblioteca, nos cursos e nas respostas do assistente." |
| **3:15 – 3:50** | **Janela do Colaborador Demo:** Início ("Sua trilha: TI"), abra um curso, **responda a pergunta de verificação** e aparece **"Nova conquista!"**. Mostre **Conquistas** e os certificados **🔒 bloqueado / 🔓 desbloqueado**. | "Gamificação para vencer a baixa retenção de treinamentos de compliance: **níveis, sequência, conquistas e certificado verificável**." |
| **3:50 – 4:25** | **Engajamento (como dono):** "Materiais que merecem atenção" e a tabela. | "O RH vê **quais materiais são mais difíceis de assimilar**: erro na 1ª tentativa, tempo acima do esperado e abandono, resumidos num índice. Dados **agregados, sem nomes**, com exportação em CSV." |
| **4:25 – 5:00** | **`/negocio.html`** | "**Modelo híbrido:** implantação de R$ 1.500 a R$ 7.000 mais assinatura de **R$ 497, R$ 1.497 e a partir de R$ 3.497 por mês**. Um cliente Growth rende de R$ 21.964 a R$ 24.964 no primeiro ano. Já funciona: IA com fonte, LGPD, multiempresa e departamentos. **Roadmap:** Slack/Teams, API e regras de dados personalizadas." |

**Se faltar tempo, corte** o bloco 1:50–2:35 (upload) ou o 2:35–3:15 (departamentos). **Se algo falhar:** a IA offline ainda mostra o trecho do manual; o restante do sistema não depende da IA.

## Os três argumentos para o RH (do documento de monetização) e onde aparecem
1. **Onboarding mais curto:** assistente, cursos gerados dos SOPs, trilhas por departamento e relatório de engajamento.
2. **LGPD:** mascaramento antes da IA, isolamento entre empresas, acesso por perfil e departamento.
3. **Respostas ancoradas e auditáveis:** fonte citada, recusa sem base, painel de lacunas.

> **Cuidado com as palavras:** não prometa "zero alucinação" nem "blindagem total". O sistema responde com base nos trechos recuperados, cita a fonte e recusa quando não há base, mas nenhuma IA garante zero erro. Diga: **"ancorada em fontes, com rastreabilidade"**. O mascaramento cobre e-mail, CPF, CNPJ e telefone (nomes e endereços ainda não).

## Para as perguntas (professor e investidores)
- **Como ele evita inventar?** Só usa os trechos recuperados dos documentos, cita a fonte e recusa sem base. Em 20 perguntas naturais de teste, 18 acharam o procedimento certo (90%); frases muito vagas podem falhar, e aí ele recusa.
- **E a LGPD?** Mascara e-mail, CPF, CNPJ e telefone antes de chamar a IA. Os trechos dos manuais vão ao provedor da IA, então o cliente deve ser informado (tem o aviso no DEPLOY.md). Regras de dados personalizadas por cliente estão no roadmap.
- **Quanto custa a IA por pergunta?** Medimos cerca de 1.200 tokens de entrada e 170 de saída por pergunta; o modelo menor (`claude-haiku-5-5`) reduz o custo. Confira o preço atual no site do provedor antes de falar números.
- **Os limites dos planos já são aplicados pelo sistema?** Ainda não: usuários e SOPs por plano são limites **comerciais**; o bloqueio automático por cota está no roadmap.
- **Escala?** Várias empresas isoladas na mesma plataforma. O SQLite atende equipes pequenas e médias; para crescer, o próximo passo é um banco gerenciado.
- **Segurança?** Senhas com hash, sessão em cookie protegido, limite de tentativas, proteção contra CSRF, isolamento por empresa e por departamento, e mais de 260 testes automáticos rodando a cada alteração no GitHub.
- **O que falta?** Slack/Teams e API, regras de dados personalizadas, cotas automáticas por plano, painel executivo customizado, cobrança e um piloto com clientes reais para validar os preços.

## Fechamento (arquitetura em 20 segundos, se perguntarem)
RAG: os manuais viram trechos e vetores (ChromaDB, modelo multilíngue) e uma busca por palavras-chave (SQLite FTS) complementa; os trechos mais parecidos vão para o Claude, que responde só com base neles e cita a fonte. Dados pessoais são mascarados antes, cada empresa só enxerga o próprio conteúdo e o acesso é por perfil e departamento.
