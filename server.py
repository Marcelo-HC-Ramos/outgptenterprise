"""Servidor local do formulário de pesquisa (somente biblioteca padrão).

Uso:  python server.py   ->  http://localhost:8000
Rotas: /               formulário
       /resultados     painel com os resultados agregados
       /api/perguntas  perguntas e opções (JSON, lidas do SQLite)
       /api/enviar     POST com as respostas
       /api/resultados agregados (JSON)
       /api/exportar.csv  respostas em CSV
"""
import csv
import io
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "outgpt.db"
TIPOS_ORG = ("Empresa", "Instituição de ensino", "Consultoria / outro")


def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def perguntas():
    with conectar() as con:
        out = []
        for p in con.execute("SELECT * FROM perguntas ORDER BY ordem"):
            ops = [dict(o) for o in con.execute("SELECT id, texto FROM opcoes WHERE pergunta_id=? ORDER BY ordem", (p["id"],))]
            out.append({"id": p["id"], "ordem": p["ordem"], "texto": p["texto"], "tipo": p["tipo"],
                        "obrigatoria": bool(p["obrigatoria"]), "opcoes": ops})
        return out


def salvar(dados):
    """Valida e grava tudo em uma transação. Devolve (ok, mensagem)."""
    esp = dados.get("especialista") or {}
    nome = str(esp.get("nome", "")).strip()[:120]
    cargo = str(esp.get("cargo", "")).strip()[:120]
    org = str(esp.get("organizacao", "")).strip()[:160]
    tipo_org = esp.get("tipo_organizacao")
    email = str(esp.get("email", "")).strip()[:160] or None
    anos = esp.get("anos_experiencia")
    if not (nome and cargo and org) or tipo_org not in TIPOS_ORG:
        return False, "Preencha nome, cargo, organização e tipo de organização."
    try:
        anos = int(anos) if anos not in (None, "") else None
        if anos is not None and not 0 <= anos <= 60:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Anos de experiência inválido."
    if not esp.get("consentimento"):
        return False, "É necessário concordar com o uso dos dados."

    resp = dados.get("respostas") or {}
    with conectar() as con:
        validas = {p["id"]: p for p in perguntas()}
        linhas = []
        for pid, p in validas.items():
            v = resp.get(str(pid))
            vazio = v in (None, "", [])
            if vazio:
                if p["obrigatoria"]:
                    return False, f"Responda a pergunta {p['ordem']}."
                continue
            ids_op = {o["id"] for o in p["opcoes"]}
            if p["tipo"] == "escala":
                if not (isinstance(v, int) and 1 <= v <= 5):
                    return False, f"Valor inválido na pergunta {p['ordem']}."
                linhas.append((pid, None, v, None))
            elif p["tipo"] == "unica":
                if v not in ids_op:
                    return False, f"Opção inválida na pergunta {p['ordem']}."
                linhas.append((pid, v, None, None))
            elif p["tipo"] == "multipla":
                if not isinstance(v, list) or not set(v) <= ids_op:
                    return False, f"Opção inválida na pergunta {p['ordem']}."
                linhas += [(pid, o, None, None) for o in dict.fromkeys(v)]
            else:
                linhas.append((pid, None, None, str(v).strip()[:2000]))
        eid = con.execute(
            "INSERT INTO especialistas (nome,email,cargo,organizacao,tipo_organizacao,anos_experiencia) VALUES (?,?,?,?,?,?)",
            (nome, email, cargo, org, tipo_org, anos)).lastrowid
        con.executemany("INSERT INTO respostas (especialista_id,pergunta_id,opcao_id,valor_escala,texto_livre) VALUES (?,?,?,?,?)",
                        [(eid, *l) for l in linhas])
    return True, "Resposta registrada. Obrigado!"


