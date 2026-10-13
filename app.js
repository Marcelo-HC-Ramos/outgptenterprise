/* OutGPT Enterprise — Front-end (Sprint Zero)
 * SPA em JavaScript puro. Todos os dados abaixo são SIMULADOS (mock) e serão
 * substituídos por chamadas ao backend (Python + RAG + ChromaDB/SQLite). */

// ---------- Dados simulados ----------
const DOCS = [
  { id: 1, nome: "SOP_Abertura_de_Chamados.pdf", tipo: "PDF", chunks: 42, status: "Indexado", data: "2026-09-28" },
  { id: 2, nome: "FAQ_Suporte_Nivel1.txt", tipo: "TXT", chunks: 18, status: "Indexado", data: "2026-09-28" },
  { id: 3, nome: "Manual_VPN_Corporativa.pdf", tipo: "PDF", chunks: 27, status: "Indexado", data: "2026-09-30" },
  { id: 4, nome: "Politica_Reset_de_Senhas.pdf", tipo: "PDF", chunks: 15, status: "Indexado", data: "2026-10-02" },
  { id: 5, nome: "Tutorial_Escalonamento_N2.txt", tipo: "TXT", chunks: 21, status: "Processando", data: "2026-10-10" },
];

const TRILHAS = [
  {
    id: 1, titulo: "Fundamentos do Suporte Técnico", nivel: "Iniciante", progresso: 60,
    modulos: [
      { t: "Como abrir e classificar um chamado", fonte: "SOP_Abertura_de_Chamados.pdf, p. 3",
        c: "Todo chamado deve ser registrado no sistema com título objetivo, descrição do problema, impacto e prioridade. A classificação segue três níveis: Baixa (sem impacto no trabalho), Média (impacto parcial) e Alta (usuário impedido de trabalhar). Chamados de prioridade Alta têm SLA de primeira resposta de 30 minutos." },
      { t: "Atendimento de nível 1 e FAQ", fonte: "FAQ_Suporte_Nivel1.txt, seção 2",
        c: "O nível 1 resolve solicitações recorrentes usando a base de FAQ: instalação de software homologado, acesso a pastas e impressoras. Se a solução não for encontrada em até 15 minutos, o chamado deve ser escalonado." },
      { t: "Quando e como escalonar", fonte: "Tutorial_Escalonamento_N2.txt, seção 1",
        c: "O escalonamento ao nível 2 exige o registro das ações já tentadas, evidências (prints, logs) e o contato do usuário. Nunca escalone sem documentar o que foi testado." },
    ],
    quiz: [
      { q: "Qual o SLA de primeira resposta para chamados de prioridade Alta?", o: ["10 minutos", "30 minutos", "2 horas", "1 dia"], r: 1, e: "Conforme o SOP de abertura de chamados, a prioridade Alta tem SLA de 30 minutos." },
      { q: "Após quanto tempo sem solução o nível 1 deve escalonar?", o: ["5 minutos", "15 minutos", "1 hora", "Nunca"], r: 1, e: "O FAQ do nível 1 define 15 minutos como limite antes do escalonamento." },
    ],
  },
  {
    id: 2, titulo: "Acesso Remoto e VPN", nivel: "Intermediário", progresso: 20,
    modulos: [
      { t: "Instalação do cliente VPN", fonte: "Manual_VPN_Corporativa.pdf, p. 5",
        c: "O cliente VPN homologado deve ser baixado exclusivamente do portal interno de software. Após instalar, utilize suas credenciais corporativas e o segundo fator de autenticação." },
      { t: "Problemas comuns de conexão", fonte: "Manual_VPN_Corporativa.pdf, p. 12",
        c: "Falhas de conexão geralmente decorrem de: relógio do computador desajustado, 2FA expirado ou bloqueio de porta pela rede local. Teste primeiro em outra rede antes de abrir chamado." },
    ],
    quiz: [
      { q: "De onde o cliente VPN deve ser baixado?", o: ["Site do fabricante", "Portal interno de software", "E-mail do colega", "Qualquer loja de apps"], r: 1, e: "Somente o portal interno garante a versão homologada." },
    ],
  },
  {
    id: 3, titulo: "Segurança e Senhas", nivel: "Iniciante", progresso: 0,
    modulos: [
      { t: "Política de redefinição de senhas", fonte: "Politica_Reset_de_Senhas.pdf, p. 2",
        c: "A redefinição de senha só pode ser feita após a validação de identidade do solicitante por meio de dois dados cadastrais ou aprovação do gestor. Senhas temporárias expiram em 24 horas." },
    ],
    quiz: [
      { q: "Em quanto tempo expira uma senha temporária?", o: ["1 hora", "12 horas", "24 horas", "7 dias"], r: 2, e: "A política define validade de 24 horas." },
    ],
  },
];

