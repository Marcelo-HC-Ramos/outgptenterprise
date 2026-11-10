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
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let pendente = null; // pergunta digitada na busca da página inicial
const estado = { usuario: null, demo: false, empresas: [], empresaId: null };
const ROTULOS = { master: "Master (dono)", admin: "Administrador", funcionario: "Funcionário", colaborador_interno: "Colaborador interno", colaborador_externo: "Colaborador externo" };
const ehAdmin = () => ["master", "admin"].includes(estado.usuario?.tipo);
const ehMaster = () => estado.usuario?.tipo === "master";
const quando = s => s ? s.replace("T", " ").slice(0, 16) : "—";

// Com o servidor Python há login e banco SQLite. Sem ele (GitHub Pages / arquivo local) roda em modo demonstração.
async function api(url, opts = {}) {
  const init = { method: opts.method || "GET", headers: {}, credentials: "same-origin" };
  if (init.method !== "GET") { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body ?? {}); }
  const r = await fetch(url, init);
  let d = null; try { d = await r.json(); } catch { /* corpo vazio */ }
  if (r.status === 401 && url !== "/api/login") { mostrarLogin("Sua sessão expirou. Entre novamente."); throw Object.assign(new Error("sessão expirada"), { status: 401 }); }
  if (!r.ok) throw Object.assign(new Error(d?.mensagem || `Erro ${r.status}`), { status: r.status });
  return d;
}

