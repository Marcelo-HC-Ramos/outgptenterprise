/* OutGPT Enterprise - front-end
 * Com o servidor Python há login, banco SQLite, cursos por empresa e IA. Sem ele (GitHub Pages ou arquivo local)
 * roda em modo demonstração, com o conteúdo de exemplo de demo_conteudos.js. */
"use strict";

// ---------- Utilidades ----------
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const estado = { usuario: null, demo: false, empresas: [], empresaId: null };
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

// ---------- Modo demonstração (sem servidor): cursos, quiz e busca sobre o conteúdo de exemplo ----------
const Demo = (() => {
  const PARTE_MAX = 12, KEY = "outgpt_demo_prog";
  const dados = () => window.DEMO_CONTEUDOS || [];
  const prog = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
  const salvar = p => { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* sem armazenamento */ } };
  const minutos = t => Math.max(1, Math.ceil((t.match(/\w+/g) || []).length / 180));
  const hash = s => { let h = 2166136261; for (const ch of s) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  const rng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const embaralhar = (a, r) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const semAcento = s => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const STOP = new Set("a o as os um uma de da do das dos em no na nos nas ao aos para por pra com sem sobre entre que qual quais quanto quantos como quando onde quem e ou se mas ser sao foi tem ter tenho posso preciso devo fazer faco minha meu isso esse essa este esta ha ja mais muito existe".split(" "));
  const termos = p => semAcento(p).match(/[a-z0-9]+/g)?.filter(t => t.length >= 3 && !STOP.has(t)) || [];
  const radical = t => t.length >= 5 ? t.slice(0, Math.max(4, t.length - 2)) : t;

  function cursos() {
    const porCat = new Map();
    dados().forEach((c, i) => { if (c.texto.length <= 6000) { if (!porCat.has(c.categoria)) porCat.set(c.categoria, []); porCat.get(c.categoria).push({ ...c, n: i + 1 }); } });
    const out = []; let id = 0;
    for (const [cat, itens] of porCat) {
      const partes = Math.ceil(itens.length / PARTE_MAX), tam = Math.ceil(itens.length / partes);
      for (let p = 0; p < partes; p++) out.push({ id: ++id, titulo: partes === 1 ? cat : `${cat} · Parte ${p + 1} de ${partes}`, descricao: `Procedimentos e regras de ${cat} da sua empresa.`,
        categoria: cat, nivel: p === 0 ? "Iniciante" : "Intermediário", itens: itens.slice(p * tam, (p + 1) * tam) });
    }
    return out;
  }
  function quiz(c) {
    if (!c.pergunta || !c.resposta) return null;
    const r = rng(hash("quiz:" + c.codigo)), certa = c.resposta.trim(), vistos = new Set([certa]), mesma = [], resto = [];
    for (const o of dados()) {
      const t = (o.resposta || "").trim();
      if (o.codigo === c.codigo || !t || vistos.has(t)) continue;
      vistos.add(t); (o.categoria === c.categoria ? mesma : resto).push(t);
    }
    const opcoes = embaralhar([...embaralhar(mesma, r), ...embaralhar(resto, r)].slice(0, 3).concat(certa), r);
    return { pergunta: c.pergunta, opcoes, indice: opcoes.indexOf(certa) };
  }
  const resumoCurso = (c, p) => {
    const feitas = c.itens.filter(i => i.codigo in p), resp = feitas.filter(i => p[i.codigo] !== null);
    const prox = c.itens.find(i => !(i.codigo in p));
    return { id: c.id, titulo: c.titulo, descricao: c.descricao, categoria: c.categoria, nivel: c.nivel, licoes: c.itens.length, concluidas: feitas.length,
      respondidas: resp.length, acertos: resp.filter(i => p[i.codigo] === 1).length, minutos: c.itens.reduce((s, i) => s + minutos(i.texto), 0),
      ultima: feitas.length ? "1" : null, proxima: prox ? { conteudo_id: prox.n, titulo: prox.titulo } : null, percentual: Math.round(100 * feitas.length / c.itens.length) };
  };
  return {
    async cursos() {
      const p = prog(), itens = cursos().map(c => resumoCurso(c, p));
      const abertos = itens.filter(c => c.proxima), andamento = abertos.filter(c => c.concluidas), esc_ = (andamento[0] || abertos[0]);
      const licoes = itens.reduce((s, c) => s + c.licoes, 0), feitas = itens.reduce((s, c) => s + c.concluidas, 0);
      return { itens, pode_editar: false, resumo: { cursos: itens.length, cursos_concluidos: itens.filter(c => c.percentual === 100).length, licoes, concluidas: feitas,
        percentual: licoes ? Math.round(100 * feitas / licoes) : 0, respondidas: itens.reduce((s, c) => s + c.respondidas, 0), acertos: itens.reduce((s, c) => s + c.acertos, 0),
        continuar: esc_ ? { curso_id: esc_.id, curso: esc_.titulo, conteudo_id: esc_.proxima.conteudo_id, licao: esc_.proxima.titulo, percentual: esc_.percentual } : null } };
    },
    async curso(id) {
      const c = cursos().find(x => x.id === +id); if (!c) throw new Error("Curso não encontrado.");
      const p = prog(), licoes = c.itens.map(i => { const q = quiz(i); return { conteudo_id: i.n, codigo: i.codigo, titulo: i.titulo, texto: i.texto, minutos: minutos(i.texto),
        concluida: i.codigo in p, acertou: i.codigo in p && p[i.codigo] !== null ? p[i.codigo] === 1 : null, quiz: q ? { pergunta: q.pergunta, opcoes: q.opcoes } : null }; });
      const feitas = licoes.filter(l => l.concluida).length;
      return { id: c.id, titulo: c.titulo, descricao: c.descricao, categoria: c.categoria, nivel: c.nivel, licoes, concluidas: feitas, percentual: Math.round(100 * feitas / licoes.length) };
    },
    async concluir(_cid, lid) { const c = dados()[lid - 1], p = prog(); if (c && !(c.codigo in p)) { p[c.codigo] = null; salvar(p); } return { ok: true }; },
    async responder(_cid, lid, opcao) {
      const c = dados()[lid - 1], q = c && quiz(c); if (!q) throw new Error("Pergunta não encontrada.");
      const p = prog(); if (!(c.codigo in p) || p[c.codigo] === null) { p[c.codigo] = opcao === q.indice ? 1 : 0; salvar(p); }
      return { correta: opcao === q.indice, indice_correto: q.indice, resposta_certa: q.opcoes[q.indice] };
    },
    async sugestoes() { return { itens: embaralhar(dados().filter(c => c.pergunta).map(c => c.pergunta), Math.random).slice(0, 6) }; },
    async conteudos() {
      const itens = dados().map((c, i) => ({ id: i + 1, codigo: c.codigo, titulo: c.titulo, categoria: c.categoria, resumo: c.texto.slice(0, 300), tamanho: c.texto.length,
        visibilidade: "todos", contem_pii: 0, arquivo_nome: null, pergunta_exemplo: c.pergunta }));
      return { total: itens.length, categorias: [...new Set(itens.map(c => c.categoria))].sort(), itens, pode_editar: false };
    },
    async conteudo(id) { const c = dados()[id - 1]; return { id, codigo: c.codigo, titulo: c.titulo, categoria: c.categoria, texto: c.texto, visibilidade: "todos" }; },
    async chat(pergunta) {   // busca por palavras-chave no conteúdo de exemplo (sem IA)
      const ts = [...new Set(termos(pergunta))]; if (!ts.length) return semResposta();
      const docs = dados().map((c, i) => ({ c, n: i + 1, norm: semAcento(`${c.titulo} ${c.texto} ${c.pergunta || ""}`) }));
      const df = t => docs.filter(d => d.norm.includes(radical(t))).length || 1;
      const pont = docs.map(d => { let s = 0, casados = 0; for (const t of ts) if (d.norm.includes(radical(t))) { casados++; s += Math.log(1 + docs.length / df(t)); } return { ...d, s, casados }; })
        .filter(d => d.casados >= Math.min(2, ts.length) && d.casados / ts.length >= 0.5).sort((a, b) => b.s - a.s);
      if (!pont.length) return semResposta();
      const t = pont[0];
      return { encontrado: true, gerado_por_ia: false, resposta: `Com base em «${t.c.titulo}» (${t.c.codigo}):\n\n${t.c.texto}`, pii_mascaradas: [],
        fontes: [{ conteudo_id: t.n, codigo: t.c.codigo, titulo: t.c.titulo, categoria: t.c.categoria }] };
    },
  };
  function semResposta() { return { encontrado: false, gerado_por_ia: false, fontes: [], pii_mascaradas: [], resposta: "Não encontrei essa informação nos conteúdos de exemplo." }; }
})();