const RESPOSTAS = [
  { k: ["vpn", "conect"], t: "Falhas de conexão na VPN geralmente decorrem de relógio desajustado, 2FA expirado ou bloqueio de porta pela rede local. Teste em outra rede antes de abrir um chamado.", f: ["Manual_VPN_Corporativa.pdf, p. 12"] },
  { k: ["sla", "prioridade", "chamado"], t: "Chamados de prioridade Alta têm SLA de primeira resposta de 30 minutos. Os chamados devem ter título objetivo, descrição, impacto e prioridade.", f: ["SOP_Abertura_de_Chamados.pdf, p. 3"] },
  { k: ["senha", "reset", "redefin"], t: "A redefinição exige validação de identidade por dois dados cadastrais ou aprovação do gestor. A senha temporária expira em 24 horas.", f: ["Politica_Reset_de_Senhas.pdf, p. 2"] },
  { k: ["escalon", "nível 2", "nivel 2", "n2"], t: "Escalone ao nível 2 após 15 minutos sem solução, registrando as ações testadas, evidências (prints/logs) e contato do usuário.", f: ["FAQ_Suporte_Nivel1.txt, seção 2", "Tutorial_Escalonamento_N2.txt, seção 1"] },
];
const SEM_RESPOSTA = { t: "Não encontrei essa informação nos manuais indexados. Para evitar respostas inventadas, recomendo consultar seu gestor ou abrir um chamado.", f: [] };

let historico = [
  { quando: "12/10 14:02", p: "Como abrir um chamado de prioridade alta?", f: "SOP_Abertura_de_Chamados.pdf" },
  { quando: "11/10 09:40", p: "Qual o prazo da senha temporária?", f: "Politica_Reset_de_Senhas.pdf" },
];

// ---------- Utilidades ----------
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let pendente = null; // pergunta digitada na busca da página inicial

// ---------- Tema ----------
const temaBtn = $("#theme");
function aplicarTema(t) {
  document.documentElement.dataset.theme = t;
  temaBtn.textContent = t === "dark" ? "☀️ Modo claro" : "🌙 Modo escuro";
}
aplicarTema(matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
temaBtn.onclick = () => aplicarTema(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

// ---------- Rotas ----------
window.addEventListener("hashchange", render);
render();
function render() {
  const [, rota = "inicio", arg] = location.hash.split("/");
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.route === rota || (rota === "aula" && a.dataset.route === "trilhas")));
  const telas = { inicio: telaInicio, trilhas: telaTrilhas, aula: () => telaAula(+arg), chat: telaChat, historico: telaHistorico, documentos: telaDocumentos, pesquisa: telaPesquisa, resultados: telaResultados, sobre: telaSobre };
  view.style.animation = "none"; view.offsetHeight; view.style.animation = "";
  (telas[rota] || telaInicio)();
  scrollTo(0, 0);
}