// ---------- Tema ----------
const temaBtn = $("#theme");
function aplicarTema(t) {
  document.documentElement.dataset.theme = t;
  temaBtn.textContent = t === "dark" ? "☀️ Modo claro" : "🌙 Modo escuro";
}
aplicarTema(matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
temaBtn.onclick = () => aplicarTema(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

// ---------- Janelas (modais) ----------
function janela(titulo, corpo, { salvar = "Salvar", aoSalvar = null } = {}) {
  const d = document.createElement("dialog");
  d.className = "modal";
  d.innerHTML = `<form method="dialog"><h2>${esc(titulo)}</h2><div class="modal-body">${corpo}</div><div id="j-erro" class="alerta bad hidden" role="alert"></div>
    <div class="modal-acoes"><button type="button" class="btn" data-fechar>${aoSalvar ? "Cancelar" : "Fechar"}</button>${aoSalvar ? `<button class="btn primary" id="j-salvar">${esc(salvar)}</button>` : ""}</div></form>`;
  document.body.appendChild(d);
  const fechar = () => { if (d.open) d.close(); d.remove(); };     // remove explicitamente (não depende do evento "close")
  d.querySelector("[data-fechar]").onclick = fechar;
  d.addEventListener("close", () => d.remove());                   // fechamento pela tecla Esc
  if (aoSalvar) d.querySelector("form").onsubmit = async e => {
    e.preventDefault();
    const btn = $("#j-salvar", d); btn.disabled = true;
    try { await aoSalvar(d); fechar(); } catch (err) { const el = $("#j-erro", d); el.textContent = err.message; el.classList.remove("hidden"); btn.disabled = false; }
  };
  d.fechar = fechar;
  d.showModal();
  return d;
}
const confirmar = msg => new Promise(res => {
  const d = janela("Confirmar", `<p>${esc(msg)}</p>`, { salvar: "Confirmar", aoSalvar: async () => res(true) });
  d.addEventListener("close", () => res(false));            // Esc ou Cancelar: a promessa já resolvida ignora este valor
  d.querySelector("[data-fechar]").addEventListener("click", () => res(false));
});

// ---------- Login / sessão ----------
function mostrarLogin(aviso) {
  estado.usuario = null;
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  const e = $("#login-erro"); e.textContent = aviso || ""; e.classList.toggle("hidden", !aviso);
}
function entrar(usuario) {
  estado.usuario = usuario;
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-nome").textContent = usuario.nome;
  $("#user-papel").textContent = ROTULOS[usuario.tipo] + (usuario.empresa ? " · " + usuario.empresa : "");
  $("#avatar").textContent = usuario.nome.split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();
  $("#banner-demo").classList.toggle("hidden", !estado.demo);
  $(".user-acoes").classList.toggle("hidden", estado.demo);
  document.querySelectorAll("#nav a").forEach(a => {
    const so = a.dataset.so;   // restrição de perfil: "admin" (master+admin) | "master"
    a.classList.toggle("hidden", Boolean((so === "admin" && !ehAdmin()) || (so === "master" && !ehMaster()) || (a.dataset.servidor && estado.demo)));
  });
  carregarEmpresas().finally(render);
}
async function carregarEmpresas() {
  if (estado.demo || !ehMaster()) return;
  try { estado.empresas = (await api("/api/empresas")).itens; } catch { estado.empresas = []; }
  if (!estado.empresas.some(e => e.id === estado.empresaId)) estado.empresaId = estado.empresas[0]?.id ?? null;
}
// Seletor de empresa (somente o master administra mais de uma)
const seletorEmpresa = () => !ehMaster() ? "" : estado.empresas.length
  ? `<label class="seletor">Empresa <select id="sel-empresa">${estado.empresas.map(e => `<option value="${e.id}" ${e.id === estado.empresaId ? "selected" : ""}>${esc(e.nome)}</option>`).join("")}</select></label>`
  : `<span class="alerta demo">Crie uma empresa primeiro (menu Empresas).</span>`;
function ligarSeletorEmpresa(fn) {
  const s = $("#sel-empresa"); if (s) s.onchange = () => { estado.empresaId = +s.value; fn(); };
}
const qEmpresa = () => ehMaster() && estado.empresaId ? `?empresa_id=${estado.empresaId}` : "";

$("#login-form").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("#login-btn"); btn.disabled = true;
  try {
    const u = await api("/api/login", { method: "POST", body: { email: $("#email").value, senha: $("#senha").value } });
    $("#senha").value = "";
    location.hash = "#/inicio";
    entrar(u);
  } catch (err) { mostrarLogin(err.message); }
  btn.disabled = false;
});
$("#sair").onclick = async () => { try { await api("/api/logout", { method: "POST" }); } catch { /* já saiu */ } mostrarLogin(); };
$("#trocar-senha").onclick = () => janela("Alterar senha", `
  <label class="field">Senha atual<input type="password" id="s-atual" autocomplete="current-password" required></label>
  <label class="field">Nova senha (mín. 10 caracteres, com letras e números)<input type="password" id="s-nova" autocomplete="new-password" required></label>`,
  { aoSalvar: async () => { await api("/api/senha", { method: "POST", body: { atual: $("#s-atual").value, nova: $("#s-nova").value } }); } });

async function iniciar() {
  let r = null;
  if (location.protocol !== "file:") { try { r = await fetch("/api/eu", { credentials: "same-origin" }); } catch { r = null; } }
  if (r && r.ok) return entrar(await r.json());                         // servidor + sessão ativa
  if (r && r.status === 401) return mostrarLogin();                      // servidor, sem sessão
  estado.demo = true;                                                    // sem servidor: demonstração
  entrar({ nome: "Visitante", tipo: "funcionario", empresa: "Demonstração", llm: false });
}

// ---------- Rotas ----------
window.addEventListener("hashchange", render);
function render() {
  if (!estado.usuario) return;
  const [, rota = "inicio", arg] = location.hash.split("/");
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.route === rota || (rota === "aula" && a.dataset.route === "trilhas")));
  const telas = { inicio: telaInicio, trilhas: telaTrilhas, aula: () => telaAula(+arg), chat: telaChat, historico: telaHistorico,
    conteudos: estado.demo ? telaConteudosDemo : telaConteudos, usuarios: telaUsuarios, empresas: telaEmpresas, sobre: telaSobre };
  const exige = { usuarios: ehAdmin() && !estado.demo, empresas: ehMaster() && !estado.demo };
  view.style.animation = "none"; view.offsetHeight; view.style.animation = "";
  ((rota in exige && !exige[rota]) ? telaInicio : (telas[rota] || telaInicio))();
  scrollTo(0, 0);
}
const erroTela = err => { view.innerHTML = `<div class="card"><h2>Não foi possível carregar</h2><p class="muted">${esc(err.message)}</p></div>`; };

