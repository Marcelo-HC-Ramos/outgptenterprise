#!/usr/bin/env bash
# Mostra como acessar o OutGPT neste Codespace (executado ao abrir um terminal).
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$CODESPACE_NAME" ] || exit 0
URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
SEM_MASTER=$(cd "$RAIZ/backend" && python -c "
import db
with db.conectar() as c:
    print(0 if c.execute(\"SELECT 1 FROM usuarios WHERE tipo='master'\").fetchone() else 1)
" 2>/dev/null)
echo
echo "================ OutGPT Enterprise ================"
echo " Endereço do sistema:  $URL"
if [ "$SEM_MASTER" = "1" ]; then
  TOKEN="${OUTGPT_SETUP_TOKEN:-$(cat "$HOME/.outgpt_setup_token" 2>/dev/null)}"
  echo " PRIMEIRO ACESSO: abra o endereço, preencha 'Primeiro acesso' e use este token:"
  echo "   $TOKEN"
fi
echo " Para qualquer pessoa abrir o link: aba PORTAS > botão direito na porta 8000 > Visibilidade da porta > Pública."
echo " Ligar a IA: entre como master > Administração > Inteligência artificial (ou crie o segredo ANTHROPIC_API_KEY nos segredos do Codespaces)."
echo " Se o sistema não responder:  bash $RAIZ/.devcontainer/iniciar.sh   (log em /tmp/outgpt.log)"
echo "==================================================="
echo