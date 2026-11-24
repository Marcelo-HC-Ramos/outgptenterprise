/* OutGPT Enterprise - front-end
 * Fala com o servidor do projeto (login, banco SQLite, cursos por empresa e IA). Sem o servidor, mostra como iniciá-lo. */
"use strict";

// ---------- Utilidades ----------
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const estado = { usuario: null, empresas: [], empresaId: null };
const ROTULOS = { master: "Master (dono)", admin: "Administrador", funcionario: "Funcionário", colaborador_interno: "Colaborador interno", colaborador_externo: "Colaborador externo" };
const ehAdmin = () => ["master", "admin"].includes(estado.usuario?.tipo);
const ehMaster = () => estado.usuario?.tipo === "master";
const quando = s => s ? s.replace("T", " ").slice(0, 16) : "—";
let pendente = null;       // pergunta digitada na página inicial, enviada ao abrir o assistente
let acaoPendente = null;   // atalho do painel (ex.: abrir o envio de arquivo na biblioteca)
let conversa = [];         // trocas recentes do assistente (memória da conversa)

// Texto -> HTML seguro com listas numeradas, marcadores e **negrito**
function md(texto) {
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const out = []; let lista = null;
  const fecha = () => { if (lista) { out.push(`<${lista.tag}>${lista.itens.join("")}</${lista.tag}>`); lista = null; } };
  for (const bruto of String(texto ?? "").replace(/\r/g, "").split("\n")) {
    const l = bruto.trim();
    if (!l) { fecha(); continue; }
    const num = l.match(/^\d+[.)]\s+(.*)/), pont = l.match(/^[-•*]\s+(.*)/);
    if (num || pont) {
      const tag = num ? "ol" : "ul";
      if (lista && lista.tag !== tag) fecha();
      (lista ||= { tag, itens: [] }).itens.push(`<li>${inline((num || pont)[1])}</li>`);
    } else { fecha(); out.push(`<p>${inline(l)}</p>`); }
  }
  fecha();
  return out.join("");
}
const ICONES = [["segur", "🔐"], ["ti ", "💻"], ["acesso", "💻"], ["infra", "🛠️"], ["recursos humanos", "👥"], ["rh", "👥"], ["opera", "📦"], ["engenharia", "🧠"], ["geral", "📘"]];
const iconeDe = cat => (ICONES.find(([k]) => (cat || "").toLowerCase().includes(k)) || [0, "📚"])[1];

// ---------- API ----------
async function api(url, opts = {}) {
  const init = { method: opts.method || "GET", headers: {}, credentials: "same-origin" };
  if (init.method !== "GET") { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.body ?? {}); }
  const r = await fetch(url, init);
  let d = null; try { d = await r.json(); } catch { /* corpo vazio */ }
  if (r.status === 401 && url !== "/api/login") { mostrarLogin("Sua sessão expirou. Entre novamente."); throw Object.assign(new Error("sessão expirada"), { status: 401 }); }
  if (!r.ok) throw Object.assign(new Error(d?.mensagem || `Erro ${r.status}`), { status: r.status });
  return d;
}
const qEmpresa = () => ehMaster() && estado.empresaId ? `?empresa_id=${estado.empresaId}` : "";

// Acesso aos dados (servidor: SQLite + IA)
const Dados = {
  cursos: () => api("/api/cursos" + qEmpresa()),
  curso: id => api(`/api/cursos/${id}${qEmpresa()}`),
  concluir: (c, l) => api(`/api/cursos/${c}/licoes/${l}/concluir${qEmpresa()}`, { method: "POST" }),
  responder: (c, l, opcao) => api(`/api/cursos/${c}/licoes/${l}/responder${qEmpresa()}`, { method: "POST", body: { opcao } }),
  sugestoes: () => api("/api/sugestoes" + qEmpresa()),
  conteudos: () => api("/api/conteudos" + qEmpresa()),
  conteudo: id => api(`/api/conteudos/${id}`),
  departamentos: () => api("/api/departamentos" + qEmpresa()),
  chat: (pergunta, historico, aoTexto) => chatStream(pergunta, historico, aoTexto),
};

// Resposta em tempo real: lê os eventos (SSE) de /api/chat/stream e chama aoTexto a cada pedaço de texto
async function chatStream(pergunta, historico, aoTexto) {
  const corpo = JSON.stringify({ pergunta, historico, empresa_id: estado.empresaId });
  const r = await fetch("/api/chat/stream", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: corpo });
  if (r.status === 401) { mostrarLogin("Sua sessão expirou. Entre novamente."); throw Object.assign(new Error("sessão expirada"), { status: 401 }); }
  if (!r.ok) { let d = null; try { d = await r.json(); } catch { /* sem corpo */ } throw Object.assign(new Error(d?.mensagem || `Erro ${r.status}`), { status: r.status }); }
  if (!r.body?.getReader) return api("/api/chat", { method: "POST", body: { pergunta, historico, empresa_id: estado.empresaId } });   // navegador sem streaming
  const leitor = r.body.getReader(), dec = new TextDecoder();
  let buf = "", final = null;
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const bloco = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = /^event: (.*)$/m.exec(bloco)?.[1], dados = /^data: (.*)$/m.exec(bloco)?.[1];
      if (!ev || !dados) continue;
      const d = JSON.parse(dados);
      if (ev === "delta") aoTexto?.(d.texto);
      else if (ev === "fim") final = d;
      else if (ev === "erro") throw new Error(d.mensagem);
    }
  }
  if (!final) throw new Error("A resposta foi interrompida. Tente novamente.");
  return final;
}
// ---------- Avisos (toast) e conquistas ----------
function toast(html, ms = 6500) {
  let box = $("#toasts");
  if (!box) { box = document.createElement("div"); box.id = "toasts"; box.setAttribute("aria-live", "polite"); document.body.appendChild(box); }
  const t = document.createElement("div"); t.className = "toast"; t.innerHTML = html; box.appendChild(t);
  setTimeout(() => t.classList.add("sai"), ms - 400); setTimeout(() => t.remove(), ms);
}
function avisarConquistas(lista) {
  (lista || []).forEach((c, i) => setTimeout(() => toast(`<span class="toast-ico">${esc(c.icone)}</span><div><strong>Nova conquista!</strong><br>${esc(c.nome)}<small class="muted"> · ${esc(c.descricao)}</small><br><a href="#/conquistas">Ver minhas conquistas</a></div>`), i * 900));
}

// Tempo de estudo por lição: conta só a atenção ativa (aba visível e com atividade nos últimos 60 s) e avisa o servidor a cada ~15 s.
// O servidor limita o crédito ao tempo real e ignora administradores; os relatórios do RH mostram apenas dados agregados.
const Tempo = {
  alvo: null, acum: 0, ult: 0, timer: null,
  seguir(curso, licao) {
    if (this.alvo && this.alvo.c === curso && this.alvo.l === licao) return;
    this.parar(true);
    this.alvo = { c: curso, l: licao }; this.acum = 0; this.ult = Date.now();
    this.timer = setInterval(() => this.tique(), 5000);
  },
  tique() {
    if (document.visibilityState === "visible" && Date.now() - this.ult < 60000) this.acum += 5;
    if (this.acum >= 15) this.enviar();
  },
  enviar() {
    const a = this.alvo;
    if (!a || this.acum < 1) return Promise.resolve();
    const seg = Math.min(this.acum, 60); this.acum -= seg;
    return fetch(`/api/cursos/${a.c}/licoes/${a.l}/tempo${qEmpresa()}`, { method: "POST", credentials: "same-origin", keepalive: true,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ segundos: seg, empresa_id: estado.empresaId }) }).catch(() => {});
  },
  parar(enviar) { if (enviar) this.enviar(); clearInterval(this.timer); this.timer = null; this.alvo = null; this.acum = 0; },
};
["mousemove", "keydown", "scroll", "touchstart", "click"].forEach(ev => addEventListener(ev, () => { Tempo.ult = Date.now(); }, { passive: true, capture: true }));
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") Tempo.enviar(); });

// ---------- Tema ----------
const temaBtn = $("#theme");
function aplicarTema(t) {
  document.documentElement.dataset.theme = t;
  temaBtn.textContent = t === "dark" ? "☀️ Modo claro" : "🌙 Modo escuro";
}
aplicarTema(matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
temaBtn.onclick = () => aplicarTema(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

// ---------- Janelas (modais) ----------
function janela(titulo, corpo, { salvar = "Salvar", aoSalvar = null, larga = false } = {}) {
  const d = document.createElement("dialog");
  d.className = "modal" + (larga ? " larga" : "");
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
  d.addEventListener("close", () => res(false));
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
  document.querySelectorAll("#nav a").forEach(a => {
    const so = a.dataset.so;   // restrição de perfil: "admin" (master + admin) | "master"
    a.classList.toggle("hidden", Boolean((so === "admin" && !ehAdmin()) || (so === "master" && !ehMaster())));
  });
  $("#nav-admin").classList.toggle("hidden", !ehAdmin());
  carregarEmpresas().finally(render);
}
async function carregarEmpresas() {
  if (!ehMaster()) return;
  try { estado.empresas = (await api("/api/empresas")).itens; } catch { estado.empresas = []; }
  if (!estado.empresas.some(e => e.id === estado.empresaId)) estado.empresaId = estado.empresas[0]?.id ?? null;
}
// Seletor de empresa (o master administra várias)
const seletorEmpresa = () => !ehMaster() ? "" : estado.empresas.length
  ? `<label class="seletor">Empresa <select id="sel-empresa">${estado.empresas.map(e => `<option value="${e.id}" ${e.id === estado.empresaId ? "selected" : ""}>${esc(e.nome)}</option>`).join("")}</select></label>`
  : `<span class="alerta aviso">Crie uma empresa primeiro (menu Empresas).</span>`;
function ligarSeletorEmpresa(fn) { const s = $("#sel-empresa"); if (s) s.onchange = () => { estado.empresaId = +s.value; fn(); }; }
const semEmpresa = () => ehMaster() && !estado.empresaId;
const avisoSemEmpresa = () => `<div class="card vazio"><div class="vazio-ico">🏢</div><h2>Comece criando uma empresa</h2><p class="muted">Cada empresa tem seus próprios usuários, conteúdos e cursos.</p><a class="btn primary" href="#/empresas">Criar empresa</a></div>`;

$("#login-form").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("#login-btn"); btn.disabled = true;
  try {
    const u = await api("/api/login", { method: "POST", body: { email: $("#email").value, senha: $("#senha").value } });
    $("#senha").value = "";
    conversa = [];
    location.hash = "#/inicio";
    entrar(u);
  } catch (err) { mostrarLogin(err.message); }
  btn.disabled = false;
});
$("#sair").onclick = async () => { Tempo.parar(true); try { await api("/api/logout", { method: "POST" }); } catch { /* já saiu */ } conversa = []; mostrarLogin(); };
$("#trocar-senha").onclick = () => janela("Alterar senha", `
  <label class="field">Senha atual<input type="password" id="s-atual" autocomplete="current-password" required></label>
  <label class="field">Nova senha (mín. 10 caracteres, com letras e números)<input type="password" id="s-nova" autocomplete="new-password" required></label>`,
  { aoSalvar: async () => { await api("/api/senha", { method: "POST", body: { atual: $("#s-atual").value, nova: $("#s-nova").value } }); } });