// ---------- Telas ----------
function telaInicio() {
  const prog = Math.round(TRILHAS.reduce((s, t) => s + t.progresso, 0) / TRILHAS.length);
  const t0 = TRILHAS[0], primeiro = estado.usuario.nome.split(" ")[0];
  view.innerHTML = `
    <section class="hero">
      <h1>Olá, ${esc(primeiro)}! Aprenda o trabalho da sua equipe em dias, não em meses.</h1>
      <p>Pergunte qualquer coisa sobre os processos da empresa. O OutGPT responde com base nos conteúdos oficiais e mostra de onde veio a informação.</p>
      <form class="search" id="busca"><input id="busca-q" placeholder="Ex.: Como faço para acessar a VPN de casa?" aria-label="Pergunte ao assistente" required><button class="btn primary">Perguntar</button></form>
    </section>
    <div class="stats">
      <div class="stat"><div class="ico">📈</div><div><b>${prog}%</b><small>Progresso geral</small></div></div>
      <div class="stat"><div class="ico">🎓</div><div><b>${TRILHAS.length}</b><small>Trilhas</small></div></div>
      <div class="stat"><div class="ico">💬</div><div><b id="n-duvidas">${estado.demo ? historico.length : "…"}</b><small>Dúvidas respondidas</small></div></div>
      <div class="stat"><div class="ico">📚</div><div><b id="n-conteudos">${estado.demo ? DOCS.length : "…"}</b><small>Conteúdos</small></div></div>
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
      <a class="card tile" href="#/conteudos"><div class="thumb">📚</div><h3>Conteúdos</h3><small>Base de conhecimento da empresa.</small></a>
    </div>`;
  $("#busca").onsubmit = e => { e.preventDefault(); pendente = $("#busca-q").value.trim(); location.hash = "#/chat"; };
  if (!estado.demo) {
    api("/api/historico" + qEmpresa()).then(d => { $("#n-duvidas").textContent = d.itens.length; }).catch(() => {});
    api("/api/conteudos" + qEmpresa()).then(d => { $("#n-conteudos").textContent = d.total; }).catch(() => {});
  }
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

function telaConteudosDemo() {
  const linhas = () => DOCS.map(d => `<tr><td>${esc(d.nome)}</td><td>${d.tipo}</td><td>${d.chunks}</td>
    <td><span class="badge ${d.status === "Indexado" ? "ok" : "warn"}">${d.status}</span></td><td>${d.data}</td>
    <td><button class="btn danger" data-del="${d.id}">Remover</button></td></tr>`).join("");
  view.innerHTML = `<div class="page-head"><div><h1>Conteúdos</h1><p class="muted">Ingestão e indexação dos manuais (SOPs, FAQs, tutoriais).</p></div></div>
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

// ---------- Assistente (RAG + LLM) ----------
const fmt = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
async function telaChat() {
  const u = estado.usuario;
  const status = estado.demo ? `<span class="badge warn">Demonstração</span>`
    : u.llm ? `<span class="badge ok">🤖 IA ativa · ${esc(u.modelo)}</span>` : `<span class="badge warn">🔎 Modo busca (LLM não configurada)</span>`;
  view.innerHTML = `<div class="page-head"><div><h1>Assistente OutGPT</h1><p class="muted">${estado.demo ? "Respostas de exemplo." : "Respostas baseadas somente nos conteúdos da empresa, com fonte citada."} ${status}</p></div>${seletorEmpresa()}</div>
    <div class="card chat">
      <div class="messages" id="msgs" aria-live="polite"><div class="msg bot">Olá! Sou o assistente de onboarding. Pergunte sobre os procedimentos da empresa.</div></div>
      <div class="suggestions" id="sugestoes"></div>
      <form class="chat-input" id="chat-form"><input id="q" placeholder="Digite sua dúvida..." autocomplete="off" maxlength="1000" required><button class="btn primary">Enviar</button></form>
    </div>`;
  ligarSeletorEmpresa(telaChat);
  const msgs = $("#msgs");
  const add = (cls, html) => { const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d; };
  const perguntar = async texto => {
    add("user", esc(texto));
    const w = add("bot typing", estado.demo ? "Buscando nos manuais..." : "Consultando os conteúdos e gerando a resposta...");
    if (estado.demo) {
      setTimeout(() => {
        const low = texto.toLowerCase(), r = RESPOSTAS.find(x => x.k.some(k => low.includes(k))) || SEM_RESPOSTA;
        w.className = "msg bot";
        w.innerHTML = esc(r.t) + (r.f.length ? `<div class="cites">${r.f.map(f => `<span class="cite">📎 ${esc(f)}</span>`).join("")}</div>` : "");
        historico.unshift({ quando: new Date().toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }), p: texto, f: r.f.join(", ") || "—" });
        msgs.scrollTop = msgs.scrollHeight;
      }, 700);
      return;
    }
    try {
      const r = await api("/api/chat", { method: "POST", body: { pergunta: texto, empresa_id: estado.empresaId } });
      w.className = "msg bot";
      const fontes = r.fontes.map(f => `<span class="cite" title="similaridade ${f.similaridade}">📎 ${esc(f.codigo)} · ${esc(f.titulo)}</span>`).join("");
      const selo = r.gerado_por_ia ? `<span class="selo">🤖 Gerado por IA a partir dos conteúdos</span>` : r.encontrado ? `<span class="selo">🔎 Trecho do manual</span>` : "";
      w.innerHTML = fmt(r.resposta) + (fontes ? `<div class="cites">${fontes}</div>` : "") + (selo ? `<div class="cites">${selo}</div>` : "")
        + (r.aviso ? `<div class="nota">ℹ️ ${esc(r.aviso)}</div>` : "")
        + (r.pii_mascaradas.length ? `<div class="nota">🔒 Dados sensíveis mascarados antes da consulta: ${esc(r.pii_mascaradas.join(", "))}</div>` : "");
    } catch (err) { if (err.status === 401) return; w.className = "msg bot"; w.innerHTML = `⚠️ ${esc(err.message)}`; }
    msgs.scrollTop = msgs.scrollHeight;
  };
  $("#chat-form").onsubmit = e => { e.preventDefault(); const q = $("#q"); const t = q.value.trim(); if (t) perguntar(t); q.value = ""; };
  let sugestoes = ["Como resolvo erro de VPN?", "Qual o SLA de prioridade alta?", "Como redefinir uma senha?", "Quando escalonar para o N2?"];
  if (!estado.demo) {
    try { sugestoes = (await api("/api/conteudos" + qEmpresa())).itens.map(c => c.pergunta_exemplo).filter(Boolean).slice(0, 4); } catch { sugestoes = []; }
  }
  $("#sugestoes").innerHTML = sugestoes.map(s => `<button class="chip">${esc(s)}</button>`).join("");
  view.querySelectorAll(".chip").forEach(c => c.onclick = () => perguntar(c.textContent));
  if (pendente) { const p = pendente; pendente = null; perguntar(p); }
}

// ---------- Histórico ----------
async function telaHistorico() {
  const cab = `<div class="page-head"><div><h1>Histórico de dúvidas</h1><p class="muted">${estado.demo || !ehAdmin() ? "Suas perguntas ao assistente." : "Perguntas feitas na empresa (gravadas já anonimizadas)."}</p></div>${seletorEmpresa()}</div>`;
  if (estado.demo) {
    view.innerHTML = cab + `<div class="card table-wrap"><table><thead><tr><th>Quando</th><th>Pergunta</th><th>Fonte</th></tr></thead><tbody>${historico.map(h => `<tr><td>${esc(h.quando)}</td><td>${esc(h.p)}</td><td>${esc(h.f)}</td></tr>`).join("")}</tbody></table></div>`;
    return;
  }
  view.innerHTML = cab + `<div class="card" id="hist">Carregando...</div>`;
  ligarSeletorEmpresa(telaHistorico);
  try {
    const d = await api("/api/historico" + qEmpresa());
    $("#hist").className = "card table-wrap";
    $("#hist").innerHTML = d.itens.length ? `<table><thead><tr><th>Quando</th>${ehAdmin() ? "<th>Usuário</th>" : ""}<th>Pergunta</th><th>Fontes</th><th></th></tr></thead><tbody>${d.itens.map(h =>
      `<tr><td>${quando(h.criado_em)}</td>${ehAdmin() ? `<td>${esc(h.usuario || "—")}</td>` : ""}<td title="${esc(h.resposta)}">${esc(h.pergunta)}</td><td>${esc(h.fontes.map(f => f.codigo).join(", ") || "—")}</td><td>${h.gerado_por_ia ? '<span class="badge">IA</span>' : ""}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">Nenhuma pergunta ainda.</p>`;
  } catch (err) { if (err.status !== 401) erroTela(err); }
}

// ---------- Conteúdos (banco da empresa) ----------
async function telaConteudos() {
  const cab = (acoes = "") => `<div class="page-head"><div><h1>Conteúdos</h1><p class="muted">Base de conhecimento usada pelo assistente e pelas trilhas.</p></div><div class="acoes">${seletorEmpresa()}${acoes}</div></div>`;
  if (ehMaster() && !estado.empresaId) { view.innerHTML = cab() + `<div class="card"><p class="muted">Crie uma empresa no menu <a href="#/empresas">Empresas</a> para começar a cadastrar conteúdos.</p></div>`; return; }
  view.innerHTML = cab() + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaConteudos);
  let d;
  try { d = await api("/api/conteudos" + qEmpresa()); } catch (err) { if (err.status !== 401) erroTela(err); return; }
  view.innerHTML = cab(d.pode_editar ? `<button class="btn" id="imp">⬆ Importar CSV</button><button class="btn primary" id="novo">+ Novo conteúdo</button>` : "") + `
    <div class="card"><div class="row2"><input id="c-q" placeholder="Filtrar por título, código ou texto..." aria-label="Filtrar conteúdos">
      <select id="c-cat"><option value="">Todas as categorias</option>${d.categorias.map(c => `<option>${esc(c)}</option>`).join("")}</select></div>
      <p class="muted" id="c-total"></p><div class="table-wrap"><table><thead><tr><th>Código</th><th>Título</th><th>Categoria</th><th>Visível para</th><th>PII</th><th></th></tr></thead><tbody id="c-body"></tbody></table></div></div>`;
  ligarSeletorEmpresa(telaConteudos);
  const pintar = () => {
    const q = $("#c-q").value.toLowerCase(), cat = $("#c-cat").value;
    const itens = d.itens.filter(c => (!cat || c.categoria === cat) && (c.codigo + " " + c.titulo + " " + c.texto).toLowerCase().includes(q));
    $("#c-total").textContent = `${itens.length} de ${d.total} conteúdo(s)`;
    $("#c-body").innerHTML = itens.map(c => `<tr><td>${esc(c.codigo)}</td><td>${esc(c.titulo)}</td><td>${esc(c.categoria)}</td>
      <td><span class="badge ${c.visibilidade === "todos" ? "ok" : ""}">${c.visibilidade === "todos" ? "Todos (inclui externos)" : "Somente internos"}</span></td>
      <td>${c.contem_pii ? '<span class="badge warn">Sim</span>' : "—"}</td>
      <td class="acoes-linha"><button class="btn" data-ver="${c.id}">Ver</button>${d.pode_editar ? `<button class="btn" data-edit="${c.id}">Editar</button><button class="btn danger" data-del="${c.id}">Excluir</button>` : ""}</td></tr>`).join("");
    view.querySelectorAll("[data-ver]").forEach(b => b.onclick = () => { const c = d.itens.find(x => x.id === +b.dataset.ver); janela(c.titulo, `<p class="muted">${esc(c.codigo)} · ${esc(c.categoria)}</p><p style="white-space:pre-wrap">${esc(c.texto)}</p>`); });
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => formConteudo(d.itens.find(x => x.id === +b.dataset.edit), telaConteudos));
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      const c = d.itens.find(x => x.id === +b.dataset.del);
      if (!(await confirmar(`Excluir "${c.titulo}"? Esta ação não pode ser desfeita.`))) return;
      try { await api(`/api/conteudos/${c.id}`, { method: "DELETE" }); telaConteudos(); } catch (err) { janela("Erro", `<p>${esc(err.message)}</p>`); }
    });
  };
  $("#c-q").oninput = pintar; $("#c-cat").onchange = pintar; pintar();
  if ($("#novo")) $("#novo").onclick = () => formConteudo(null, telaConteudos);
  if ($("#imp")) $("#imp").onclick = () => formImportar(telaConteudos);
}