// ---------- Telas ----------
function telaInicio() {
  const prog = Math.round(TRILHAS.reduce((s, t) => s + t.progresso, 0) / TRILHAS.length);
  const t0 = TRILHAS[0];
  view.innerHTML = `
    <section class="hero">
      <h1>Aprenda o trabalho da sua equipe em dias, não em meses.</h1>
      <p>Pergunte qualquer coisa sobre os processos da empresa. O OutGPT responde com base nos manuais e mostra de onde veio a informação.</p>
      <form class="search" id="busca"><input id="busca-q" placeholder="Ex.: Como resolvo um erro de VPN?" aria-label="Pergunte ao assistente" required><button class="btn primary">Perguntar</button></form>
    </section>
    <div class="stats">
      <div class="stat"><div class="ico">📈</div><div><b>${prog}%</b><small>Progresso geral</small></div></div>
      <div class="stat"><div class="ico">🎓</div><div><b>${TRILHAS.length}</b><small>Trilhas</small></div></div>
      <div class="stat"><div class="ico">💬</div><div><b>${historico.length}</b><small>Dúvidas respondidas</small></div></div>
      <div class="stat"><div class="ico">📚</div><div><b>${DOCS.length}</b><small>Documentos</small></div></div>
    </div>
    <div class="section-title"><h2>Continuar aprendendo</h2><a href="#/trilhas">Ver todas →</a></div>
    <div class="card"><div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center">
      <div style="flex:1;min-width:220px"><span class="badge">${t0.nivel}</span><h3 style="margin-top:8px">${esc(t0.titulo)}</h3>
      <div class="progress"><i style="width:${t0.progresso}%"></i></div><small>${t0.progresso}% concluído</small></div>
      <a class="btn primary" href="#/aula/1">Retomar</a></div></div>
    <div class="section-title"><h2>Atalhos</h2></div>
    <div class="grid">
      <a class="card tile" href="#/chat"><div class="thumb">✨</div><h3>Assistente</h3><small>Tire dúvidas com fonte citada.</small></a>
      <a class="card tile" href="#/trilhas"><div class="thumb">🎓</div><h3>Trilhas</h3><small>Cursos gerados dos manuais.</small></a>
      <a class="card tile" href="#/documentos"><div class="thumb">📚</div><h3>Documentos</h3><small>Base de conhecimento indexada.</small></a>
      <a class="card tile" href="#/pesquisa"><div class="thumb">📝</div><h3>Pesquisa</h3><small>Opinião de especialistas sobre a ferramenta.</small></a>
    </div>`;
  $("#busca").onsubmit = e => { e.preventDefault(); pendente = $("#busca-q").value.trim(); location.hash = "#/chat"; };
}

function telaTrilhas() {
  view.innerHTML = `<div class="page-head"><div><h1>Trilhas de aprendizagem</h1><p class="muted">Cursos gerados a partir dos manuais operacionais.</p></div></div>
    <div class="grid">${TRILHAS.map(t => `
      <div class="card"><div class="thumb">${["🛠️", "🔐", "🛡️"][t.id - 1] || "📘"}</div><span class="badge">${t.nivel}</span>
        <h3 style="margin-top:8px">${esc(t.titulo)}</h3>
        <small>${t.modulos.length} módulo(s) • ${t.quiz.length} questão(ões)</small>
        <div class="progress"><i style="width:${t.progresso}%"></i></div><small>${t.progresso}%</small><br><br>
        <a class="btn primary" href="#/aula/${t.id}">${t.progresso ? "Continuar" : "Iniciar"}</a>
      </div>`).join("")}</div>`;
}

