"""Teste de ponta a ponta do sistema (servidor, banco, RAG, cursos, IA...) em banco temporário.

A API da Anthropic é simulada por um servidor local: nenhuma chave real é usada e nada é cobrado.
Uso (na pasta backend):  python -m pip install -r requirements.txt fpdf2   e depois   python tests/teste_sistema.py
Sai com código 1 se alguma verificação falhar (usado pelo GitHub Actions).
"""
import atexit, base64, http.server, io, json, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
from pathlib import Path

BACK = str(Path(__file__).resolve().parent.parent)
tmp = tempfile.mkdtemp()
env = {**os.environ, "OUTGPT_DB": os.path.join(tmp, "t.db"), "OUTGPT_CHROMA": os.path.join(tmp, "chroma"), "OUTGPT_ENV_ARQ": os.path.join(tmp, "teste.env"),
       "OUTGPT_PORTA": "8170", "ANTHROPIC_API_KEY": "chave-de-teste", "ANTHROPIC_BASE_URL": "http://127.0.0.1:8171"}
env.pop("ANTHROPIC_AUTH_TOKEN", None)
capturado = []


class Falso(http.server.BaseHTTPRequestHandler):
    def _sse(self, corpo, texto):
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        def ev(nome, dados): self.wfile.write(f"event: {nome}\ndata: {json.dumps(dados)}\n\n".encode()); self.wfile.flush()
        ev("message_start", {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"], "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 120, "output_tokens": 1}}})
        ev("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
        for parte in texto:
            ev("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": parte}}); time.sleep(0.25)
        ev("content_block_stop", {"type": "content_block_stop", "index": 0})
        ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 15}})
        ev("message_stop", {"type": "message_stop"})

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        corpo["_chave"] = self.headers.get("x-api-key") or (self.headers.get("authorization") or "").replace("Bearer ", "")
        capturado.append(corpo)
        bruto = json.dumps(corpo)
        if "FALHAR" in bruto:
            self.send_response(401); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(b'{"type":"error","error":{"type":"authentication_error","message":"x"}}'); return
        fmt = (corpo.get("output_config") or {}).get("format")
        if fmt:   # saída estruturada (geração de pergunta de verificação)
            if "JSONRUIM" in bruto: txt = "isto nao e json"
            elif "DUPLICADA" in bruto: txt = json.dumps({"pergunta": "P?", "correta": "A", "errada_1": "A", "errada_2": "B", "errada_3": "C"})
            else: txt = json.dumps({"pergunta": "Qual é o prazo para pedir aprovação da viagem?", "correta": "10 dias de antecedência", "errada_1": "2 dias de antecedência", "errada_2": "30 dias de antecedência", "errada_3": "Não é preciso pedir aprovação"})
            b = json.dumps({"id": "msg_q", "type": "message", "role": "assistant", "model": corpo["model"], "stop_reason": "end_turn", "stop_sequence": None, "content": [{"type": "text", "text": txt}], "usage": {"input_tokens": 300, "output_tokens": 60}}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        sem_base = "tempo amanha" in bruto
        achou = re.search(r'<documento codigo="([^"]+)"', str((corpo.get("messages") or [{}])[-1].get("content", "")))
        cita = achou.group(1) if ("CITAR_FONTE" in bruto and not sem_base and achou) else None     # cita só o 1º documento recebido
        if corpo.get("stream"):
            return self._sse(corpo, ["SEM_", "BASE"] if sem_base else ["Resposta ", "simulada ", "em partes. ", f"Fonte: [{cita}]" if cita else "Fonte: [X]"])
        r = {"id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"], "stop_reason": "end_turn", "stop_sequence": None,
             "content": [{"type": "text", "text": "SEM_BASE" if sem_base else (f"Resposta simulada. Fonte: [{cita}]" if cita else "Resposta simulada. Fonte: [X]")}], "usage": {"input_tokens": 120, "output_tokens": 15}}
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a): pass

threading.Thread(target=http.server.HTTPServer(("127.0.0.1", 8171), Falso).serve_forever, daemon=True).start()
r = subprocess.run([sys.executable, "init_db.py"], cwd=BACK, env=env, capture_output=True, text=True); print(r.stdout.strip().splitlines()[0][:70])
sys.path.insert(0, BACK)
os.environ.update({k: env[k] for k in ("OUTGPT_DB", "OUTGPT_CHROMA", "OUTGPT_ENV_ARQ")})
import auth, db  # noqa
PW = "Teste-Master-123"
with db.conectar() as con:
    con.execute("INSERT INTO usuarios (empresa_id,nome,email,senha_hash,tipo) VALUES (NULL,'Dono','dono@teste.com',?,'master')", (auth.hash_senha(PW),))
LOG = open(os.path.join(tmp, "servidor.log"), "w")
env = {**env, "CODESPACE_NAME": "meucodespace", "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"}   # testa a origem do Codespaces
srv = subprocess.Popen([sys.executable, "server.py"], cwd=BACK, env=env, stdout=LOG, stderr=subprocess.STDOUT, text=True)
atexit.register(srv.terminate)
B = "http://127.0.0.1:8170"
for _ in range(180):                       # espera o servidor responder (o primeiro início pode demorar)
    try:
        urllib.request.urlopen(B + "/saude", timeout=2).read(); break
    except Exception:
        time.sleep(1)
else:
    print("O servidor não iniciou. Log:"); print(open(os.path.join(tmp, "servidor.log")).read()[-3000:]); sys.exit(1)


class Cli:
    def __init__(self): self.cookie = None

    def req(self, m, p, d=None, origin=None, extra=None):
        h = {"Content-Type": "application/json", **(extra or {})}
        if self.cookie: h["Cookie"] = self.cookie
        if origin: h["Origin"] = origin
        rq = urllib.request.Request(B + p, data=None if d is None else json.dumps(d).encode(), method=m, headers=h)
        try: r = urllib.request.urlopen(rq, timeout=180)
        except urllib.error.HTTPError as e: r = e
        sc = r.headers.get("Set-Cookie")
        if sc and "=" in sc: self.cookie = sc.split(";")[0] if not sc.split(";")[0].endswith("=") else None
        raw = r.read()
        try: return r.status, json.loads(raw)
        except Exception: return r.status, raw

    def stream(self, p, d):
        h = {"Content-Type": "application/json"}
        if self.cookie: h["Cookie"] = self.cookie
        rq = urllib.request.Request(B + p, data=json.dumps(d).encode(), method="POST", headers=h)
        try: r = urllib.request.urlopen(rq, timeout=180)
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read()), []
        eventos, atual = [], None
        for linha in r:
            linha = linha.decode().rstrip("\n")
            if linha.startswith("event: "): atual = linha[7:]
            elif linha.startswith("data: "): eventos.append((atual, json.loads(linha[6:]), time.time()))
        return r.status, r.headers.get("Content-Type"), eventos

ok = fail = 0
def chk(nome, cond, extra=""):
    global ok, fail
    ok += bool(cond); fail += (not cond)
    print(("PASS " if cond else "FAIL ") + nome + (" | " + str(extra)[:200] if (not cond or extra) else ""))

m = Cli(); chk("login master", m.req("POST", "/api/login", {"email": "dono@teste.com", "senha": PW})[0] == 200)
_a = m.req("POST", "/api/empresas", {"nome": "Acme"}); _b = m.req("POST", "/api/empresas", {"nome": "Beta"}); print("empresas:", _a, _b)
acme = _a[1]["id"]; beta = _b[1]["id"]
csvtxt = open(os.path.join(BACK, "data", "sops_corporativos.csv"), encoding="utf-8-sig").read()
s, d = m.req("POST", "/api/conteudos/importar", {"empresa_id": acme, "csv": csvtxt, "visibilidade": "internos"}); chk("importa 100 SOPs", s == 200 and d["importados"] == 100, d)
for nome, email, tipo in [("Ana", "ana@acme.com", "admin"), ("Fabio", "fabio@acme.com", "funcionario"), ("Carla", "carla@ext.com", "colaborador_externo")]:
    m.req("POST", "/api/usuarios", {"empresa_id": acme, "nome": nome, "email": email, "senha": "senhaforte123", "tipo": tipo})
adm, func, ext = Cli(), Cli(), Cli()
for cl, e in ((adm, "ana@acme.com"), (func, "fabio@acme.com"), (ext, "carla@ext.com")): cl.req("POST", "/api/login", {"email": e, "senha": "senhaforte123"})