function formConteudo(c, depois) {
  const novo = !c;
  janela(novo ? "Novo conteúdo" : "Editar conteúdo", `
    ${novo ? `<label class="field">Código (opcional)<input id="f-codigo" maxlength="60" placeholder="Ex.: SOP_RH_30"></label>` : `<p class="muted">Código: ${esc(c.codigo)}</p>`}
    <label class="field">Título *<input id="f-titulo" maxlength="200" required value="${esc(c?.titulo)}"></label>
    <div class="row2"><label class="field">Categoria<input id="f-cat" maxlength="100" value="${esc(c?.categoria || "Geral")}"></label>
      <label class="field">Visível para<select id="f-vis"><option value="internos" ${c?.visibilidade !== "todos" ? "selected" : ""}>Somente internos (admin, funcionários e colaboradores internos)</option>
        <option value="todos" ${c?.visibilidade === "todos" ? "selected" : ""}>Todos (inclui colaboradores externos)</option></select></label></div>
    <label class="field">Conteúdo *<textarea id="f-texto" maxlength="20000" rows="8" required>${esc(c?.texto)}</textarea></label>
    <label class="field">Pergunta de exemplo (melhora a busca)<input id="f-perg" maxlength="500" value="${esc(c?.pergunta_exemplo)}"></label>
    <label class="opt"><input type="checkbox" id="f-pii" ${c?.contem_pii ? "checked" : ""}><span>Este conteúdo trata de dados pessoais (PII)</span></label>`,
    { aoSalvar: async () => {
      const corpo = { titulo: $("#f-titulo").value, categoria: $("#f-cat").value, texto: $("#f-texto").value, pergunta_exemplo: $("#f-perg").value, visibilidade: $("#f-vis").value, contem_pii: $("#f-pii").checked };
      if (novo) await api("/api/conteudos", { method: "POST", body: { ...corpo, codigo: $("#f-codigo").value, empresa_id: estado.empresaId } });
      else await api(`/api/conteudos/${c.id}`, { method: "PUT", body: corpo });
      depois();
    } });
}