// Servidor novo (sem nenhum master): mostra a tela "Primeiro acesso" no lugar do login
async function verificarPrimeiroAcesso() {
  try {
    const s = await (await fetch("/api/status")).json();
    $("#setup-form").classList.toggle("hidden", !s.precisa_configurar);
    $("#login-form").classList.toggle("hidden", !!s.precisa_configurar);
  } catch { /* sem status: segue com o login normal */ }
}
$("#setup-form").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("#setup-btn"), erro = $("#setup-erro"); btn.disabled = true; erro.classList.add("hidden");
  try {
    await api("/api/configuracao-inicial", { method: "POST", body: { token: $("#st-token").value, nome: $("#st-nome").value, email: $("#st-email").value, senha: $("#st-senha").value } });
    $("#email").value = $("#st-email").value; $("#setup-form").reset();
    $("#setup-form").classList.add("hidden"); $("#login-form").classList.remove("hidden");
    mostrarLogin("Master criado! Entre com o seu e-mail e a senha.");
  } catch (err) { erro.textContent = err.message; erro.classList.remove("hidden"); }
  btn.disabled = false;
});
// Sem servidor: explica como iniciar o sistema (não há versão simulada)
function mostrarOffline() {
  estado.usuario = null;
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  $("#login-form").classList.add("hidden"); $("#setup-form").classList.add("hidden");
  $("#offline-card").classList.remove("hidden");
  const arquivo = location.protocol === "file:";
  $("#offline-msg").innerHTML = arquivo
    ? "Você abriu o arquivo diretamente. O OutGPT precisa do servidor do projeto para funcionar: ele guarda o banco de dados, os logins e liga a IA."
    : "O servidor do OutGPT não respondeu. Pode estar desligado ou reiniciando; tente novamente em instantes.";
  $("#offline-passos").classList.toggle("hidden", !arquivo);
}
$("#offline-retry").onclick = () => location.reload();

async function iniciar() {
  let r = null;
  if (location.protocol !== "file:") { try { r = await fetch("/api/eu", { credentials: "same-origin" }); } catch { r = null; } }
  if (r && r.ok) return entrar(await r.json());                         // servidor + sessão ativa
  if (r && r.status === 401) { await verificarPrimeiroAcesso(); return mostrarLogin(); }   // servidor, sem sessão
  mostrarOffline();                                                      // sem servidor
}

// ---------- Rotas ----------
window.addEventListener("hashchange", render);
function render() {
  if (!estado.usuario) return;
  const [, rota = "inicio", a1, a2] = location.hash.split("/");
  if (rota !== "curso") Tempo.parar(true);
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.route === rota || (rota === "curso" && a.dataset.route === "cursos")));
  const telas = { inicio: telaInicio, cursos: telaCursos, curso: () => telaCurso(+a1, +a2 || null), chat: telaChat, historico: telaHistorico,
    biblioteca: telaBiblioteca, usuarios: telaUsuarios, lacunas: telaLacunas, empresas: telaEmpresas, ia: telaIA, sobre: telaSobre,
    conquistas: telaConquistas, engajamento: telaEngajamento };
  const exige = { usuarios: ehAdmin(), lacunas: ehAdmin(), engajamento: ehAdmin(), empresas: ehMaster(), ia: ehMaster() };
  view.style.animation = "none"; view.offsetHeight; view.style.animation = "";
  ((rota in exige && !exige[rota]) ? telaInicio : (telas[rota] || telaInicio))();
  scrollTo(0, 0);
}
const erroTela = err => { if (err.status !== 401) view.innerHTML = `<div class="card"><h2>Não foi possível carregar</h2><p class="muted">${esc(err.message)}</p></div>`; };
const cabecalho = (titulo, sub, acoes = "") => `<div class="page-head"><div><h1>${titulo}</h1><p class="muted">${sub}</p></div><div class="acoes">${seletorEmpresa()}${acoes}</div></div>`;

// ---------- Início ----------
const anel = pct => `<div class="anel" style="--p:${pct}"><span>${pct}%</span></div>`;
const certChip = c => c.certificado ? `<span class="badge ok">🏆 Certificado emitido</span>`
  : c.percentual === 100 ? `<span class="badge warn">🔓 Certificado disponível</span>`
  : `<span class="badge soft" title="Conclua todas as lições para desbloquear o certificado">🔒 Certificado: faltam ${c.faltam} lição(ões)</span>`;
const cartaoCurso = c => `<a class="curso" href="#/curso/${c.id}">
  <div class="curso-topo"><span class="curso-ico">${iconeDe(c.categoria)}</span><span class="curso-selos">${c.personalizado ? '<span class="badge soft">Personalizado</span>' : ""}${c.percentual === 100 ? '<span class="badge ok">Concluído</span>' : c.concluidas ? '<span class="badge">Em andamento</span>' : '<span class="badge soft">Novo</span>'}</span></div>
  <h3>${esc(c.titulo)}</h3><p class="muted">${c.licoes} lições · ~${c.minutos} min</p>
  <div class="progress"><i style="width:${c.percentual}%"></i></div><small class="muted">${c.concluidas} de ${c.licoes} concluídas</small><div class="cert-chip">${certChip(c)}</div></a>`;

async function telaInicio() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Início", "Bem-vindo ao OutGPT Enterprise.") + avisoSemEmpresa(); ligarSeletorEmpresa(telaInicio); return; }
  const primeiro = estado.usuario.nome.split(" ")[0];
  view.innerHTML = `${cabecalho(`Olá, ${esc(primeiro)} 👋`, "Tudo o que você precisa para aprender e resolver dúvidas do dia a dia.")}
    ${estado.usuario.departamento ? `<p class="trilha-info">🧭 Sua trilha: <span class="badge">${esc(estado.usuario.departamento)}</span> <span class="muted">Os cursos e as normas abaixo são os da sua área, além dos gerais da empresa.</span></p>` : ""}
    <form class="busca-grande" id="busca"><input id="busca-q" placeholder="Pergunte qualquer coisa sobre os procedimentos da empresa..." aria-label="Pergunte ao assistente" maxlength="1000" required><button class="btn primary">Perguntar</button></form>
    <div class="chips-linha" id="sug"></div>
    <div id="painel-admin"></div>
    <div id="meu-progresso"><div class="card">Carregando...</div></div>`;
  ligarSeletorEmpresa(telaInicio);
  $("#busca").onsubmit = e => { e.preventDefault(); pendente = $("#busca-q").value.trim(); location.hash = "#/chat"; };
  Dados.sugestoes().then(d => { $("#sug").innerHTML = d.itens.slice(0, 4).map(s => `<button class="chip" data-q="${esc(s)}">${esc(s)}</button>`).join(""); view.querySelectorAll("#sug .chip").forEach(c => c.onclick = () => { pendente = c.dataset.q; location.hash = "#/chat"; }); }).catch(() => {});
  if (ehAdmin()) painelAdmin();
  try {
    const d = await Dados.cursos(), r = d.resumo;
    if (!d.itens.length) {
      $("#meu-progresso").innerHTML = `<div class="card vazio"><div class="vazio-ico">🎓</div><h2>Ainda não há cursos</h2><p class="muted">${ehAdmin() ? "Cadastre conteúdos na Biblioteca: cada categoria vira um curso automaticamente." : "Quando sua empresa cadastrar conteúdos, os cursos aparecerão aqui."}</p>${ehAdmin() ? '<a class="btn primary" href="#/biblioteca">Ir para a Biblioteca</a>' : ""}</div>`;
      return;
    }
    const cont = r.continuar;
    $("#meu-progresso").innerHTML = `
      <div class="grid-2">
        <div class="card continuar">
          <small class="muted">${cont ? "CONTINUE DE ONDE PAROU" : "PARABÉNS"}</small>
          ${cont ? `<h2>${esc(cont.curso)}</h2><p class="muted">Próxima lição: <strong>${esc(cont.licao)}</strong></p><div class="progress"><i style="width:${cont.percentual}%"></i></div>
            <a class="btn primary" href="#/curso/${cont.curso_id}/${cont.conteudo_id}">${cont.percentual ? "Continuar" : "Começar"} →</a>` : `<h2>Você concluiu todos os cursos 🎉</h2><p class="muted">Use o assistente sempre que surgir uma dúvida.</p>`}
        </div>
        <div class="card progresso">${anel(r.percentual)}<div><h2>Seu progresso</h2>
          <p class="muted">${r.concluidas} de ${r.licoes} lições · ${r.cursos_concluidos} de ${r.cursos} cursos concluídos${r.respondidas ? ` · ${r.acertos}/${r.respondidas} acertos nas perguntas` : ""}</p></div></div>
      </div>
      <div class="section-title"><h2>Seus cursos</h2><a href="#/cursos">Ver todos (${d.itens.length}) →</a></div>
      <div class="grid">${d.itens.slice().sort((a, b) => (b.concluidas > 0 && b.percentual < 100) - (a.concluidas > 0 && a.percentual < 100) || a.percentual - b.percentual).slice(0, 6).map(cartaoCurso).join("")}</div>`;
    api("/api/conquistas").then(g => { const alvo = $("#meu-progresso .grid-2"); if (g.disponivel && alvo) alvo.insertAdjacentHTML("afterend", cartaoNivel(g)); }).catch(() => {});
  } catch (err) { erroTela(err); }
}

async function painelAdmin() {
  const box = $("#painel-admin");
  try {
    const p = await api("/api/painel" + qEmpresa());
    let ia = "";
    if (ehMaster()) { const s = await api("/api/llm"); ia = s.configurada ? `<span class="badge ok">🤖 IA ativa · ${esc(s.modelo)}</span>` : `<a class="alerta aviso" href="#/ia">⚠️ A IA ainda não está ligada. Configure a chave da API →</a>`; }
    box.innerHTML = `<div class="card painel"><div class="painel-topo"><h2>Painel da empresa</h2>${ia}</div>
      <div class="painel-nums"><div><b>${p.usuarios}</b><small>usuários ativos</small></div><div><b>${p.conteudos}</b><small>conteúdos</small></div><div><b>${p.cursos}</b><small>cursos</small></div><div><b>${p.perguntas_7d}</b><small>perguntas em 7 dias</small></div><div><b>${p.satisfacao === null ? "—" : p.satisfacao + "%"}</b><small>respostas úteis</small></div></div>${p.lacunas ? `<a class="alerta aviso" href="#/lacunas">🔎 ${p.lacunas} pergunta(s) sem resposta: cadastre conteúdo para cobrir →</a>` : ""}
      <div class="painel-acoes"><button class="btn" data-acao="arquivo">⬆ Enviar arquivo</button><button class="btn" data-acao="novo">+ Novo conteúdo</button><a class="btn" href="#/usuarios">👥 Cadastrar usuário</a></div></div>`;
    box.querySelectorAll("[data-acao]").forEach(b => b.onclick = () => { acaoPendente = b.dataset.acao; location.hash = "#/biblioteca"; });
  } catch { /* painel é opcional */ }
}