// Acesso aos dados: servidor (SQLite + IA) ou demonstração
const Dados = {
  cursos: () => estado.demo ? Demo.cursos() : api("/api/cursos" + qEmpresa()),
  curso: id => estado.demo ? Demo.curso(id) : api(`/api/cursos/${id}${qEmpresa()}`),
  concluir: (c, l) => estado.demo ? Demo.concluir(c, l) : api(`/api/cursos/${c}/licoes/${l}/concluir${qEmpresa()}`, { method: "POST" }),
  responder: (c, l, opcao) => estado.demo ? Demo.responder(c, l, opcao) : api(`/api/cursos/${c}/licoes/${l}/responder${qEmpresa()}`, { method: "POST", body: { opcao } }),
  sugestoes: () => estado.demo ? Demo.sugestoes() : api("/api/sugestoes" + qEmpresa()),
  conteudos: () => estado.demo ? Demo.conteudos() : api("/api/conteudos" + qEmpresa()),
  conteudo: id => estado.demo ? Demo.conteudo(id) : api(`/api/conteudos/${id}`),
  chat: (pergunta, historico, aoTexto) => estado.demo ? Demo.chat(pergunta) : chatStream(pergunta, historico, aoTexto),
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
  $("#banner-demo").classList.toggle("hidden", !estado.demo);
  $(".user-acoes").classList.toggle("hidden", estado.demo);
  document.querySelectorAll("#nav a").forEach(a => {
    const so = a.dataset.so;   // restrição de perfil: "admin" (master + admin) | "master"
    a.classList.toggle("hidden", Boolean((so === "admin" && !ehAdmin()) || (so === "master" && !ehMaster()) || (a.dataset.servidor && estado.demo)));
  });
  $("#nav-admin").classList.toggle("hidden", !ehAdmin() || estado.demo);
  carregarEmpresas().finally(render);
}
async function carregarEmpresas() {
  if (estado.demo || !ehMaster()) return;
  try { estado.empresas = (await api("/api/empresas")).itens; } catch { estado.empresas = []; }
  if (!estado.empresas.some(e => e.id === estado.empresaId)) estado.empresaId = estado.empresas[0]?.id ?? null;
}
// Seletor de empresa (o master administra várias)
const seletorEmpresa = () => !ehMaster() ? "" : estado.empresas.length
  ? `<label class="seletor">Empresa <select id="sel-empresa">${estado.empresas.map(e => `<option value="${e.id}" ${e.id === estado.empresaId ? "selected" : ""}>${esc(e.nome)}</option>`).join("")}</select></label>`
  : `<span class="alerta demo">Crie uma empresa primeiro (menu Empresas).</span>`;