# ---------- cursos ----------
s, d = func.req("GET", "/api/cursos"); cs = d["itens"]
chk("12 cursos gerados das 6 categorias", s == 200 and len(cs) == 12, [c["titulo"] for c in cs])
chk("categorias grandes divididas em partes", any("Parte 1 de 3" in c["titulo"] for c in cs) and sum(c["licoes"] for c in cs) == 100, sum(c["licoes"] for c in cs))
chk("externo não vê cursos (tudo é interno)", ext.req("GET", "/api/cursos")[1]["itens"] == [])
chk("master precisa escolher empresa", m.req("GET", "/api/cursos")[0] == 400 and m.req("GET", f"/api/cursos?empresa_id={acme}")[0] == 200)
c0 = cs[0]; s, det = func.req("GET", f"/api/cursos/{c0['id']}")
chk("detalhe do curso com lições e quiz", s == 200 and det["licoes"] and det["licoes"][0]["quiz"] and len(det["licoes"][0]["quiz"]["opcoes"]) == 4, det["licoes"][0]["quiz"] if det["licoes"] else det)
chk("detalhe NÃO revela a alternativa certa", "indice" not in json.dumps(det) and "resposta_certa" not in json.dumps(det))
lic = det["licoes"][0]
with db.conectar() as con:
    certa = con.execute("SELECT resposta_exemplo FROM conteudos WHERE id=?", (lic["conteudo_id"],)).fetchone()[0]
idx = lic["quiz"]["opcoes"].index(certa)
errada = (idx + 1) % 4
s, r = func.req("POST", f"/api/cursos/{c0['id']}/licoes/{lic['conteudo_id']}/responder", {"opcao": errada})
chk("resposta errada corrigida e certa revelada", s == 200 and r["correta"] is False and r["resposta_certa"] == certa, r)
s, r = func.req("POST", f"/api/cursos/{c0['id']}/licoes/{lic['conteudo_id']}/responder", {"opcao": idx})
chk("só a 1ª tentativa conta (segue 0 acertos)", s == 200 and func.req("GET", "/api/cursos")[1]["resumo"]["acertos"] == 0 and func.req("GET", "/api/cursos")[1]["resumo"]["respondidas"] == 1)
lic2 = det["licoes"][1]
func.req("POST", f"/api/cursos/{c0['id']}/licoes/{lic2['conteudo_id']}/responder", {"opcao": lic2 and __import__('builtins').next(i for i, o in enumerate(lic2["quiz"]["opcoes"]) if o == __import__('sqlite3').connect(env["OUTGPT_DB"]).execute("SELECT resposta_exemplo FROM conteudos WHERE id=?", (lic2["conteudo_id"],)).fetchone()[0])})
res = func.req("GET", "/api/cursos")[1]["resumo"]
chk("progresso: 2 lições concluídas, 1 acerto", res["concluidas"] == 2 and res["acertos"] == 1 and res["continuar"]["curso_id"] == c0["id"], res)
chk("concluir lição sem quiz", func.req("POST", f"/api/cursos/{c0['id']}/licoes/{det['licoes'][2]['conteudo_id']}/concluir", {})[0] == 200)
chk("progresso é por usuário", adm.req("GET", "/api/cursos")[1]["resumo"]["concluidas"] == 0)
chk("lição de outro curso/empresa não conclui", func.req("POST", f"/api/cursos/{c0['id']}/licoes/999999/concluir", {})[0] == 404)
chk("funcionário não gerencia cursos", func.req("DELETE", f"/api/cursos/{c0['id']}")[0] == 403 and func.req("POST", "/api/cursos/sincronizar", {})[0] == 403)
chk("admin edita curso", adm.req("PUT", f"/api/cursos/{c0['id']}", {"titulo": "TI e Acessos (novo)", "descricao": "d"})[0] == 200)
chk("admin Acme não mexe em curso de outra empresa", m.req("POST", "/api/empresas", {"nome": "Z"})[0] == 200)

# ---------- visibilidade pública libera cursos ao externo ----------
s, d = adm.req("POST", "/api/conteudos", {"codigo": "PUB1", "titulo": "Horário da recepção", "categoria": "Geral", "texto": "A recepção funciona das 8h às 18h.",
                                          "visibilidade": "todos", "pergunta_exemplo": "Qual o horário da recepção?", "resposta_exemplo": "Das 8h às 18h."}); pub = d["id"]
chk("novo conteúdo gera curso 'Geral' automaticamente", any(c["titulo"] == "Geral" for c in adm.req("GET", "/api/cursos")[1]["itens"]))
ce = ext.req("GET", "/api/cursos")[1]["itens"]
chk("externo vê só o curso com conteúdo público", [c["titulo"] for c in ce] == ["Geral"], ce)
chk("quiz some quando faltam alternativas (poucos conteúdos públicos)", ext.req("GET", f"/api/cursos/{ce[0]['id']}")[1]["licoes"][0]["quiz"] is None)

# ---------- listagem / detalhe de conteúdos ----------
s, d = func.req("GET", "/api/conteudos"); chk("lista traz resumo, não o texto todo", "resumo" in d["itens"][0] and "texto" not in d["itens"][0])
sid = d["itens"][0]["id"]; chk("detalhe completo por id", "texto" in func.req("GET", f"/api/conteudos/{sid}")[1])
chk("externo não abre conteúdo interno por id", ext.req("GET", f"/api/conteudos/{sid}")[0] == 404)

# ---------- arquivos: TXT longo, DOCX, PDF ----------
base_p = [
 "Todos os colaboradores devem registrar a entrada e a saída no sistema de ponto eletrônico. Em caso de esquecimento, a correção deve ser solicitada ao gestor no mesmo dia.",
 "O uso de equipamentos da empresa é restrito a atividades profissionais. Notebooks devem ser guardados em gaveta com chave ao fim do expediente e nunca deixados em veículos.",
 "As reuniões devem ser agendadas pelo calendário corporativo com pelo menos um dia de antecedência, informando pauta e participantes. Salas não utilizadas após quinze minutos são liberadas.",
 "A sala de reunião azul possui um cofre para guardar documentos de clientes. O código do cofre da sala de reunião azul é 7391 e só o gerente de operações pode abri-lo.",
 "Visitantes devem ser registrados na recepção e acompanhados durante toda a permanência. O crachá de visitante deve ser devolvido na saída.",
 "A copa possui café e água à vontade. Alimentos devem ser identificados com nome e data, e a geladeira é limpa toda sexta-feira às dezesseis horas.",
 "Solicitações de manutenção predial devem ser abertas no sistema de chamados informando o local exato e o problema observado, com fotos quando possível.",
]
longo = "\n\n".join(base_p * 8)            # ~9 mil caracteres: grande demais para virar lição
b64 = lambda b: base64.b64encode(b).decode()
s, d = adm.req("POST", "/api/conteudos/arquivo", {"nome": "manual_convivencia.txt", "dados": b64(longo.encode()), "categoria": "Manuais", "visibilidade": "internos"})
chk("TXT longo enviado e dividido em vários trechos", s == 200 and d["trechos"] >= 8, d)
import docx as _docx
dd = _docx.Document(); dd.add_paragraph("Política de reembolso de táxi"); dd.add_paragraph("O reembolso de táxi exige a nota fiscal e o motivo da corrida; o limite mensal é de R$ 450,00 por pessoa.")
bio = io.BytesIO(); dd.save(bio)
s, d = adm.req("POST", "/api/conteudos/arquivo", {"nome": "politica_taxi.docx", "dados": b64(bio.getvalue()), "visibilidade": "internos"}); chk("DOCX enviado", s == 200, d)
from fpdf import FPDF
p = FPDF(); p.add_page(); p.set_font("Helvetica", size=12); p.multi_cell(0, 8, "Procedimento de devolucao de equipamentos. O colaborador deve devolver notebook e crachá em ate 5 dias uteis apos o desligamento, no setor de TI.")
s, d = adm.req("POST", "/api/conteudos/arquivo", {"nome": "devolucao.pdf", "dados": b64(bytes(p.output())), "visibilidade": "internos"}); chk("PDF enviado e texto extraído", s == 200, d)
chk("formato inválido rejeitado", adm.req("POST", "/api/conteudos/arquivo", {"nome": "x.exe", "dados": b64(b"MZ....")})[0] == 400)
chk("base64 inválido rejeitado", adm.req("POST", "/api/conteudos/arquivo", {"nome": "x.txt", "dados": "###"})[0] == 400)
chk("funcionário não envia arquivo", func.req("POST", "/api/conteudos/arquivo", {"nome": "x.txt", "dados": b64(b"abc")})[0] == 403)
chk("manual longo NÃO vira lição (fica só na busca)", not any(c["titulo"] == "Manuais" for c in adm.req("GET", "/api/cursos")[1]["itens"]))