def resultados():
    with conectar() as con:
        total = con.execute("SELECT COUNT(*) FROM especialistas").fetchone()[0]
        por_tipo = {r[0]: r[1] for r in con.execute("SELECT tipo_organizacao, COUNT(*) FROM especialistas GROUP BY 1")}
        out = []
        for p in perguntas():
            item = {"ordem": p["ordem"], "texto": p["texto"], "tipo": p["tipo"]}
            if p["tipo"] == "escala":
                r = con.execute("SELECT AVG(valor_escala), COUNT(*) FROM respostas WHERE pergunta_id=?", (p["id"],)).fetchone()
                dist = {i: 0 for i in range(1, 6)}
                for v, c in con.execute("SELECT valor_escala, COUNT(*) FROM respostas WHERE pergunta_id=? GROUP BY 1", (p["id"],)):
                    dist[v] = c
                item.update(media=round(r[0], 2) if r[0] else None, n=r[1], distribuicao=dist)
            elif p["tipo"] in ("unica", "multipla"):
                item["opcoes"] = [{"texto": t, "n": n} for t, n in con.execute(
                    "SELECT o.texto, COUNT(r.id) FROM opcoes o LEFT JOIN respostas r ON r.opcao_id=o.id "
                    "WHERE o.pergunta_id=? GROUP BY o.id ORDER BY o.ordem", (p["id"],))]
            else:
                item["textos"] = [r[0] for r in con.execute(
                    "SELECT texto_livre FROM respostas WHERE pergunta_id=? AND texto_livre IS NOT NULL ORDER BY id DESC", (p["id"],))]
            out.append(item)
        return {"total": total, "por_tipo": por_tipo, "perguntas": out}


def exportar_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["especialista_id", "nome", "cargo", "organizacao", "tipo_organizacao", "anos_experiencia",
                "pergunta", "resposta", "data"])
    with conectar() as con:
        for r in con.execute(
            "SELECT e.id,e.nome,e.cargo,e.organizacao,e.tipo_organizacao,e.anos_experiencia,p.ordem,"
            "COALESCE(o.texto, CAST(r.valor_escala AS TEXT), r.texto_livre),r.criado_em "
            "FROM respostas r JOIN especialistas e ON e.id=r.especialista_id JOIN perguntas p ON p.id=r.pergunta_id "
            "LEFT JOIN opcoes o ON o.id=r.opcao_id ORDER BY e.id,p.ordem"):
            w.writerow(["" if c is None else (("'" + c) if isinstance(c, str) and c[:1] in "=+-@" else c) for c in r])
    return buf.getvalue().encode("utf-8-sig")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        rota = self.path.split("?")[0]
        if rota in ("/", "/index.html"):
            self._send(200, (BASE / "formulario.html").read_bytes(), "text/html; charset=utf-8")
        elif rota == "/resultados":
            self._send(200, (BASE / "resultados.html").read_bytes(), "text/html; charset=utf-8")
        elif rota == "/api/perguntas":
            self._json(perguntas())
        elif rota == "/api/resultados":
            self._json(resultados())
        elif rota == "/api/exportar.csv":
            self._send(200, exportar_csv(), "text/csv; charset=utf-8",
                       {"Content-Disposition": "attachment; filename=respostas_outgpt.csv"})
        else:
            self._send(404, b"Nao encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/enviar":
            return self._send(404, b"Nao encontrado", "text/plain; charset=utf-8")
        try:
            tam = int(self.headers.get("Content-Length", 0))
            if tam > 100_000:
                return self._json({"ok": False, "mensagem": "Requisição grande demais."}, 413)
            dados = json.loads(self.rfile.read(tam) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json({"ok": False, "mensagem": "JSON inválido."}, 400)
        ok, msg = salvar(dados)
        self._json({"ok": ok, "mensagem": msg}, 200 if ok else 400)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    if not DB.exists():
        raise SystemExit("Banco não encontrado. Rode antes: python init_db.py")
    print("Formulário:  http://localhost:8000\nResultados:  http://localhost:8000/resultados\n(Ctrl+C para parar)")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