function telaAula(id) {
  const t = TRILHAS.find(x => x.id === id) || TRILHAS[0];
  let atual = 0;
  const desenhar = () => {
    const m = t.modulos[atual];
    view.innerHTML = `
      <div class="page-head"><div><a href="#/trilhas" class="muted">← Trilhas</a><h1>${esc(t.titulo)}</h1></div></div>
      <div class="lesson-layout">
        <div class="card"><ul class="modules">${t.modulos.map((x, i) => `<li data-i="${i}" class="${i === atual ? "active" : ""}">${i + 1}. ${esc(x.t)}</li>`).join("")}
          <li data-i="quiz" class="${atual === "quiz" ? "active" : ""}">📝 Questionário</li></ul></div>
        <div class="card lesson-body">${atual === "quiz" ? htmlQuiz(t) : `
          <h2>${esc(m.t)}</h2><p>${esc(m.c)}</p>
          <div class="source">Fonte: ${esc(m.fonte)}</div><br>
          <button class="btn primary" id="prox">${atual < t.modulos.length - 1 ? "Próximo módulo →" : "Ir ao questionário →"}</button>`}
        </div>
      </div>`;
    view.querySelectorAll(".modules li").forEach(li => li.onclick = () => { atual = li.dataset.i === "quiz" ? "quiz" : +li.dataset.i; desenhar(); });
    const prox = $("#prox"); if (prox) prox.onclick = () => { atual = atual < t.modulos.length - 1 ? atual + 1 : "quiz"; desenhar(); };
    if (atual === "quiz") ligarQuiz(t);
  };
  desenhar();
}
function htmlQuiz(t) {
  return `<h2>Questionário de fixação</h2>` + t.quiz.map((q, i) => `
    <div class="quiz-q" data-q="${i}"><strong>${i + 1}. ${esc(q.q)}</strong>
      ${q.o.map((o, j) => `<label class="opt"><input type="radio" name="q${i}" value="${j}"> ${esc(o)}</label>`).join("")}
      <div class="explain hidden"></div></div>`).join("") +
    `<button class="btn primary" id="corrigir">Corrigir</button> <span id="nota" class="badge hidden"></span>`;
}
function ligarQuiz(t) {
  $("#corrigir").onclick = () => {
    let acertos = 0;
    t.quiz.forEach((q, i) => {
      const bloco = view.querySelector(`[data-q="${i}"]`);
      const sel = bloco.querySelector("input:checked");
      bloco.querySelectorAll(".opt").forEach((l, j) => { l.classList.remove("right", "wrong"); if (j === q.r) l.classList.add("right"); else if (sel && +sel.value === j) l.classList.add("wrong"); });
      if (sel && +sel.value === q.r) acertos++;
      const ex = bloco.querySelector(".explain"); ex.textContent = "Gabarito: " + q.e; ex.classList.remove("hidden");
    });
    const n = $("#nota"); n.textContent = `${acertos}/${t.quiz.length} acertos`; n.className = "badge " + (acertos === t.quiz.length ? "ok" : "warn");
  };
}

function telaChat() {
  view.innerHTML = `<div class="page-head"><div><h1>Assistente OutGPT</h1><p class="muted">Respostas baseadas somente nos documentos da empresa.</p></div></div>
    <div class="card chat">
      <div class="messages" id="msgs" aria-live="polite">
        <div class="msg bot">Olá! Sou o assistente de onboarding. Pergunte sobre chamados, VPN, senhas ou escalonamento.</div></div>
      <div class="suggestions">${["Como resolvo erro de VPN?", "Qual o SLA de prioridade alta?", "Como redefinir uma senha?", "Quando escalonar para o N2?"].map(s => `<button class="chip">${s}</button>`).join("")}</div>
      <form class="chat-input" id="chat-form"><input id="q" placeholder="Digite sua dúvida..." autocomplete="off" required><button class="btn primary">Enviar</button></form>
    </div>`;
  const msgs = $("#msgs");
  const add = (cls, html) => { const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d; };
  const perguntar = texto => {
    add("user", esc(texto));
    const w = add("bot typing", "Buscando nos manuais...");
    setTimeout(() => {
      const low = texto.toLowerCase();
      const r = RESPOSTAS.find(x => x.k.some(k => low.includes(k))) || SEM_RESPOSTA;
      w.className = "msg bot";
      w.innerHTML = esc(r.t) + (r.f.length ? `<div class="cites">${r.f.map(f => `<span class="cite">📎 ${esc(f)}</span>`).join("")}</div>` : "");
      historico.unshift({ quando: new Date().toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }), p: texto, f: r.f.length ? r.f.join(", ") : "—" });
      msgs.scrollTop = msgs.scrollHeight;
    }, 700);
  };
  $("#chat-form").onsubmit = e => { e.preventDefault(); const q = $("#q"); perguntar(q.value.trim()); q.value = ""; };
  view.querySelectorAll(".chip").forEach(c => c.onclick = () => perguntar(c.textContent));
  if (pendente) { const p = pendente; pendente = null; perguntar(p); }
}