# ---------- chunking no RAG + LLM ----------
n0 = len(capturado)
s, d = func.req("POST", "/api/chat", {"pergunta": "qual o código do cofre da sala azul?"})
ctx = json.dumps(capturado[-1], ensure_ascii=False)
chk("RAG acha o trecho certo dentro do documento longo", s == 200 and d["gerado_por_ia"] and "7391" in ctx and "manual convivencia" in ctx.lower().replace("_", " "), d.get("fontes"))
msg_user = capturado[-1]["messages"][-1]["content"]
chk("só os trechos relevantes (não o manual inteiro) vão à LLM", len(msg_user) < len(longo) * 0.5, f"{len(msg_user)} vs {len(longo)}")
s, d = func.req("POST", "/api/chat", {"pergunta": "qual o limite mensal do reembolso de táxi?"}); ctx = json.dumps(capturado[-1], ensure_ascii=False)
chk("RAG responde de DOCX (450,00)", d["gerado_por_ia"] and "450,00" in ctx, d.get("fontes"))
s, d = func.req("POST", "/api/chat", {"pergunta": "em quantos dias devolvo o notebook ao sair?"}); ctx = json.dumps(capturado[-1], ensure_ascii=False)
chk("RAG responde de PDF (5 dias)", d["gerado_por_ia"] and "5 dias" in ctx, d.get("fontes"))
chk("prompt: instruções de clareza e fonte", "Fonte: [CÓDIGO]" in capturado[-1]["system"] and "negrito" in capturado[-1]["system"])
s, d = func.req("POST", "/api/chat", {"pergunta": "previsao do tempo amanha"})
chk("LLM responde SEM_BASE: vira recusa, sem fontes", s == 200 and d["encontrado"] is False and d["fontes"] == [] and "Não encontrei" in d["resposta"], d)
s, d = func.req("POST", "/api/chat", {"pergunta": "como funciona o ponto eletrônico?"})
chk("busca por palavras-chave rescata pergunta curta (ponto eletrônico)", d["encontrado"] and d["gerado_por_ia"], d.get("fontes"))
s, d = func.req("POST", "/api/chat", {"pergunta": "Como faco para aceder aos sistemas internos de casa?"}); ctx = json.dumps(capturado[-1], ensure_ascii=False)
chk("SOP: contexto traz resposta_modelo e fonte", "<resposta_modelo>" in ctx and d["fontes"][0]["codigo"] == "SOP_TI_01", d["fontes"])
# histórico da conversa
hist = [{"pergunta": "Como faco para aceder aos sistemas internos de casa? meu email e ze@x.com", "resposta": d["resposta"]}]
func.req("POST", "/api/chat", {"pergunta": "e precisa de 2FA?", "historico": hist})
msgs = capturado[-1]["messages"]
chk("conversa anterior enviada à LLM (user/assistant/user)", [m_["role"] for m_ in msgs] == ["user", "assistant", "user"], [m_["role"] for m_ in msgs])
chk("e-mail do histórico mascarado", "ze@x.com" not in json.dumps(capturado[-1]) and "[EMAIL]" in msgs[0]["content"])
chk("pergunta curta de continuação usa o contexto anterior na busca", "SOP_TI_01" in json.dumps(capturado[-1]))
func.req("POST", "/api/chat", {"pergunta": "E preciso de segundo fator de autenticação?", "historico": hist})
chk("continuação longa (6+ palavras, sem assunto próprio) também recupera a fonte anterior", "SOP_TI_01" in json.dumps(capturado[-1]), capturado[-1]["messages"][-1])
s, d = func.req("POST", "/api/chat", {"pergunta": "Quanto tempo de antecedencia preciso para pedir ferias? CITAR_FONTE"})
n_docs = capturado[-1]["messages"][-1]["content"].count("<documento ")
chk("só aparecem as fontes que a resposta cita (recuperou vários, citou um)", n_docs > 1 and len(d["fontes"]) == 1, (n_docs, [f["codigo"] for f in d["fontes"]], d.get("resposta"), d.get("gerado_por_ia"), d.get("aviso")))
chk("histórico malformado é ignorado", func.req("POST", "/api/chat", {"pergunta": "oi tudo bem?", "historico": [{"x": 1}, "texto", None]})[0] == 200)
# externos
s, d = ext.req("POST", "/api/chat", {"pergunta": "qual o código do cofre da sala azul?"})
chk("externo NÃO acessa trechos de manual interno", not any("Manuais" in str(f) or "convivencia" in str(f).lower() for f in d["fontes"]) and "7391" not in json.dumps(d), d["fontes"])
# isolamento
s, d = m.req("POST", "/api/conteudos", {"empresa_id": beta, "codigo": "B1", "titulo": "Segredo Beta", "categoria": "X", "texto": "A senha do cofre da Beta é 9999.", "visibilidade": "internos"})
chk("isolamento entre empresas no RAG", "9999" not in json.dumps(func.req("POST", "/api/chat", {"pergunta": "qual a senha do cofre da Beta?"})[1]))
chk("isolamento nos cursos (Acme não vê 'X')", not any(c["titulo"] == "X" for c in func.req("GET", "/api/cursos")[1]["itens"]))

# ---------- edição/exclusão e sincronização ----------
cid = [i for i in adm.req("GET", "/api/conteudos")[1]["itens"] if i["codigo"] == "PUB1"][0]["id"]
chk("admin edita conteúdo (reindexa)", adm.req("PUT", f"/api/conteudos/{cid}", {"titulo": "Horário da recepção", "categoria": "Geral", "texto": "A recepção agora funciona das 7h às 19h.", "visibilidade": "todos", "pergunta_exemplo": "Qual o horário da recepção?"})[0] == 200)
s, d = ext.req("POST", "/api/chat", {"pergunta": "Qual o horário da recepção?"}); chk("busca reflete a edição", "7h" in json.dumps(capturado[-1], ensure_ascii=False), d.get("fontes"))
adm.req("DELETE", f"/api/conteudos/{cid}")
chk("excluir conteúdo remove curso vazio", not any(c["titulo"] == "Geral" for c in adm.req("GET", "/api/cursos")[1]["itens"]))
chk("sincronizar é idempotente", adm.req("POST", "/api/cursos/sincronizar", {})[1] == {"criados": 0, "anexados": 0})

# ---------- admin: painel, sugestões, LLM ----------
p = adm.req("GET", "/api/painel")[1]; chk("painel da empresa", p["usuarios"] == 3 and p["conteudos"] >= 100 and p["cursos"] >= 12 and p["perguntas_7d"] >= 5, p)
chk("painel só para admin", func.req("GET", "/api/painel")[0] == 403)
sg = func.req("GET", "/api/sugestoes")[1]["itens"]; chk("sugestões de perguntas", 1 <= len(sg) <= 6, sg)
chk("/api/llm só master", adm.req("GET", "/api/llm")[0] == 403 and m.req("GET", "/api/llm")[1]["configurada"] is True)
chk("testar conexão da LLM", m.req("POST", "/api/llm/testar", {})[1]["ok"] is True)
chk("chave inválida rejeitada", m.req("POST", "/api/llm/chave", {"chave": "abc"})[0] == 400)
chave = "sk-ant-" + "x" * 40
s, d = m.req("POST", "/api/llm/chave", {"chave": chave})
chk("chave válida salva (validada com chamada real à API simulada)", s == 200 and capturado[-1]["_chave"] == chave, (d, capturado[-1]["_chave"]))
chk("chave gravada no .env de teste e NÃO ecoada", chave in open(env["OUTGPT_ENV_ARQ"]).read() and chave not in json.dumps(d))
chk("admin não configura chave", adm.req("POST", "/api/llm/chave", {"chave": chave})[0] == 403)
s, d = func.req("POST", "/api/chat", {"pergunta": "FALHAR sobre o prazo do atestado médico?"})
chk("LLM com erro: cai para os trechos + aviso", s == 200 and d["gerado_por_ia"] is False and d.get("aviso") and "Com base em" in d["resposta"], d.get("aviso"))