// ---------- Cursos ----------
async function telaCursos() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Cursos", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaCursos); return; }
  view.innerHTML = cabecalho("Cursos", "Aprenda no seu ritmo. Cada curso é montado com os procedimentos da sua empresa.") + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaCursos);
  let d; try { d = await Dados.cursos(); } catch (err) { return erroTela(err); }
  const cats = [...new Set(d.itens.filter(c => c.categoria).map(c => c.categoria))], temPers = d.itens.some(c => c.personalizado);
  const acoes = `<button class="btn" id="meus-cert">🎓 Certificados</button>` + (d.pode_editar ? `<button class="btn" id="sinc" title="Cria cursos para categorias novas e inclui conteúdos novos">↻ Atualizar cursos</button><button class="btn primary" id="novo-curso">+ Curso personalizado</button>` : "");
  view.innerHTML = cabecalho("Cursos", `${d.itens.length} cursos · ${d.resumo.licoes} lições · ${d.resumo.percentual}% concluído`, acoes) + (d.itens.length ? `
    <div class="chips-linha"><button class="chip on" data-cat="">Todos</button>${cats.map(c => `<button class="chip" data-cat="${esc(c)}">${iconeDe(c)} ${esc(c)}</button>`).join("")}${temPers ? `<button class="chip" data-cat="__pers">⭐ Personalizados</button>` : ""}</div>
    <div class="grid" id="lista-cursos"></div>` : `<div class="card vazio"><div class="vazio-ico">🎓</div><h2>Ainda não há cursos</h2><p class="muted">Cadastre conteúdos na Biblioteca para gerar cursos.</p></div>`);
  ligarSeletorEmpresa(telaCursos);
  const pintar = cat => {
    $("#lista-cursos").innerHTML = d.itens.filter(c => !cat || (cat === "__pers" ? c.personalizado : c.categoria === cat)).map(c => d.pode_editar
      ? `<div class="curso-wrap">${cartaoCurso(c)}<div class="curso-admin">${c.personalizado ? `<button class="btn mini" data-edl="${c.id}">Editar lições</button>` : ""}<button class="btn mini" data-ren="${c.id}">Renomear</button><button class="btn mini danger" data-del="${c.id}">Excluir</button></div></div>` : cartaoCurso(c)).join("");
    view.querySelectorAll("[data-ren]").forEach(b => b.onclick = () => { const c = d.itens.find(x => x.id === +b.dataset.ren);
      janela("Renomear curso", `<label class="field">Título<input id="c-tit" maxlength="200" required value="${esc(c.titulo)}"></label><label class="field">Descrição<input id="c-desc" maxlength="500" value="${esc(c.descricao)}"></label>`,
        { aoSalvar: async () => { await api(`/api/cursos/${c.id}`, { method: "PUT", body: { titulo: $("#c-tit").value, descricao: $("#c-desc").value } }); telaCursos(); } }); });
    view.querySelectorAll("[data-edl]").forEach(b => b.onclick = async () => { try { editorCurso(await api(`/api/cursos/${b.dataset.edl}/estrutura${qEmpresa()}`), telaCursos); } catch (e) { janela("Erro", `<p>${esc(e.message)}</p>`); } });
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => { const c = d.itens.find(x => x.id === +b.dataset.del);
      if (await confirmar(`Excluir o curso "${c.titulo}"? Os conteúdos continuam na Biblioteca; o progresso dos usuários neste curso será apagado.`)) { await api(`/api/cursos/${c.id}`, { method: "DELETE" }); telaCursos(); } });
  };
  if (d.itens.length) { pintar(""); view.querySelectorAll(".chips-linha .chip").forEach(b => b.onclick = () => { view.querySelectorAll(".chips-linha .chip").forEach(x => x.classList.toggle("on", x === b)); pintar(b.dataset.cat); }); }
  if ($("#novo-curso")) $("#novo-curso").onclick = () => editorCurso(null, telaCursos);
  if ($("#meus-cert")) $("#meus-cert").onclick = listarCertificados;
  if ($("#sinc")) $("#sinc").onclick = async () => { const r = await api("/api/cursos/sincronizar" + qEmpresa(), { method: "POST" }); janela("Cursos atualizados", `<p>${r.criados} curso(s) criado(s) e ${r.anexados} lição(ões) adicionada(s).</p>`); telaCursos(); };
}

async function telaCurso(id, licaoId) {
  view.innerHTML = `<div class="card">Carregando...</div>`;
  let c; try { c = await Dados.curso(id); } catch (err) { return erroTela(err); }
  let atual = c.licoes.findIndex(l => l.conteudo_id === licaoId);
  if (atual < 0) atual = Math.max(0, c.licoes.findIndex(l => !l.concluida));
  const feitas = () => c.licoes.filter(l => l.concluida).length;

  const desenhar = () => {
    const l = c.licoes[atual], pct = Math.round(100 * feitas() / c.licoes.length), ultimo = atual === c.licoes.length - 1;
    const respondida = l.acertou !== null;
    if (!ehAdmin() && !l.concluida) Tempo.seguir(c.id, l.conteudo_id); else Tempo.parar(true);       // mede o tempo até a lição ser concluída
    view.innerHTML = `<a href="#/cursos" class="muted voltar">← Cursos</a>
      <div class="curso-cab"><div><h1>${iconeDe(c.categoria)} ${esc(c.titulo)}</h1><p class="muted">${esc(c.descricao || "")}</p></div>${anel(pct)}</div>
      ${bannerQuiz()}
      <div class="aula-layout">
        <nav class="card licoes" aria-label="Lições"><ol>${c.licoes.map((x, i) => `<li><button class="${i === atual ? "ativa" : ""} ${x.concluida ? "feita" : ""}" data-i="${i}"><span class="marca">${x.concluida ? "✓" : i + 1}</span><span>${esc(x.titulo)}</span></button></li>`).join("")}</ol></nav>
        <div class="aula">
          <article class="card">
            <small class="muted">LIÇÃO ${atual + 1} DE ${c.licoes.length} · ~${l.minutos} MIN</small>
            <h2>${esc(l.titulo)}</h2>
            <div class="texto-aula">${md(l.texto)}</div>
          </article>
          ${pct === 100 && l.concluida && ultimo ? finalCurso() : ""}
          ${l.quiz ? `<div class="card quiz"><small class="muted">VERIFIQUE O QUE APRENDEU${l.quiz.ia ? " · 🤖 pergunta gerada por IA" : ""}</small><h3>${esc(l.quiz.pergunta)}</h3>
              <div id="alt">${l.quiz.opcoes.map((o, i) => `<button class="opt-btn" data-o="${i}" ${respondida ? "disabled" : ""}>${esc(o)}</button>`).join("")}</div>
              <div id="retorno-quiz">${respondida ? `<p class="muted">Você já respondeu esta pergunta (${l.acertou ? "acertou ✓" : "errou"}).</p>` : ""}</div></div>` : ""}
          <div class="aula-nav">
            <button class="btn" id="ant" ${atual === 0 ? "disabled" : ""}>← Anterior</button>
            ${!l.quiz && !l.concluida ? `<button class="btn primary" id="concluir">Concluir lição${ultimo ? "" : " e continuar"}</button>` : ""}
            <button class="btn ${l.concluida || l.quiz ? "primary" : ""}" id="prox" ${ultimo ? "disabled" : ""}>Próxima →</button>
          </div>
          ${ehAdmin() ? "" : `<p class="muted tempo-aviso">⏱ O tempo que você passa em cada lição é medido e aparece nos relatórios do RH só de forma agregada, sem nomes, para melhorar os materiais.</p>`}
        </div></div>`;
    if ($("#gerar-quiz")) $("#gerar-quiz").onclick = gerarQuiz;
    if ($("#emitir-cert")) $("#emitir-cert").onclick = async () => { try { const cert = await api(`/api/cursos/${c.id}/certificado${qEmpresa()}`, { method: "POST" }); mostrarCertificado(cert); avisarConquistas(cert.novas_conquistas); } catch (e) { janela("Não foi possível emitir", `<p>${esc(e.message)}</p>`); } };
    view.querySelectorAll("[data-i]").forEach(b => b.onclick = () => { atual = +b.dataset.i; desenhar(); scrollTo(0, 0); });
    $("#ant").onclick = () => { atual--; desenhar(); scrollTo(0, 0); };
    $("#prox").onclick = () => { atual++; desenhar(); scrollTo(0, 0); };
    if ($("#concluir")) $("#concluir").onclick = async () => { try { await Tempo.enviar(); const r = await Dados.concluir(c.id, l.conteudo_id); avisarConquistas(r.novas_conquistas); l.concluida = true; if (!ultimo) atual++; desenhar(); scrollTo(0, 0); } catch (err) { erroTela(err); } };
    view.querySelectorAll("[data-o]").forEach(b => b.onclick = async () => {
      view.querySelectorAll("[data-o]").forEach(x => x.disabled = true);
      try {
        await Tempo.enviar();                                    // o tempo até aqui conta; depois de concluída a lição, deixa de contar
        const r = await Dados.responder(c.id, l.conteudo_id, +b.dataset.o);
        avisarConquistas(r.novas_conquistas);
        l.concluida = true; l.acertou = r.correta;
        view.querySelectorAll("[data-o]").forEach((x, i) => { if (i === r.indice_correto) x.classList.add("certa"); else if (x === b) x.classList.add("errada"); });
        $("#retorno-quiz").innerHTML = r.correta ? `<p class="feedback ok">✅ Correto!</p>` : `<p class="feedback bad">Não foi dessa vez. A resposta certa é a destacada em verde.</p>`;
        $("#prox").classList.add("primary");
        const itemAtivo = view.querySelector(".licoes button.ativa");       // marca ✓ na lista sem redesenhar a tela
        if (itemAtivo) { itemAtivo.classList.add("feita"); itemAtivo.querySelector(".marca").textContent = "✓"; }
        if (feitas() === c.licoes.length) setTimeout(desenhar, 900);
      } catch (err) { erroTela(err); }
    });
  };
  const semQuiz = () => c.licoes.filter(l => !l.quiz);
  const bannerQuiz = () => (ehAdmin() && semQuiz().length)
    ? `<div class="alerta aviso banner-quiz"><span>${semQuiz().length} lição(ões) sem pergunta de verificação.</span>${estado.usuario.llm ? `<button class="btn mini" id="gerar-quiz">🤖 Gerar com IA</button>` : `<a href="#/ia">Ligue a IA para gerar →</a>`}</div>` : "";
  const gerarQuiz = async () => {
    const lista = semQuiz();
    if (!(await confirmar(`Gerar perguntas de verificação com a IA para ${lista.length} lição(ões)? Será feita uma chamada à IA por lição.`))) return;
    const d = janela("Gerando perguntas...", `<p id="g-prog" class="muted">0 de ${lista.length}</p><div class="progress"><i id="g-barra" style="width:0%"></i></div><div id="g-falhas" class="nota"></div>`);
    let ok = 0, falhas = [];
    for (const [i, l] of lista.entries()) {
      if (!document.body.contains(d)) break;                         // o admin fechou a janela: para
      try { const r = await api(`/api/conteudos/${l.conteudo_id}/quiz`, { method: "POST", body: {} }); if (r.gerado) ok++; } catch (e) { falhas.push(`${l.titulo}: ${e.message}`); }
      if (document.body.contains(d)) { $("#g-prog", d).textContent = `${i + 1} de ${lista.length}`; $("#g-barra", d).style.width = `${Math.round(100 * (i + 1) / lista.length)}%`; }
    }
    if (document.body.contains(d)) { $("#g-prog", d).textContent = `Concluído: ${ok} pergunta(s) gerada(s)${falhas.length ? `, ${falhas.length} falha(s)` : ""}.`; $("#g-falhas", d).innerHTML = falhas.map(esc).join("<br>"); }
    telaCurso(id, c.licoes[atual]?.conteudo_id);
  };
  const finalCurso = () => { const resp = c.licoes.filter(x => x.acertou !== null), ac = resp.filter(x => x.acertou).length;
    return `<div class="card parabens"><div class="vazio-ico">🎉</div><h2>Curso concluído!</h2><p class="muted">Você completou as ${c.licoes.length} lições${resp.length ? ` e acertou ${ac} de ${resp.length} perguntas` : ""}.</p><button class="btn primary" id="emitir-cert">🎓 Emitir certificado</button> <a class="btn" href="#/cursos">Ver outros cursos</a></div>`; };
  desenhar();
}