function telaHistorico() {
  view.innerHTML = `<div class="page-head"><div><h1>Histórico de dúvidas</h1><p class="muted">Perguntas já respondidas pelo assistente.</p></div></div>
    <div class="card table-wrap"><table><thead><tr><th>Quando</th><th>Pergunta</th><th>Fonte</th></tr></thead>
    <tbody>${historico.map(h => `<tr><td>${esc(h.quando)}</td><td>${esc(h.p)}</td><td>${esc(h.f)}</td></tr>`).join("")}</tbody></table></div>`;
}

function telaDocumentos() {
  const linhas = () => DOCS.map(d => `<tr><td>${esc(d.nome)}</td><td>${d.tipo}</td><td>${d.chunks}</td>
    <td><span class="badge ${d.status === "Indexado" ? "ok" : "warn"}">${d.status}</span></td><td>${d.data}</td>
    <td><button class="btn danger" data-del="${d.id}">Remover</button></td></tr>`).join("");
  view.innerHTML = `<div class="page-head"><div><h1>Base de documentos</h1><p class="muted">Ingestão e indexação dos manuais (SOPs, FAQs, tutoriais).</p></div></div>
    <label class="drop card" id="drop" for="file">📤 Arraste arquivos .pdf / .txt aqui ou clique para enviar
      <input type="file" id="file" accept=".pdf,.txt,.docx" multiple hidden></label>
    <div class="card table-wrap"><table><thead><tr><th>Arquivo</th><th>Tipo</th><th>Chunks</th><th>Status</th><th>Data</th><th></th></tr></thead>
    <tbody id="docs">${linhas()}</tbody></table></div>`;
  const refresh = () => { $("#docs").innerHTML = linhas(); ligar(); };
  const ligar = () => view.querySelectorAll("[data-del]").forEach(b => b.onclick = () => { DOCS.splice(DOCS.findIndex(d => d.id === +b.dataset.del), 1); refresh(); });
  const receber = files => [...files].forEach(f => {
    DOCS.push({ id: Date.now() + Math.random(), nome: f.name, tipo: f.name.split(".").pop().toUpperCase(), chunks: Math.max(1, Math.round(f.size / 800)), status: "Processando", data: new Date().toISOString().slice(0, 10) });
    refresh();
  });
  $("#file").onchange = e => receber(e.target.files);
  const drop = $("#drop");
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); receber(e.dataTransfer.files); };
  ligar();
}

function telaSobre() {
  view.innerHTML = `<div class="page-head"><div><h1>Sobre o projeto</h1><p class="muted">Fatec Cotia • Ciência de Dados • Processamento de Linguagem Natural</p></div></div>
    <div class="card"><h2>OutGPT Enterprise</h2>
      <p>Plataforma que usa IA Generativa com RAG para transformar manuais operacionais em trilhas de capacitação e um assistente interativo, acelerando o onboarding e reduzindo a perda de conhecimento tácito (brain drain).</p></div>
    <div class="card"><h2>Equipe</h2><ul><li>Marcelo Henrique do Carmo Ramos</li><li>Victor Henrique Duarte Cardoso</li></ul></div>
    <div class="card"><h2>Stack planejada</h2>
      <p><span class="badge">Python</span> <span class="badge">LLM + RAG</span> <span class="badge">ChromaDB</span> <span class="badge">SQLite</span> <span class="badge">HTML/CSS/JS (front-end)</span></p>
      <p class="muted">Sprint Zero: front-end. Sprint Um (13/10–20/10): base de dados e diagrama ER com CRUD.</p></div>`;
}