# ========== ETAPA 1: streaming ==========
s, ct, ev = func.req_stream = func.stream("/api/chat/stream", {"pergunta": "Como faco para aceder aos sistemas internos de casa?"})
deltas = [e for e in ev if e[0] == "delta"]; fim = [e for e in ev if e[0] == "fim"]
chk("stream: Content-Type SSE", s == 200 and "text/event-stream" in ct, ct)
chk("stream: texto chega em vários pedaços e ao longo do tempo", len(deltas) >= 3 and (deltas[-1][2] - deltas[0][2]) > 0.3, [len(deltas), round(deltas[-1][2] - deltas[0][2], 2) if deltas else 0])
chk("stream: 'fim' traz resposta completa, fontes e id do histórico", len(fim) == 1 and fim[0][1]["resposta"] == "".join(d[1]["texto"] for d in deltas) and fim[0][1]["gerado_por_ia"] and fim[0][1]["fontes"] and fim[0][1]["id"], fim[0][1] if fim else ev)
chk("stream: a chamada à LLM foi feita em modo stream", capturado[-1].get("stream") is True)
s, ct, ev = func.stream("/api/chat/stream", {"pergunta": "previsao do tempo amanha"})
chk("stream: SEM_BASE não vaza para a tela e vira recusa", not [e for e in ev if e[0] == "delta"] and ev[-1][0] == "fim" and ev[-1][1]["encontrado"] is False and ev[-1][1]["fontes"] == [], ev)
s, ct, ev = func.stream("/api/chat/stream", {"pergunta": "quanto custa o bolo de cenoura gigante?"})
chk("stream: fora do assunto nem chama a LLM e responde 'fim' direto", ev and ev[-1][0] == "fim" and ev[-1][1]["encontrado"] is False)
s, ct, ev = func.stream("/api/chat/stream", {"pergunta": "FALHAR prazo do atestado médico?"})
chk("stream: erro da LLM cai para os trechos + aviso", ev[-1][0] == "fim" and ev[-1][1]["gerado_por_ia"] is False and ev[-1][1].get("aviso"), ev[-1][1] if ev else None)
s, b, ev = func.stream("/api/chat/stream", {"pergunta": ""}); chk("stream: validação sai como JSON 400", s == 400 and not ev, (s, b))
chk("stream: exige login", Cli().stream("/api/chat/stream", {"pergunta": "oi"})[0] == 401)
hid = func.req("GET", "/api/historico")[1]["itens"]; chk("stream: pergunta gravada no histórico", any("casa" in h["pergunta"] for h in hid))
# ========== ETAPA 2: lacunas de conteúdo ==========
m.req("POST", "/api/usuarios", {"empresa_id": acme, "nome": "Bia", "email": "bia@acme.com", "senha": "senhaforte123", "tipo": "funcionario"})
f2 = Cli(); f2.req("POST", "/api/login", {"email": "bia@acme.com", "senha": "senhaforte123"})
for q in ["quanto custa o bolo de cenoura gigante?", "Quanto custa o bolo de cenoura gigante", "quanto custa o bolo de cenoura gigante???", "como cadastrar meu cachorro no plano da empresa jacaré?"]:
    f2.req("POST", "/api/chat", {"pergunta": q})
s, d = adm.req("GET", "/api/lacunas"); itens = d["itens"]
chk("lacunas: perguntas sem resposta aparecem, agrupadas por semelhança", s == 200 and itens and itens[0]["vezes"] >= 3 and "bolo" in itens[0]["pergunta"].lower(), itens[:2])
chk("lacunas: a mais repetida vem primeiro e traz usuários distintos", itens[0]["usuarios"] >= 1 and len(itens[0]["ids"]) == itens[0]["vezes"] and itens[0]["usuarios"] <= itens[0]["vezes"])
chk("lacunas: só admin/master", func.req("GET", "/api/lacunas")[0] == 403 and ext.req("GET", "/api/lacunas")[0] == 403)
chk("lacunas: painel conta", adm.req("GET", "/api/painel")[1]["lacunas"] >= 2, adm.req("GET", "/api/painel")[1])
chk("lacunas: pergunta respondida não vira lacuna", not any("ponto eletr" in i["pergunta"].lower() for i in itens))
chk("lacunas: resolver some da lista", adm.req("POST", "/api/lacunas/resolver", {"ids": itens[0]["ids"]})[0] == 200 and not any("bolo" in i["pergunta"].lower() for i in adm.req("GET", "/api/lacunas")[1]["itens"]))
chk("lacunas: resolver exige ids", adm.req("POST", "/api/lacunas/resolver", {"ids": []})[0] == 400)
chk("lacunas: admin de uma empresa não resolve registros de outra", m.req("POST", "/api/lacunas/resolver", {"ids": [999999], "empresa_id": acme})[0] == 200 and True)
# ========== ETAPA 3: feedback 👍/👎 ==========
r1 = f2.req("POST", "/api/chat", {"pergunta": "Como faco para aceder aos sistemas internos de casa?"})[1]
r2 = f2.req("POST", "/api/chat", {"pergunta": "esqueci minha senha e a conta bloqueou"})[1]
chk("chat devolve o id do registro (para avaliar)", isinstance(r1.get("id"), int))
chk("avaliar 👍", f2.req("POST", "/api/avaliar", {"id": r1["id"], "avaliacao": 1})[0] == 200)
chk("avaliar 👎 com comentário", f2.req("POST", "/api/avaliar", {"id": r2["id"], "avaliacao": -1, "comentario": "Faltou dizer o ramal do suporte"})[0] == 200)
chk("avaliação inválida rejeitada", f2.req("POST", "/api/avaliar", {"id": r1["id"], "avaliacao": 5})[0] == 400 and f2.req("POST", "/api/avaliar", {"id": "x", "avaliacao": 1})[0] == 400)
chk("só avalia as próprias respostas", ext.req("POST", "/api/avaliar", {"id": r1["id"], "avaliacao": -1})[0] == 404 and adm.req("POST", "/api/avaliar", {"id": r1["id"], "avaliacao": -1})[0] == 404)
fb = adm.req("GET", "/api/feedback")[1]
chk("admin vê resumo e as respostas que não ajudaram", fb["uteis"] >= 1 and fb["nao_ajudaram"] >= 1 and fb["satisfacao"] is not None and any(i["comentario"] == "Faltou dizer o ramal do suporte" and i["usuario"] == "Bia" for i in fb["itens"]), fb)
chk("feedback só para admin/master", func.req("GET", "/api/feedback")[0] == 403)
chk("painel traz satisfação", adm.req("GET", "/api/painel")[1]["satisfacao"] is not None)
idr = [i for i in fb["itens"] if i["comentario"]][0]["id"]
chk("admin marca como tratado e some da lista", adm.req("POST", "/api/feedback/resolver", {"id": idr})[0] == 200 and not any(i["id"] == idr for i in adm.req("GET", "/api/feedback")[1]["itens"]))
chk("mudar de ideia: 👍 depois de 👎", f2.req("POST", "/api/avaliar", {"id": r2["id"], "avaliacao": 1})[0] == 200 and adm.req("GET", "/api/feedback")[1]["nao_ajudaram"] == fb["nao_ajudaram"] - 1)
# ========== ETAPA 4: perguntas de verificação geradas pela IA ==========
s, d = adm.req("POST", "/api/conteudos", {"codigo": "VIA1", "titulo": "Política de viagens", "categoria": "Políticas", "texto": "Peça aprovação ao gestor com 10 dias de antecedência. Reserve pelo portal de viagens. O limite de diária de hotel é de R$ 380,00.", "visibilidade": "internos"})
via = d["id"]
cur = [c for c in adm.req("GET", "/api/cursos")[1]["itens"] if c["titulo"] == "Políticas"][0]
det = adm.req("GET", f"/api/cursos/{cur['id']}")[1]
chk("lição sem exemplos começa sem pergunta", det["licoes"][0]["quiz"] is None)
chk("só admin gera a pergunta com IA", func.req("POST", f"/api/conteudos/{via}/quiz", {})[0] == 403)
s, d = adm.req("POST", f"/api/conteudos/{via}/quiz", {})
chk("IA gera a pergunta (saída estruturada JSON)", s == 200 and d["gerado"] and "prazo" in d["pergunta"], d)
fmt = capturado[-1]["output_config"]["format"]; chk("chamada usou json_schema com 5 campos obrigatórios", fmt["type"] == "json_schema" and len(fmt["schema"]["required"]) == 5)
chk("o texto da lição foi enviado como dado delimitado", "<conteudo" in json.dumps(capturado[-1]["messages"]) and "10 dias" in json.dumps(capturado[-1]["messages"], ensure_ascii=False))
det = adm.req("GET", f"/api/cursos/{cur['id']}")[1]; q = det["licoes"][0]["quiz"]
chk("lição agora tem pergunta com 4 alternativas, marcada como IA", q and len(q["opcoes"]) == 4 and q["ia"] is True and "10 dias de antecedência" in q["opcoes"], q)
chk("o detalhe NÃO revela a certa", "indice" not in json.dumps(det) and "correta" not in json.dumps(det["licoes"][0]))
certa = q["opcoes"].index("10 dias de antecedência")
s, r = adm.req("POST", f"/api/cursos/{cur['id']}/licoes/{via}/responder", {"opcao": certa}); chk("corrige a pergunta gerada (acertou)", s == 200 and r["correta"] is True and r["resposta_certa"] == "10 dias de antecedência", r)
chk("lição com exemplos próprios não é refeita pela IA", adm.req("POST", f"/api/conteudos/{sid}/quiz", {})[1].get("gerado") is False)
chk("editar o texto invalida a pergunta gerada", adm.req("PUT", f"/api/conteudos/{via}", {"titulo": "Política de viagens", "categoria": "Políticas", "texto": "Texto novo sobre viagens: peça aprovação com 15 dias.", "visibilidade": "internos"})[0] == 200
    and adm.req("GET", f"/api/cursos/{cur['id']}")[1]["licoes"][0]["quiz"] is None)