function formImportar(depois) {
  janela("Importar conteúdos de um CSV", `
    <p class="muted">Colunas: <code>id, categoria, procedimento_titulo, contexto_documental, pergunta_utilizador, resposta_esperada, contem_pii</code>. Conteúdos com o mesmo id são atualizados.</p>
    <label class="field">Arquivo CSV<input type="file" id="f-arq" accept=".csv,text/csv" required></label>
    <label class="field">Visível para<select id="f-vis"><option value="internos">Somente internos</option><option value="todos">Todos (inclui externos)</option></select></label>`,
    { salvar: "Importar", aoSalvar: async () => {
      const arq = $("#f-arq").files[0]; if (!arq) throw new Error("Escolha um arquivo.");
      const r = await api("/api/conteudos/importar", { method: "POST", body: { csv: await arq.text(), visibilidade: $("#f-vis").value, empresa_id: estado.empresaId } });
      janela("Importação concluída", `<p>${r.importados} conteúdo(s) importados e indexados.</p>`);
      depois();
    } });
}

// ---------- Usuários ----------
async function telaUsuarios() {
  const cab = (acoes = "") => `<div class="page-head"><div><h1>Usuários</h1><p class="muted">Logins de funcionários e colaboradores.</p></div><div class="acoes">${seletorEmpresa()}${acoes}</div></div>`;
  if (ehMaster() && !estado.empresaId) { view.innerHTML = cab() + `<div class="card"><p class="muted">Crie uma empresa no menu <a href="#/empresas">Empresas</a> primeiro.</p></div>`; return; }
  view.innerHTML = cab() + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaUsuarios);
  let d;
  try { d = await api("/api/usuarios" + qEmpresa()); } catch (err) { if (err.status !== 401) erroTela(err); return; }
  view.innerHTML = cab(`<button class="btn primary" id="novo">+ Novo usuário</button>`) + `<div class="card table-wrap"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Último acesso</th><th>Status</th><th></th></tr></thead><tbody>${d.itens.map(x => `
    <tr><td>${esc(x.nome)}</td><td>${esc(x.email)}</td><td>${esc(ROTULOS[x.tipo])}</td><td>${quando(x.ultimo_login)}</td>
    <td><span class="badge ${x.ativo ? "ok" : "warn"}">${x.ativo ? "Ativo" : "Desativado"}</span></td>
    <td class="acoes-linha">${x.tipo === "master" ? "" : `<button class="btn" data-edit="${x.id}">Editar</button>`}</td></tr>`).join("")}</tbody></table></div>`;
  ligarSeletorEmpresa(telaUsuarios);
  const tipos = ehMaster() ? ["admin", "funcionario", "colaborador_interno", "colaborador_externo"] : ["funcionario", "colaborador_interno", "colaborador_externo"];
  const opcoes = sel => tipos.map(t => `<option value="${t}" ${t === sel ? "selected" : ""}>${ROTULOS[t]}</option>`).join("");
  $("#novo").onclick = () => janela("Novo usuário", `
    <label class="field">Nome *<input id="u-nome" maxlength="120" required></label>
    <label class="field">E-mail (será o login) *<input id="u-email" type="email" maxlength="160" required></label>
    <label class="field">Senha inicial * (mín. 10 caracteres, com letras e números)<input id="u-senha" type="password" autocomplete="new-password" required></label>
    <label class="field">Perfil<select id="u-tipo">${opcoes("funcionario")}</select></label>
    <p class="muted">Funcionários e colaboradores internos veem todos os conteúdos da empresa; colaboradores externos veem só os marcados como "Todos".</p>`,
    { salvar: "Criar usuário", aoSalvar: async () => {
      await api("/api/usuarios", { method: "POST", body: { nome: $("#u-nome").value, email: $("#u-email").value, senha: $("#u-senha").value, tipo: $("#u-tipo").value, empresa_id: estado.empresaId } });
      telaUsuarios();
    } });
  view.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
    const x = d.itens.find(i => i.id === +b.dataset.edit);
    const podeTipo = tipos.includes(x.tipo);
    janela("Editar usuário", `
      <p class="muted">${esc(x.email)}</p>
      <label class="field">Nome<input id="u-nome" maxlength="120" required value="${esc(x.nome)}"></label>
      <label class="field">Perfil<select id="u-tipo" ${podeTipo ? "" : "disabled"}>${podeTipo ? opcoes(x.tipo) : `<option>${esc(ROTULOS[x.tipo])}</option>`}</select></label>
      <label class="opt"><input type="checkbox" id="u-ativo" ${x.ativo ? "checked" : ""}><span>Usuário ativo</span></label>
      <label class="field">Nova senha (deixe em branco para manter)<input id="u-senha" type="password" autocomplete="new-password"></label>`,
      { aoSalvar: async () => {
        const corpo = { nome: $("#u-nome").value, ativo: $("#u-ativo").checked };
        if (podeTipo) corpo.tipo = $("#u-tipo").value;
        if ($("#u-senha").value) corpo.nova_senha = $("#u-senha").value;
        await api(`/api/usuarios/${x.id}`, { method: "PUT", body: corpo });
        telaUsuarios();
      } });
  });
}