// ---------- Pesquisa com especialistas (integrada ao SQLite via server.py) ----------
async function api(url, opts) {
  if (location.protocol === "file:") throw new Error("offline");
  const r = await fetch(url, opts);
  return r.json();
}
const avisoServidor = () => `<div class="card"><h2>Servidor não encontrado</h2>
  <p class="muted">Esta área usa o banco SQLite. Inicie o servidor com <code>python server.py</code> (pasta <code>outgpt-pesquisa</code>) e acesse <strong>http://localhost:8000</strong>.</p></div>`;

async function telaPesquisa() {
  view.innerHTML = `<div class="page-head"><div><h1>Pesquisa com especialistas</h1>
    <p class="muted">Qual a importância do OutGPT para empresas e instituições de ensino? Leva cerca de 3 minutos.</p></div></div><div id="pesq"></div>`;
  let ps;
  try { ps = await api("/api/perguntas"); } catch { $("#pesq").innerHTML = avisoServidor(); return; }
  const campo = (id, rot, extra = "") => `<label class="field">${rot}<input id="${id}" ${extra}></label>`;
  const bloco = p => {
    let corpo;
    if (p.tipo === "escala") corpo = `<div class="scale">${[1, 2, 3, 4, 5].map(n => `<label><input type="radio" name="q${p.id}" value="${n}" hidden>${n}</label>`).join("")}</div><div class="legend"><span>Baixa</span><span>Alta</span></div>`;
    else if (p.tipo === "aberta") corpo = `<textarea name="q${p.id}" maxlength="2000" placeholder="Escreva aqui (opcional)"></textarea>`;
    else corpo = p.opcoes.map(o => `<label class="opt"><input type="${p.tipo === "unica" ? "radio" : "checkbox"}" name="q${p.id}" value="${o.id}"><span>${esc(o.texto)}</span></label>`).join("");
    return `<div class="card" data-q="${p.id}"><h2><span class="q-num">${p.ordem}</span>${esc(p.texto)}${p.obrigatoria ? " *" : ""}</h2>${corpo}</div>`;
  };
  $("#pesq").innerHTML = `<form id="pform" novalidate>
    <div class="card"><h2>Sobre você</h2>
      <div class="row2">${campo("p-nome", "Nome *", 'maxlength="120"')}${campo("p-email", "E-mail (opcional)", 'type="email" maxlength="160"')}</div>
      <div class="row2">${campo("p-cargo", "Cargo / função *", 'maxlength="120"')}${campo("p-org", "Organização *", 'maxlength="160"')}</div>
      <div class="row2"><label class="field">Tipo de organização *<select id="p-tipo"><option value="">Selecione...</option><option>Empresa</option><option>Instituição de ensino</option><option>Consultoria / outro</option></select></label>
        ${campo("p-anos", "Anos de experiência", 'type="number" min="0" max="60"')}</div></div>
    ${ps.map(bloco).join("")}
    <div class="card"><label class="opt" style="margin:0"><input type="checkbox" id="p-ok"><span class="muted">Concordo que minhas respostas sejam usadas, de forma acadêmica, no trabalho de PLN da Fatec Cotia, em conformidade com a LGPD.</span></label></div>
    <button class="btn primary" id="p-enviar">Enviar respostas</button><div id="p-ret" role="status"></div></form>`;

  $("#pform").onsubmit = async e => {
    e.preventDefault();
    const ret = $("#p-ret"); ret.innerHTML = "";
    document.querySelectorAll(".card.err").forEach(c => c.classList.remove("err"));
    const respostas = {};
    for (const p of ps) {
      const b = view.querySelector(`[data-q="${p.id}"]`);
      const marcados = [...b.querySelectorAll("input:checked")].map(i => +i.value);
      respostas[p.id] = p.tipo === "multipla" ? marcados : p.tipo === "aberta" ? b.querySelector("textarea").value.trim() : (marcados[0] ?? null);
      const vazio = respostas[p.id] === null || respostas[p.id] === "" || (Array.isArray(respostas[p.id]) && !respostas[p.id].length);
      if (p.obrigatoria && vazio) { b.classList.add("err"); b.scrollIntoView({ behavior: "smooth", block: "center" }); ret.innerHTML = `<div class="msg bad">Responda a pergunta ${p.ordem}.</div>`; return; }
    }
    const especialista = { nome: $("#p-nome").value, email: $("#p-email").value, cargo: $("#p-cargo").value, organizacao: $("#p-org").value, tipo_organizacao: $("#p-tipo").value, anos_experiencia: $("#p-anos").value, consentimento: $("#p-ok").checked };
    $("#p-enviar").disabled = true;
    try {
      const j = await api("/api/enviar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ especialista, respostas }) });
      if (j.ok) { view.innerHTML = `<div class="card" style="text-align:center;padding:48px 22px"><div class="thumb" style="max-width:120px;margin:0 auto 16px">🎉</div><h1>Obrigado!</h1><p class="muted">${esc(j.mensagem)}</p><a class="btn primary" href="#/resultados">Ver resultados</a></div>`; return; }
      ret.innerHTML = `<div class="msg bad">${esc(j.mensagem)}</div>`;
    } catch { ret.innerHTML = `<div class="msg bad">Falha de conexão com o servidor.</div>`; }
    $("#p-enviar").disabled = false;
  };
}

async function telaResultados() {
  view.innerHTML = `<div class="page-head"><div><h1>Resultados da pesquisa</h1><p class="muted" id="r-resumo">Carregando...</p></div>
    <div><a class="btn" href="/api/exportar.csv">⬇ Exportar CSV</a> <a class="btn primary" href="#/pesquisa">Responder</a></div></div><div id="r-out"></div>`;
  let d;
  try { d = await api("/api/resultados"); } catch { $("#r-out").innerHTML = avisoServidor(); $("#r-resumo").textContent = ""; return; }
  const tipos = Object.entries(d.por_tipo).map(([k, v]) => `${esc(k)}: ${v}`).join(" • ");
  $("#r-resumo").innerHTML = `${d.total} especialista(s)${tipos ? " • " + tipos : ""}`;
  const barra = (rot, n, max) => `<div class="bar"><span>${esc(rot)}</span><div class="track"><i style="width:${max ? n / max * 100 : 0}%"></i></div><b>${n}</b></div>`;
  $("#r-out").innerHTML = d.perguntas.map(p => {
    let corpo;
    if (p.tipo === "escala") {
      const max = Math.max(...Object.values(p.distribuicao), 0);
      corpo = `<div class="media">${p.media ?? "—"} <small class="muted">média (${p.n} resp.)</small></div>` + Object.entries(p.distribuicao).map(([k, v]) => barra("Nota " + k, v, max)).join("");
    } else if (p.tipo === "aberta") {
      corpo = p.textos.length ? p.textos.map(t => `<blockquote>${esc(t)}</blockquote>`).join("") : `<span class="muted">Sem comentários.</span>`;
    } else {
      const max = Math.max(...p.opcoes.map(o => o.n), 0);
      corpo = p.opcoes.map(o => barra(o.texto, o.n, max)).join("");
    }
    return `<div class="card"><h2><span class="q-num">${p.ordem}</span>${esc(p.texto)}</h2>${corpo}</div>`;
  }).join("");
}
