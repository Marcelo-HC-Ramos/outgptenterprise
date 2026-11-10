"""Autenticação: senhas com scrypt, sessões por token aleatório e permissões por tipo de usuário."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

TIPOS = ("master", "admin", "funcionario", "colaborador_interno", "colaborador_externo")
INTERNOS = ("master", "admin", "funcionario", "colaborador_interno")   # enxergam conteúdos 'internos'
GERENCIAVEIS_POR_ADMIN = ("funcionario", "colaborador_interno", "colaborador_externo")
DURACAO_SESSAO = timedelta(hours=8)
MAX_FALHAS = 5
BLOQUEIO = timedelta(minutes=15)
SENHA_MIN = 10
_N, _R, _P = 2 ** 14, 8, 1
_FMT = "%Y-%m-%d %H:%M:%S"


def agora():
    return datetime.utcnow()


def hash_senha(senha):
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${h.hex()}"


def verificar_senha(senha, armazenado):
    try:
        _, n, r, p, sal, h = armazenado.split("$")
        calc = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, bytes.fromhex(h))
    except (ValueError, TypeError):
        return False


_HASH_FALSO = hash_senha("senha-falsa-para-igualar-o-tempo")


def validar_senha_nova(senha):
    """Devolve mensagem de erro ou None."""
    if not isinstance(senha, str) or len(senha) < SENHA_MIN:
        return f"A senha deve ter pelo menos {SENHA_MIN} caracteres."
    if len(senha) > 200:
        return "Senha longa demais."
    if senha.isdigit() or senha.isalpha():
        return "Misture letras e números (ou símbolos) na senha."
    return None


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def autenticar(con, email, senha):
    """Devolve (usuario_row, erro). Bloqueia a conta por 15 min após 5 falhas seguidas."""
    u = con.execute("SELECT * FROM usuarios WHERE email = ?", (str(email or "").strip(),)).fetchone()
    if u is None:
        verificar_senha(str(senha or ""), _HASH_FALSO)        # mesmo custo, para não revelar se o e-mail existe
        return None, "E-mail ou senha incorretos."
    if u["bloqueado_ate"] and datetime.strptime(u["bloqueado_ate"], _FMT) > agora():
        return None, "Conta temporariamente bloqueada por excesso de tentativas. Tente novamente em alguns minutos."
    if not verificar_senha(str(senha or ""), u["senha_hash"]):
        falhas = u["tentativas_falhas"] + 1
        bloqueio = (agora() + BLOQUEIO).strftime(_FMT) if falhas >= MAX_FALHAS else None
        con.execute("UPDATE usuarios SET tentativas_falhas=?, bloqueado_ate=? WHERE id=?",
                    (0 if bloqueio else falhas, bloqueio, u["id"]))
        con.commit()
        return None, "E-mail ou senha incorretos."
    if not u["ativo"]:
        return None, "Usuário desativado."
    if u["empresa_id"] is not None:
        ativa = con.execute("SELECT ativa FROM empresas WHERE id=?", (u["empresa_id"],)).fetchone()
        if not ativa or not ativa["ativa"]:
            return None, "Empresa desativada."
    con.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL, ultimo_login=? WHERE id=?",
                (agora().strftime(_FMT), u["id"]))
    con.commit()
    return u, None


def criar_sessao(con, usuario_id):
    token = secrets.token_urlsafe(32)
    con.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora().strftime(_FMT),))
    con.execute("INSERT INTO sessoes (token_hash, usuario_id, expira_em) VALUES (?,?,?)",
                (_hash_token(token), usuario_id, (agora() + DURACAO_SESSAO).strftime(_FMT)))
    con.commit()
    return token


def usuario_da_sessao(con, token):
    if not token:
        return None
    return con.execute(
        "SELECT u.* FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "LEFT JOIN empresas e ON e.id = u.empresa_id "
        "WHERE s.token_hash = ? AND s.expira_em > ? AND u.ativo = 1 AND (u.empresa_id IS NULL OR e.ativa = 1)",
        (_hash_token(token), agora().strftime(_FMT))).fetchone()


def encerrar_sessao(con, token):
    con.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash_token(token or ""),))
    con.commit()


def encerrar_sessoes_do_usuario(con, usuario_id):
    con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))


def visibilidades_do(tipo):
    """Quais níveis de visibilidade de conteúdo o tipo de usuário enxerga."""
    return ["todos", "internos"] if tipo in INTERNOS else ["todos"]