function ligarSeletorEmpresa(fn) { const s = $("#sel-empresa"); if (s) s.onchange = () => { estado.empresaId = +s.value; fn(); }; }
const semEmpresa = () => ehMaster() && !estado.empresaId && !estado.demo;
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
$("#sair").onclick = async () => { try { await api("/api/logout", { method: "POST" }); } catch { /* já saiu */ } conversa = []; mostrarLogin(); };
$("#trocar-senha").onclick = () => janela("Alterar senha", `
  <label class="field">Senha atual<input type="password" id="s-atual" autocomplete="current-password" required></label>
  <label class="field">Nova senha (mín. 10 caracteres, com letras e números)<input type="password" id="s-nova" autocomplete="new-password" required></label>`,
  { aoSalvar: async () => { await api("/api/senha", { method: "POST", body: { atual: $("#s-atual").value, nova: $("#s-nova").value } }); } });

const carregarScript = src => new Promise((ok, falha) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = falha; document.head.appendChild(s); });
async function iniciar() {
  let r = null;
  if (location.protocol !== "file:") { try { r = await fetch("/api/eu", { credentials: "same-origin" }); } catch { r = null; } }
  if (r && r.ok) return entrar(await r.json());                         // servidor + sessão ativa
  if (r && r.status === 401) return mostrarLogin();                      // servidor, sem sessão
  estado.demo = true;                                                    // sem servidor: demonstração
  try { await carregarScript("demo_conteudos.js"); } catch { /* sem conteúdo de exemplo */ }
  entrar({ nome: "Visitante", tipo: "funcionario", empresa: "Demonstração", llm: false });
}

// ---------- Rotas ----------
window.addEventListener("hashchange", render);
function render() {
  if (!estado.usuario) return;
  const [, rota = "inicio", a1, a2] = location.hash.split("/");
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.route === rota || (rota === "curso" && a.dataset.route === "cursos")));
  const telas = { inicio: telaInicio, cursos: telaCursos, curso: () => telaCurso(+a1, +a2 || null), chat: telaChat, historico: telaHistorico,
    biblioteca: telaBiblioteca, usuarios: telaUsuarios, lacunas: telaLacunas, empresas: telaEmpresas, ia: telaIA, sobre: telaSobre };
  const exige = { usuarios: ehAdmin() && !estado.demo, lacunas: ehAdmin() && !estado.demo, empresas: ehMaster() && !estado.demo, ia: ehMaster() && !estado.demo };
  view.style.animation = "none"; view.offsetHeight; view.style.animation = "";
  ((rota in exige && !exige[rota]) ? telaInicio : (telas[rota] || telaInicio))();
  scrollTo(0, 0);
}
const erroTela = err => { if (err.status !== 401) view.innerHTML = `<div class="card"><h2>Não foi possível carregar</h2><p class="muted">${esc(err.message)}</p></div>`; };
const cabecalho = (titulo, sub, acoes = "") => `<div class="page-head"><div><h1>${titulo}</h1><p class="muted">${sub}</p></div><div class="acoes">${seletorEmpresa()}${acoes}</div></div>`;