// ---------- Editor de curso personalizado ----------
function editorCurso(curso, depois) {
  Dados.conteudos().then(({ itens: todos }) => {
    const porId = new Map(todos.map(c => [c.id, c]));
    let sel = curso ? curso.conteudo_ids.filter(i => porId.has(i)) : [];
    const d = janela(curso ? "Editar lições do curso" : "Novo curso personalizado", `
      <div class="row2"><label class="field">Título *<input id="ec-tit" maxlength="200" value="${esc(curso?.titulo)}"></label>
        <label class="field">Nível<select id="ec-nivel">${["Iniciante", "Intermediário", "Avançado"].map(n => `<option ${curso?.nivel === n ? "selected" : ""}>${n}</option>`).join("")}</select></label></div>
      <label class="field">Descrição<input id="ec-desc" maxlength="500" value="${esc(curso?.descricao)}"></label>
      <div class="editor-curso">
        <div><h4>Biblioteca</h4><input id="ec-q" placeholder="Filtrar conteúdos..." aria-label="Filtrar"><div id="ec-bib" class="lista-sel"></div></div>
        <div><h4>Lições do curso (<span id="ec-n">0</span>)</h4><ol id="ec-sel" class="lista-sel"></ol><p class="muted" id="ec-vazio">Clique em "+" nos conteúdos da esquerda.</p></div>
      </div>`, { larga: true, salvar: curso ? "Salvar" : "Criar curso", aoSalvar: async () => {
        if (!$("#ec-tit", d).value.trim()) throw new Error("Dê um título ao curso.");
        if (!sel.length) throw new Error("Escolha pelo menos uma lição.");
        const corpo = { titulo: $("#ec-tit", d).value, descricao: $("#ec-desc", d).value, nivel: $("#ec-nivel", d).value, conteudo_ids: sel };
        if (curso) await api(`/api/cursos/${curso.id}${qEmpresa()}`, { method: "PUT", body: corpo });
        else await api("/api/cursos", { method: "POST", body: { ...corpo, empresa_id: estado.empresaId } });
        depois();
      } });
    const pintar = () => {
      const q = $("#ec-q", d).value.toLowerCase();
      $("#ec-bib", d).innerHTML = todos.filter(c => `${c.titulo} ${c.categoria} ${c.codigo}`.toLowerCase().includes(q)).slice(0, 150).map(c =>
        `<button type="button" class="item-sel" data-add="${c.id}" ${sel.includes(c.id) ? "disabled" : ""}><span>${sel.includes(c.id) ? "✓" : "+"}</span><span>${esc(c.titulo)}<small class="muted"> · ${esc(c.categoria)}</small></span></button>`).join("");
      $("#ec-sel", d).innerHTML = sel.map((id, i) => `<li><span>${esc(porId.get(id).titulo)}</span><span class="mov"><button type="button" class="mini-btn" data-sobe="${i}" ${i === 0 ? "disabled" : ""} title="Subir">↑</button><button type="button" class="mini-btn" data-desce="${i}" ${i === sel.length - 1 ? "disabled" : ""} title="Descer">↓</button><button type="button" class="mini-btn" data-tira="${i}" title="Remover">✕</button></span></li>`).join("");
      $("#ec-n", d).textContent = sel.length; $("#ec-vazio", d).classList.toggle("hidden", sel.length > 0);
      d.querySelectorAll("[data-add]").forEach(b => b.onclick = () => { if (sel.length < 60) { sel.push(+b.dataset.add); pintar(); } });
      d.querySelectorAll("[data-tira]").forEach(b => b.onclick = () => { sel.splice(+b.dataset.tira, 1); pintar(); });
      d.querySelectorAll("[data-sobe]").forEach(b => b.onclick = () => { const i = +b.dataset.sobe; [sel[i - 1], sel[i]] = [sel[i], sel[i - 1]]; pintar(); });
      d.querySelectorAll("[data-desce]").forEach(b => b.onclick = () => { const i = +b.dataset.desce; [sel[i + 1], sel[i]] = [sel[i], sel[i + 1]]; pintar(); });
    };
    $("#ec-q", d).oninput = pintar; pintar();
  }).catch(e => janela("Erro", `<p>${esc(e.message)}</p>`));
}

// ---------- Certificados ----------
function mostrarCertificado(c) {
  const url = `${location.origin}/verificar.html?codigo=${encodeURIComponent(c.codigo)}`;
  const data = new Date(c.emitido_em.replace(" ", "T")).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
  const d = janela("Certificado de conclusão", `
    <div class="certificado"><div class="cert-marca">Out<span>GPT</span> Enterprise</div><h2>Certificado de Conclusão</h2>
      <p>Certificamos que</p><div class="nome">${esc(c.nome)}</div><p>concluiu o curso</p><div class="curso-nome">${esc(c.curso_titulo)}</div>
      <p class="muted">${c.empresa_nome ? `${esc(c.empresa_nome)} · ` : ""}${c.licoes} lição(ões) concluída(s)${c.respondidas ? ` · ${c.acertos} de ${c.respondidas} perguntas corretas` : ""}</p>
      <p>${esc(data)}</p><p class="cert-codigo muted">Código ${esc(c.codigo)}<br>Verifique em ${esc(url)}</p></div>
    <div class="cert-acoes"><button class="btn primary" id="cert-print">🖨 Imprimir / salvar em PDF</button></div>`, { larga: true });
  $("#cert-print", d).onclick = () => window.print();
}
async function listarCertificados() {
  try {
    const { itens } = await api("/api/certificados");
    const d = janela("Meus certificados", itens.length ? `<ul class="lista-cert">${itens.map(c => `<li><div><strong>${esc(c.curso_titulo)}</strong><br><small class="muted">${esc(c.codigo)} · ${quando(c.emitido_em)}</small></div><button class="btn mini" data-abrir="${c.codigo}">Abrir</button></li>`).join("")}</ul>`
      : `<p class="muted">Você ainda não tem certificados. Conclua todas as lições de um curso para emitir o seu.</p>`, { larga: true });
    d.querySelectorAll("[data-abrir]").forEach(b => b.onclick = () => { mostrarCertificado(itens.find(c => c.codigo === b.dataset.abrir)); });
  } catch (e) { janela("Erro", `<p>${esc(e.message)}</p>`); }
}

// ---------- Assistente (RAG + LLM) ----------
async function telaChat() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Assistente", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaChat); return; }
  const u = estado.usuario;
  const status = u.llm ? `<span class="badge ok">🤖 IA ativa · ${esc(u.modelo)}</span>` : `<span class="badge warn">🔎 Só busca (IA não configurada)</span>`;
  view.innerHTML = cabecalho("Assistente OutGPT", `Respostas baseadas só nos conteúdos da empresa, com fonte citada. ${status}`, `<button class="btn" id="nova">+ Nova conversa</button>`) + `
    <div class="card chat">
      <div class="messages" id="msgs" aria-live="polite"></div>
      <div class="suggestions" id="sugestoes"></div>
      <form class="chat-input" id="chat-form"><input id="q" placeholder="Digite sua dúvida..." autocomplete="off" maxlength="1000" required><button class="btn primary">Enviar</button></form>
    </div>`;
  ligarSeletorEmpresa(telaChat);
  const msgs = $("#msgs");
  const add = (cls, html) => { const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d; };
  const boasVindas = () => add("bot", "Olá! Sou o assistente de onboarding. Pergunte sobre os procedimentos da empresa — por exemplo prazos, acessos, benefícios ou regras de segurança.");
  boasVindas();
  const mostrarFontes = fontes => fontes.map(f => `<button class="cite" data-fonte="${esc(f.conteudo_id)}" title="Abrir o conteúdo">📎 ${esc(f.codigo)} · ${esc(f.titulo)}</button>`).join("");
  const perguntar = async texto => {
    add("user", esc(texto));
    const w = add("bot typing", "Consultando os conteúdos e preparando a resposta...");
    let acumulado = "", agendado = false, finalizado = false;
    const aoTexto = t => {        // mostra o texto aos poucos (no máximo um redesenho a cada 40 ms)
      acumulado += t;
      if (agendado) return;
      agendado = true;
      setTimeout(() => { agendado = false; if (finalizado) return; w.className = "msg bot digitando"; w.innerHTML = md(acumulado); msgs.scrollTop = msgs.scrollHeight; }, 40);
    };
    try {
      const r = await Dados.chat(texto, conversa, aoTexto);
      finalizado = true;
      w.className = "msg bot";
      avisarConquistas(r.novas_conquistas);
      const selo = r.gerado_por_ia ? `<span class="selo">🤖 Resposta gerada por IA a partir dos conteúdos</span>` : r.encontrado ? `<span class="selo">🔎 Trecho do manual</span>` : "";
      w.innerHTML = md(r.resposta) + (r.fontes.length ? `<div class="cites">${mostrarFontes(r.fontes)}</div>` : "") + (selo ? `<div class="cites">${selo}</div>` : "")
        + (r.aviso ? `<div class="nota">ℹ️ ${esc(r.aviso)}</div>` : "")
        + (r.pii_mascaradas?.length ? `<div class="nota">🔒 Dados sensíveis mascarados antes da consulta: ${esc(r.pii_mascaradas.join(", "))}</div>` : "");
      w.querySelectorAll("[data-fonte]").forEach(b => b.onclick = async () => { try { const c = await Dados.conteudo(+b.dataset.fonte); janela(c.titulo, `<p class="muted">${esc(c.codigo)} · ${esc(c.categoria)}</p>${md(c.texto)}`, { larga: true }); } catch (e) { janela("Erro", `<p>${esc(e.message)}</p>`); } });
      if (r.id && r.encontrado) w.insertAdjacentHTML("beforeend", `<div class="avalia" data-id="${r.id}"><span class="muted">Essa resposta ajudou?</span><button class="mini-btn" data-nota="1" title="Ajudou">👍</button><button class="mini-btn" data-nota="-1" title="Não ajudou">👎</button></div>`);
      w.querySelectorAll(".avalia [data-nota]").forEach(b => b.onclick = () => avaliar(w.querySelector(".avalia"), +b.parentElement.dataset.id, +b.dataset.nota));
      if (r.encontrado) { conversa.push({ pergunta: texto, resposta: r.resposta }); conversa = conversa.slice(-3); }
    } catch (err) { finalizado = true; if (err.status === 401) return; w.className = "msg bot"; w.innerHTML = `⚠️ ${esc(err.message)}`; }
    msgs.scrollTop = msgs.scrollHeight;
  };
  $("#chat-form").onsubmit = e => { e.preventDefault(); const q = $("#q"), t = q.value.trim(); if (t) perguntar(t); q.value = ""; };
  $("#nova").onclick = () => { conversa = []; msgs.innerHTML = ""; boasVindas(); };
  Dados.sugestoes().then(d => { $("#sugestoes").innerHTML = d.itens.slice(0, 4).map(s => `<button class="chip">${esc(s)}</button>`).join(""); view.querySelectorAll("#sugestoes .chip").forEach(c => c.onclick = () => perguntar(c.textContent)); }).catch(() => {});
  if (pendente) { const p = pendente; pendente = null; perguntar(p); }
}

// Avaliação de uma resposta (👍 / 👎 com comentário opcional)
async function avaliar(box, id, nota) {
  const enviar = async comentario => {
    try { await api("/api/avaliar", { method: "POST", body: { id, avaliacao: nota, comentario } }); box.innerHTML = `<span class="muted">${nota === 1 ? "Obrigado pelo feedback! 👍" : "Obrigado! Vamos usar isso para melhorar. 👎"}</span>`; }
    catch (e) { box.innerHTML = `<span class="muted">Não foi possível enviar: ${esc(e.message)}</span>`; }
  };
  if (nota === 1) return enviar(null);
  janela("O que faltou nessa resposta?", `<label class="field">Comentário (opcional)<textarea id="av-com" maxlength="500" rows="3" placeholder="Ex.: faltou dizer o ramal do suporte"></textarea></label>`,
    { salvar: "Enviar", aoSalvar: async () => { await enviar($("#av-com").value.trim() || null); } });
}
// ---------- Histórico ----------
async function telaHistorico() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Histórico", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaHistorico); return; }
  view.innerHTML = cabecalho("Histórico de dúvidas", ehAdmin() ? "Perguntas feitas na empresa (gravadas já anonimizadas)." : "Suas perguntas ao assistente.") + `<div class="card" id="hist">Carregando...</div>`;
  ligarSeletorEmpresa(telaHistorico);
  try {
    const d = await api("/api/historico" + qEmpresa());
    $("#hist").className = "card table-wrap";
    $("#hist").innerHTML = d.itens.length ? `<table><thead><tr><th>Quando</th>${ehAdmin() ? "<th>Usuário</th>" : ""}<th>Pergunta</th><th>Fontes</th><th></th></tr></thead><tbody>${d.itens.map(h =>
      `<tr><td>${quando(h.criado_em)}</td>${ehAdmin() ? `<td>${esc(h.usuario || "—")}</td>` : ""}<td title="${esc(h.resposta)}">${esc(h.pergunta)}</td><td>${esc(h.fontes.map(f => f.codigo).join(", ") || "—")}</td><td>${h.gerado_por_ia ? '<span class="badge">IA</span>' : ""}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">Nenhuma pergunta ainda.</p>`;
  } catch (err) { erroTela(err); }
}

