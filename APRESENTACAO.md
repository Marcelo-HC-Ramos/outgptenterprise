# Apresentação: 5 minutos de slides + vídeo do sistema

**Ordem do dia:** (1) fala de 5 minutos com os slides, (2) vídeo do sistema funcionando (~3 minutos), (3) perguntas.

- **Slides (8, com poucas palavras):** https://claude.ai/artifact/2iK2GM3wzUJKyLYk4Aeo7X
  O link é privado (só a sua conta abre). Para levar à apresentação, **baixe o deck em .pptx ou PDF** pela opção de baixar/exportar do próprio deck. As falas estão nas **notas do orador** de cada slide e também abaixo.
- **Vídeo:** você grava seguindo o roteiro da seção 2.
- **Plano B ao vivo:** se o vídeo não tocar, o roteiro de demonstração ao vivo está no [DEMO.md](DEMO.md).

---

## 1. Roteiro da fala (5:00)

Fale devagar, em frases curtas. Cada slide tem 1 ideia; não leia o slide, conte a história.

| Tempo | Slide | O que dizer |
|---|---|---|
| **0:00 – 0:15** | **1. Capa** | "Bom dia, professor e investidores. Somos o Marcelo e o Victor e vamos apresentar o **OutGPT Enterprise**: uma plataforma com inteligência artificial que acelera o onboarding de novos colaboradores e responde sempre **citando a fonte**." |
| **0:15 – 0:50** | **2. O problema** | "Todo novo colaborador chega com dezenas de dúvidas, e o caminho mais fácil é perguntar para quem já sabe. Isso **interrompe os mais experientes** o dia inteiro. Os manuais existem, mas ficam espalhados e desatualizados, então **quase ninguém consulta**. E quando um profissional sai, **o conhecimento que só ele tinha vai embora junto**." |
| **0:50 – 1:35** | **3. A solução** | "O OutGPT lê os procedimentos da própria empresa e os transforma em um **assistente e em cursos**. O manual entra; antes de qualquer consulta à IA, **dados pessoais como CPF, e-mail e telefone são mascarados**; a IA busca o trecho certo no manual; e a resposta chega **com a fonte**, para conferir. Se o assunto não está nos manuais, ele **recusa em vez de inventar**. Isso se chama RAG: a IA responde com base nos documentos, não de memória." |
| **1:35 – 2:30** | **4. Três razões para o RH** | "Para o RH, o valor está em três pontos. **Onboarding mais curto**: os seniores deixam de ser interrompidos. **LGPD desde o projeto**: CPF, e-mail, CNPJ e telefone são mascarados antes da IA. E **respostas auditáveis**: cada uma cita o documento de origem. Em um teste interno com 20 perguntas em linguagem natural, **18 encontraram o procedimento certo**." |
| **2:30 – 3:10** | **5. Engajamento** | "Além do assistente, o sistema gera **cursos** a partir dos manuais. Cada pessoa tem um **departamento** e vê só as normas e a trilha da sua área. Para combater a baixa retenção dos treinamentos de compliance e ética, há **níveis, conquistas e certificado verificável**. E o RH ganha um relatório que mostra **quais materiais são mais difíceis de assimilar**, sem identificar ninguém." |
| **3:10 – 4:05** | **6. Modelo de negócio** | "O modelo é **híbrido**. Na assinatura cobramos uma **implantação de R$ 1.500 a R$ 7.000**, que cobre a organização dos manuais e a calibração da privacidade. Depois, uma assinatura mensal em três planos: **Starter, R$ 497**, até 30 pessoas; **Growth, R$ 1.497**, até 150 pessoas e vários departamentos; e **Enterprise, a partir de R$ 3.497**, sem limite e com SLA. Com esses valores sugeridos, um cliente Growth gera de **R$ 21.964 a R$ 24.964 no primeiro ano**." *(Diga que os valores são sugeridos e serão validados com clientes-piloto.)* |
| **4:05 – 4:35** | **7. Onde estamos** | "Hoje já funcionam a IA com fonte citada, o mascaramento de dados, várias empresas e departamentos, e os cursos com conquistas e relatório de engajamento, tudo testado automaticamente. Os próximos passos: **Slack e Teams, API, regras de dados por cliente, cotas por plano** e, principalmente, um **piloto com clientes reais**." |
| **4:35 – 5:00** | **8. Veja funcionando** | "Para fechar: o OutGPT transforma os manuais da empresa em um assistente que **cita a fonte**, **protege os dados** e mostra ao RH **onde as pessoas travam**. Agora vamos ver o sistema funcionando, em um vídeo. Obrigado!" → **dê play no vídeo.** |

**Não diga** "zero alucinação" nem "blindagem jurídica total". Diga **"respostas ancoradas em fontes, com rastreabilidade"**. O mascaramento cobre e-mail, CPF, CNPJ e telefone (nomes e endereços, ainda não).

---

## 2. Roteiro do vídeo (3 a 3,5 minutos)