// ---------- Início ----------
const anel = pct => `<div class="anel" style="--p:${pct}"><span>${pct}%</span></div>`;
const cartaoCurso = c => `<a class="curso" href="#/curso/${c.id}">
  <div class="curso-topo"><span class="curso-ico">${iconeDe(c.categoria)}</span>${c.percentual === 100 ? '<span class="badge ok">Concluído</span>' : c.concluidas ? '<span class="badge">Em andamento</span>' : '<span class="badge soft">Novo</span>'}</div>
  <h3>${esc(c.titulo)}</h3><p class="muted">${c.licoes} lições · ~${c.minutos} min</p>
  <div class="progress"><i style="width:${c.percentual}%"></i></div><small class="muted">${c.concluidas} de ${c.licoes} concluídas</small></a>`;

async function telaInicio() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Início", "Bem-vindo ao OutGPT Enterprise.") + avisoSemEmpresa(); ligarSeletorEmpresa(telaInicio); return; }
  const primeiro = estado.usuario.nome.split(" ")[0];
  view.innerHTML = `${cabecalho(`Olá, ${esc(primeiro)} 👋`, "Tudo o que você precisa para aprender e resolver dúvidas do dia a dia.")}
    <form class="busca-grande" id="busca"><input id="busca-q" placeholder="Pergunte qualquer coisa sobre os procedimentos da empresa..." aria-label="Pergunte ao assistente" maxlength="1000" required><button class="btn primary">Perguntar</button></form>
    <div class="chips-linha" id="sug"></div>
    <div id="painel-admin"></div>
    <div id="meu-progresso"><div class="card">Carregando...</div></div>`;
  ligarSeletorEmpresa(telaInicio);
  $("#busca").onsubmit = e => { e.preventDefault(); pendente = $("#busca-q").value.trim(); location.hash = "#/chat"; };
  Dados.sugestoes().then(d => { $("#sug").innerHTML = d.itens.slice(0, 4).map(s => `<button class="chip" data-q="${esc(s)}">${esc(s)}</button>`).join(""); view.querySelectorAll("#sug .chip").forEach(c => c.onclick = () => { pendente = c.dataset.q; location.hash = "#/chat"; }); }).catch(() => {});
  if (ehAdmin() && !estado.demo) painelAdmin();
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
  } catch (err) { erroTela(err); }
}