// ---------- Biblioteca (conteúdos da empresa) ----------
async function telaBiblioteca() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Biblioteca", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaBiblioteca); return; }
  view.innerHTML = cabecalho("Biblioteca", "Conteúdos que alimentam o assistente e os cursos.") + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaBiblioteca);
  let d; try { d = await Dados.conteudos(); } catch (err) { return erroTela(err); }
  const temDeps = d.pode_editar && (d.departamentos || []).length > 0;
  const nomeDep = id => (d.departamentos || []).find(x => x.id === id)?.nome || "?";
  const acoes = d.pode_editar ? `<button class="btn" id="imp">⬆ Importar CSV</button><button class="btn" id="arq">📄 Enviar arquivo</button><button class="btn primary" id="novo">+ Novo conteúdo</button>` : "";
  view.innerHTML = cabecalho("Biblioteca", `${d.total} conteúdo(s) disponíveis para você.`, acoes) + `
    <div class="card"><div class="${temDeps ? "row3" : "row2"}"><input id="c-q" placeholder="Filtrar por título, código ou texto..." aria-label="Filtrar conteúdos">
      <select id="c-cat"><option value="">Todas as categorias</option>${d.categorias.map(c => `<option>${esc(c)}</option>`).join("")}</select>
      ${temDeps ? `<select id="c-dep" aria-label="Filtrar por departamento"><option value="">Todos os públicos</option><option value="geral">Gerais (todos os departamentos)</option>${d.departamentos.map(x => `<option value="${x.id}">${esc(x.nome)}</option>`).join("")}</select>` : ""}</div>
      <p class="muted" id="c-total"></p><div class="table-wrap"><table><thead><tr><th>Código</th><th>Título</th><th>Categoria</th><th>Visível para</th><th></th></tr></thead><tbody id="c-body"></tbody></table></div></div>`;
  ligarSeletorEmpresa(telaBiblioteca);
  const pintar = () => {
    const q = $("#c-q").value.toLowerCase(), cat = $("#c-cat").value, fd = $("#c-dep")?.value || "";
    const doDep = c => !fd || (fd === "geral" ? !(c.departamentos || []).length : (c.departamentos || []).includes(+fd));
    const itens = d.itens.filter(c => (!cat || c.categoria === cat) && doDep(c) && `${c.codigo} ${c.titulo} ${c.resumo}`.toLowerCase().includes(q));
    $("#c-total").textContent = `${itens.length} de ${d.total} conteúdo(s)`;
    $("#c-body").innerHTML = itens.map(c => `<tr><td>${esc(c.codigo)}</td><td>${c.arquivo_nome ? "📄 " : ""}${esc(c.titulo)}${c.contem_pii ? ' <span class="badge warn">PII</span>' : ""}</td><td>${esc(c.categoria)}</td>
      <td><span class="badge ${c.visibilidade === "todos" ? "ok" : ""}">${c.visibilidade === "todos" ? "Todos (inclui externos)" : "Somente internos"}</span>${(c.departamentos || []).length ? `<br><span class="badge soft" title="Só estes departamentos (e os administradores) veem este conteúdo">🏷 ${c.departamentos.map(id => esc(nomeDep(id))).join(", ")}</span>` : ""}</td>
      <td class="acoes-linha"><button class="btn mini" data-ver="${c.id}">Ver</button>${d.pode_editar ? `<button class="btn mini" data-edit="${c.id}">Editar</button><button class="btn mini danger" data-del="${c.id}">Excluir</button>` : ""}</td></tr>`).join("");
    view.querySelectorAll("[data-ver]").forEach(b => b.onclick = async () => { try { const c = await Dados.conteudo(+b.dataset.ver); janela(c.titulo, `<p class="muted">${esc(c.codigo)} · ${esc(c.categoria)}${c.arquivo_nome ? " · arquivo " + esc(c.arquivo_nome) : ""}${(c.departamentos || []).length ? " · restrito a: " + c.departamentos.map(id => esc(nomeDep(id))).join(", ") : ""}</p>${md(c.texto)}`, { larga: true }); } catch (e) { janela("Erro", `<p>${esc(e.message)}</p>`); } });
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = async () => formConteudo(await api(`/api/conteudos/${b.dataset.edit}`), d.categorias));
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      const c = d.itens.find(x => x.id === +b.dataset.del);
      if (!(await confirmar(`Excluir "${c.titulo}"? Esta ação não pode ser desfeita.`))) return;
      try { await api(`/api/conteudos/${c.id}`, { method: "DELETE" }); telaBiblioteca(); } catch (err) { janela("Erro", `<p>${esc(err.message)}</p>`); }
    });
  };
  $("#c-q").oninput = pintar; $("#c-cat").onchange = pintar; if ($("#c-dep")) $("#c-dep").onchange = pintar; pintar();
  if ($("#novo")) $("#novo").onclick = () => formConteudo(null, d.categorias);
  if ($("#arq")) $("#arq").onclick = () => formArquivo(d.categorias);
  if ($("#imp")) $("#imp").onclick = () => formImportar();
  if (acaoPendente && d.pode_editar) { const a = acaoPendente; acaoPendente = null; (a === "arquivo" ? formArquivo(d.categorias) : formConteudo(null, d.categorias)); }
}

const datalistCats = cats => `<datalist id="lista-cats">${(cats || []).map(c => `<option value="${esc(c)}">`).join("")}</datalist>`;
// Público por departamento (RBAC): sem seleção = todos os departamentos veem; com seleção, só eles (e os administradores).
async function departamentosDaEmpresa() { try { return (await Dados.departamentos()).itens; } catch { return []; } }
function campoPublico(deps, marcados = []) {
  if (!deps.length) return "";           // a empresa ainda não tem departamentos: nada a escolher
  const restrito = marcados.length > 0;
  return `<fieldset class="publico"><legend>Quem pode ver (departamentos)</legend>
    <label class="opt"><input type="radio" name="f-pub" value="todos" ${restrito ? "" : "checked"}><span>Todos os departamentos</span></label>
    <label class="opt"><input type="radio" name="f-pub" value="alguns" ${restrito ? "checked" : ""}><span>Somente os escolhidos:</span></label>
    <div class="pub-lista">${deps.map(x => `<label class="opt"><input type="checkbox" class="f-dep" value="${x.id}" ${marcados.includes(x.id) ? "checked" : ""}><span>${esc(x.nome)}</span></label>`).join("")}</div>
    <p class="muted">Quem não está nesses departamentos não vê este conteúdo na biblioteca, nos cursos nem nas respostas do assistente. Administradores sempre veem.</p></fieldset>`;
}
function ligarPublico(modal) {          // marcar um departamento seleciona "Somente os escolhidos"
  modal.querySelectorAll(".f-dep").forEach(x => x.onchange = () => { if (x.checked) modal.querySelector('input[name="f-pub"][value="alguns"]').checked = true; });
}
function lerPublico(modal) {            // undefined = a janela não tem o seletor; [] = todos; [ids] = restrito
  if (!modal.querySelector(".f-dep")) return undefined;
  const alguns = modal.querySelector('input[name="f-pub"]:checked')?.value === "alguns";
  const ids = [...modal.querySelectorAll(".f-dep:checked")].map(x => +x.value);
  if (alguns && !ids.length) throw new Error('Escolha pelo menos um departamento ou marque "Todos os departamentos".');
  return alguns ? ids : [];
}

async function formConteudo(c, cats, opc = {}) {
  const novo = !c || opc.semId;
  const deps = await departamentosDaEmpresa();
  const d = janela(novo ? "Novo conteúdo" : "Editar conteúdo", `
    ${novo ? `<label class="field">Código (opcional)<input id="f-codigo" maxlength="60" placeholder="Ex.: SOP_RH_30"></label>` : `<p class="muted">Código: ${esc(c.codigo)}${c.arquivo_nome ? " · arquivo " + esc(c.arquivo_nome) : ""}</p>`}
    <label class="field">Título *<input id="f-titulo" maxlength="200" required value="${esc(c?.titulo)}"></label>
    <div class="row2"><label class="field">Categoria (vira um curso)<input id="f-cat" list="lista-cats" maxlength="100" value="${esc(c?.categoria || "Geral")}"></label>${datalistCats(cats)}
      <label class="field">Visível para<select id="f-vis"><option value="internos" ${c?.visibilidade !== "todos" ? "selected" : ""}>Somente internos</option>
        <option value="todos" ${c?.visibilidade === "todos" ? "selected" : ""}>Todos (inclui colaboradores externos)</option></select></label></div>
    ${campoPublico(deps, c?.departamentos || [])}
    <label class="field">Conteúdo *<textarea id="f-texto" maxlength="400000" rows="9" required>${esc(c?.texto)}</textarea></label>
    <label class="field">Pergunta de exemplo (melhora a busca e gera a pergunta de verificação do curso)<input id="f-perg" maxlength="500" value="${esc(c?.pergunta_exemplo)}"></label>
    <label class="field">Resposta de exemplo (resposta correta da pergunta acima)<textarea id="f-resp" maxlength="2000" rows="3">${esc(c?.resposta_exemplo)}</textarea></label>
    <label class="opt"><input type="checkbox" id="f-pii" ${c?.contem_pii ? "checked" : ""}><span>Este conteúdo trata de dados pessoais (PII)</span></label>`,
    { larga: true, aoSalvar: async modal => {
      const corpo = { titulo: $("#f-titulo").value, categoria: $("#f-cat").value, texto: $("#f-texto").value, pergunta_exemplo: $("#f-perg").value, resposta_exemplo: $("#f-resp").value, visibilidade: $("#f-vis").value, contem_pii: $("#f-pii").checked };
      const pub = lerPublico(modal);
      if (pub !== undefined) corpo.departamentos = pub;     // ao editar, sempre envia o que está na tela (nunca libera sem querer)
      if (novo) await api("/api/conteudos", { method: "POST", body: { ...corpo, codigo: $("#f-codigo")?.value, empresa_id: estado.empresaId } });
      else await api(`/api/conteudos/${c.id}`, { method: "PUT", body: corpo });
      if (opc.aoCriar) opc.aoCriar(); else telaBiblioteca();
    } });
  ligarPublico(d);
}