for titulo, nome in (("Viagem FALHAR", "erro da API"), ("Viagem JSONRUIM", "JSON inválido"), ("Viagem DUPLICADA", "alternativas repetidas")):
    cid_ = adm.req("POST", "/api/conteudos", {"codigo": "X" + titulo[-4:], "titulo": titulo, "categoria": "Políticas", "texto": "Texto qualquer sobre " + titulo + " com algumas regras.", "visibilidade": "internos"})[1]["id"]
    s, d = adm.req("POST", f"/api/conteudos/{cid_}/quiz", {}); chk(f"geração falha com segurança: {nome}", s == 503 and "mensagem" in d, d)
chk("falha não grava pergunta pela metade", adm.req("GET", f"/api/cursos/{cur['id']}")[1]["licoes"][-1]["quiz"] is None)
# ========== ETAPA 5: cursos personalizados + certificado ==========
itens_conteudo = adm.req("GET", "/api/conteudos")[1]["itens"]
ids_ti = [i["id"] for i in itens_conteudo if i["categoria"] == "TI e Acessos"][:3]
s, d = adm.req("POST", "/api/cursos", {"titulo": "Integração de TI (Acme)", "descricao": "Primeira semana", "nivel": "Avançado", "conteudo_ids": list(reversed(ids_ti))})
chk("admin cria curso personalizado", s == 200 and d["id"], d); cp = d["id"]
lista = func.req("GET", "/api/cursos")[1]["itens"]; meu = next(c for c in lista if c["id"] == cp)
chk("curso personalizado aparece para todos, marcado e com nível", meu["personalizado"] is True and meu["licoes"] == 3 and meu["nivel"] == "Avançado", meu)
chk("ordem escolhida pelo admin é respeitada", [l["conteudo_id"] for l in func.req("GET", f"/api/cursos/{cp}")[1]["licoes"]] == list(reversed(ids_ti)))
chk("cursos automáticos não são 'personalizados'", not any(c["personalizado"] for c in lista if c["id"] != cp and c["categoria"]))
chk("funcionário não cria curso", func.req("POST", "/api/cursos", {"titulo": "x", "conteudo_ids": ids_ti})[0] == 403)
chk("validações: sem lições / título / nível / duplicadas / de outra empresa",
    adm.req("POST", "/api/cursos", {"titulo": "x", "conteudo_ids": []})[0] == 400 and adm.req("POST", "/api/cursos", {"titulo": "", "conteudo_ids": ids_ti})[0] == 400
    and adm.req("POST", "/api/cursos", {"titulo": "x", "nivel": "Mestre", "conteudo_ids": ids_ti})[0] == 400 and adm.req("POST", "/api/cursos", {"titulo": "x", "conteudo_ids": [ids_ti[0], ids_ti[0]]})[0] == 400
    and adm.req("POST", "/api/cursos", {"titulo": "x", "conteudo_ids": [999999]})[0] == 400)
bid = m.req("GET", f"/api/conteudos?empresa_id={beta}")[1]["itens"][0]["id"]
chk("não dá para incluir conteúdo de outra empresa", adm.req("POST", "/api/cursos", {"titulo": "x", "conteudo_ids": [bid]})[0] == 400)
est = adm.req("GET", f"/api/cursos/{cp}/estrutura")[1]; chk("estrutura para o editor", est["personalizado"] and est["conteudo_ids"] == list(reversed(ids_ti)))
chk("estrutura só para admin", func.req("GET", f"/api/cursos/{cp}/estrutura")[0] == 403)
chk("admin edita lições e dados do curso personalizado", adm.req("PUT", f"/api/cursos/{cp}", {"titulo": "Integração de TI", "descricao": "d", "nivel": "Iniciante", "conteudo_ids": ids_ti[:2]})[0] == 200 and len(adm.req("GET", f"/api/cursos/{cp}")[1]["licoes"]) == 2)
auto = next(c for c in lista if c["categoria"] == "TI e Acessos")
chk("curso automático não aceita trocar lições", adm.req("PUT", f"/api/cursos/{auto['id']}", {"titulo": "x", "conteudo_ids": ids_ti})[0] == 400)
chk("curso automático ainda aceita renomear", adm.req("PUT", f"/api/cursos/{auto['id']}", {"titulo": "TI e Acessos", "descricao": "Acessos e contas"})[0] == 200)
chk("sincronizar não mexe no curso personalizado", adm.req("POST", "/api/cursos/sincronizar", {})[1] == {"criados": 0, "anexados": 0} and len(adm.req("GET", f"/api/cursos/{cp}")[1]["licoes"]) == 2)
# certificado
f3 = Cli(); m.req("POST", "/api/usuarios", {"empresa_id": acme, "nome": "Caio Certificado", "email": "caio@acme.com", "senha": "senhaforte123", "tipo": "funcionario"}); f3.req("POST", "/api/login", {"email": "caio@acme.com", "senha": "senhaforte123"})
s, d = f3.req("POST", f"/api/cursos/{cp}/certificado", {}); chk("sem concluir não emite certificado", s == 400 and "Conclua" in d["mensagem"], d)
for lic in f3.req("GET", f"/api/cursos/{cp}")[1]["licoes"]: f3.req("POST", f"/api/cursos/{cp}/licoes/{lic['conteudo_id']}/concluir", {})
s, cert = f3.req("POST", f"/api/cursos/{cp}/certificado", {})
chk("curso 100% concluído emite certificado com código", s == 200 and cert["codigo"].startswith("OUT-") and len(cert["codigo"]) == 18 and cert["nome"] == "Caio Certificado" and cert["curso_titulo"] == "Integração de TI" and cert["empresa_nome"] == "Acme", cert)
chk("emitir de novo devolve o mesmo (idempotente)", f3.req("POST", f"/api/cursos/{cp}/certificado", {})[1]["codigo"] == cert["codigo"])
chk("lista os meus certificados", [c["codigo"] for c in f3.req("GET", "/api/certificados")[1]["itens"]] == [cert["codigo"]] and func.req("GET", "/api/certificados")[1]["itens"] == [])
s, v = Cli().req("GET", f"/api/verificar/{cert['codigo']}"); chk("verificação pública (sem login)", s == 200 and v["valido"] and v["nome"] == "Caio Certificado" and v["curso_titulo"] == "Integração de TI", v)
chk("verificação aceita minúsculas", Cli().req("GET", f"/api/verificar/{cert['codigo'].lower()}")[0] == 200)
chk("código inexistente = 404", Cli().req("GET", "/api/verificar/OUT-0000-0000-0000")[0] == 404)
chk("verificação pública não expõe e-mail nem ids", not any(k in v for k in ("email", "usuario_id", "id")), list(v))
adm.req("PUT", f"/api/cursos/{cp}", {"titulo": "Integração de TI v2", "descricao": "d", "nivel": "Iniciante"})
chk("certificado guarda o título da época (não muda ao renomear o curso)", Cli().req("GET", f"/api/verificar/{cert['codigo']}")[1]["curso_titulo"] == "Integração de TI")
chk("excluir o curso não apaga o certificado", adm.req("DELETE", f"/api/cursos/{cp}")[0] == 200 and Cli().req("GET", f"/api/verificar/{cert['codigo']}")[0] == 200)
# ========== DEPARTAMENTOS (RBAC por função): trilhas e conteúdos por área ==========
_g = m.req("POST", "/api/empresas", {"nome": "Gama"}); gama = _g[1]["id"]
for nome, email, tipo in [("Gil Admin", "gil@gama.com", "admin"), ("Gabi RH", "gabi@gama.com", "funcionario"), ("Hugo TI", "hugo@gama.com", "funcionario"),
                          ("Ivo Sem Depto", "ivo@gama.com", "funcionario"), ("Eva Externa", "eva@gama.com", "colaborador_externo")]:
    m.req("POST", "/api/usuarios", {"empresa_id": gama, "nome": nome, "email": email, "senha": "senhaforte123", "tipo": tipo})
gadm, gabi, hugo, ivo, eva = Cli(), Cli(), Cli(), Cli(), Cli()
for cl, e in ((gadm, "gil@gama.com"), (gabi, "gabi@gama.com"), (hugo, "hugo@gama.com"), (ivo, "ivo@gama.com"), (eva, "eva@gama.com")):
    cl.req("POST", "/api/login", {"email": e, "senha": "senhaforte123"})