// ---------- Empresas (somente master) ----------
async function telaEmpresas() {
  view.innerHTML = `<div class="page-head"><div><h1>Empresas</h1><p class="muted">Clientes da plataforma. Cada empresa tem seus próprios usuários e conteúdos, isolados das demais.</p></div><div class="acoes"><button class="btn primary" id="novo">+ Nova empresa</button></div></div><div class="card" id="emp">Carregando...</div>`;
  $("#novo").onclick = () => janela("Nova empresa", `<label class="field">Nome *<input id="e-nome" maxlength="120" required></label>`,
    { salvar: "Criar", aoSalvar: async () => { await api("/api/empresas", { method: "POST", body: { nome: $("#e-nome").value } }); await carregarEmpresas(); telaEmpresas(); } });
  try {
    const d = await api("/api/empresas"); estado.empresas = d.itens;
    $("#emp").className = "card table-wrap";
    $("#emp").innerHTML = d.itens.length ? `<table><thead><tr><th>Empresa</th><th>Usuários</th><th>Conteúdos</th><th>Criada em</th><th>Status</th><th></th></tr></thead><tbody>${d.itens.map(e => `
      <tr><td>${esc(e.nome)}</td><td>${e.usuarios}</td><td>${e.conteudos}</td><td>${quando(e.criado_em)}</td>
      <td><span class="badge ${e.ativa ? "ok" : "warn"}">${e.ativa ? "Ativa" : "Desativada"}</span></td>
      <td class="acoes-linha"><button class="btn" data-edit="${e.id}">Editar</button></td></tr>`).join("")}</tbody></table>` : `<p class="muted">Nenhuma empresa ainda. Crie a primeira para começar.</p>`;
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const e = d.itens.find(i => i.id === +b.dataset.edit);
      janela("Editar empresa", `<label class="field">Nome<input id="e-nome" maxlength="120" required value="${esc(e.nome)}"></label>
        <label class="opt"><input type="checkbox" id="e-ativa" ${e.ativa ? "checked" : ""}><span>Empresa ativa (desativar bloqueia o login de todos os seus usuários)</span></label>`,
        { aoSalvar: async () => { await api(`/api/empresas/${e.id}`, { method: "PUT", body: { nome: $("#e-nome").value, ativa: $("#e-ativa").checked } }); await carregarEmpresas(); telaEmpresas(); } });
    });
  } catch (err) { if (err.status !== 401) erroTela(err); }
}