async function formArquivo(cats) {
  const deps = await departamentosDaEmpresa();
  const d = janela("Enviar arquivo", `
    <p class="muted">O texto do arquivo é dividido em trechos e indexado: o assistente passa a responder com base nele. Formatos: <strong>.txt, .md, .pdf, .docx</strong> (até 8 MB; PDF precisa ter texto selecionável).</p>
    <label class="field">Arquivo *<input type="file" id="f-arq" accept=".txt,.md,.pdf,.docx" required></label>
    <label class="field">Título (opcional; padrão: nome do arquivo)<input id="f-titulo" maxlength="200"></label>
    <div class="row2"><label class="field">Categoria<input id="f-cat" list="lista-cats" maxlength="100" value="Documentos"></label>${datalistCats(cats)}
      <label class="field">Visível para<select id="f-vis"><option value="internos">Somente internos</option><option value="todos">Todos (inclui externos)</option></select></label></div>
    ${campoPublico(deps)}`,
    { salvar: "Enviar e indexar", aoSalvar: async modal => {
      const arq = $("#f-arq").files[0]; if (!arq) throw new Error("Escolha um arquivo.");
      if (arq.size > 8_000_000) throw new Error("O arquivo passa de 8 MB.");
      const pub = lerPublico(modal);
      $("#j-salvar", modal).textContent = "Processando...";
      const b64 = await new Promise((ok, falha) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = falha; r.readAsDataURL(arq); });
      const corpo = { nome: arq.name, dados: b64, titulo: $("#f-titulo").value, categoria: $("#f-cat").value, visibilidade: $("#f-vis").value, empresa_id: estado.empresaId };
      if (pub?.length) corpo.departamentos = pub;
      const r = await api("/api/conteudos/arquivo", { method: "POST", body: corpo });
      janela("Arquivo indexado", `<p>${r.caracteres.toLocaleString("pt-BR")} caracteres divididos em <strong>${r.trechos}</strong> trecho(s). O assistente já pode responder com base neste arquivo.</p>`);
      telaBiblioteca();
    } });
  ligarPublico(d);
}

async function formImportar() {
  const deps = await departamentosDaEmpresa();
  const d = janela("Importar conteúdos de um CSV", `
    <p class="muted">Colunas: <code>id, categoria, procedimento_titulo, contexto_documental, pergunta_utilizador, resposta_esperada, contem_pii</code>. Conteúdos com o mesmo id são atualizados. Cada categoria vira um curso.</p>
    <label class="field">Arquivo CSV<input type="file" id="f-arq" accept=".csv,text/csv" required></label>
    <label class="field">Visível para<select id="f-vis"><option value="internos">Somente internos</option><option value="todos">Todos (inclui externos)</option></select></label>
    ${campoPublico(deps)}`,
    { salvar: "Importar", aoSalvar: async modal => {
      const arq = $("#f-arq").files[0]; if (!arq) throw new Error("Escolha um arquivo.");
      const pub = lerPublico(modal);
      $("#j-salvar", modal).textContent = "Importando...";
      const corpo = { csv: await arq.text(), visibilidade: $("#f-vis").value, empresa_id: estado.empresaId };
      if (pub?.length) corpo.departamentos = pub;       // sem seleção, não mexe no público de conteúdos que já existem
      const r = await api("/api/conteudos/importar", { method: "POST", body: corpo });
      janela("Importação concluída", `<p>${r.importados} conteúdo(s) importados, indexados e organizados em cursos.</p>`);
      telaBiblioteca();
    } });
  ligarPublico(d);
}

// ---------- Lacunas de conteúdo e feedback (admin) ----------
async function telaLacunas() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Lacunas e feedback", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaLacunas); return; }
  view.innerHTML = cabecalho("Lacunas e feedback", "O que os usuários perguntaram e o assistente não soube responder, e as respostas que não ajudaram.") + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaLacunas);
  let l, f;
  try { [l, f] = await Promise.all([api("/api/lacunas" + qEmpresa()), api("/api/feedback" + qEmpresa())]); } catch (err) { return erroTela(err); }
  const sat = f.satisfacao === null ? "—" : f.satisfacao + "%";
  view.innerHTML = cabecalho("Lacunas e feedback", "O que os usuários perguntaram e o assistente não soube responder, e as respostas que não ajudaram.") + `
    <div class="stats"><div class="stat"><div class="ico">🔎</div><div><b>${l.itens.length}</b><small>perguntas sem resposta</small></div></div>
      <div class="stat"><div class="ico">👍</div><div><b>${f.uteis}</b><small>respostas úteis (30 dias)</small></div></div>
      <div class="stat"><div class="ico">👎</div><div><b>${f.nao_ajudaram}</b><small>não ajudaram (30 dias)</small></div></div>
      <div class="stat"><div class="ico">😊</div><div><b>${sat}</b><small>satisfação</small></div></div></div>
    <div class="card"><h2>Perguntas sem resposta</h2><p class="muted">Cadastre um conteúdo que responda e a lacuna some. As mais repetidas aparecem primeiro.</p>
      ${l.itens.length ? `<div class="table-wrap"><table><thead><tr><th>Pergunta</th><th>Vezes</th><th>Usuários</th><th>Última</th><th></th></tr></thead><tbody>${l.itens.map((i, n) => `
        <tr><td>${esc(i.pergunta)}</td><td>${i.vezes}</td><td>${i.usuarios}</td><td>${quando(i.ultima)}</td>
        <td class="acoes-linha"><button class="btn mini primary" data-criar="${n}">Criar conteúdo</button><button class="btn mini" data-ignorar="${n}">Ignorar</button></td></tr>`).join("")}</tbody></table></div>` : `<p class="muted">🎉 Nenhuma lacuna no momento.</p>`}</div>
    <div class="card"><h2>Respostas que não ajudaram</h2>
      ${f.itens.length ? `<div class="table-wrap"><table><thead><tr><th>Pergunta</th><th>Comentário</th><th>Usuário</th><th>Quando</th><th></th></tr></thead><tbody>${f.itens.map((i, n) => `
        <tr><td title="${esc(i.resposta)}">${esc(i.pergunta)}</td><td>${esc(i.comentario || "—")}</td><td>${esc(i.usuario || "—")}</td><td>${quando(i.criado_em)}</td>
        <td class="acoes-linha"><button class="btn mini" data-ver="${n}">Ver resposta</button><button class="btn mini" data-tratado="${n}">Tratado</button></td></tr>`).join("")}</tbody></table></div>` : `<p class="muted">Nenhuma resposta mal avaliada pendente.</p>`}</div>`;
  ligarSeletorEmpresa(telaLacunas);
  const resolver = async ids => { await api("/api/lacunas/resolver" + qEmpresa(), { method: "POST", body: { ids } }); telaLacunas(); };
  view.querySelectorAll("[data-ignorar]").forEach(b => b.onclick = () => resolver(l.itens[+b.dataset.ignorar].ids));
  view.querySelectorAll("[data-criar]").forEach(b => b.onclick = async () => {
    const item = l.itens[+b.dataset.criar];
    let cats = []; try { cats = (await Dados.conteudos()).categorias; } catch { /* sem categorias */ }
    formConteudo({ titulo: item.pergunta.replace(/[?]+$/, ""), pergunta_exemplo: item.pergunta, categoria: "Geral", visibilidade: "internos" }, cats, { aoCriar: () => resolver(item.ids), semId: true });
  });
  view.querySelectorAll("[data-ver]").forEach(b => b.onclick = () => { const i = f.itens[+b.dataset.ver]; janela("Resposta que não ajudou", `<p><strong>Pergunta:</strong> ${esc(i.pergunta)}</p><hr>${md(i.resposta)}${i.comentario ? `<hr><p><strong>Comentário:</strong> ${esc(i.comentario)}</p>` : ""}<p class="muted">Fontes: ${esc(i.fontes.map(x => x.codigo).join(", ") || "nenhuma")}</p>`, { larga: true }); });
  view.querySelectorAll("[data-tratado]").forEach(b => b.onclick = async () => { await api("/api/feedback/resolver" + qEmpresa(), { method: "POST", body: { id: f.itens[+b.dataset.tratado].id } }); telaLacunas(); });
}
// ---------- Usuários ----------
async function telaUsuarios() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Usuários", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaUsuarios); return; }
  view.innerHTML = cabecalho("Usuários", "Logins de funcionários e colaboradores.") + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaUsuarios);
  let d, deps; try { [d, deps] = await Promise.all([api("/api/usuarios" + qEmpresa()), Dados.departamentos()]); } catch (err) { return erroTela(err); }
  const departamentos = deps.itens;
  view.innerHTML = cabecalho("Usuários", `${d.itens.length} usuário(s).`, `<button class="btn primary" id="novo">+ Novo usuário</button>`) + `
    <div class="card" id="deptos"></div>
    <div class="card table-wrap"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Departamento</th><th>Último acesso</th><th>Status</th><th></th></tr></thead><tbody>${d.itens.map(x => `
    <tr><td>${esc(x.nome)}</td><td>${esc(x.email)}</td><td>${esc(ROTULOS[x.tipo])}</td><td>${x.departamento ? `<span class="badge">${esc(x.departamento)}</span>` : '<span class="muted">—</span>'}</td><td>${quando(x.ultimo_login)}</td>
    <td><span class="badge ${x.ativo ? "ok" : "warn"}">${x.ativo ? "Ativo" : "Desativado"}</span></td>
    <td class="acoes-linha">${x.tipo === "master" ? "" : `<button class="btn mini" data-edit="${x.id}">Editar</button>`}</td></tr>`).join("")}</tbody></table></div>`;
  ligarSeletorEmpresa(telaUsuarios);

  // --- departamentos: grupos de funções que formam as trilhas de aprendizado ---
  const formDepto = (x = null) => janela(x ? "Renomear departamento" : "Novo departamento", `
    <label class="field">Nome *<input id="dp-nome" maxlength="80" required value="${esc(x?.nome)}" placeholder="Ex.: RH, TI, Financeiro"></label>
    <label class="field">Descrição (opcional)<input id="dp-desc" maxlength="200" value="${esc(x?.descricao)}"></label>`,
    { salvar: x ? "Salvar" : "Criar departamento", aoSalvar: async () => {
      const corpo = { nome: $("#dp-nome").value, descricao: $("#dp-desc").value };
      if (x) await api(`/api/departamentos/${x.id}`, { method: "PUT", body: corpo });
      else await api("/api/departamentos", { method: "POST", body: { ...corpo, empresa_id: estado.empresaId } });
      telaUsuarios();
    } });
  $("#deptos").innerHTML = `<div class="section-title"><h2>Departamentos</h2><button class="btn mini" id="novo-dep">+ Novo departamento</button></div>
    <p class="muted">Ligam pessoas a conteúdos: quem está em um departamento vê, na biblioteca, nos cursos e no assistente, os conteúdos gerais e os restritos à sua área. Cada pessoa recebe uma trilha própria. Administradores veem tudo.</p>
    ${departamentos.length ? `<div class="deptos">${departamentos.map(x => `<div class="depto"><div><strong>${esc(x.nome)}</strong>${x.descricao ? `<div class="muted">${esc(x.descricao)}</div>` : ""}<small class="muted">${x.usuarios} pessoa(s) · ${x.conteudos} conteúdo(s) restrito(s)</small></div>
      <span class="acoes-linha"><button class="btn mini" data-dren="${x.id}">Editar</button><button class="btn mini danger" data-ddel="${x.id}">Excluir</button></span></div>`).join("")}</div>`
      : `<p class="muted">Nenhum departamento ainda. Crie o primeiro (por exemplo RH, TI ou Financeiro) para montar trilhas por área.</p>`}`;
  $("#novo-dep").onclick = () => formDepto();
  view.querySelectorAll("[data-dren]").forEach(b => b.onclick = () => formDepto(departamentos.find(i => i.id === +b.dataset.dren)));
  view.querySelectorAll("[data-ddel]").forEach(b => b.onclick = async () => {
    const x = departamentos.find(i => i.id === +b.dataset.ddel);
    if (!(await confirmar(`Excluir o departamento "${x.nome}"? As ${x.usuarios} pessoa(s) dele ficam sem departamento.`))) return;
    try { await api(`/api/departamentos/${x.id}`, { method: "DELETE" }); telaUsuarios(); } catch (err) { janela("Não foi possível excluir", `<p>${esc(err.message)}</p>`); }
  });

  // --- usuários ---
  const tipos = ehMaster() ? ["admin", "funcionario", "colaborador_interno", "colaborador_externo"] : ["funcionario", "colaborador_interno", "colaborador_externo"];
  const opcoes = sel => tipos.map(t => `<option value="${t}" ${t === sel ? "selected" : ""}>${ROTULOS[t]}</option>`).join("");
  const opcoesDep = sel => `<option value="">— Sem departamento —</option>` + departamentos.map(x => `<option value="${x.id}" ${x.id === sel ? "selected" : ""}>${esc(x.nome)}</option>`).join("");
  const depEscolhido = () => ($("#u-dep").value ? +$("#u-dep").value : null);
  const abrirNovo = () => janela("Novo usuário", `
    <label class="field">Nome *<input id="u-nome" maxlength="120" required></label>
    <label class="field">E-mail (será o login) *<input id="u-email" type="email" maxlength="160" required></label>
    <label class="field">Senha inicial * (mín. 10 caracteres, com letras e números)<input id="u-senha" type="password" autocomplete="new-password" required></label>
    <div class="row2"><label class="field">Perfil<select id="u-tipo">${opcoes("funcionario")}</select></label>
      <label class="field">Departamento (define a trilha)<select id="u-dep">${opcoesDep(null)}</select></label></div>
    <p class="muted">Funcionários e colaboradores internos veem os conteúdos gerais e os do seu departamento; colaboradores externos veem só os marcados como "Todos".</p>`,
    { salvar: "Criar usuário", aoSalvar: async () => {
      await api("/api/usuarios", { method: "POST", body: { nome: $("#u-nome").value, email: $("#u-email").value, senha: $("#u-senha").value, tipo: $("#u-tipo").value, departamento_id: depEscolhido(), empresa_id: estado.empresaId } });
      telaUsuarios();
    } });
  $("#novo").onclick = abrirNovo;
  view.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
    const x = d.itens.find(i => i.id === +b.dataset.edit);
    const podeTipo = tipos.includes(x.tipo);
    janela("Editar usuário", `
      <p class="muted">${esc(x.email)}</p>
      <label class="field">Nome<input id="u-nome" maxlength="120" required value="${esc(x.nome)}"></label>
      <div class="row2"><label class="field">Perfil<select id="u-tipo" ${podeTipo ? "" : "disabled"}>${podeTipo ? opcoes(x.tipo) : `<option>${esc(ROTULOS[x.tipo])}</option>`}</select></label>
        <label class="field">Departamento (define a trilha)<select id="u-dep">${opcoesDep(x.departamento_id)}</select></label></div>
      <label class="opt"><input type="checkbox" id="u-ativo" ${x.ativo ? "checked" : ""}><span>Usuário ativo</span></label>
      <label class="field">Nova senha (deixe em branco para manter)<input id="u-senha" type="password" autocomplete="new-password"></label>`,
      { aoSalvar: async () => {
        const corpo = { nome: $("#u-nome").value, ativo: $("#u-ativo").checked, departamento_id: depEscolhido() };
        if (podeTipo) corpo.tipo = $("#u-tipo").value;
        if ($("#u-senha").value) corpo.nova_senha = $("#u-senha").value;
        await api(`/api/usuarios/${x.id}`, { method: "PUT", body: corpo });
        telaUsuarios();
      } });
  });
  if (acaoPendente === "usuario") { acaoPendente = null; abrirNovo(); }
}