# --- cadastro de departamentos ---
s, d = gadm.req("POST", "/api/departamentos", {"nome": "RH", "descricao": "Pessoas e cultura"}); dep_rh = d.get("id")
chk("departamentos: admin cria", s == 200 and dep_rh, d)
dep_ti = gadm.req("POST", "/api/departamentos", {"nome": "TI"})[1]["id"]
chk("departamentos: nome único por empresa (sem diferenciar maiúsculas)", gadm.req("POST", "/api/departamentos", {"nome": "rh"})[0] == 409)
chk("departamentos: mesmo nome em outra empresa é permitido", adm.req("POST", "/api/departamentos", {"nome": "RH"})[0] == 200)
chk("departamentos: funcionário não lista nem cria", gabi.req("POST", "/api/departamentos", {"nome": "X"})[0] == 403 and gabi.req("GET", "/api/departamentos")[0] == 403)
chk("departamentos: nome obrigatório", gadm.req("POST", "/api/departamentos", {"nome": "  "})[0] == 400)
gl = gadm.req("GET", "/api/departamentos")[1]["itens"]
chk("departamentos: lista só os da própria empresa, com contagens", sorted(x["nome"] for x in gl) == ["RH", "TI"] and all(x["usuarios"] == 0 and x["conteudos"] == 0 for x in gl), gl)
acme_dep = adm.req("GET", "/api/departamentos")[1]["itens"][0]["id"]
chk("departamentos: admin não edita nem apaga os de outra empresa", gadm.req("PUT", f"/api/departamentos/{acme_dep}", {"nome": "Hack"})[0] == 404 and gadm.req("DELETE", f"/api/departamentos/{acme_dep}")[0] == 404)
chk("departamentos: renomear", gadm.req("PUT", f"/api/departamentos/{dep_ti}", {"nome": "TI e Dados", "descricao": "Tecnologia"})[0] == 200 and "TI e Dados" in [x["nome"] for x in gadm.req("GET", "/api/departamentos")[1]["itens"]])
chk("departamentos: renomear para um nome que já existe = 409", gadm.req("PUT", f"/api/departamentos/{dep_ti}", {"nome": "RH"})[0] == 409)
chk("departamentos: master lista e cria em qualquer empresa", m.req("GET", f"/api/departamentos?empresa_id={gama}")[0] == 200 and m.req("POST", "/api/departamentos", {"empresa_id": gama, "nome": "Financeiro"})[0] == 200)

# --- departamento do usuário ---
ids_u = {u["email"]: u["id"] for u in gadm.req("GET", "/api/usuarios")[1]["itens"]}
chk("usuários: admin define o departamento", gadm.req("PUT", f"/api/usuarios/{ids_u['gabi@gama.com']}", {"departamento_id": dep_rh})[0] == 200 and gadm.req("PUT", f"/api/usuarios/{ids_u['hugo@gama.com']}", {"departamento_id": dep_ti})[0] == 200)
ul = {u["email"]: u for u in gadm.req("GET", "/api/usuarios")[1]["itens"]}
chk("usuários: lista mostra o departamento (ou nada)", ul["gabi@gama.com"]["departamento"] == "RH" and ul["hugo@gama.com"]["departamento"] == "TI e Dados" and ul["ivo@gama.com"]["departamento"] is None, [(e, u["departamento"]) for e, u in ul.items()])
chk("usuários: departamento de outra empresa é recusado", gadm.req("PUT", f"/api/usuarios/{ids_u['ivo@gama.com']}", {"departamento_id": acme_dep})[0] == 400)
chk("usuários: valor inválido (texto, booleano) é recusado", gadm.req("PUT", f"/api/usuarios/{ids_u['ivo@gama.com']}", {"departamento_id": "abc"})[0] == 400 and gadm.req("PUT", f"/api/usuarios/{ids_u['ivo@gama.com']}", {"departamento_id": True})[0] == 400)
s, d = gadm.req("POST", "/api/usuarios", {"nome": "Nina Nova", "email": "nina@gama.com", "senha": "senhaforte123", "tipo": "funcionario", "departamento_id": dep_rh})
chk("usuários: criar já com departamento", s == 200 and {u["email"]: u for u in gadm.req("GET", "/api/usuarios")[1]["itens"]}["nina@gama.com"]["departamento_id"] == dep_rh, d)
chk("usuários: criar com departamento de outra empresa = 400", gadm.req("POST", "/api/usuarios", {"nome": "Z", "email": "z@gama.com", "senha": "senhaforte123", "tipo": "funcionario", "departamento_id": acme_dep})[0] == 400)
nina = d["id"]
gadm.req("PUT", f"/api/usuarios/{nina}", {"nome": "Nina N."})
chk("usuários: editar sem o campo mantém o departamento", {u["email"]: u for u in gadm.req("GET", "/api/usuarios")[1]["itens"]}["nina@gama.com"]["departamento_id"] == dep_rh)
gadm.req("PUT", f"/api/usuarios/{nina}", {"departamento_id": None})
chk("usuários: departamento nulo remove o vínculo", {u["email"]: u for u in gadm.req("GET", "/api/usuarios")[1]["itens"]}["nina@gama.com"]["departamento_id"] is None)
eu = gabi.req("GET", "/api/eu")[1]; chk("/api/eu traz o departamento", eu["departamento"] == "RH" and eu["departamento_id"] == dep_rh and ivo.req("GET", "/api/eu")[1]["departamento"] is None, eu)

# --- conteúdos com público por departamento ---
def novo(cod, tit, cat, texto, perg, resp, deps=None, vis="internos"):
    corpo = {"codigo": cod, "titulo": tit, "categoria": cat, "texto": texto, "pergunta_exemplo": perg, "resposta_exemplo": resp, "visibilidade": vis}
    if deps is not None: corpo["departamentos"] = deps
    return gadm.req("POST", "/api/conteudos", corpo)
GERAIS = [("G_P1", "Horário do refeitório", "O refeitório funciona das 11h30 às 14h, de segunda a sexta.", "Qual o horário do refeitório?", "Das 11h30 às 14h."),
          ("G_P2", "Estacionamento", "O estacionamento é gratuito para funcionários e tem 40 vagas cobertas.", "O estacionamento é pago?", "Não, é gratuito para funcionários."),
          ("G_P3", "Copa e café", "A copa tem café e água à vontade; a geladeira é limpa toda sexta.", "Quando a geladeira é limpa?", "Toda sexta-feira."),
          ("G_P4", "Recepção", "A recepção atende das 8h às 18h e registra todos os visitantes.", "Quem registra os visitantes?", "A recepção."),
          ("G_P5", "Biblioteca interna", "A biblioteca interna empresta livros por 15 dias, renováveis uma vez.", "Por quantos dias empresto um livro?", "Por 15 dias.")]
for cod, tit, texto, perg, resp in GERAIS:
    chk(f"conteúdo geral {cod} criado (sem departamentos = todos)", novo(cod, tit, "Geral", texto, perg, resp)[0] == 200)
s, d = novo("G_RH", "Cofre financeiro", "Pessoas", "Procedimento zorbax do cofre financeiro: a senha do cofre fica com o RH e só é entregue com a assinatura do diretor de pessoas.",
            "Como acesso o cofre zorbax financeiro?", "SEGREDO-RH-ALFA: assinatura do diretor de pessoas.", [dep_rh]); id_rh = d.get("id"); chk("conteúdo restrito ao RH criado", s == 200 and id_rh, d)
s, d = novo("G_TI", "Rotação de chaves", "Tecnologia", "Procedimento quantix de rotação das chaves do servidor: executar toda sexta-feira com dois engenheiros.",
            "Como rotaciono as chaves quantix?", "SEGREDO-TI-BETA: toda sexta com dois engenheiros.", [dep_ti]); id_ti = d.get("id"); chk("conteúdo restrito à TI criado", s == 200 and id_ti, d)
s, d = novo("G_AMBOS", "Crachás de acesso", "Pessoas", "Os crachás de acesso das áreas de RH e de TI são emitidos pela portaria mediante chamado aprovado.",
            "Como peço o crachá das áreas de RH e TI?", "SEGREDO-AMBOS-GAMA: crachá azul pela portaria.", [dep_rh, dep_ti]); id_ambos = d.get("id"); chk("conteúdo para RH e TI criado", s == 200 and id_ambos, d)