async function painelAdmin() {
  const box = $("#painel-admin");
  try {
    const p = await api("/api/painel" + qEmpresa());
    let ia = "";
    if (ehMaster()) { const s = await api("/api/llm"); ia = s.configurada ? `<span class="badge ok">🤖 IA ativa · ${esc(s.modelo)}</span>` : `<a class="alerta demo" href="#/ia">⚠️ A IA ainda não está ligada. Configure a chave da API →</a>`; }
    box.innerHTML = `<div class="card painel"><div class="painel-topo"><h2>Painel da empresa</h2>${ia}</div>
      <div class="painel-nums"><div><b>${p.usuarios}</b><small>usuários ativos</small></div><div><b>${p.conteudos}</b><small>conteúdos</small></div><div><b>${p.cursos}</b><small>cursos</small></div><div><b>${p.perguntas_7d}</b><small>perguntas em 7 dias</small></div><div><b>${p.satisfacao === null ? "—" : p.satisfacao + "%"}</b><small>respostas úteis</small></div></div>${p.lacunas ? `<a class="alerta demo" href="#/lacunas">🔎 ${p.lacunas} pergunta(s) sem resposta: cadastre conteúdo para cobrir →</a>` : ""}
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
  const cats = [...new Set(d.itens.map(c => c.categoria))];
  const acoes = d.pode_editar ? `<button class="btn" id="sinc" title="Cria cursos para categorias novas e inclui conteúdos novos">↻ Atualizar cursos</button>` : "";
  view.innerHTML = cabecalho("Cursos", `${d.itens.length} cursos · ${d.resumo.licoes} lições · ${d.resumo.percentual}% concluído`, acoes) + (d.itens.length ? `
    <div class="chips-linha"><button class="chip on" data-cat="">Todos</button>${cats.map(c => `<button class="chip" data-cat="${esc(c)}">${iconeDe(c)} ${esc(c)}</button>`).join("")}</div>
    <div class="grid" id="lista-cursos"></div>` : `<div class="card vazio"><div class="vazio-ico">🎓</div><h2>Ainda não há cursos</h2><p class="muted">Cadastre conteúdos na Biblioteca para gerar cursos.</p></div>`);
  ligarSeletorEmpresa(telaCursos);
  const pintar = cat => {
    $("#lista-cursos").innerHTML = d.itens.filter(c => !cat || c.categoria === cat).map(c => d.pode_editar
      ? `<div class="curso-wrap">${cartaoCurso(c)}<div class="curso-admin"><button class="btn mini" data-ren="${c.id}">Renomear</button><button class="btn mini danger" data-del="${c.id}">Excluir</button></div></div>` : cartaoCurso(c)).join("");
    view.querySelectorAll("[data-ren]").forEach(b => b.onclick = () => { const c = d.itens.find(x => x.id === +b.dataset.ren);
      janela("Renomear curso", `<label class="field">Título<input id="c-tit" maxlength="200" required value="${esc(c.titulo)}"></label><label class="field">Descrição<input id="c-desc" maxlength="500" value="${esc(c.descricao)}"></label>`,
        { aoSalvar: async () => { await api(`/api/cursos/${c.id}`, { method: "PUT", body: { titulo: $("#c-tit").value, descricao: $("#c-desc").value } }); telaCursos(); } }); });
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => { const c = d.itens.find(x => x.id === +b.dataset.del);
      if (await confirmar(`Excluir o curso "${c.titulo}"? Os conteúdos continuam na Biblioteca; o progresso dos usuários neste curso será apagado.`)) { await api(`/api/cursos/${c.id}`, { method: "DELETE" }); telaCursos(); } });
  };
  if (d.itens.length) { pintar(""); view.querySelectorAll(".chips-linha .chip").forEach(b => b.onclick = () => { view.querySelectorAll(".chips-linha .chip").forEach(x => x.classList.toggle("on", x === b)); pintar(b.dataset.cat); }); }
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
    view.innerHTML = `<a href="#/cursos" class="muted voltar">← Cursos</a>
      <div class="curso-cab"><div><h1>${iconeDe(c.categoria)} ${esc(c.titulo)}</h1><p class="muted">${esc(c.descricao || "")}</p></div>${anel(pct)}</div>
      <div class="aula-layout">
        <nav class="card licoes" aria-label="Lições"><ol>${c.licoes.map((x, i) => `<li><button class="${i === atual ? "ativa" : ""} ${x.concluida ? "feita" : ""}" data-i="${i}"><span class="marca">${x.concluida ? "✓" : i + 1}</span><span>${esc(x.titulo)}</span></button></li>`).join("")}</ol></nav>
        <div class="aula">
          <article class="card">
            <small class="muted">LIÇÃO ${atual + 1} DE ${c.licoes.length} · ~${l.minutos} MIN</small>
            <h2>${esc(l.titulo)}</h2>
            <div class="texto-aula">${md(l.texto)}</div>
          </article>
          ${pct === 100 && l.concluida && ultimo ? finalCurso() : ""}
          ${l.quiz ? `<div class="card quiz"><small class="muted">VERIFIQUE O QUE APRENDEU</small><h3>${esc(l.quiz.pergunta)}</h3>
              <div id="alt">${l.quiz.opcoes.map((o, i) => `<button class="opt-btn" data-o="${i}" ${respondida ? "disabled" : ""}>${esc(o)}</button>`).join("")}</div>
              <div id="retorno-quiz">${respondida ? `<p class="muted">Você já respondeu esta pergunta (${l.acertou ? "acertou ✓" : "errou"}).</p>` : ""}</div></div>` : ""}
          <div class="aula-nav">
            <button class="btn" id="ant" ${atual === 0 ? "disabled" : ""}>← Anterior</button>
            ${!l.quiz && !l.concluida ? `<button class="btn primary" id="concluir">Concluir lição${ultimo ? "" : " e continuar"}</button>` : ""}
            <button class="btn ${l.concluida || l.quiz ? "primary" : ""}" id="prox" ${ultimo ? "disabled" : ""}>Próxima →</button>
          </div>
        </div></div>`;
    view.querySelectorAll("[data-i]").forEach(b => b.onclick = () => { atual = +b.dataset.i; desenhar(); scrollTo(0, 0); });
    $("#ant").onclick = () => { atual--; desenhar(); scrollTo(0, 0); };
    $("#prox").onclick = () => { atual++; desenhar(); scrollTo(0, 0); };
    if ($("#concluir")) $("#concluir").onclick = async () => { try { await Dados.concluir(c.id, l.conteudo_id); l.concluida = true; if (!ultimo) atual++; desenhar(); scrollTo(0, 0); } catch (err) { erroTela(err); } };
    view.querySelectorAll("[data-o]").forEach(b => b.onclick = async () => {
      view.querySelectorAll("[data-o]").forEach(x => x.disabled = true);
      try {
        const r = await Dados.responder(c.id, l.conteudo_id, +b.dataset.o);
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
  const finalCurso = () => { const resp = c.licoes.filter(x => x.acertou !== null), ac = resp.filter(x => x.acertou).length;
    return `<div class="card parabens"><div class="vazio-ico">🎉</div><h2>Curso concluído!</h2><p class="muted">Você completou as ${c.licoes.length} lições${resp.length ? ` e acertou ${ac} de ${resp.length} perguntas` : ""}.</p><a class="btn primary" href="#/cursos">Ver outros cursos</a></div>`; };
  desenhar();
}

// ---------- Assistente (RAG + LLM) ----------
async function telaChat() {
  if (semEmpresa()) { view.innerHTML = cabecalho("Assistente", "") + avisoSemEmpresa(); ligarSeletorEmpresa(telaChat); return; }
  const u = estado.usuario;
  const status = estado.demo ? `<span class="badge warn">Demonstração · sem IA</span>` : u.llm ? `<span class="badge ok">🤖 IA ativa · ${esc(u.modelo)}</span>` : `<span class="badge warn">🔎 Só busca (IA não configurada)</span>`;
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
    const w = add("bot typing", estado.demo ? "Buscando nos conteúdos..." : "Consultando os conteúdos e preparando a resposta...");
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
      const selo = r.gerado_por_ia ? `<span class="selo">🤖 Resposta gerada por IA a partir dos conteúdos</span>` : r.encontrado ? `<span class="selo">🔎 Trecho do manual${estado.demo ? " (demonstração)" : ""}</span>` : "";
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
  if (estado.demo) { view.innerHTML = cabecalho("Histórico de dúvidas", "Disponível quando o servidor está ativo.") + `<div class="card vazio"><div class="vazio-ico">🕘</div><p class="muted">O histórico das suas perguntas é guardado no banco de dados da empresa.</p></div>`; return; }
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
  const acoes = d.pode_editar ? `<button class="btn" id="imp">⬆ Importar CSV</button><button class="btn" id="arq">📄 Enviar arquivo</button><button class="btn primary" id="novo">+ Novo conteúdo</button>` : "";
  view.innerHTML = cabecalho("Biblioteca", `${d.total} conteúdo(s) disponíveis para você.`, acoes) + `
    <div class="card"><div class="row2"><input id="c-q" placeholder="Filtrar por título, código ou texto..." aria-label="Filtrar conteúdos">
      <select id="c-cat"><option value="">Todas as categorias</option>${d.categorias.map(c => `<option>${esc(c)}</option>`).join("")}</select></div>
      <p class="muted" id="c-total"></p><div class="table-wrap"><table><thead><tr><th>Código</th><th>Título</th><th>Categoria</th><th>Visível para</th><th></th></tr></thead><tbody id="c-body"></tbody></table></div></div>`;
  ligarSeletorEmpresa(telaBiblioteca);
  const pintar = () => {
    const q = $("#c-q").value.toLowerCase(), cat = $("#c-cat").value;
    const itens = d.itens.filter(c => (!cat || c.categoria === cat) && `${c.codigo} ${c.titulo} ${c.resumo}`.toLowerCase().includes(q));
    $("#c-total").textContent = `${itens.length} de ${d.total} conteúdo(s)`;
    $("#c-body").innerHTML = itens.map(c => `<tr><td>${esc(c.codigo)}</td><td>${c.arquivo_nome ? "📄 " : ""}${esc(c.titulo)}${c.contem_pii ? ' <span class="badge warn">PII</span>' : ""}</td><td>${esc(c.categoria)}</td>
      <td><span class="badge ${c.visibilidade === "todos" ? "ok" : ""}">${c.visibilidade === "todos" ? "Todos (inclui externos)" : "Somente internos"}</span></td>
      <td class="acoes-linha"><button class="btn mini" data-ver="${c.id}">Ver</button>${d.pode_editar ? `<button class="btn mini" data-edit="${c.id}">Editar</button><button class="btn mini danger" data-del="${c.id}">Excluir</button>` : ""}</td></tr>`).join("");
    view.querySelectorAll("[data-ver]").forEach(b => b.onclick = async () => { try { const c = await Dados.conteudo(+b.dataset.ver); janela(c.titulo, `<p class="muted">${esc(c.codigo)} · ${esc(c.categoria)}${c.arquivo_nome ? " · arquivo " + esc(c.arquivo_nome) : ""}</p>${md(c.texto)}`, { larga: true }); } catch (e) { janela("Erro", `<p>${esc(e.message)}</p>`); } });
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = async () => formConteudo(await api(`/api/conteudos/${b.dataset.edit}`), d.categorias));
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      const c = d.itens.find(x => x.id === +b.dataset.del);
      if (!(await confirmar(`Excluir "${c.titulo}"? Esta ação não pode ser desfeita.`))) return;
      try { await api(`/api/conteudos/${c.id}`, { method: "DELETE" }); telaBiblioteca(); } catch (err) { janela("Erro", `<p>${esc(err.message)}</p>`); }
    });
  };
  $("#c-q").oninput = pintar; $("#c-cat").onchange = pintar; pintar();
  if ($("#novo")) $("#novo").onclick = () => formConteudo(null, d.categorias);
  if ($("#arq")) $("#arq").onclick = () => formArquivo(d.categorias);
  if ($("#imp")) $("#imp").onclick = () => formImportar();
  if (acaoPendente && d.pode_editar) { const a = acaoPendente; acaoPendente = null; (a === "arquivo" ? formArquivo(d.categorias) : formConteudo(null, d.categorias)); }
}

const datalistCats = cats => `<datalist id="lista-cats">${(cats || []).map(c => `<option value="${esc(c)}">`).join("")}</datalist>`;
function formConteudo(c, cats, opc = {}) {
  const novo = !c || opc.semId;
  janela(novo ? "Novo conteúdo" : "Editar conteúdo", `
    ${novo ? `<label class="field">Código (opcional)<input id="f-codigo" maxlength="60" placeholder="Ex.: SOP_RH_30"></label>` : `<p class="muted">Código: ${esc(c.codigo)}${c.arquivo_nome ? " · arquivo " + esc(c.arquivo_nome) : ""}</p>`}
    <label class="field">Título *<input id="f-titulo" maxlength="200" required value="${esc(c?.titulo)}"></label>
    <div class="row2"><label class="field">Categoria (vira um curso)<input id="f-cat" list="lista-cats" maxlength="100" value="${esc(c?.categoria || "Geral")}"></label>${datalistCats(cats)}
      <label class="field">Visível para<select id="f-vis"><option value="internos" ${c?.visibilidade !== "todos" ? "selected" : ""}>Somente internos</option>
        <option value="todos" ${c?.visibilidade === "todos" ? "selected" : ""}>Todos (inclui colaboradores externos)</option></select></label></div>
    <label class="field">Conteúdo *<textarea id="f-texto" maxlength="400000" rows="9" required>${esc(c?.texto)}</textarea></label>
    <label class="field">Pergunta de exemplo (melhora a busca e gera a pergunta de verificação do curso)<input id="f-perg" maxlength="500" value="${esc(c?.pergunta_exemplo)}"></label>
    <label class="field">Resposta de exemplo (resposta correta da pergunta acima)<textarea id="f-resp" maxlength="2000" rows="3">${esc(c?.resposta_exemplo)}</textarea></label>
    <label class="opt"><input type="checkbox" id="f-pii" ${c?.contem_pii ? "checked" : ""}><span>Este conteúdo trata de dados pessoais (PII)</span></label>`,
    { larga: true, aoSalvar: async () => {
      const corpo = { titulo: $("#f-titulo").value, categoria: $("#f-cat").value, texto: $("#f-texto").value, pergunta_exemplo: $("#f-perg").value, resposta_exemplo: $("#f-resp").value, visibilidade: $("#f-vis").value, contem_pii: $("#f-pii").checked };
      if (novo) await api("/api/conteudos", { method: "POST", body: { ...corpo, codigo: $("#f-codigo")?.value, empresa_id: estado.empresaId } });
      else await api(`/api/conteudos/${c.id}`, { method: "PUT", body: corpo });
      if (opc.aoCriar) opc.aoCriar(); else telaBiblioteca();
    } });
}

function formArquivo(cats) {
  janela("Enviar arquivo", `
    <p class="muted">O texto do arquivo é dividido em trechos e indexado: o assistente passa a responder com base nele. Formatos: <strong>.txt, .md, .pdf, .docx</strong> (até 8 MB; PDF precisa ter texto selecionável).</p>
    <label class="field">Arquivo *<input type="file" id="f-arq" accept=".txt,.md,.pdf,.docx" required></label>
    <label class="field">Título (opcional; padrão: nome do arquivo)<input id="f-titulo" maxlength="200"></label>
    <div class="row2"><label class="field">Categoria<input id="f-cat" list="lista-cats" maxlength="100" value="Documentos"></label>${datalistCats(cats)}
      <label class="field">Visível para<select id="f-vis"><option value="internos">Somente internos</option><option value="todos">Todos (inclui externos)</option></select></label></div>`,
    { salvar: "Enviar e indexar", aoSalvar: async d => {
      const arq = $("#f-arq").files[0]; if (!arq) throw new Error("Escolha um arquivo.");
      if (arq.size > 8_000_000) throw new Error("O arquivo passa de 8 MB.");
      $("#j-salvar", d).textContent = "Processando...";
      const b64 = await new Promise((ok, falha) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = falha; r.readAsDataURL(arq); });
      const r = await api("/api/conteudos/arquivo", { method: "POST", body: { nome: arq.name, dados: b64, titulo: $("#f-titulo").value, categoria: $("#f-cat").value, visibilidade: $("#f-vis").value, empresa_id: estado.empresaId } });
      janela("Arquivo indexado", `<p>${r.caracteres.toLocaleString("pt-BR")} caracteres divididos em <strong>${r.trechos}</strong> trecho(s). O assistente já pode responder com base neste arquivo.</p>`);
      telaBiblioteca();
    } });
}

function formImportar() {
  janela("Importar conteúdos de um CSV", `
    <p class="muted">Colunas: <code>id, categoria, procedimento_titulo, contexto_documental, pergunta_utilizador, resposta_esperada, contem_pii</code>. Conteúdos com o mesmo id são atualizados. Cada categoria vira um curso.</p>
    <label class="field">Arquivo CSV<input type="file" id="f-arq" accept=".csv,text/csv" required></label>
    <label class="field">Visível para<select id="f-vis"><option value="internos">Somente internos</option><option value="todos">Todos (inclui externos)</option></select></label>`,
    { salvar: "Importar", aoSalvar: async d => {
      const arq = $("#f-arq").files[0]; if (!arq) throw new Error("Escolha um arquivo.");
      $("#j-salvar", d).textContent = "Importando...";
      const r = await api("/api/conteudos/importar", { method: "POST", body: { csv: await arq.text(), visibilidade: $("#f-vis").value, empresa_id: estado.empresaId } });
      janela("Importação concluída", `<p>${r.importados} conteúdo(s) importados, indexados e organizados em cursos.</p>`);
      telaBiblioteca();
    } });
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
  let d; try { d = await api("/api/usuarios" + qEmpresa()); } catch (err) { return erroTela(err); }
  view.innerHTML = cabecalho("Usuários", `${d.itens.length} usuário(s).`, `<button class="btn primary" id="novo">+ Novo usuário</button>`) + `<div class="card table-wrap"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Último acesso</th><th>Status</th><th></th></tr></thead><tbody>${d.itens.map(x => `
    <tr><td>${esc(x.nome)}</td><td>${esc(x.email)}</td><td>${esc(ROTULOS[x.tipo])}</td><td>${quando(x.ultimo_login)}</td>
    <td><span class="badge ${x.ativo ? "ok" : "warn"}">${x.ativo ? "Ativo" : "Desativado"}</span></td>
    <td class="acoes-linha">${x.tipo === "master" ? "" : `<button class="btn mini" data-edit="${x.id}">Editar</button>`}</td></tr>`).join("")}</tbody></table></div>`;
  ligarSeletorEmpresa(telaUsuarios);
  const tipos = ehMaster() ? ["admin", "funcionario", "colaborador_interno", "colaborador_externo"] : ["funcionario", "colaborador_interno", "colaborador_externo"];
  const opcoes = sel => tipos.map(t => `<option value="${t}" ${t === sel ? "selected" : ""}>${ROTULOS[t]}</option>`).join("");
  const abrirNovo = () => janela("Novo usuário", `
    <label class="field">Nome *<input id="u-nome" maxlength="120" required></label>
    <label class="field">E-mail (será o login) *<input id="u-email" type="email" maxlength="160" required></label>
    <label class="field">Senha inicial * (mín. 10 caracteres, com letras e números)<input id="u-senha" type="password" autocomplete="new-password" required></label>
    <label class="field">Perfil<select id="u-tipo">${opcoes("funcionario")}</select></label>
    <p class="muted">Funcionários e colaboradores internos veem todos os conteúdos da empresa; colaboradores externos veem só os marcados como "Todos".</p>`,
    { salvar: "Criar usuário", aoSalvar: async () => {
      await api("/api/usuarios", { method: "POST", body: { nome: $("#u-nome").value, email: $("#u-email").value, senha: $("#u-senha").value, tipo: $("#u-tipo").value, empresa_id: estado.empresaId } });
      telaUsuarios();
    } });
  $("#novo").onclick = abrirNovo;
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
  if (acaoPendente === "usuario") { acaoPendente = null; abrirNovo(); }
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
    <div class="card"><h2>Pesquisa com especialistas</h2>
      <p class="muted">Ajude o projeto: responda à pesquisa sobre a importância da ferramenta para empresas e instituições de ensino.</p>
      <a class="btn" href="pesquisa.html">Abrir a pesquisa</a></div>`;
}

iniciar();