// ---------- Conquistas (gamificação) ----------
const cartaoNivel = g => `<a class="card nivel-card" href="#/conquistas"><div class="nivel-ico">🏅</div>
  <div class="nivel-corpo"><div class="nivel-topo"><strong>Nível ${esc(g.nivel.nome)}</strong><span class="muted">${g.pontos} pontos</span></div>
    <div class="progress"><i style="width:${g.progresso_nivel}%"></i></div>
    <small class="muted">${g.proximo_nivel ? `Faltam ${g.proximo_nivel.faltam} pontos para ${esc(g.proximo_nivel.nome)}` : "Você chegou ao nível máximo"} · 🔥 ${g.sequencia_atual} dia(s) seguidos · ${g.desbloqueadas} de ${g.total_conquistas} conquistas</small></div></a>`;
const dataBr = s => new Date(String(s).replace(" ", "T")).toLocaleDateString("pt-BR");

async function telaConquistas() {
  view.innerHTML = cabecalho("Conquistas", "Seu nível, suas conquistas e seus certificados.") + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaConquistas);
  let g; try { g = await api("/api/conquistas"); } catch (err) { return erroTela(err); }
  if (!g.disponivel) { view.innerHTML = cabecalho("Conquistas", "") + `<div class="card vazio"><div class="vazio-ico">🏅</div><h2>Conquistas são de quem faz os cursos</h2><p class="muted">Entre com um usuário da empresa (funcionário ou colaborador) para ver níveis, conquistas e certificados.</p></div>`; return; }
  let cd = { itens: [] }, certs = { itens: [] };
  try { [cd, certs] = await Promise.all([Dados.cursos(), api("/api/certificados")]); } catch { /* segue sem a seção de certificados */ }
  const emitidos = cd.itens.filter(c => c.certificado), disponiveis = cd.itens.filter(c => !c.certificado && c.percentual === 100), bloqueados = cd.itens.filter(c => c.percentual < 100);
  view.innerHTML = cabecalho("Conquistas", `${g.desbloqueadas} de ${g.total_conquistas} conquistas desbloqueadas`) + `
    ${cartaoNivel(g).replace('<a class="card nivel-card" href="#/conquistas">', '<div class="card nivel-card">').replace(/<\/a>$/, "</div>")}
    <div class="painel-nums nums-conq"><div><b>🔥 ${g.sequencia_atual}</b><small>dia(s) seguidos (melhor: ${g.melhor_sequencia})</small></div><div><b>${g.licoes}</b><small>lições concluídas</small></div>
      <div><b>${g.cursos_concluidos}/${g.total_cursos}</b><small>cursos concluídos</small></div><div><b>${g.respondidas ? `${g.acertos}/${g.respondidas}` : "—"}</b><small>acertos de primeira</small></div><div><b>${g.certificados}</b><small>certificado(s)</small></div></div>
    <div class="section-title"><h2>Conquistas</h2></div>
    <div class="conquistas">${g.conquistas.map(c => `<div class="conquista ${c.conquistada_em ? "on" : "off"}"><div class="conquista-ico">${esc(c.icone)}</div><strong>${esc(c.nome)}</strong><small class="muted">${esc(c.descricao)}</small>
      ${c.conquistada_em ? `<span class="badge ok">Conquistada em ${dataBr(c.conquistada_em)}</span>` : `<div class="progress"><i style="width:${Math.round(100 * c.atual / c.meta)}%"></i></div><small class="muted">${c.atual} de ${c.meta}</small>`}</div>`).join("")}</div>
    <div class="section-title"><h2>Certificados</h2></div>
    <div class="card" id="certs">${cd.itens.length ? `<ul class="lista-cert">
      ${emitidos.map(c => `<li><div><strong>🏆 ${esc(c.titulo)}</strong><br><small class="muted">Emitido · código ${esc(c.certificado)}</small></div><button class="btn mini" data-abrir="${esc(c.certificado)}">Abrir</button></li>`).join("")}
      ${disponiveis.map(c => `<li><div><strong>🔓 ${esc(c.titulo)}</strong><br><small class="muted">Curso concluído: seu certificado está liberado</small></div><button class="btn mini primary" data-emitir="${c.id}">Emitir agora</button></li>`).join("")}
      ${bloqueados.map(c => `<li class="trancado"><div><strong>🔒 ${esc(c.titulo)}</strong><br><small class="muted">Faltam ${c.faltam} lição(ões) para desbloquear</small><div class="progress"><i style="width:${c.percentual}%"></i></div></div><a class="btn mini" href="#/curso/${c.id}">Continuar</a></li>`).join("")}</ul>`
      : `<p class="muted">Ainda não há cursos. Quando houver, o certificado de cada um será desbloqueado ao concluir todas as lições.</p>`}</div>`;
  ligarSeletorEmpresa(telaConquistas);
  view.querySelectorAll("[data-abrir]").forEach(b => b.onclick = () => mostrarCertificado(certs.itens.find(c => c.codigo === b.dataset.abrir)));
  view.querySelectorAll("[data-emitir]").forEach(b => b.onclick = async () => {
    try { const cert = await api(`/api/cursos/${b.dataset.emitir}/certificado${qEmpresa()}`, { method: "POST" }); mostrarCertificado(cert); avisarConquistas(cert.novas_conquistas); telaConquistas(); }
    catch (e) { janela("Não foi possível emitir", `<p>${esc(e.message)}</p>`); }
  });
}