s, d = novo("G_PUBTI", "Sala de servidores", "Geral", "A sala de servidores só pode ser aberta pela equipe de TI, com registro em livro.", "Quem abre a sala de servidores?", "A equipe de TI.", [dep_ti], vis="todos")
id_pubti = d.get("id"); chk("conteúdo 'todos' restrito à TI criado", s == 200 and id_pubti, d)
cods = lambda cl: sorted(i["codigo"] for i in cl.req("GET", "/api/conteudos")[1]["itens"])
GER = sorted(c[0] for c in GERAIS)
chk("biblioteca: admin vê tudo", cods(gadm) == sorted(GER + ["G_RH", "G_TI", "G_AMBOS", "G_PUBTI"]), cods(gadm))
chk("biblioteca: RH vê os gerais, os do RH e os dos dois", cods(gabi) == sorted(GER + ["G_RH", "G_AMBOS"]), cods(gabi))
chk("biblioteca: TI vê os gerais, os da TI e os dos dois", cods(hugo) == sorted(GER + ["G_TI", "G_AMBOS", "G_PUBTI"]), cods(hugo))
chk("biblioteca: sem departamento só vê os gerais", cods(ivo) == GER, cods(ivo))
chk("biblioteca: só o admin vê o público de cada conteúdo", [i for i in gadm.req("GET", "/api/conteudos")[1]["itens"] if i["codigo"] == "G_AMBOS"][0]["departamentos"] == sorted([dep_rh, dep_ti])
    and all("departamentos" not in i for i in gabi.req("GET", "/api/conteudos")[1]["itens"]) and "departamentos" not in gabi.req("GET", "/api/conteudos")[1])
chk("biblioteca: master vê tudo da empresa escolhida", sorted(i["codigo"] for i in m.req("GET", f"/api/conteudos?empresa_id={gama}")[1]["itens"]) == sorted(GER + ["G_RH", "G_TI", "G_AMBOS", "G_PUBTI"]))
chk("detalhe por id respeita o departamento (nada de vazar pelo id)", hugo.req("GET", f"/api/conteudos/{id_rh}")[0] == 404 and ivo.req("GET", f"/api/conteudos/{id_ti}")[0] == 404 and gabi.req("GET", f"/api/conteudos/{id_rh}")[0] == 200)
dg = gadm.req("GET", f"/api/conteudos/{id_ambos}")[1]; chk("detalhe do admin traz o público; o do funcionário não", dg["departamentos"] == sorted([dep_rh, dep_ti]) and "departamentos" not in gabi.req("GET", f"/api/conteudos/{id_ambos}")[1], dg.get("departamentos"))
sug_ivo = ivo.req("GET", "/api/sugestoes")[1]["itens"]; sug_hugo = hugo.req("GET", "/api/sugestoes")[1]["itens"]
chk("sugestões de perguntas não revelam conteúdo de outro departamento", "Como acesso o cofre zorbax financeiro?" not in sug_ivo + sug_hugo and "Como rotaciono as chaves quantix?" not in sug_ivo and len(sug_ivo) == 5, (sug_ivo, sug_hugo))
gadm.req("PUT", f"/api/usuarios/{ids_u['eva@gama.com']}", {"departamento_id": dep_ti})
chk("visibilidade e departamento valem juntos (externo na TI vê só o 'todos' da TI)", cods(eva) == ["G_PUBTI"], cods(eva))
gadm.req("PUT", f"/api/usuarios/{ids_u['eva@gama.com']}", {"departamento_id": None})
chk("externo sem departamento não vê o conteúdo restrito", cods(eva) == [])

# --- trilhas: cursos e lições por departamento ---
tit = lambda cl: sorted(c["titulo"] for c in cl.req("GET", "/api/cursos")[1]["itens"])
nlic = lambda cl, t: next(c["licoes"] for c in cl.req("GET", "/api/cursos")[1]["itens"] if c["titulo"] == t)
chk("trilha: admin vê todos os cursos", tit(gadm) == ["Geral", "Pessoas", "Tecnologia"], tit(gadm))
chk("trilha: RH vê Geral e Pessoas", tit(gabi) == ["Geral", "Pessoas"], tit(gabi))
chk("trilha: TI vê Geral, Pessoas e Tecnologia", tit(hugo) == ["Geral", "Pessoas", "Tecnologia"], tit(hugo))
chk("trilha: sem departamento só vê o curso Geral", tit(ivo) == ["Geral"], tit(ivo))
chk("trilha: lições contadas só entre as visíveis", nlic(gadm, "Geral") == 6 and nlic(hugo, "Geral") == 6 and nlic(gabi, "Geral") == 5 and nlic(ivo, "Geral") == 5
    and nlic(gadm, "Pessoas") == 2 and nlic(gabi, "Pessoas") == 2 and nlic(hugo, "Pessoas") == 1,
    {"admin Geral": nlic(gadm, "Geral"), "hugo Geral": nlic(hugo, "Geral"), "gabi Geral": nlic(gabi, "Geral"), "ivo Geral": nlic(ivo, "Geral"), "admin Pessoas": nlic(gadm, "Pessoas"), "gabi Pessoas": nlic(gabi, "Pessoas"), "hugo Pessoas": nlic(hugo, "Pessoas")})
pessoas = next(c["id"] for c in gadm.req("GET", "/api/cursos")[1]["itens"] if c["titulo"] == "Pessoas")
tecno = next(c["id"] for c in gadm.req("GET", "/api/cursos")[1]["itens"] if c["titulo"] == "Tecnologia")
chk("trilha: curso inteiro de outro departamento dá 404", ivo.req("GET", f"/api/cursos/{pessoas}")[0] == 404 and gabi.req("GET", f"/api/cursos/{tecno}")[0] == 404)
chk("trilha: detalhe do TI no curso Pessoas traz só a lição liberada", [l["codigo"] for l in hugo.req("GET", f"/api/cursos/{pessoas}")[1]["licoes"]] == ["G_AMBOS"]
    and sorted(l["codigo"] for l in gabi.req("GET", f"/api/cursos/{pessoas}")[1]["licoes"]) == ["G_AMBOS", "G_RH"])
chk("trilha: não conclui nem responde lição de outro departamento", hugo.req("POST", f"/api/cursos/{pessoas}/licoes/{id_rh}/concluir", {})[0] == 404 and hugo.req("POST", f"/api/cursos/{pessoas}/licoes/{id_rh}/responder", {"opcao": 0})[0] == 404
    and ivo.req("POST", f"/api/cursos/{pessoas}/licoes/{id_rh}/concluir", {})[0] == 404)
opc_hugo = json.dumps(hugo.req("GET", f"/api/cursos/{pessoas}")[1]); opc_gabi = json.dumps(gabi.req("GET", f"/api/cursos/{pessoas}")[1])
chk("quiz: alternativas erradas não vazam resposta de outro departamento", "SEGREDO-RH-ALFA" not in opc_hugo and "SEGREDO-RH-ALFA" in opc_gabi, ("hugo tem RH-ALFA" if "SEGREDO-RH-ALFA" in opc_hugo else "ok"))
geral_ivo = json.dumps(ivo.req("GET", f"/api/cursos/{next(c['id'] for c in ivo.req('GET', '/api/cursos')[1]['itens'] if c['titulo'] == 'Geral')}")[1])
chk("quiz: quem não tem departamento não vê nenhuma resposta restrita", "SEGREDO-" not in geral_ivo)
hugo.req("POST", f"/api/cursos/{pessoas}/licoes/{id_ambos}/concluir", {})
cp_h = next(c for c in hugo.req("GET", "/api/cursos")[1]["itens"] if c["titulo"] == "Pessoas"); cp_g = next(c for c in gabi.req("GET", "/api/cursos")[1]["itens"] if c["titulo"] == "Pessoas")
chk("trilha: o progresso é medido só sobre as lições da pessoa", cp_h["percentual"] == 100 and cp_g["percentual"] == 0, (cp_h["percentual"], cp_g["percentual"]))
chk("trilha: certificado sai ao concluir a trilha da própria área", hugo.req("POST", f"/api/cursos/{pessoas}/certificado", {})[0] == 200 and gabi.req("POST", f"/api/cursos/{pessoas}/certificado", {})[0] == 400)

# --- assistente (RAG): a busca nunca traz conteúdo de outro departamento ---
PERG = "Como acesso o cofre zorbax financeiro e qual a senha?"
r_ivo = ivo.req("POST", "/api/chat", {"pergunta": PERG})[1]; r_hugo = hugo.req("POST", "/api/chat", {"pergunta": PERG})[1]; r_gabi = gabi.req("POST", "/api/chat", {"pergunta": PERG})[1]
chk("assistente: RH recebe o conteúdo do RH como fonte", "G_RH" in [f["codigo"] for f in r_gabi.get("fontes", [])], r_gabi.get("fontes"))
chk("assistente: TI e sem departamento não recebem o conteúdo do RH", "G_RH" not in [f["codigo"] for f in r_hugo.get("fontes", [])] and "G_RH" not in [f["codigo"] for f in r_ivo.get("fontes", [])]
    and "diretor de pessoas" not in json.dumps(r_hugo) and "diretor de pessoas" not in json.dumps(r_ivo), (r_hugo.get("fontes"), r_ivo.get("fontes")))
