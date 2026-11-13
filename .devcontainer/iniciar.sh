#!/usr/bin/env bash
# Roda toda vez que o Codespace liga: inicia o servidor do OutGPT em segundo plano.
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ/backend"
export OUTGPT_HOST=0.0.0.0 OUTGPT_PORTA=8000 OUTGPT_COOKIE_SECURE=1 OUTGPT_CONFIAR_PROXY=1

python init_db.py >/dev/null 2>&1

# Token do primeiro acesso: usa o segredo OUTGPT_SETUP_TOKEN do Codespaces, se existir; senão gera um (guardado só neste Codespace).
if [ -z "$OUTGPT_SETUP_TOKEN" ]; then
  [ -f "$HOME/.outgpt_setup_token" ] || python -c "import secrets; print(secrets.token_urlsafe(18))" > "$HOME/.outgpt_setup_token"
  chmod 600 "$HOME/.outgpt_setup_token"
  export OUTGPT_SETUP_TOKEN="$(cat "$HOME/.outgpt_setup_token")"
fi

if curl -fs "http://127.0.0.1:8000/saude" >/dev/null 2>&1; then
  echo "OutGPT já está em execução."
else
  nohup python server.py > /tmp/outgpt.log 2>&1 &
  disown || true
fi

python aguardar.py && echo "OutGPT no ar na porta 8000." || echo "O servidor ainda não respondeu: veja /tmp/outgpt.log"

# tenta deixar a porta pública (para abrir o link sem entrar no GitHub); se não der, a visibilidade pode ser mudada na aba PORTAS
if [ -n "$CODESPACE_NAME" ] && command -v gh >/dev/null 2>&1; then
  gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >/dev/null 2>&1 || true
fi
exit 0