// ---------- Engajamento (RH): quais materiais são mais difíceis de assimilar ----------
let engFiltro = { dep: "", curso: "" };
const fmtTempo = s => s == null ? "—" : s < 60 ? `${s} s` : s < 3600 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1).replace(".", ",")} h`;
const fmtPct = v => v == null ? "—" : `${v}%`;
const NIVEIS_DIF = { dificil: "Difícil", atencao: "Atenção", tranquila: "Tranquila" };
const tagDif = (l, min) => l.nivel === "amostra" ? `<span class="dif amostra" title="Menos de ${min} pessoas começaram esta lição: poucos dados para classificar">amostra pequena</span>` : `<span class="dif ${l.nivel}">${NIVEIS_DIF[l.nivel]} · ${l.dificuldade}</span>`;
const motivosDif = l => [
  l.respondidas && l.acerto_1a_pct !== null && l.acerto_1a_pct < 70 ? `${100 - l.acerto_1a_pct}% erraram a pergunta de primeira` : null,
  l.ritmo !== null && l.ritmo >= 1.5 ? `tempo ${String(l.ritmo.toFixed(1)).replace(".", ",")}× o esperado` : null,
  l.abandono_pct ? `${l.abandono_pct}% começaram e não concluíram` : null,
  l.tentativas_media && l.tentativas_media >= 1.5 ? `${String(l.tentativas_media).replace(".", ",")} tentativas em média` : null].filter(Boolean);

async function telaEngajamento() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Engajamento", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaEngajamento); return; }
  view.innerHTML = cabecalho("Engajamento", "Quais materiais são mais difíceis de assimilar.") + `<div class="card">Carregando...</div>`;
  ligarSeletorEmpresa(telaEngajamento);
  const qs = new URLSearchParams();
  if (ehMaster() && estado.empresaId) qs.set("empresa_id", estado.empresaId);
  if (engFiltro.dep) qs.set("departamento_id", engFiltro.dep);
  if (engFiltro.curso) qs.set("curso_id", engFiltro.curso);
  const q = qs.toString() ? "?" + qs : "";
  let rel, deps = [], cursosLista = [];
  try { [rel, deps, cursosLista] = await Promise.all([api("/api/engajamento" + q), Dados.departamentos().then(d => d.itens).catch(() => []), Dados.cursos().then(d => d.itens).catch(() => [])]); }
  catch (err) { return erroTela(err); }
  const r = rel.resumo, min = r.min_amostra;
  const atencao = rel.licoes.filter(l => l.nivel === "dificil" || l.nivel === "atencao").slice(0, 6);
  view.innerHTML = cabecalho("Engajamento", "Quais materiais são mais difíceis de assimilar.", `<a class="btn" href="/api/engajamento/licoes.csv${q}" download>⬇ Exportar CSV</a>`) + `
    <div class="card"><div class="row2"><label class="field">Departamento<select id="eg-dep"><option value="">Todos</option>${deps.map(d => `<option value="${d.id}" ${String(d.id) === engFiltro.dep ? "selected" : ""}>${esc(d.nome)}</option>`).join("")}</select></label>
      <label class="field">Curso<select id="eg-curso"><option value="">Todos</option>${cursosLista.map(c => `<option value="${c.id}" ${String(c.id) === engFiltro.curso ? "selected" : ""}>${esc(c.titulo)}</option>`).join("")}</select></label></div>
      <div class="painel-nums"><div><b>${r.pessoas}</b><small>pessoas na análise</small></div><div><b>${r.ativas}</b><small>ativas nos últimos ${r.janela_ativos_dias} dias</small></div><div><b>${r.licoes_concluidas}</b><small>lições concluídas</small></div>
        <div><b>${fmtTempo(r.tempo_total_s)}</b><small>tempo de estudo</small></div><div><b>${fmtPct(r.conclusao_media_pct)}</b><small>conclusão média</small></div><div><b>${fmtPct(r.acerto_1a_pct)}</b><small>acerto de 1ª tentativa</small></div></div></div>
    <div class="section-title"><h2>Materiais que merecem atenção</h2></div>
    ${atencao.length ? `<div class="grid">${atencao.map(l => `<div class="card atencao"><div class="atencao-topo">${tagDif(l, min)}<small class="muted">${esc(l.curso)}</small></div><h3>${esc(l.titulo)}</h3>
        <ul class="motivos">${motivosDif(l).map(m => `<li>${m}</li>`).join("") || "<li>Sinais moderados de dificuldade.</li>"}</ul><small class="muted">${l.iniciaram} de ${l.elegiveis} pessoas começaram · ${l.concluiram} concluíram</small></div>`).join("")}</div>`
      : `<div class="card vazio"><div class="vazio-ico">✅</div><h2>Nenhum material com sinais de dificuldade</h2><p class="muted">Ou ainda há poucos dados: cada lição precisa de pelo menos ${min} pessoas que a tenham começado para ser classificada.</p></div>`}
    <div class="section-title"><h2>Todas as lições</h2><small class="muted">ordenadas da mais difícil para a mais tranquila</small></div>
    <div class="card table-wrap"><table><thead><tr><th>Lição</th><th>Começaram</th><th>Concluíram</th><th>Abandono</th><th>Tempo (mediana)</th><th>Acerto 1ª</th><th>Tentativas</th><th>Dificuldade</th></tr></thead><tbody>
      ${rel.licoes.length ? rel.licoes.map(l => `<tr><td><strong>${esc(l.titulo)}</strong><br><small class="muted">${esc(l.curso)} · ${esc(l.codigo)}</small></td><td>${l.iniciaram}/${l.elegiveis}</td><td>${l.concluiram}</td><td>${fmtPct(l.abandono_pct)}</td>
        <td>${fmtTempo(l.tempo_mediano_s)}<br><small class="muted">esperado ${fmtTempo(l.esperado_s)}</small></td><td>${fmtPct(l.acerto_1a_pct)}</td><td>${l.tentativas_media ?? "—"}</td><td>${tagDif(l, min)}</td></tr>`).join("") : `<tr><td colspan="8" class="muted">Nenhuma lição para este filtro.</td></tr>`}</tbody></table></div>
    <div class="grid-2 g2-eng">
      <div class="card table-wrap"><h3>Por curso</h3><table><thead><tr><th>Curso</th><th>Começaram</th><th>Concluíram</th><th>Tempo</th></tr></thead><tbody>${rel.cursos.map(c => `<tr><td>${esc(c.titulo)}</td><td>${c.iniciaram}/${c.elegiveis}</td><td>${c.concluiram} (${fmtPct(c.conclusao_pct)})</td><td>${fmtTempo(c.tempo_total_s)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">—</td></tr>`}</tbody></table></div>
      <div class="card table-wrap"><h3>Por departamento</h3><table><thead><tr><th>Departamento</th><th>Pessoas</th><th>Ativas</th><th>Conclusão média</th></tr></thead><tbody>${rel.departamentos.map(d => `<tr><td>${esc(d.nome)}</td><td>${d.pessoas}</td><td>${d.ativas}</td><td>${fmtPct(d.conclusao_media_pct)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">—</td></tr>`}</tbody></table></div>
    </div>
    <details class="card metodo"><summary>Como o índice de dificuldade é calculado</summary>
      <p class="muted">É uma nota de 0 a 100 que combina três sinais de cada lição: <strong>erro na 1ª tentativa</strong> da pergunta de verificação (peso 5), <strong>tempo acima do esperado</strong> (peso 3; o esperado vem do tamanho do texto, e 2× o esperado conta como máximo) e <strong>abandono</strong>, quem começou e não concluiu (peso 2). Só entram os sinais que existem para a lição. <strong>Difícil</strong> a partir de 60, <strong>Atenção</strong> a partir de 35. Com menos de ${min} pessoas a lição aparece como "amostra pequena" e não é classificada.</p>
      <p class="muted"><strong>Privacidade:</strong> os números são agregados por lição, curso e departamento; nomes e e-mails não aparecem. O tempo conta só a atenção ativa (aba aberta e com uso), até a lição ser concluída. Administradores não entram na análise.</p></details>`;
  ligarSeletorEmpresa(telaEngajamento);
  $("#eg-dep").onchange = e => { engFiltro.dep = e.target.value; telaEngajamento(); };
  $("#eg-curso").onchange = e => { engFiltro.curso = e.target.value; telaEngajamento(); };
}

// ---------- Empresas (somente master) ----------
async function telaEmpresas() {
  view.innerHTML = cabecalho("Empresas", "Clientes da plataforma. Cada empresa tem seus próprios usuários, conteúdos e cursos, isolados das demais.", `<button class="btn primary" id="novo">+ Nova empresa</button>`).replace(seletorEmpresa(), "") + `<div class="card" id="emp">Carregando...</div>`;
  $("#novo").onclick = () => janela("Nova empresa", `<label class="field">Nome *<input id="e-nome" maxlength="120" required></label>`,
    { salvar: "Criar", aoSalvar: async () => { const r = await api("/api/empresas", { method: "POST", body: { nome: $("#e-nome").value } }); estado.empresaId = r.id; await carregarEmpresas(); telaEmpresas(); } });
  try {
    const d = await api("/api/empresas"); estado.empresas = d.itens;
    $("#emp").className = "card table-wrap";
    $("#emp").innerHTML = d.itens.length ? `<table><thead><tr><th>Empresa</th><th>Usuários</th><th>Conteúdos</th><th>Criada em</th><th>Status</th><th></th></tr></thead><tbody>${d.itens.map(e => `
      <tr><td>${esc(e.nome)}</td><td>${e.usuarios}</td><td>${e.conteudos}</td><td>${quando(e.criado_em)}</td>
      <td><span class="badge ${e.ativa ? "ok" : "warn"}">${e.ativa ? "Ativa" : "Desativada"}</span></td>
      <td class="acoes-linha"><button class="btn mini" data-edit="${e.id}">Editar</button></td></tr>`).join("")}</tbody></table>` : `<p class="muted">Nenhuma empresa ainda. Crie a primeira para começar.</p>`;
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const e = d.itens.find(i => i.id === +b.dataset.edit);
      janela("Editar empresa", `<label class="field">Nome<input id="e-nome" maxlength="120" required value="${esc(e.nome)}"></label>
        <label class="opt"><input type="checkbox" id="e-ativa" ${e.ativa ? "checked" : ""}><span>Empresa ativa (desativar bloqueia o login de todos os seus usuários)</span></label>`,
        { aoSalvar: async () => { await api(`/api/empresas/${e.id}`, { method: "PUT", body: { nome: $("#e-nome").value, ativa: $("#e-ativa").checked } }); await carregarEmpresas(); telaEmpresas(); } });
    });
  } catch (err) { erroTela(err); }
}

// ---------- Inteligência artificial (somente master) ----------
async function telaIA() {
  view.innerHTML = cabecalho("Inteligência artificial", "Liga o assistente à LLM (Claude) para respostas claras sobre os procedimentos.").replace(seletorEmpresa(), "") + `<div class="card" id="ia">Carregando...</div>`;
  let s; try { s = await api("/api/llm"); } catch (err) { return erroTela(err); }
  const pintar = () => {
    $("#ia").innerHTML = `
      <div class="ia-status"><span class="badge ${s.configurada ? "ok" : "warn"}">${s.configurada ? "🤖 IA ligada" : "⚠️ IA desligada"}</span><span class="muted">Modelo: <strong>${esc(s.modelo)}</strong> · esforço: ${esc(s.esforco)}</span></div>
      <p class="muted">${s.configurada ? "O assistente usa a LLM para escrever as respostas a partir dos trechos recuperados. Se a chamada falhar, ele mostra o trecho do manual no lugar." : "Sem a chave da API, o assistente só mostra o trecho do manual encontrado, sem resposta escrita pela IA."}</p>
      ${s.configurada ? `<button class="btn" id="testar">Testar conexão</button><div id="res-teste"></div><hr>` : ""}
      <h3>${s.configurada ? "Trocar a chave da API" : "Ligar a IA"}</h3>
      <ol class="passos"><li>Crie uma chave em <strong>console.anthropic.com</strong> (menu API Keys).</li><li>Cole a chave abaixo. Ela é testada e guardada só neste servidor (arquivo <code>backend/.env</code>); nunca aparece de novo na tela.</li></ol>
      <form id="form-chave" class="linha-form"><input type="password" id="chave" placeholder="sk-ant-..." autocomplete="off" required><button class="btn primary" id="salvar-chave">Testar e salvar</button></form><div id="res-chave"></div>`;
    if ($("#testar")) $("#testar").onclick = async () => { $("#res-teste").innerHTML = `<p class="muted">Testando...</p>`; try { const r = await api("/api/llm/testar", { method: "POST" }); $("#res-teste").innerHTML = `<p class="alerta ${r.ok ? "ok" : "bad"}">${esc(r.mensagem)}</p>`; } catch (e) { $("#res-teste").innerHTML = `<p class="alerta bad">${esc(e.message)}</p>`; } };
    $("#form-chave").onsubmit = async e => {
      e.preventDefault(); const btn = $("#salvar-chave"); btn.disabled = true; $("#res-chave").innerHTML = `<p class="muted">Validando a chave com uma chamada real...</p>`;
      try { const r = await api("/api/llm/chave", { method: "POST", body: { chave: $("#chave").value } }); $("#chave").value = ""; estado.usuario.llm = true; s.configurada = true; pintar(); $("#res-chave").innerHTML = `<p class="alerta ok">✅ ${esc(r.mensagem)} A IA já está funcionando no assistente.</p>`; }
      catch (err) { $("#res-chave").innerHTML = `<p class="alerta bad">${esc(err.message)}</p>`; btn.disabled = false; }
    };
  };
  pintar();
}

// ---------- Sobre ----------
function telaSobre() {
  view.innerHTML = cabecalho("Sobre o projeto", "Fatec Cotia • Ciência de Dados • Processamento de Linguagem Natural") + `
    <div class="card"><h2>OutGPT Enterprise</h2>
      <p>Plataforma que usa IA generativa com RAG para transformar os manuais e procedimentos de cada empresa em cursos e em um assistente que responde dúvidas com a fonte citada, acelerando o onboarding e reduzindo a perda de conhecimento tácito (brain drain).</p></div>
    <div class="card"><h2>Equipe</h2><ul><li>Marcelo Henrique do Carmo Ramos</li><li>Victor Henrique Duarte Cardoso</li></ul></div>
    <div class="card"><h2>Tecnologia</h2>
      <p><span class="badge">Python</span> <span class="badge">Claude (LLM)</span> <span class="badge">RAG híbrido</span> <span class="badge">ChromaDB</span> <span class="badge">SQLite</span> <span class="badge">HTML/CSS/JS</span></p></div>
    <div class="card"><h2>Modelo de negócio</h2>
      <p class="muted">Implantação (setup fee) mais assinatura mensal em três planos: Starter, Growth e Enterprise.</p>
      <a class="btn" href="negocio.html">Ver planos e modelo de negócio</a></div>
    <div class="card"><h2>Pesquisa com especialistas</h2>
      <p class="muted">Ajude o projeto: responda à pesquisa sobre a importância da ferramenta para empresas e instituições de ensino.</p>
      <a class="btn" href="pesquisa.html">Abrir a pesquisa</a></div>`;
}

iniciar();