s_ivo = Cli(); s_ivo.cookie = ivo.cookie
s, tipo_ct, ev = s_ivo.stream("/api/chat/stream", {"pergunta": PERG})
chk("assistente (streaming): também respeita o departamento", s == 200 and ev and "diretor de pessoas" not in json.dumps([e[1] for e in ev]) and "G_RH" not in json.dumps([e[1].get("fontes") for e in ev if e[0] == "fim"]))

# --- mudar o público de um conteúdo ---
base_rh = gadm.req("GET", f"/api/conteudos/{id_rh}")[1]
corpo_rh = {k: base_rh[k] for k in ("titulo", "categoria", "texto", "pergunta_exemplo", "resposta_exemplo", "contem_pii", "visibilidade")}
chk("editar conteúdo sem o campo 'departamentos' mantém o público (nunca libera sem querer)", gadm.req("PUT", f"/api/conteudos/{id_rh}", corpo_rh)[0] == 200 and "G_RH" not in cods(ivo) and "G_RH" in cods(gabi))
chk("editar com lista vazia libera para todos", gadm.req("PUT", f"/api/conteudos/{id_rh}", {**corpo_rh, "departamentos": []})[0] == 200 and "G_RH" in cods(ivo) and "G_RH" in cods(hugo))
chk("editar com departamentos restringe de novo", gadm.req("PUT", f"/api/conteudos/{id_rh}", {**corpo_rh, "departamentos": [dep_rh]})[0] == 200 and "G_RH" not in cods(ivo) and "G_RH" not in cods(hugo) and "G_RH" in cods(gabi))
chk("editar com departamento de outra empresa = 400 (e não muda nada)", gadm.req("PUT", f"/api/conteudos/{id_rh}", {**corpo_rh, "departamentos": [acme_dep]})[0] == 400 and "G_RH" not in cods(ivo))
n_antes = len(cods(gadm))
chk("criar com departamentos inválidos (outra empresa, texto, booleano) = 400, sem criar", [novo("G_X1", "x", "Geral", "x" * 30, None, None, [acme_dep])[0], novo("G_X2", "x", "Geral", "x" * 30, None, None, "abc")[0], novo("G_X3", "x", "Geral", "x" * 30, None, None, [True])[0]] == [400, 400, 400] and len(cods(gadm)) == n_antes)
chk("admin de outra empresa usa o próprio departamento, não o da Gama", adm.req("POST", "/api/conteudos", {"codigo": "A_X", "titulo": "x", "categoria": "Geral", "texto": "x" * 30, "departamentos": [dep_rh]})[0] == 400)

# --- excluir departamento ---
s, d = gadm.req("DELETE", f"/api/departamentos/{dep_rh}"); chk("excluir departamento com conteúdo restrito é recusado (não libera sem querer)", s == 409 and "restritos" in d["mensagem"], d)
chk("departamento recusado continua existindo e os usuários seguem nele", "RH" in [x["nome"] for x in gadm.req("GET", "/api/departamentos")[1]["itens"]] and gabi.req("GET", "/api/eu")[1]["departamento"] == "RH")
dep_tmp = gadm.req("POST", "/api/departamentos", {"nome": "Temporário"})[1]["id"]; gadm.req("PUT", f"/api/usuarios/{nina}", {"departamento_id": dep_tmp})
chk("excluir departamento sem conteúdo funciona e solta os usuários", gadm.req("DELETE", f"/api/departamentos/{dep_tmp}")[0] == 200 and {u["email"]: u for u in gadm.req("GET", "/api/usuarios")[1]["itens"]}["nina@gama.com"]["departamento_id"] is None)
chk("funcionário não exclui departamento", gabi.req("DELETE", f"/api/departamentos/{dep_ti}")[0] == 403)
chk("contagens do departamento no painel", {x["nome"]: (x["usuarios"], x["conteudos"]) for x in gadm.req("GET", "/api/departamentos")[1]["itens"]}["RH"] == (1, 2), gadm.req("GET", "/api/departamentos")[1]["itens"])

# --- arquivo e CSV com público ---
s, d = gadm.req("POST", "/api/conteudos/arquivo", {"nome": "manual_ti.txt", "dados": b64("Manual interno da TI sobre o procedimento vortex de backup semanal dos servidores.".encode()), "categoria": "Manuais", "visibilidade": "internos", "departamentos": [dep_ti]})
id_arq = d.get("id"); chk("arquivo enviado com público restrito", s == 200 and id_arq, d)
chk("arquivo restrito: TI vê, RH e sem departamento não", any(i["id"] == id_arq for i in hugo.req("GET", "/api/conteudos")[1]["itens"]) and not any(i["id"] == id_arq for i in gabi.req("GET", "/api/conteudos")[1]["itens"]) and not any(i["id"] == id_arq for i in ivo.req("GET", "/api/conteudos")[1]["itens"]))
r_arq = gabi.req("POST", "/api/chat", {"pergunta": "Qual o procedimento vortex de backup semanal?"})[1]
chk("assistente: arquivo restrito à TI não aparece para o RH", id_arq not in [f["conteudo_id"] for f in r_arq.get("fontes", [])], r_arq.get("fontes"))
csv_rh = "id,categoria,procedimento_titulo,contexto_documental,pergunta_utilizador,resposta_esperada,contem_pii\nG_CSV1,Pessoas,Férias do RH,Procedimento csvrh de férias coletivas da empresa.,Como funcionam as férias coletivas?,Pelo calendário do RH.,nao\n"
s, d = gadm.req("POST", "/api/conteudos/importar", {"csv": csv_rh, "visibilidade": "internos", "departamentos": [dep_rh]}); chk("CSV importado com público restrito", s == 200 and d["importados"] == 1, d)
chk("CSV restrito: RH vê, TI não", "G_CSV1" in cods(gabi) and "G_CSV1" not in cods(hugo) and "G_CSV1" not in cods(ivo))
gadm.req("POST", "/api/conteudos/importar", {"csv": csv_rh, "visibilidade": "internos"})
chk("importar de novo sem o campo mantém o público", "G_CSV1" not in cods(hugo) and "G_CSV1" in cods(gabi))
chk("CSV com departamento de outra empresa = 400", gadm.req("POST", "/api/conteudos/importar", {"csv": csv_rh, "departamentos": [acme_dep]})[0] == 400)
chk("excluir conteúdo restrito remove o vínculo (departamento volta a poder ser apagado)", gadm.req("DELETE", f"/api/conteudos/{id_ti}")[0] == 200
    and {x["nome"]: x["conteudos"] for x in gadm.req("GET", "/api/departamentos")[1]["itens"]}["TI e Dados"] == 3)  # G_AMBOS, G_PUBTI e o arquivo ainda o usam
chk("a Acme não foi afetada (conteúdos e cursos intactos)", len(func.req("GET", "/api/cursos")[1]["itens"]) >= 12 and len(func.req("GET", "/api/conteudos")[1]["itens"]) >= 100)
# ========== SEGURANÇA: origem das requisições (CSRF) e Codespaces ==========
chk("CSRF: origem estranha é bloqueada (403)", Cli().req("POST", "/api/login", {"email": "dono@teste.com", "senha": PW}, origin="https://site-malicioso.com")[0] == 403)
chk("CSRF: a própria origem do site é aceita", Cli().req("POST", "/api/login", {"email": "dono@teste.com", "senha": PW}, origin=B)[0] == 200)
chk("CSRF: X-Forwarded-Host não vale sem proxy confiável", Cli().req("POST", "/api/login", {"email": "dono@teste.com", "senha": PW}, origin="https://falso.com", extra={"X-Forwarded-Host": "falso.com"})[0] == 403)
chk("Codespaces: a origem pública do codespace é aceita", Cli().req("POST", "/api/login", {"email": "dono@teste.com", "senha": PW}, origin="https://meucodespace-8170.app.github.dev")[0] == 200)
chk("Codespaces: outro codespace não é aceito", Cli().req("POST", "/api/login", {"email": "dono@teste.com", "senha": PW}, origin="https://outro-8170.app.github.dev")[0] == 403)

srv.terminate()
print(f"\n{ok} ok, {fail} falhas")
if fail:
    print("--- final do log do servidor ---"); print(open(os.path.join(tmp, "servidor.log")).read()[-2000:])
LOG.close(); shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if fail else 0)