// ---------- Sobre ----------
function telaSobre() {
  view.innerHTML = `<div class="page-head"><div><h1>Sobre o projeto</h1><p class="muted">Fatec Cotia • Ciência de Dados • Processamento de Linguagem Natural</p></div></div>
    <div class="card"><h2>OutGPT Enterprise</h2>
      <p>Plataforma que usa IA Generativa com RAG para transformar os manuais e procedimentos de cada empresa em trilhas de capacitação e um assistente interativo, acelerando o onboarding e reduzindo a perda de conhecimento tácito (brain drain).</p></div>
    <div class="card"><h2>Equipe</h2><ul><li>Marcelo Henrique do Carmo Ramos</li><li>Victor Henrique Duarte Cardoso</li></ul></div>
    <div class="card"><h2>Stack</h2>
      <p><span class="badge">Python</span> <span class="badge">Claude (LLM)</span> <span class="badge">RAG</span> <span class="badge">ChromaDB</span> <span class="badge">SQLite</span> <span class="badge">HTML/CSS/JS</span></p></div>
    <div class="card"><h2>Pesquisa com especialistas</h2>
      <p class="muted">Ajude o projeto: responda à pesquisa sobre a importância da ferramenta para empresas e instituições de ensino.</p>
      <a class="btn" href="pesquisa.html">Abrir a pesquisa</a></div>`;
}

iniciar();