### Antes de gravar (15 minutos)
1. Ligue o sistema: dois cliques em **`INICIAR.bat`** (abre em http://localhost:8000) e entre como dono.
2. Dois cliques em **`DEMO_CRIAR.bat`**: cria departamentos, colaboradores simulados e o histórico de estudo. **Anote a senha do "Colaborador Demo"** (aparece uma vez).
3. Abra uma **janela anônima** do navegador, entre em http://localhost:8000 como `colaborador@demo.outgpt` e deixe-a pronta.
4. Faça **uma pergunta de aquecimento** no Assistente (a primeira resposta é mais lenta).
5. Deixe a tela limpa: navegador em tela cheia (F11), zoom em 110% a 125%, sem abas extras, notificações desligadas (Windows: Não perturbe).
6. Ensaie uma vez sem gravar. **Para gravar no Windows:** `Win + Alt + R` (Xbox Game Bar) grava a janela com áudio; ou o OBS Studio. Edite, se quiser, no Clipchamp (já vem no Windows 11).
7. **Depois de gravar:** dois cliques em **`DEMO_REMOVER.bat`** e exclua o arquivo de exemplo da Biblioteca.

### Cenas
Você pode **gravar com a sua voz** ou **gravar sem voz e narrar ao vivo** enquanto o vídeo toca (o mais simples; o texto abaixo serve para os dois).

| Tempo | Cena (o que aparece e o que fazer) | Narração |
|---|---|---|
| **0:00 – 0:15** | **Início.** Logado como dono: mostre a busca, os cursos e o painel. | "Este é o OutGPT Enterprise funcionando de verdade. Vou mostrar o caminho de um colaborador e o do RH." |
| **0:15 – 0:55** | **Assistente.** Digite: `Como faço para trabalhar de casa e acessar a rede da empresa?` Quando a resposta terminar, **clique na fonte** (📎) para abrir o manual. | "A resposta vem do manual da empresa, com passos claros. E mostra a fonte: ao clicar, vemos o trecho oficial. Nada é inventado." |
| **0:55 – 1:20** | **LGPD.** Digite: `Meu CPF é 123.456.789-09, como peço reembolso de viagem?` Aponte o aviso **"Dados sensíveis mascarados antes da consulta: CPF"**. | "Se alguém digita um CPF, ele é mascarado antes de a pergunta chegar à IA. A privacidade está no desenho do produto." |
| **1:20 – 1:35** | **Recusa.** Digite: `Qual é o valor do vale-refeição mensal da empresa?` | "E quando o assunto não está nos manuais, o assistente recusa em vez de inventar." |
| **1:35 – 2:05** | **Conteúdo da empresa.** *Biblioteca > Enviar arquivo*: escolha `backend/data/exemplo_politica_de_viagens.txt` e envie. Volte ao Assistente e digite: `Quanto posso gastar por noite de hotel numa viagem e quanto tempo tenho para prestar contas?` | "O RH sobe um documento e, em segundos, o assistente já responde com base nele: R$ 380 por noite e 5 dias úteis. E ainda avisa que outro manual traz um prazo diferente." |
| **2:05 – 2:25** | **Departamentos.** *Usuários*: mostre o painel RH, TI e Operações. *Biblioteca > Novo conteúdo*: mostre **"Quem pode ver (departamentos)"** e feche sem salvar. | "Cada pessoa tem um departamento e vê só as normas e a trilha da sua área, na biblioteca, nos cursos e nas respostas." |
| **2:25 – 2:50** | **Colaborador** *(janela anônima)*. Início ("Sua trilha: TI"); abra o curso, **responda a pergunta de verificação**; aparece **"Nova conquista!"**; abra **Conquistas**. | "Agora a visão do colaborador. Ele aprende em cursos gerados dos manuais, responde perguntas de verificação e ganha conquistas, níveis e certificado: é o que combate a baixa retenção dos treinamentos." |
| **2:50 – 3:15** | **RH.** *Engajamento*: mostre os cartões **"Materiais que merecem atenção"** (Difícil e Atenção) e role a tabela. | "E o RH enxerga quais materiais são mais difíceis: quanto tempo as pessoas gastam, quantas erram na primeira tentativa e quantas abandonam. Tudo agregado, sem nomes." |
| **3:15 – 3:25** | **Encerramento.** Volte ao Início (ou à página `/negocio.html`). | "Esse é o OutGPT Enterprise: onboarding mais rápido, com IA que cita a fonte e protege os dados. Obrigado!" |

> **Dicas:** (1) digite devagar ou cole as perguntas prontas; (2) se uma resposta demorar mais que 10 s, corte na edição; (3) se a internet falhar, regrave só aquela cena; (4) o relatório de Engajamento mostra o KPI "conclusão média" baixo porque a demonstração cobre só um curso: **foque nos cartões**, não nesse número.

---

## 3. Para as perguntas (professor e investidores)
As respostas prontas (como evita inventar, LGPD, custo da IA, escala, segurança, o que falta) estão no [DEMO.md](DEMO.md), seção "Para as perguntas". Pontos que mais caem:
- **Limites dos planos:** são comerciais; o bloqueio automático por cota ainda não existe (roadmap).
- **Preços:** são sugeridos e serão validados com um piloto.
- **Custo da IA:** cerca de 1.200 tokens de entrada e 170 de saída por pergunta; confira o preço atual do modelo antes de falar números.

## 4. Checklist final
- [ ] Deck baixado (.pptx ou PDF) e testado no computador da apresentação
- [ ] Vídeo gravado, tocando no player do computador, com som
- [ ] `DEMO_REMOVER.bat` executado depois de gravar
- [ ] Notebook na tomada, suspensão desligada, internet testada
- [ ] Chave da API revogada depois do evento (ela foi compartilhada no chat)
